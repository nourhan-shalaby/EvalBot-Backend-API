"""EvalBot audio analysis pipeline.

Recorded interview in -> PDF + JSON candidate report out.

Steps:
  1. Convert any audio/video to 16 kHz mono WAV (ffmpeg)
  2. Transcribe with speaker diarization (AssemblyAI)
  3. Extract prosodic features per utterance (librosa)
  4. Identify speakers with NVIDIA NeMo TitaNet embeddings + Pinecone vector index
  5. Classify each speaker as Interviewer / Interviewee (Random Forest trained on
     the labeled MIT interview transcripts)
  6. Analyze the interviewee's voice (rate, fillers, repetition, pitch, intensity,
     confidence / anxiety / hesitation)
  7. Generate a structured evaluation with Gemini
  8. Render a multi-page PDF report and a JSON export
"""
import csv
import io
import json
import logging
import os
import re
import subprocess
import threading
import time
import uuid
from typing import Dict, List, Optional
from xml.sax.saxutils import escape

import joblib
import librosa
import numpy as np
import requests
import soundfile as sf

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import letter  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import inch  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.model_selection import GroupShuffleSplit  # noqa: E402
from sklearn.pipeline import FeatureUnion, Pipeline  # noqa: E402
from sklearn.preprocessing import FunctionTransformer  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("evalbot")
logging.getLogger("nemo_logger").setLevel(logging.ERROR)
logging.getLogger("nemo").setLevel(logging.ERROR)

# --------------------------------------------------------------------------------------
# Configuration (all secrets come from environment variables / Space secrets)
# --------------------------------------------------------------------------------------
OUTPUT_DIR = os.getenv("EVALBOT_WORK_DIR", "./processed_audio")
MODEL_DIR = os.getenv("EVALBOT_MODEL_DIR", "./models")
TRAINING_CSV = os.getenv("EVALBOT_TRAINING_CSV", "interview_transcripts_by_turkers.csv")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "interview-speaker-embeddings")
SPEAKER_MATCH_THRESHOLD = float(os.getenv("SPEAKER_MATCH_THRESHOLD", "0.7"))
TRANSCRIPTION_TIMEOUT_S = int(os.getenv("TRANSCRIPTION_TIMEOUT_S", "900"))

ASSEMBLYAI_BASE = "https://api.assemblyai.com/v2"
FILLER_PATTERN = re.compile(
    r"\b(um+|uh+|uhm+|erm*|ah+|hmm+|mhm|you know|i mean|kind of|sort of|basically|actually|like)\b"
)
QUESTION_WORDS = re.compile(r"\b(why|how|what|when|where|who|which|tell me|describe|can you|could you)\b")


def validate_env_vars() -> Dict[str, bool]:
    """Report which external services are configured. Only AssemblyAI is mandatory."""
    status = {
        "assemblyai": bool(ASSEMBLYAI_API_KEY),
        "pinecone": bool(PINECONE_API_KEY),
        "gemini": bool(GEMINI_API_KEY),
    }
    for name, ok in status.items():
        if not ok:
            level = logging.ERROR if name == "assemblyai" else logging.WARNING
            logger.log(level, "%s API key not set; %s", name,
                       "transcription will fail" if name == "assemblyai" else "this step will be skipped")
    return status


# --------------------------------------------------------------------------------------
# Lazy service / model initialization (loaded once, on first use)
# --------------------------------------------------------------------------------------
_init_lock = threading.Lock()
_services: Dict[str, object] = {}


def _get_speaker_model():
    with _init_lock:
        if "speaker_model" not in _services:
            import torch
            from nemo.collections.asr.models import EncDecSpeakerLabelModel

            torch.set_num_threads(max(1, os.cpu_count() or 1))
            logger.info("Loading NVIDIA TitaNet speaker verification model...")
            model = EncDecSpeakerLabelModel.from_pretrained(
                "nvidia/speakerverification_en_titanet_large", map_location=torch.device("cpu")
            )
            model.eval()
            _services["speaker_model"] = model
        return _services["speaker_model"]


def _get_pinecone_index():
    if not PINECONE_API_KEY:
        return None
    with _init_lock:
        if "pinecone_index" not in _services:
            from pinecone import Pinecone, ServerlessSpec

            pc = Pinecone(api_key=PINECONE_API_KEY)
            existing = [i["name"] for i in pc.list_indexes()]
            if PINECONE_INDEX not in existing:
                logger.info("Creating Pinecone index %s", PINECONE_INDEX)
                pc.create_index(
                    name=PINECONE_INDEX, dimension=192, metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
                )
                while not pc.describe_index(PINECONE_INDEX).status["ready"]:
                    time.sleep(1)
            _services["pinecone_index"] = pc.Index(PINECONE_INDEX)
        return _services["pinecone_index"]


def _get_gemini_client():
    if not GEMINI_API_KEY:
        return None
    with _init_lock:
        if "gemini" not in _services:
            from google import genai

            _services["gemini"] = genai.Client(api_key=GEMINI_API_KEY)
        return _services["gemini"]


def load_models() -> None:
    """Warm up everything at startup so the first request is not slow."""
    validate_env_vars()
    get_role_classifier()
    _get_speaker_model()
    try:
        _get_pinecone_index()
    except Exception as e:  # Pinecone is optional
        logger.warning("Pinecone unavailable: %s", e)


# --------------------------------------------------------------------------------------
# 1. Audio conversion
# --------------------------------------------------------------------------------------
def convert_to_wav(input_path: str, output_dir: str = OUTPUT_DIR) -> str:
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{uuid.uuid4().hex}.wav")
    command = ["ffmpeg", "-y", "-loglevel", "error", "-i", input_path, "-vn",
               "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", output_path]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError(f"Could not read the audio file: {result.stderr.strip()[:300]}")
    logger.info("Converted to WAV (%.2f MB)", os.path.getsize(output_path) / 1024 / 1024)
    return output_path


# --------------------------------------------------------------------------------------
# 2. Transcription (AssemblyAI, with speaker labels and disfluencies kept)
# --------------------------------------------------------------------------------------
def transcribe(audio_path: str, speakers_expected: Optional[int] = 2) -> Dict:
    if not ASSEMBLYAI_API_KEY:
        raise RuntimeError("ASSEMBLYAI_API_KEY is not configured")
    headers = {"authorization": ASSEMBLYAI_API_KEY}

    with open(audio_path, "rb") as f:
        upload = requests.post(f"{ASSEMBLYAI_BASE}/upload", headers=headers, data=f, timeout=300)
    upload.raise_for_status()
    audio_url = upload.json()["upload_url"]

    payload = {
        "audio_url": audio_url,
        "speaker_labels": True,
        "disfluencies": True,  # keep "um"/"uh" so filler-word analysis is meaningful
        "speech_models": ["universal-2"],
        "language_code": "en",
    }
    if speakers_expected:
        payload["speakers_expected"] = speakers_expected
    job = requests.post(f"{ASSEMBLYAI_BASE}/transcript", headers=headers, json=payload, timeout=60)
    if job.status_code != 200:
        raise RuntimeError(f"AssemblyAI rejected the request: {job.status_code} {job.text[:300]}")
    transcript_id = job.json()["id"]

    deadline = time.time() + TRANSCRIPTION_TIMEOUT_S
    while time.time() < deadline:
        poll = requests.get(f"{ASSEMBLYAI_BASE}/transcript/{transcript_id}", headers=headers, timeout=60)
        poll.raise_for_status()
        result = poll.json()
        if result["status"] == "completed":
            return result
        if result["status"] == "error":
            raise RuntimeError(f"AssemblyAI error: {result.get('error')}")
        time.sleep(3)
    raise TimeoutError("Transcription timed out")


# --------------------------------------------------------------------------------------
# 3. Prosodic features
# --------------------------------------------------------------------------------------
EMPTY_PROSODY = {k: 0.0 for k in ("duration", "mean_pitch", "min_pitch", "max_pitch", "pitch_sd",
                                  "intensityMean", "intensityMin", "intensityMax", "intensitySD")}


def extract_prosodic_features(y: np.ndarray, sr: int, start_ms: int, end_ms: int) -> Dict:
    segment = y[int(start_ms * sr / 1000): int(end_ms * sr / 1000)]
    if len(segment) < sr // 10:
        return {**EMPTY_PROSODY, "duration": (end_ms - start_ms) / 1000}
    try:
        pitches = librosa.piptrack(y=segment, sr=sr, fmin=60, fmax=400)[0]
        pitches = pitches[pitches > 0]
        rms = librosa.feature.rms(y=segment)[0]
        has_pitch = len(pitches) > 0
        return {
            "duration": (end_ms - start_ms) / 1000,
            "mean_pitch": float(np.mean(pitches)) if has_pitch else 0.0,
            "min_pitch": float(np.min(pitches)) if has_pitch else 0.0,
            "max_pitch": float(np.max(pitches)) if has_pitch else 0.0,
            "pitch_sd": float(np.std(pitches)) if has_pitch else 0.0,
            "intensityMean": float(np.mean(rms)),
            "intensityMin": float(np.min(rms)),
            "intensityMax": float(np.max(rms)),
            "intensitySD": float(np.std(rms)),
        }
    except Exception as e:
        logger.warning("Prosodic feature extraction failed: %s", e)
        return {**EMPTY_PROSODY, "duration": (end_ms - start_ms) / 1000}


# --------------------------------------------------------------------------------------
# 4. Speaker identification (TitaNet embeddings + Pinecone)
# --------------------------------------------------------------------------------------
def _speaker_embedding(y: np.ndarray, sr: int, utterances: List[Dict], max_seconds: float = 45.0) -> np.ndarray:
    """One embedding per diarized speaker, from up to `max_seconds` of their speech."""
    chunks, total = [], 0.0
    for u in sorted(utterances, key=lambda u: u["end"] - u["start"], reverse=True):
        seg = y[int(u["start"] * sr / 1000): int(u["end"] * sr / 1000)]
        chunks.append(seg)
        total += len(seg) / sr
        if total >= max_seconds:
            break
    audio = np.concatenate(chunks) if chunks else np.zeros(sr, dtype=np.float32)
    tmp = os.path.join(OUTPUT_DIR, f"spk_{uuid.uuid4().hex}.wav")
    sf.write(tmp, audio, sr)
    try:
        import torch

        with torch.no_grad():
            emb = _get_speaker_model().get_embedding(tmp).cpu().numpy().flatten()
        return emb / (np.linalg.norm(emb) + 1e-9)
    finally:
        os.remove(tmp)


def identify_speakers(transcript: Dict, y: np.ndarray, sr: int, enroll: bool = True) -> Dict[str, Dict]:
    """Map each diarization label (A, B, ...) to a persistent speaker identity."""
    by_label: Dict[str, List[Dict]] = {}
    for u in transcript["utterances"]:
        by_label.setdefault(u["speaker"], []).append(u)

    index = None
    try:
        index = _get_pinecone_index()
    except Exception as e:
        logger.warning("Pinecone unavailable, skipping speaker matching: %s", e)

    speakers = {}
    for label, utts in by_label.items():
        info = {"label": label, "speaker_id": f"session_{label}", "speaker_name": f"Speaker {label}",
                "matched_existing": False, "match_score": None}
        try:
            emb = _speaker_embedding(y, sr, utts)
            if index is not None:
                res = index.query(vector=emb.tolist(), top_k=1, include_metadata=True)
                matches = [m if isinstance(m, dict) else m.to_dict() for m in (res["matches"] or [])]
                if matches and matches[0]["score"] >= SPEAKER_MATCH_THRESHOLD:
                    info.update(speaker_id=matches[0]["id"],
                                speaker_name=matches[0]["metadata"].get("speaker_name", matches[0]["id"]),
                                matched_existing=True, match_score=round(float(matches[0]["score"]), 3))
                elif enroll:
                    new_id = f"spk_{uuid.uuid4().hex[:8]}"
                    index.upsert(vectors=[{"id": new_id, "values": emb.tolist(),
                                           "metadata": {"speaker_name": f"Speaker {new_id[-4:]}",
                                                        "enrolled_at": time.strftime("%Y-%m-%d")}}])
                    info.update(speaker_id=new_id, speaker_name=f"Speaker {new_id[-4:]}")
        except Exception as e:
            logger.warning("Speaker embedding failed for %s: %s", label, e)
        speakers[label] = info
    return speakers


# --------------------------------------------------------------------------------------
# 5. Role classification (Random Forest trained on labeled MIT interview transcripts)
# --------------------------------------------------------------------------------------
def _handcrafted_features(texts: List[str]) -> np.ndarray:
    rows = []
    for t in texts:
        low = t.lower()
        words = low.split()
        n = max(len(words), 1)
        rows.append([
            int(t.strip().endswith("?")),
            t.count("?"),
            len(QUESTION_WORDS.findall(low)),
            np.log1p(len(words)),
            sum(1 for w in words if w in ("i", "i'm", "my", "me", "i've")) / n,
            sum(1 for w in words if w in ("you", "your", "you're")) / n,
            len(FILLER_PATTERN.findall(low)) / n,
        ])
    return np.array(rows, dtype=float)


def _load_training_data(path: str):
    texts, labels, groups = [], [], []
    with open(path, encoding="utf-8", errors="replace") as f:
        for row in csv.reader(f):
            if len(row) < 2:
                continue
            for turn in row[1].split("|"):
                if ":" not in turn:
                    continue
                who, text = turn.split(":", 1)
                who = who.strip().lower()
                text = re.sub(r"\[.*?\]", " ", text).strip()
                if not text:
                    continue
                if who.startswith("interviewer") or who.startswith("intrviewer"):
                    labels.append("Interviewer")
                elif who.startswith("interview") or who.startswith("inerviewee"):
                    labels.append("Interviewee")
                else:
                    continue
                texts.append(text)
                groups.append(row[0])
    return texts, labels, groups


def _build_role_pipeline() -> Pipeline:
    return Pipeline([
        ("features", FeatureUnion([
            ("tfidf", TfidfVectorizer(max_features=3000, ngram_range=(1, 2), sublinear_tf=True)),
            ("handcrafted", FunctionTransformer(_handcrafted_features)),
        ])),
        ("clf", RandomForestClassifier(n_estimators=300, min_samples_leaf=2, class_weight="balanced",
                                       random_state=42, n_jobs=-1)),
    ])


def train_role_classifier(csv_path: str = TRAINING_CSV) -> Pipeline:
    texts, labels, groups = _load_training_data(csv_path)
    # Hold out whole interviews to get an honest accuracy estimate
    split = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(split.split(texts, labels, groups))
    model = _build_role_pipeline()
    model.fit([texts[i] for i in train_idx], [labels[i] for i in train_idx])
    acc = model.score([texts[i] for i in test_idx], [labels[i] for i in test_idx])
    logger.info("Role classifier: %d utterances, held-out utterance accuracy %.3f", len(texts), acc)

    model = _build_role_pipeline().fit(texts, labels)
    model.heldout_accuracy_ = float(acc)
    joblib.dump(model, os.path.join(MODEL_DIR, "role_classifier.joblib"))
    return model


def get_role_classifier() -> Pipeline:
    with _init_lock:
        if "role_clf" not in _services:
            path = os.path.join(MODEL_DIR, "role_classifier.joblib")
            model = None
            if os.path.exists(path):
                try:
                    model = joblib.load(path)
                except Exception as e:
                    logger.warning("Could not load cached role classifier (%s); retraining", e)
            _services["role_clf"] = model
    if _services["role_clf"] is None:
        _services["role_clf"] = train_role_classifier()
    return _services["role_clf"]


def classify_roles(utterances: List[Dict]) -> Dict[str, str]:
    """Assign one role per speaker by aggregating utterance-level probabilities."""
    model = get_role_classifier()
    texts = [u["text"] for u in utterances]
    probs = model.predict_proba(texts)
    interviewer_col = list(model.classes_).index("Interviewer")

    score: Dict[str, float] = {}
    weight: Dict[str, float] = {}
    for u, p in zip(utterances, probs):
        w = np.log1p(len(u["text"].split()))
        score[u["speaker"]] = score.get(u["speaker"], 0.0) + w * p[interviewer_col]
        weight[u["speaker"]] = weight.get(u["speaker"], 0.0) + w
    interviewer_prob = {s: score[s] / weight[s] for s in score if weight[s] > 0}

    if len(interviewer_prob) == 1:
        only = next(iter(interviewer_prob))
        return {only: "Interviewer" if interviewer_prob[only] > 0.5 else "Interviewee"}
    interviewer = max(interviewer_prob, key=interviewer_prob.get)
    return {s: ("Interviewer" if s == interviewer else "Interviewee") for s in interviewer_prob}


# --------------------------------------------------------------------------------------
# 6. Interviewee voice analysis
# --------------------------------------------------------------------------------------
def analyze_interviewee_voice(y: np.ndarray, sr: int, utterances: List[Dict]) -> Dict:
    interviewee = [u for u in utterances if u["role"] == "Interviewee"]
    if not interviewee:
        return {"error": "No interviewee speech detected"}

    segments = [y[int(u["start"] * sr / 1000): int(u["end"] * sr / 1000)] for u in interviewee]
    segments = [s for s in segments if len(s) > sr // 10]

    total_duration = sum(u["prosodic_features"]["duration"] for u in interviewee)
    words = " ".join(u["text"].lower() for u in interviewee)
    word_list = re.findall(r"[a-z']+", words)
    total_words = len(word_list)
    speaking_rate = total_words / total_duration if total_duration > 0 else 0.0

    filler_hits = FILLER_PATTERN.findall(words)
    filler_ratio = len(filler_hits) / total_words if total_words else 0.0
    filler_breakdown: Dict[str, int] = {}
    for f in filler_hits:
        filler_breakdown[f] = filler_breakdown.get(f, 0) + 1

    bigrams = list(zip(word_list, word_list[1:]))
    immediate_repeats = sum(1 for a, b in zip(word_list, word_list[1:]) if a == b)
    bigram_counts: Dict[tuple, int] = {}
    for bg in bigrams:
        bigram_counts[bg] = bigram_counts.get(bg, 0) + 1
    repeated_bigrams = sum(c - 1 for c in bigram_counts.values() if c > 1)
    repetition_score = (immediate_repeats + 0.25 * repeated_bigrams) / total_words if total_words else 0.0

    pitches: List[float] = []
    for seg in segments:
        f0, voiced, _ = librosa.pyin(seg, fmin=70, fmax=350, sr=sr, frame_length=1024)
        pitches.extend(f0[voiced & ~np.isnan(f0)].tolist())
    pitches_arr = np.array(pitches)
    pitch_mean = float(pitches_arr.mean()) if len(pitches_arr) else 0.0
    pitch_std = float(pitches_arr.std()) if len(pitches_arr) else 0.0
    jitter = float(np.mean(np.abs(np.diff(pitches_arr))) / pitch_mean) if len(pitches_arr) > 1 and pitch_mean else 0.0

    intensities = np.concatenate([librosa.feature.rms(y=s)[0] for s in segments]) if segments else np.array([])
    intensity_mean = float(intensities.mean()) if len(intensities) else 0.0
    intensity_std = float(intensities.std()) if len(intensities) else 0.0
    shimmer = float(np.mean(np.abs(np.diff(intensities))) / intensity_mean) if len(intensities) > 1 and intensity_mean else 0.0

    # Heuristic composite scores, clamped to [0, 1]
    pitch_cv = pitch_std / pitch_mean if pitch_mean else 0.0
    anxiety = float(np.clip(0.6 * pitch_cv + 0.4 * (jitter + shimmer) / 2, 0, 1))
    rate_penalty = min(abs(speaking_rate - 2.5) / 2.5, 1.0)
    intensity_cv = intensity_std / intensity_mean if intensity_mean else 1.0
    confidence = float(np.clip(1 - (0.35 * min(intensity_cv, 1) + 0.35 * min(filler_ratio * 8, 1)
                                     + 0.15 * rate_penalty + 0.15 * anxiety), 0, 1))
    hesitation = float(np.clip(filler_ratio * 5 + repetition_score * 5, 0, 1))

    def level(v, hi, mid, labels=("high", "moderate", "low")):
        return labels[0] if v > hi else labels[1] if v > mid else labels[2]

    fluency = ("fluent" if filler_ratio < 0.03 and repetition_score < 0.02 else
               "moderate" if filler_ratio < 0.07 and repetition_score < 0.05 else "disfluent")

    return {
        "speaking_rate": round(speaking_rate, 2),
        "speaking_time_seconds": round(total_duration, 1),
        "word_count": total_words,
        "filler_ratio": round(filler_ratio, 4),
        "filler_words": dict(sorted(filler_breakdown.items(), key=lambda kv: -kv[1])),
        "repetition_score": round(repetition_score, 4),
        "pitch_analysis": {"mean_hz": round(pitch_mean, 1), "std_dev_hz": round(pitch_std, 1),
                           "jitter": round(jitter, 4)},
        "intensity_analysis": {"mean_rms": round(intensity_mean, 4), "std_dev_rms": round(intensity_std, 4),
                               "shimmer": round(shimmer, 4)},
        "composite_scores": {"anxiety": round(anxiety, 3), "confidence": round(confidence, 3),
                             "hesitation": round(hesitation, 3)},
        "interpretation": {"anxiety_level": level(anxiety, 0.35, 0.18),
                           "confidence_level": level(confidence, 0.7, 0.5),
                           "fluency_level": fluency},
    }


# --------------------------------------------------------------------------------------
# 7. Evaluation with Gemini (structured JSON output)
# --------------------------------------------------------------------------------------
EVALUATION_SCHEMA = {
    "type": "object",
    "properties": {
        "content_score": {"type": "integer", "description": "0-100 quality of the answers' content"},
        "executive_summary": {"type": "array", "items": {"type": "string"}},
        "communication": {"type": "array", "items": {"type": "string"}},
        "communication_tip": {"type": "string"},
        "strengths": {"type": "array", "items": {"type": "object", "properties": {
            "competency": {"type": "string"}, "explanation": {"type": "string"},
            "evidence": {"type": "string"}}, "required": ["competency", "explanation", "evidence"]}},
        "weaknesses": {"type": "array", "items": {"type": "object", "properties": {
            "area": {"type": "string"}, "feedback": {"type": "string"}},
            "required": ["area", "feedback"]}},
        "role_fit": {"type": "array", "items": {"type": "string"}},
        "recommendations": {"type": "array", "items": {"type": "object", "properties": {
            "category": {"type": "string", "enum": ["Communication Skills", "Content Delivery",
                                                    "Professional Presentation"]},
            "recommendation": {"type": "string"}, "how_to": {"type": "string"}},
            "required": ["category", "recommendation", "how_to"]}},
        "next_steps": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["content_score", "executive_summary", "communication", "communication_tip", "strengths",
                 "weaknesses", "role_fit", "recommendations", "next_steps"],
}


def _format_transcript(utterances: List[Dict], limit_chars: int = 60000) -> str:
    lines = [f"{u['role']}: {u['text']}" for u in utterances]
    text = "\n".join(lines)
    return text[:limit_chars]


def generate_evaluation(analysis: Dict) -> Optional[Dict]:
    client = _get_gemini_client()
    if client is None:
        return None
    voice = analysis["voice_analysis"]
    metrics = {k: voice.get(k) for k in ("speaking_rate", "filler_ratio", "repetition_score",
                                         "composite_scores", "interpretation")} if "error" not in voice else voice
    prompt = f"""You are EvalBot, a senior HR analyst. Evaluate the INTERVIEWEE in this interview.

Rules:
- Base every point on what the interviewee actually said (quote or paraphrase as evidence) or on the metrics.
- Be specific, professional and constructive. No generic filler. Do not invent facts.
- 5-8 strengths, 4-8 weaknesses, exactly 5 recommendations, 5 next steps, 3 bullets each for
  executive summary, communication and role fit.
- content_score: 0-100 for the quality, relevance and depth of the answers (not the voice).

Vocal metrics (computed from audio):
{json.dumps(metrics, indent=1)}
Interview duration: {analysis['interview']['duration_seconds']:.0f} s, speaker turns: {analysis['interview']['speaker_turns']}

Transcript:
{_format_transcript(analysis['transcript'])}
"""
    from google.genai import types

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=EVALUATION_SCHEMA,
                    temperature=0.4,
                ),
            )
            return json.loads(response.text)
        except Exception as e:
            logger.warning("Gemini evaluation attempt %d failed: %s", attempt + 1, e)
            time.sleep(2 * (attempt + 1))
    return None


def fallback_evaluation(analysis: Dict) -> Dict:
    """Metric-only evaluation used when Gemini is not configured or unavailable."""
    v = analysis["voice_analysis"]
    if "error" in v:
        return {"content_score": None, "executive_summary": [v["error"]], "communication": [],
                "communication_tip": "", "strengths": [], "weaknesses": [], "role_fit": [],
                "recommendations": [], "next_steps": [], "ai_generated": False}
    interp = v["interpretation"]
    comm = [
        f"Speaking rate of {v['speaking_rate']} words/sec "
        f"({'within' if 2.0 <= v['speaking_rate'] <= 3.0 else 'outside'} the 2-3 words/sec range typical of clear speech).",
        f"Filler words make up {v['filler_ratio'] * 100:.1f}% of the interviewee's words; fluency is {interp['fluency_level']}.",
        f"Vocal confidence is {interp['confidence_level']} and anxiety is {interp['anxiety_level']}, based on pitch and loudness stability.",
    ]
    return {
        "content_score": None,
        "executive_summary": ["Automated content evaluation was unavailable for this run; this report is based on vocal metrics only."] + comm[:1],
        "communication": comm,
        "communication_tip": "Pause briefly instead of using filler words, and keep answers structured (situation, action, result).",
        "strengths": [], "weaknesses": [], "role_fit": [], "recommendations": [], "next_steps": [],
        "ai_generated": False,
    }


# --------------------------------------------------------------------------------------
# Suitability score
# --------------------------------------------------------------------------------------
def calculate_acceptance_probability(voice: Dict, content_score: Optional[int]) -> float:
    """Heuristic 0-100 suitability score: 60% answer content (if available), 40% delivery."""
    if "error" in voice:
        return float(content_score) if content_score is not None else 0.0
    cs = voice["composite_scores"]
    fluency_val = {"fluent": 1.0, "moderate": 0.6, "disfluent": 0.25}[voice["interpretation"]["fluency_level"]]
    rate_score = max(0.0, 1 - abs(voice["speaking_rate"] - 2.5) / 2.5)
    delivery = (0.35 * cs["confidence"] + 0.25 * (1 - cs["anxiety"]) + 0.25 * fluency_val + 0.15 * rate_score)
    if content_score is None:
        return round(delivery * 100, 1)
    return round(0.6 * content_score + 0.4 * delivery * 100, 1)


def verdict_for(score: float) -> str:
    if score >= 80:
        return "Outstanding candidate, recommended for advancement."
    if score >= 65:
        return "Strong candidate, suitable for further evaluation."
    if score >= 50:
        return "Moderate potential, needs additional assessment."
    return "Limited fit at this stage; significant improvement needed."


# --------------------------------------------------------------------------------------
# 8. Charts + PDF report
# --------------------------------------------------------------------------------------
BRAND = colors.HexColor("#0B3D91")
ACCENT = colors.HexColor("#1F6FEB")
MUTED = colors.HexColor("#5B6573")
GRID = colors.HexColor("#DDE4EE")
SOFT = colors.HexColor("#F4F7FB")


def _chart_scores(composite: Dict) -> io.BytesIO:
    labels = ["Confidence", "Anxiety", "Hesitation"]
    values = [composite["confidence"], composite["anxiety"], composite["hesitation"]]
    fig, ax = plt.subplots(figsize=(5.2, 2.6))
    bars = ax.barh(labels, values, color=["#2E7D32", "#C62828", "#EF6C00"], height=0.55)
    ax.set_xlim(0, 1)
    ax.invert_yaxis()
    for b, v in zip(bars, values):
        ax.text(min(v + 0.02, 0.9), b.get_y() + b.get_height() / 2, f"{v:.2f}", va="center", fontsize=10)
    ax.set_title("Vocal dynamics (0 = low, 1 = high)", fontsize=11)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", alpha=0.3)
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=200)
    plt.close(fig)
    buf.seek(0)
    return buf


def _chart_talk_time(utterances: List[Dict]) -> io.BytesIO:
    totals: Dict[str, float] = {}
    for u in utterances:
        totals[u["role"]] = totals.get(u["role"], 0.0) + (u["end"] - u["start"]) / 1000
    fig, ax = plt.subplots(figsize=(3.2, 2.6))
    ax.pie(list(totals.values()), labels=list(totals.keys()), autopct="%1.0f%%",
           colors=["#1F6FEB", "#9DB9E8", "#CCCCCC"][: len(totals)], startangle=90,
           wedgeprops={"linewidth": 1, "edgecolor": "white"})
    ax.set_title("Talk time", fontsize=11)
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=200)
    plt.close(fig)
    buf.seek(0)
    return buf


def _p(text, style) -> Paragraph:
    clean = str(text).encode("latin-1", "replace").decode("latin-1")
    return Paragraph(escape(clean), style)


def _table(rows, widths, header=True, zebra=True):
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, GRID),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), BRAND)]
    if zebra:
        for r in range(1 if header else 0, len(rows)):
            if r % 2 == 0:
                style.append(("BACKGROUND", (0, r), (-1, r), SOFT))
    t.setStyle(TableStyle(style))
    return t


def create_pdf_report(analysis: Dict, output_path: str) -> None:
    doc = SimpleDocTemplate(output_path, pagesize=letter, rightMargin=0.75 * inch, leftMargin=0.75 * inch,
                            topMargin=0.9 * inch, bottomMargin=0.8 * inch,
                            title="EvalBot Interview Analysis Report", author="EvalBot")
    title = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=24, leading=30, textColor=BRAND, alignment=1)
    subtitle = ParagraphStyle("subtitle", fontName="Helvetica", fontSize=11, leading=15, textColor=MUTED, alignment=1)
    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=BRAND, spaceBefore=6, spaceAfter=10)
    h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=ACCENT, spaceBefore=10, spaceAfter=6)
    body = ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, leading=13.5, textColor=colors.HexColor("#222222"), spaceAfter=4)
    small = ParagraphStyle("small", parent=body, fontSize=8.5, leading=11.5, textColor=MUTED)
    bullet = ParagraphStyle("bullet", parent=body, leftIndent=14, bulletIndent=4)
    th = ParagraphStyle("th", parent=body, fontName="Helvetica-Bold", textColor=colors.white, spaceAfter=0)
    td = ParagraphStyle("td", parent=body, spaceAfter=0)
    tdb = ParagraphStyle("tdb", parent=td, fontName="Helvetica-Bold")

    ev = analysis["evaluation"]
    voice = analysis["voice_analysis"]
    score = analysis["suitability_score"]
    score_color = "#2E7D32" if score >= 65 else "#EF6C00" if score >= 50 else "#C62828"
    story = []

    def bullets(items):
        for it in items:
            clean = escape(str(it).encode("latin-1", "replace").decode("latin-1"))
            story.append(Paragraph(clean, bullet, bulletText="•"))

    def header_footer(canvas, d):
        canvas.saveState()
        canvas.setStrokeColor(ACCENT)
        canvas.setLineWidth(0.8)
        canvas.line(d.leftMargin, letter[1] - 0.6 * inch, letter[0] - d.rightMargin, letter[1] - 0.6 * inch)
        canvas.setFont("Helvetica-Bold", 8.5)
        canvas.setFillColor(BRAND)
        canvas.drawString(d.leftMargin, letter[1] - 0.52 * inch, "EvalBot  |  Interview Analysis Report")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(letter[0] - d.rightMargin, letter[1] - 0.52 * inch, analysis["generated_at"])
        canvas.drawString(d.leftMargin, 0.5 * inch, "Confidential - generated automatically by EvalBot")
        canvas.drawRightString(letter[0] - d.rightMargin, 0.5 * inch, f"Page {d.page}")
        canvas.restoreState()

    # ---- Page 1: overview -------------------------------------------------------------
    story += [Spacer(1, 0.3 * inch), _p("Candidate Interview Analysis", title), Spacer(1, 6),
              _p(f"Candidate ID: {analysis['user_id']}   |   Generated {analysis['generated_at']}", subtitle),
              Spacer(1, 0.35 * inch)]
    score_tbl = Table([[Paragraph(f"<font size=30 color='{score_color}'><b>{score:.0f}</b></font>"
                                  f"<font size=12 color='#5B6573'> / 100</font>", ParagraphStyle("s", alignment=1, leading=36)),
                        Paragraph(f"<b>Suitability score</b><br/>{escape(analysis['verdict'])}<br/>"
                                  f"<font size=8 color='#5B6573'>Content {ev.get('content_score') if ev.get('content_score') is not None else 'n/a'}"
                                  f" (60%) + vocal delivery (40%)</font>", body)]],
                      colWidths=[1.8 * inch, 5.0 * inch])
    score_tbl.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1, GRID), ("BACKGROUND", (0, 0), (-1, -1), SOFT),
                                   ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 12),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 12)]))
    story += [score_tbl, Spacer(1, 0.25 * inch)]

    info = analysis["interview"]
    rows = [[_p("Interview", th), _p("", th)],
            [_p("Duration", tdb), _p(f"{info['duration_seconds'] / 60:.1f} minutes", td)],
            [_p("Speaker turns", tdb), _p(str(info["speaker_turns"]), td)],
            [_p("Speakers", tdb), _p(", ".join(f"{s['speaker_name']} ({s['role']})" for s in analysis["speakers"].values()), td)]]
    if "error" not in voice:
        rows.append([_p("Interviewee speaking time", tdb),
                     _p(f"{voice['speaking_time_seconds'] / 60:.1f} minutes, {voice['word_count']} words", td)])
    story += [_table(rows, [2.2 * inch, 4.6 * inch]), Spacer(1, 0.2 * inch)]

    story.append(_p("Executive Summary", h1))
    bullets(ev.get("executive_summary", []))
    story.append(PageBreak())

    # ---- Page 2: communication & vocal dynamics -----------------------------------------
    story.append(_p("Communication & Vocal Dynamics", h1))
    if "error" not in voice:
        interp = voice["interpretation"]
        cs = voice["composite_scores"]
        top_fillers = ", ".join(f"'{k}' x{v}" for k, v in list(voice["filler_words"].items())[:5]) or "none"
        metric_rows = [
            [_p("Metric", th), _p("Value", th), _p("What it means", th)],
            [_p("Speaking rate", tdb), _p(f"{voice['speaking_rate']:.2f} words/sec", td), _p("2.0-3.0 words/sec is typical of clear, paced speech.", td)],
            [_p("Filler words", tdb), _p(f"{voice['filler_ratio'] * 100:.1f}% of words", td), _p(f"Most frequent: {top_fillers}", td)],
            [_p("Repetition", tdb), _p(f"{voice['repetition_score']:.3f}", td), _p("Repeated words and phrases; lower is better.", td)],
            [_p("Fluency", tdb), _p(interp["fluency_level"].title(), td), _p("Combines filler words and repetition.", td)],
            [_p("Confidence", tdb), _p(f"{interp['confidence_level'].title()} ({cs['confidence']:.2f})", td), _p("Steady loudness, few fillers, comfortable pace.", td)],
            [_p("Anxiety", tdb), _p(f"{interp['anxiety_level'].title()} ({cs['anxiety']:.2f})", td), _p("Pitch variability and voice instability (jitter / shimmer).", td)],
            [_p("Pitch", tdb), _p(f"{voice['pitch_analysis']['mean_hz']:.0f} Hz (sd {voice['pitch_analysis']['std_dev_hz']:.0f})", td), _p("Average voice pitch and its variation.", td)],
        ]
        story += [_table(metric_rows, [1.5 * inch, 1.7 * inch, 3.6 * inch]), Spacer(1, 0.15 * inch)]
        charts = Table([[Image(_chart_scores(cs), width=3.9 * inch, height=1.95 * inch),
                         Image(_chart_talk_time(analysis["transcript"]), width=2.5 * inch, height=2.03 * inch)]],
                       colWidths=[4.1 * inch, 2.7 * inch])
        story += [charts, Spacer(1, 0.1 * inch)]
    else:
        story.append(_p(voice["error"], body))
    if ev.get("communication"):
        story.append(_p("Observations", h2))
        bullets(ev["communication"])
    if ev.get("communication_tip"):
        story.append(_p("Tip for workplace communication", h2))
        story.append(_p(ev["communication_tip"], body))

    # ---- Competencies ------------------------------------------------------------------
    if ev.get("strengths") or ev.get("weaknesses"):
        story.append(PageBreak())
        story.append(_p("Competency Evaluation", h1))
    if ev.get("strengths"):
        story.append(_p("Strengths", h2))
        rows = [[_p("Competency", th), _p("Assessment and evidence", th)]]
        for s in ev["strengths"]:
            rows.append([_p(s["competency"], tdb),
                         Paragraph(f"{escape(s['explanation'])}<br/><font color='#5B6573'><i>Evidence: {escape(s['evidence'])}</i></font>", td)])
        t = _table(rows, [1.7 * inch, 5.1 * inch], zebra=False)
        t.setStyle(TableStyle([("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#EEF8EF"))]))
        story += [t, Spacer(1, 0.15 * inch)]
    if ev.get("weaknesses"):
        story.append(_p("Development areas", h2))
        rows = [[_p("Area", th), _p("Actionable feedback", th)]]
        for w in ev["weaknesses"]:
            rows.append([_p(w["area"], tdb), _p(w["feedback"], td)])
        t = _table(rows, [1.7 * inch, 5.1 * inch], zebra=False)
        t.setStyle(TableStyle([("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#FDF1F1"))]))
        story += [t, Spacer(1, 0.15 * inch)]

    # ---- Role fit, recommendations, next steps -------------------------------------------
    if ev.get("role_fit") or ev.get("recommendations") or ev.get("next_steps"):
        story.append(PageBreak())
    if ev.get("role_fit"):
        story.append(_p("Role Fit & Potential", h1))
        bullets(ev["role_fit"])
    if ev.get("recommendations"):
        story.append(_p("Recommendations for the Candidate", h1))
        rows = [[_p("Area", th), _p("Recommendation", th), _p("How to practice", th)]]
        for r in ev["recommendations"]:
            rows.append([_p(r["category"], tdb), _p(r["recommendation"], td), _p(r["how_to"], td)])
        story += [_table(rows, [1.4 * inch, 2.6 * inch, 2.8 * inch]), Spacer(1, 0.15 * inch)]
    if ev.get("next_steps"):
        story.append(KeepTogether([_p("Next Steps for Hiring Managers", h1)]))
        bullets(ev["next_steps"])

    # ---- Appendix: transcript -----------------------------------------------------------
    story.append(PageBreak())
    story.append(_p("Appendix: Annotated Transcript", h1))
    story.append(_p("Speaker roles were assigned automatically by the role classifier.", small))
    rows = [[_p("Time", th), _p("Role", th), _p("Text", th)]]
    for u in analysis["transcript"]:
        m, s = divmod(int(u["start"] / 1000), 60)
        rows.append([_p(f"{m:02d}:{s:02d}", td), _p(u["role"], tdb), _p(u["text"], td)])
    story.append(_table(rows, [0.6 * inch, 1.0 * inch, 5.2 * inch]))

    if not ev.get("ai_generated", True):
        story += [Spacer(1, 0.2 * inch),
                  _p("Note: AI content evaluation was unavailable for this run, so sections that depend on it were omitted.", small)]

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    logger.info("PDF report written to %s", output_path)


# --------------------------------------------------------------------------------------
# Main pipeline
# --------------------------------------------------------------------------------------
def convert_to_serializable(obj):
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: convert_to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [convert_to_serializable(v) for v in obj]
    return obj


def process_interview(audio_path: str, user_id: str = "candidate", output_dir: str = OUTPUT_DIR,
                      progress=None) -> Dict:
    """Run the full pipeline. Returns paths to the PDF and JSON reports plus a short summary."""

    def step(msg):
        logger.info(msg)
        if progress:
            progress(msg)

    wav_file = None
    try:
        step("Converting audio")
        wav_file = convert_to_wav(audio_path)
        y, sr = librosa.load(wav_file, sr=16000)

        step("Transcribing with speaker diarization")
        transcript = transcribe(wav_file)
        utterances = transcript.get("utterances") or []
        if not utterances:
            raise ValueError("No speech was detected in the recording")

        step("Extracting prosodic features")
        for u in utterances:
            u["prosodic_features"] = extract_prosodic_features(y, sr, u["start"], u["end"])

        step("Identifying speakers")
        speakers = identify_speakers(transcript, y, sr)

        step("Classifying interviewer and interviewee")
        roles = classify_roles(utterances)
        for label, info in speakers.items():
            info["role"] = roles.get(label, "Interviewee")
        clean_utts = [{
            "speaker": speakers[u["speaker"]]["speaker_name"],
            "label": u["speaker"],
            "role": speakers[u["speaker"]]["role"],
            "start": u["start"], "end": u["end"],
            "text": u["text"],
            "confidence": round(float(u.get("confidence", 0)), 3),
            "prosodic_features": u["prosodic_features"],
        } for u in utterances]

        step("Analyzing the interviewee's voice")
        voice = analyze_interviewee_voice(y, sr, clean_utts)

        analysis = {
            "user_id": user_id,
            "generated_at": time.strftime("%B %d, %Y"),
            "interview": {
                "duration_seconds": round(len(y) / sr, 1),
                "speaker_turns": len(clean_utts),
                "language": transcript.get("language_code", "en"),
            },
            "speakers": speakers,
            "voice_analysis": voice,
            "transcript": clean_utts,
            "models": {
                "transcription": "AssemblyAI universal-2",
                "speaker_embeddings": "nvidia/speakerverification_en_titanet_large",
                "role_classifier": "RandomForest (TF-IDF + handcrafted), trained on MIT interview transcripts",
                "role_classifier_heldout_accuracy": getattr(get_role_classifier(), "heldout_accuracy_", None),
                "evaluation": GEMINI_MODEL if GEMINI_API_KEY else None,
            },
        }

        step("Generating AI evaluation")
        evaluation = generate_evaluation(analysis)
        if evaluation is None:
            evaluation = fallback_evaluation(analysis)
        else:
            evaluation["ai_generated"] = True
        analysis["evaluation"] = evaluation
        analysis["suitability_score"] = calculate_acceptance_probability(voice, evaluation.get("content_score"))
        analysis["verdict"] = (verdict_for(analysis["suitability_score"]) if evaluation.get("content_score") is not None
                               else "Provisional: based on vocal delivery only (answer content was not evaluated).")

        step("Building PDF report")
        base = f"{user_id}_{uuid.uuid4().hex[:8]}"
        os.makedirs(output_dir, exist_ok=True)
        pdf_path = os.path.abspath(os.path.join(output_dir, f"{base}_report.pdf"))
        json_path = os.path.abspath(os.path.join(output_dir, f"{base}_analysis.json"))
        create_pdf_report(analysis, pdf_path)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(convert_to_serializable(analysis), f, indent=2, ensure_ascii=False)

        step("Done")
        return {
            "pdf_path": pdf_path,
            "json_path": json_path,
            "suitability_score": analysis["suitability_score"],
            "verdict": analysis["verdict"],
            "summary": evaluation.get("executive_summary", []),
            "voice": voice.get("interpretation", {}),
        }
    finally:
        if wav_file and os.path.exists(wav_file):
            os.remove(wav_file)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("usage: python process_interview.py <audio-file> [user_id]")
        sys.exit(1)
    out = process_interview(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "candidate")
    print(json.dumps(out, indent=2))
