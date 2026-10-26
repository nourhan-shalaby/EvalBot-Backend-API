"""EvalBot audio analysis service (FastAPI).

Endpoints
  GET  /                      Web demo: upload an interview recording and get the report
  GET  /health                Health check (also reports which services are configured)
  POST /process-audio         Synchronous API used by the EvalBot backend/mobile app
  POST /jobs                  Start an analysis in the background (used by the web demo; sample=true uses the demo interview)
  GET  /jobs/{job_id}         Poll job status / result
  GET  /practice/questions    Built-in practice question bank
  POST /practice/generate     AI-generated questions for a given role
  POST /practice              Evaluate one recorded answer to one question (instant feedback)
  GET  /sample.mp3            The demo interview recording
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
from platform_app import core as platform_core
from platform_app import routes as platform_routes

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

app = FastAPI(title="EvalBot", version="3.0")
app.include_router(platform_routes.router)
_jobs: Dict[str, Dict] = {}
_job_lock = threading.Lock()
_pipeline_lock = threading.Semaphore(int(os.getenv("MAX_CONCURRENT_JOBS", "1")))


@app.on_event("startup")
def warm_up():
    threading.Thread(target=pipeline.load_models, daemon=True).start()
    try:
        platform_core.init_db()
        if platform_core.enabled():
            platform_core.ensure_bucket()
    except Exception:
        logger.exception("Platform initialisation failed")


SAMPLE_AUDIO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sample_interview.mp3")


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


def _lang(value: Optional[str]) -> str:
    return "ar" if (value or "").lower().startswith("ar") else "en"


def _copy_sample(user_id: str) -> str:
    local_path = os.path.join(TEMP_DIR, f"{user_id}_{uuid.uuid4().hex}.mp3")
    shutil.copy(SAMPLE_AUDIO, local_path)
    return local_path


def _run(local_path: str, user_id: str, progress=None, lang: str = "en") -> Dict:
    with _pipeline_lock:
        try:
            result = pipeline.process_interview(local_path, user_id=user_id, progress=progress, lang=lang)
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
        "lang": result["lang"],
    }


@app.get("/health")
def health():
    return {"status": "ok", "services": pipeline.validate_env_vars()}


@app.post("/process-audio", response_model=ProcessResponse)
def process_audio(user_id: str = Form(...), file_url: Optional[str] = Form(None),
                  file: Optional[UploadFile] = File(None), lang: str = Form("en")):
    user_id = _safe_id(user_id)
    local_path = _save_input(user_id, file_url, file)
    try:
        return _run(local_path, user_id, lang=_lang(lang))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Processing failed")
        raise HTTPException(500, f"Processing failed: {e}")


@app.post("/jobs")
def create_job(user_id: str = Form("candidate"), file_url: Optional[str] = Form(None),
               file: Optional[UploadFile] = File(None), lang: str = Form("en"), sample: bool = Form(False)):
    user_id = _safe_id(user_id)
    lang = _lang(lang)
    local_path = _copy_sample(user_id) if sample else _save_input(user_id, file_url, file)
    job_id = uuid.uuid4().hex
    with _job_lock:
        _jobs[job_id] = {"status": "queued", "step": "Waiting to start", "created": time.time()}

    def progress(msg):
        with _job_lock:
            _jobs[job_id].update(status="running", step=msg)

    def worker():
        try:
            result = _run(local_path, user_id, progress, lang)
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


@app.get("/sample.mp3")
def sample_audio():
    return FileResponse(SAMPLE_AUDIO, media_type="audio/mpeg")


@app.get("/practice/questions")
def practice_questions():
    return pipeline.QUESTION_BANK


@app.post("/practice/generate")
def practice_generate(role: str = Form(...)):
    questions = pipeline.generate_practice_questions(role)
    if not questions:
        raise HTTPException(503, "Could not generate questions right now. Try one of the built-in categories.")
    return {"role": role, "questions": questions}


@app.post("/practice")
def practice(question: str = Form(...), file: UploadFile = File(...), lang: str = Form("en"),
             role: str = Form("")):
    if not question.strip():
        raise HTTPException(400, "Missing question")
    if file.filename and "." not in file.filename:
        file.filename += ".webm"
    local_path = _save_input("practice", None, file)
    try:
        with _pipeline_lock:
            return pipeline.evaluate_practice_answer(local_path, question.strip()[:500], _lang(lang), role.strip()[:80])
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("Practice evaluation failed")
        raise HTTPException(500, f"Could not evaluate the answer: {e}")
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)


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


@app.get("/demo", response_class=HTMLResponse)
def demo():
    with open(os.path.join(os.path.dirname(__file__), "static_ui.html"), encoding="utf-8") as f:
        return f.read()


# ---- Single-page web app (built from ./frontend into ./frontend/dist) ----------------------
DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    if full_path.startswith(("api/", "static/", "jobs/", "practice/")):
        raise HTTPException(404)
    candidate = os.path.normpath(os.path.join(DIST, full_path))
    if full_path and candidate.startswith(DIST) and os.path.isfile(candidate):
        return FileResponse(candidate)
    index_html = os.path.join(DIST, "index.html")
    if os.path.isfile(index_html):
        return FileResponse(index_html, headers={"Cache-Control": "no-cache"})
    return demo()
