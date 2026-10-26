"""EvalBot audio analysis service (FastAPI).

Endpoints
  GET  /                      Web demo: upload an interview recording and get the report
  GET  /health                Health check (also reports which services are configured)
  POST /process-audio         Synchronous API used by the EvalBot backend/mobile app
  POST /jobs                  Start an analysis in the background (used by the web demo)
  GET  /jobs/{job_id}         Poll job status / result
  GET  /static/outputs/pdf/{filename}, /static/outputs/json/{filename}   Download reports
"""
import logging
import os
import re
import shutil
import threading
import time
import uuid
from typing import Dict, Optional

import requests
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

import process_interview as pipeline

logger = logging.getLogger("evalbot.app")

TEMP_DIR = "./temp_files"
OUTPUT_DIR = "./static/outputs"
JSON_DIR = os.path.join(OUTPUT_DIR, "json")
PDF_DIR = os.path.join(OUTPUT_DIR, "pdf")
for d in (TEMP_DIR, JSON_DIR, PDF_DIR):
    os.makedirs(d, exist_ok=True)

BASE_URL = os.getenv("BASE_URL", "https://evalbot-audio-evalbot.hf.space").rstrip("/")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100"))
ALLOWED_EXT = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm", ".mp4", ".aac", ".opus"}

app = FastAPI(title="EvalBot Audio Analysis", version="2.0")
_jobs: Dict[str, Dict] = {}
_job_lock = threading.Lock()
_pipeline_lock = threading.Semaphore(int(os.getenv("MAX_CONCURRENT_JOBS", "1")))


@app.on_event("startup")
def warm_up():
    threading.Thread(target=pipeline.load_models, daemon=True).start()


class ProcessResponse(BaseModel):
    user_id: str
    summary: str
    suitability_score: float
    verdict: str
    json_url: str
    pdf_url: str


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", value or "candidate")[:40]
    return cleaned or "candidate"


def _save_input(user_id: str, file_url: Optional[str], file: Optional[UploadFile]) -> str:
    suffix = ".audio"
    if file is not None and file.filename:
        suffix = os.path.splitext(file.filename)[1].lower() or suffix
        if suffix not in ALLOWED_EXT:
            raise HTTPException(400, f"Unsupported file type {suffix}. Use one of: {', '.join(sorted(ALLOWED_EXT))}")
    local_path = os.path.join(TEMP_DIR, f"{user_id}_{uuid.uuid4().hex}{suffix}")
    limit = MAX_UPLOAD_MB * 1024 * 1024
    written = 0
    try:
        if file_url:
            with requests.get(file_url, stream=True, timeout=60) as resp:
                if resp.status_code != 200:
                    raise HTTPException(400, "Could not download the audio from the provided URL.")
                with open(local_path, "wb") as out:
                    for chunk in resp.iter_content(1024 * 1024):
                        written += len(chunk)
                        if written > limit:
                            raise HTTPException(413, f"File is larger than {MAX_UPLOAD_MB} MB.")
                        out.write(chunk)
        elif file is not None:
            with open(local_path, "wb") as out:
                while chunk := file.file.read(1024 * 1024):
                    written += len(chunk)
                    if written > limit:
                        raise HTTPException(413, f"File is larger than {MAX_UPLOAD_MB} MB.")
                    out.write(chunk)
        else:
            raise HTTPException(400, "Provide an audio file or a file_url.")
    except Exception:
        if os.path.exists(local_path):
            os.remove(local_path)
        raise
    return local_path


def _run(local_path: str, user_id: str, progress=None) -> Dict:
    with _pipeline_lock:
        try:
            result = pipeline.process_interview(local_path, user_id=user_id, progress=progress)
        finally:
            if os.path.exists(local_path):
                os.remove(local_path)
    pdf_name = os.path.basename(result["pdf_path"])
    json_name = os.path.basename(result["json_path"])
    shutil.move(result["pdf_path"], os.path.join(PDF_DIR, pdf_name))
    shutil.move(result["json_path"], os.path.join(JSON_DIR, json_name))
    return {
        "user_id": user_id,
        "summary": " ".join(result["summary"]) if result["summary"] else "Interview analyzed successfully.",
        "executive_summary": result["summary"],
        "suitability_score": result["suitability_score"],
        "verdict": result["verdict"],
        "voice": result["voice"],
        "pdf_url": f"{BASE_URL}/static/outputs/pdf/{pdf_name}",
        "json_url": f"{BASE_URL}/static/outputs/json/{json_name}",
        "pdf_path": f"/static/outputs/pdf/{pdf_name}",
        "json_path": f"/static/outputs/json/{json_name}",
    }


@app.get("/health")
def health():
    return {"status": "ok", "services": pipeline.validate_env_vars()}


@app.post("/process-audio", response_model=ProcessResponse)
def process_audio(user_id: str = Form(...), file_url: Optional[str] = Form(None),
                  file: Optional[UploadFile] = File(None)):
    user_id = _safe_id(user_id)
    local_path = _save_input(user_id, file_url, file)
    try:
        return _run(local_path, user_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Processing failed")
        raise HTTPException(500, f"Processing failed: {e}")


@app.post("/jobs")
def create_job(user_id: str = Form("candidate"), file_url: Optional[str] = Form(None),
               file: Optional[UploadFile] = File(None)):
    user_id = _safe_id(user_id)
    local_path = _save_input(user_id, file_url, file)
    job_id = uuid.uuid4().hex
    with _job_lock:
        _jobs[job_id] = {"status": "queued", "step": "Waiting to start", "created": time.time()}

    def progress(msg):
        with _job_lock:
            _jobs[job_id].update(status="running", step=msg)

    def worker():
        try:
            result = _run(local_path, user_id, progress)
            with _job_lock:
                _jobs[job_id].update(status="done", step="Done", result=result)
        except Exception as e:
            logger.exception("Job %s failed", job_id)
            with _job_lock:
                _jobs[job_id].update(status="error", step="Failed", error=str(e))

    threading.Thread(target=worker, daemon=True).start()
    return {"job_id": job_id}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@app.get("/static/outputs/{kind}/{filename}")
def get_output(kind: str, filename: str):
    if kind not in ("pdf", "json"):
        raise HTTPException(404)
    safe = os.path.basename(filename)
    path = os.path.join(PDF_DIR if kind == "pdf" else JSON_DIR, safe)
    if not os.path.isfile(path):
        raise HTTPException(404, "File not found")
    return FileResponse(path, media_type="application/pdf" if kind == "pdf" else "application/json",
                        filename=safe)


@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(os.path.dirname(__file__), "static_ui.html"), encoding="utf-8") as f:
        return f.read()
