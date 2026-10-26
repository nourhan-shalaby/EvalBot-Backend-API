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

ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY") or os.getenv("ASSEMBLYAI_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_TIMEOUT_S = int(os.getenv("GEMINI_TIMEOUT_S", "60"))
# Tried in order if the configured model is unavailable (Google retires model IDs regularly)
GEMINI_FALLBACK_MODELS = [m.strip() for m in os.getenv(
    "GEMINI_FALLBACK_MODELS", "gemini-3.6-flash,gemini-flash-latest,gemini-2.5-flash").split(",") if m.strip()]
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
        "pinecone": bool(PINECONE_API_KEY),  # optional: falls back to the built-in local index
        "gemini": bool(GEMINI_API_KEY),
    }
    for name, ok in status.items():
        if not ok:
            level = logging.ERROR if name == "assemblyai" else logging.WARNING
            logger.log(level, "%s API key not set; %s", name,
                       "transcription will fail" if name == "assemblyai" else "using the built-in local speaker index" if name == "pinecone" else "this step will be skipped")
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


class LocalSpeakerIndex:
    """Small built-in vector store used when Pinecone is not configured.

    Stores L2-normalized speaker embeddings in a .npz file and matches by cosine
    similarity. Mirrors the subset of the Pinecone Index API that the pipeline uses.
    """

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self.ids: List[str] = []
        self.names: List[str] = []
        self.vectors = np.zeros((0, 192), dtype=np.float32)
        if os.path.exists(path):
            try:
                data = np.load(path, allow_pickle=False)
                self.ids, self.names = list(data["ids"]), list(data["names"])
                self.vectors = data["vectors"].astype(np.float32)
            except Exception as e:
                logger.warning("Could not load local speaker index (%s); starting empty", e)

    def query(self, vector, top_k=1, include_metadata=True):
        with self._lock:
            if not len(self.ids):
                return {"matches": []}
            v = np.asarray(vector, dtype=np.float32)
            v = v / (np.linalg.norm(v) + 1e-9)
            scores = self.vectors @ v
            order = np.argsort(-scores)[:top_k]
            return {"matches": [{"id": self.ids[i], "score": float(scores[i]),
                                 "metadata": {"speaker_name": self.names[i]}} for i in order]}

    def upsert(self, vectors):
        with self._lock:
            for item in vectors:
                v = np.asarray(item["values"], dtype=np.float32)
                v = v / (np.linalg.norm(v) + 1e-9)
                self.ids.append(item["id"])
                self.names.append(item.get("metadata", {}).get("speaker_name", item["id"]))
                self.vectors = np.vstack([self.vectors, v[None, :]])
            tmp = self.path + ".tmp.npz"
            np.savez(tmp, ids=np.array(self.ids), names=np.array(self.names), vectors=self.vectors)
            os.replace(tmp, self.path)


def _local_index_path() -> str:
    # /data is the persistent-storage mount on Hugging Face Spaces (if enabled)
    base = os.getenv("SPEAKER_INDEX_DIR") or ("/data" if os.path.isdir("/data") and os.access("/data", os.W_OK) else MODEL_DIR)
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "speaker_index.npz")


def _get_pinecone_index():
    """Speaker vector index: Pinecone if a key is configured, otherwise the built-in local index."""
    if not PINECONE_API_KEY:
        with _init_lock:
            if "local_index" not in _services:
                _services["local_index"] = LocalSpeakerIndex(_local_index_path())
                logger.info("Using built-in local speaker index at %s", _services["local_index"].path)
            return _services["local_index"]
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
            from google.genai import types

            _services["gemini"] = genai.Client(
                api_key=GEMINI_API_KEY, http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_S * 1000))
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
def transcribe(audio_path: str, speakers_expected: Optional[int] = 2, diarize: bool = True) -> Dict:
    if not ASSEMBLYAI_API_KEY:
        raise RuntimeError("ASSEMBLYAI_API_KEY is not configured")
    headers = {"authorization": ASSEMBLYAI_API_KEY}

    with open(audio_path, "rb") as f:
        upload = requests.post(f"{ASSEMBLYAI_BASE}/upload", headers=headers, data=f, timeout=300)
    upload.raise_for_status()
    audio_url = upload.json()["upload_url"]

    payload = {
        "audio_url": audio_url,
        "speaker_labels": diarize,
        "disfluencies": True,  # keep "um"/"uh" so filler-word analysis is meaningful
        "speech_models": ["universal-2"],
        "language_code": "en",
    }
    if diarize and speakers_expected:
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
# Question / answer pairing
# --------------------------------------------------------------------------------------
def build_qa_pairs(utterances: List[Dict], max_pairs: int = 25) -> List[Dict]:
    """Merge consecutive turns by role, then pair each interviewer block with the answer after it."""
    blocks: List[Dict] = []
    for u in utterances:
        if blocks and blocks[-1]["role"] == u["role"]:
            blocks[-1]["text"] += " " + u["text"]
            blocks[-1]["end"] = u["end"]
        else:
            blocks.append({"role": u["role"], "text": u["text"], "start": u["start"], "end": u["end"]})
    pairs = []
    for q, a in zip(blocks, blocks[1:]):
        if q["role"] == "Interviewer" and a["role"] == "Interviewee" and len(a["text"].split()) >= 4:
            pairs.append({"index": len(pairs) + 1, "question": q["text"], "answer": a["text"],
                          "question_start": q["start"], "answer_start": a["start"], "answer_end": a["end"],
                          "answer_seconds": round((a["end"] - a["start"]) / 1000, 1)})
            if len(pairs) >= max_pairs:
                break
    return pairs


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
        "questions": {"type": "array", "items": {"type": "object", "properties": {
            "index": {"type": "integer"},
            "score": {"type": "integer", "description": "0-10"},
            "what_went_well": {"type": "string"},
            "what_to_improve": {"type": "string"},
            "improved_answer": {"type": "string"}},
            "required": ["index", "score", "what_went_well", "what_to_improve", "improved_answer"]}},
        "role_fit": {"type": "array", "items": {"type": "string"}},
        "recommendations": {"type": "array", "items": {"type": "object", "properties": {
            "category": {"type": "string", "enum": ["Communication Skills", "Content Delivery",
                                                    "Professional Presentation"]},
            "recommendation": {"type": "string"}, "how_to": {"type": "string"}},
            "required": ["category", "recommendation", "how_to"]}},
        "next_steps": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["content_score", "executive_summary", "communication", "communication_tip", "strengths",
                 "weaknesses", "questions", "role_fit", "recommendations", "next_steps"],
}


def _language_rule(lang: str) -> str:
    if lang == "ar":
        return ("- Write ALL free-text values in clear Modern Standard Arabic. Keep technical terms "
                "(e.g. API, Spark, SQL) and direct quotes from the transcript in English.\n"
                "- improved_answer must stay in ENGLISH, because the interview itself is in English.\n")
    return "- Write all text in English.\n"


def _gemini_json(prompt: str, schema: Dict, temperature: float = 0.4) -> Optional[Dict]:
    client = _get_gemini_client()
    if client is None:
        return None
    from google.genai import types

    global GEMINI_MODEL
    models = [GEMINI_MODEL] + [m for m in GEMINI_FALLBACK_MODELS if m != GEMINI_MODEL]
    config = types.GenerateContentConfig(response_mime_type="application/json",
                                         response_schema=schema, temperature=temperature)
    for model in models:
        for attempt in range(3):
            try:
                t0 = time.time()
                response = client.models.generate_content(model=model, contents=prompt, config=config)
                logger.info("Gemini %s answered in %.1fs", model, time.time() - t0)
                if model != GEMINI_MODEL:
                    logger.info("Switching Gemini model to %s", model)
                    GEMINI_MODEL = model
                return json.loads(response.text)
            except Exception as e:
                msg = str(e).lower()
                unavailable = any(k in msg for k in ("not found", "404", "is not supported", "no longer available",
                                                     "deprecated", "permission_denied", "not available"))
                overloaded = any(k in msg for k in ("503", "unavailable", "high demand", "overloaded", "429",
                                                    "resource_exhausted", "timed out", "timeout", "deadline"))
                logger.warning("Gemini (%s) attempt %d failed: %s", model, attempt + 1, str(e)[:300])
                if unavailable or (overloaded and attempt >= 1):
                    break  # try the next model
                time.sleep(1.5 * (attempt + 1))
    return None


def _format_transcript(utterances: List[Dict], limit_chars: int = 50000) -> str:
    return "\n".join(f"{u['role']}: {u['text']}" for u in utterances)[:limit_chars]


def generate_evaluation(analysis: Dict, lang: str = "en") -> Optional[Dict]:
    voice = analysis["voice_analysis"]
    metrics = ({k: voice.get(k) for k in ("speaking_rate", "filler_ratio", "repetition_score",
                                          "composite_scores", "interpretation")}
               if "error" not in voice else voice)
    qa_text = "\n\n".join(f"[{p['index']}] Q: {p['question']}\n    A: {p['answer']}" for p in analysis["qa_pairs"])
    prompt = f"""You are EvalBot, a senior HR analyst and interview coach. Evaluate the INTERVIEWEE.

Rules:
- Base every point on what the interviewee actually said (quote or paraphrase as evidence) or on the metrics.
- Be specific, professional and constructive. No generic filler. Do not invent facts about the candidate.
- 4-8 strengths, 3-8 weaknesses, exactly 5 recommendations, 5 next steps, 3 bullets each for
  executive summary, communication and role fit.
- content_score: 0-100 for the quality, relevance and depth of the answers (not the voice).
- questions: one entry per numbered question-answer pair below, using the same index.
  score is 0-10 for that answer. improved_answer is a stronger version of the candidate's answer
  (3-5 sentences, first person, STAR structure where it fits) that reuses only facts the candidate
  mentioned; where a concrete detail would help, write a placeholder like [number] or [tool].
{_language_rule(lang)}
Vocal metrics (computed from audio):
{json.dumps(metrics, indent=1)}
Interview duration: {analysis['interview']['duration_seconds']:.0f} s, speaker turns: {analysis['interview']['speaker_turns']}

Question-answer pairs:
{qa_text or '(none detected)'}

Full transcript:
{_format_transcript(analysis['transcript'])}
"""
    return _gemini_json(prompt, EVALUATION_SCHEMA)


def fallback_evaluation(analysis: Dict, lang: str = "en") -> Dict:
    """Metric-only evaluation used when Gemini is not configured or unavailable."""
    v = analysis["voice_analysis"]
    empty = {"content_score": None, "communication": [], "communication_tip": "", "strengths": [],
             "weaknesses": [], "questions": [], "role_fit": [], "recommendations": [], "next_steps": [],
             "ai_generated": False}
    if "error" in v:
        return {**empty, "executive_summary": [v["error"]]}
    i = v["interpretation"]
    if lang == "ar":
        comm = [
            f"معدل الكلام {v['speaking_rate']} كلمة في الثانية (المعدل الطبيعي للكلام الواضح من 2 إلى 3).",
            f"كلمات الحشو تمثل {v['filler_ratio'] * 100:.1f}% من كلام المرشّح، ومستوى الطلاقة: {L('ar', i['fluency_level'])}.",
            f"الثقة الصوتية: {L('ar', i['confidence_level'])}، والقلق: {L('ar', i['anxiety_level'])}، بناءً على ثبات طبقة الصوت وشدته.",
        ]
        note = "لم يكن تقييم المحتوى بالذكاء الاصطناعي متاحاً في هذه المرة، فالتقرير مبني على مقاييس الصوت فقط."
        tip = "توقّف لحظة بدل استخدام كلمات الحشو، ورتّب إجاباتك: الموقف، ثم ما فعلته، ثم النتيجة."
    else:
        comm = [
            f"Speaking rate of {v['speaking_rate']} words/sec "
            f"({'within' if 2.0 <= v['speaking_rate'] <= 3.0 else 'outside'} the 2-3 words/sec range typical of clear speech).",
            f"Filler words make up {v['filler_ratio'] * 100:.1f}% of the interviewee's words; fluency is {i['fluency_level']}.",
            f"Vocal confidence is {i['confidence_level']} and anxiety is {i['anxiety_level']}, based on pitch and loudness stability.",
        ]
        note = "Automated content evaluation was unavailable for this run; this report is based on vocal metrics only."
        tip = "Pause briefly instead of using filler words, and keep answers structured (situation, action, result)."
    return {**empty, "executive_summary": [note, comm[0]], "communication": comm, "communication_tip": tip}


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


def verdict_for(score: Optional[float], lang: str = "en", provisional: bool = False) -> str:
    if provisional:
        return L(lang, "verdict_provisional")
    key = ("verdict_top" if score >= 80 else "verdict_strong" if score >= 65
           else "verdict_moderate" if score >= 50 else "verdict_low")
    return L(lang, key)


# --------------------------------------------------------------------------------------
# Labels (English / Arabic)
# --------------------------------------------------------------------------------------
LABELS = {
    "en": {
        "report_title": "Candidate Interview Analysis", "header": "EvalBot  |  Interview Analysis Report",
        "footer": "Confidential - generated automatically by EvalBot", "page": "Page",
        "candidate_id": "Candidate ID", "generated": "Generated",
        "suitability": "Suitability score", "score_basis": "Content {content} (60%) + vocal delivery (40%)",
        "interview": "Interview", "duration": "Duration", "minutes": "minutes", "speaker_turns": "Speaker turns",
        "speakers": "Speakers", "interviewee_time": "Interviewee speaking time", "words": "words",
        "questions_answered": "Questions answered",
        "exec_summary": "Executive Summary", "comm_title": "Communication & Vocal Dynamics",
        "metric": "Metric", "value": "Value", "meaning": "What it means",
        "speaking_rate": "Speaking rate", "wps": "words/sec", "fillers": "Filler words", "of_words": "of words",
        "most_frequent": "Most frequent", "none": "none", "repetition": "Repetition", "fluency": "Fluency",
        "confidence": "Confidence", "anxiety": "Anxiety", "hesitation": "Hesitation", "pitch": "Pitch",
        "m_rate": "2.0-3.0 words/sec is typical of clear, paced speech.",
        "m_rep": "Repeated words and phrases; lower is better.", "m_flu": "Combines filler words and repetition.",
        "m_conf": "Steady loudness, few fillers, comfortable pace.",
        "m_anx": "Pitch variability and voice instability (jitter / shimmer).",
        "m_pitch": "Average voice pitch and its variation.",
        "observations": "Observations", "tip": "Tip for workplace communication",
        "qa_title": "Question-by-Question Feedback", "question": "Question", "answer": "Answer (excerpt)",
        "went_well": "What went well", "to_improve": "What to improve", "better_answer": "A stronger answer",
        "competency_title": "Competency Evaluation", "strengths": "Strengths", "competency": "Competency",
        "assessment": "Assessment and evidence", "evidence": "Evidence", "dev_areas": "Development areas",
        "area": "Area", "feedback": "Actionable feedback", "role_fit": "Role Fit & Potential",
        "recs": "Recommendations for the Candidate", "rec_area": "Area", "recommendation": "Recommendation",
        "how_to": "How to practice", "next_steps": "Next Steps for Hiring Managers",
        "appendix": "Appendix: Annotated Transcript",
        "appendix_note": "Speaker roles were assigned automatically by the role classifier.",
        "time": "Time", "role": "Role", "text": "Text", "Interviewer": "Interviewer", "Interviewee": "Interviewee",
        "ai_unavailable": "Note: AI content evaluation was unavailable for this run, so sections that depend on it were omitted.",
        "chart_vocal": "Vocal dynamics (0 = low, 1 = high)", "chart_talk": "Talk time",
        "chart_q": "Score per question (0-10)",
        "high": "High", "moderate": "Moderate", "low": "Low", "fluent": "Fluent", "disfluent": "Disfluent",
        "Communication Skills": "Communication Skills", "Content Delivery": "Content Delivery",
        "Professional Presentation": "Professional Presentation",
        "verdict_top": "Outstanding candidate, recommended for advancement.",
        "verdict_strong": "Strong candidate, suitable for further evaluation.",
        "verdict_moderate": "Moderate potential, needs additional assessment.",
        "verdict_low": "Limited fit at this stage; significant improvement needed.",
        "verdict_provisional": "Provisional: based on vocal delivery only (answer content was not evaluated).",
    },
    "ar": {
        "report_title": "تحليل مقابلة المرشّح", "header": "EvalBot  |  تقرير تحليل المقابلة",
        "footer": "سري - تم إنشاؤه تلقائياً بواسطة EvalBot", "page": "صفحة",
        "candidate_id": "رقم المرشّح", "generated": "تاريخ الإنشاء",
        "suitability": "درجة الملاءمة", "score_basis": "المحتوى {content} (60%) + الأداء الصوتي (40%)",
        "interview": "المقابلة", "duration": "المدة", "minutes": "دقيقة", "speaker_turns": "عدد المداخلات",
        "speakers": "المتحدثون", "interviewee_time": "مدة كلام المرشّح", "words": "كلمة",
        "questions_answered": "عدد الأسئلة المُجاب عليها",
        "exec_summary": "الملخص التنفيذي", "comm_title": "التواصل والأداء الصوتي",
        "metric": "المقياس", "value": "القيمة", "meaning": "المعنى",
        "speaking_rate": "معدل الكلام", "wps": "كلمة/ثانية", "fillers": "كلمات الحشو", "of_words": "من الكلمات",
        "most_frequent": "الأكثر تكراراً", "none": "لا يوجد", "repetition": "التكرار", "fluency": "الطلاقة",
        "confidence": "الثقة", "anxiety": "القلق", "hesitation": "التردد", "pitch": "طبقة الصوت",
        "m_rate": "من 2 إلى 3 كلمات في الثانية هو المعدل المعتاد للكلام الواضح.",
        "m_rep": "تكرار الكلمات والعبارات، وكلما قلّ كان أفضل.", "m_flu": "يجمع بين كلمات الحشو والتكرار.",
        "m_conf": "ثبات شدة الصوت، وقلة كلمات الحشو، وسرعة مريحة.",
        "m_anx": "تذبذب طبقة الصوت وعدم ثباته.", "m_pitch": "متوسط طبقة الصوت ومدى تغيّرها.",
        "observations": "ملاحظات", "tip": "نصيحة للتواصل في بيئة العمل",
        "qa_title": "تقييم كل سؤال على حدة", "question": "السؤال", "answer": "الإجابة (مقتطف)",
        "went_well": "ما كان جيداً", "to_improve": "ما يحتاج إلى تحسين", "better_answer": "إجابة أقوى",
        "competency_title": "تقييم الكفاءات", "strengths": "نقاط القوة", "competency": "الكفاءة",
        "assessment": "التقييم والدليل", "evidence": "الدليل", "dev_areas": "مجالات التطوير",
        "area": "المجال", "feedback": "ملاحظات قابلة للتطبيق", "role_fit": "الملاءمة للدور والإمكانات",
        "recs": "توصيات للمرشّح", "rec_area": "المجال", "recommendation": "التوصية",
        "how_to": "طريقة التدريب", "next_steps": "الخطوات التالية لمسؤولي التوظيف",
        "appendix": "ملحق: نص المقابلة",
        "appendix_note": "تم تحديد دور كل متحدث تلقائياً بواسطة نموذج تصنيف الأدوار.",
        "time": "الوقت", "role": "الدور", "text": "النص", "Interviewer": "المحاوِر", "Interviewee": "المرشّح",
        "ai_unavailable": "ملاحظة: لم يكن تقييم المحتوى بالذكاء الاصطناعي متاحاً، فتم حذف الأقسام المعتمدة عليه.",
        "chart_vocal": "الأداء الصوتي (0 = منخفض، 1 = مرتفع)", "chart_talk": "توزيع وقت الكلام",
        "chart_q": "درجة كل سؤال (من 10)",
        "high": "مرتفع", "moderate": "متوسط", "low": "منخفض", "fluent": "طليق", "disfluent": "متقطع",
        "Communication Skills": "مهارات التواصل", "Content Delivery": "تقديم المحتوى",
        "Professional Presentation": "الحضور المهني",
        "verdict_top": "مرشّح متميز، يُنصح بانتقاله للمرحلة التالية.",
        "verdict_strong": "مرشّح قوي، مناسب لمزيد من التقييم.",
        "verdict_moderate": "إمكانات متوسطة، يحتاج إلى تقييم إضافي.",
        "verdict_low": "ملاءمة محدودة حالياً، ويحتاج إلى تحسين كبير.",
        "verdict_provisional": "مبدئي: مبني على الأداء الصوتي فقط (لم يتم تقييم محتوى الإجابات).",
    },
}


def L(lang: str, key: str) -> str:
    return LABELS.get(lang, LABELS["en"]).get(key, LABELS["en"].get(key, key))


# --------------------------------------------------------------------------------------
# 8. Charts + PDF report (English left-to-right, Arabic right-to-left)
# --------------------------------------------------------------------------------------
from reportlab.lib.enums import TA_CENTER, TA_LEFT  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import Flowable  # noqa: E402

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")
BRAND = colors.HexColor("#0B3D91")
ACCENT = colors.HexColor("#1F6FEB")
MUTED = colors.HexColor("#5B6573")
INK = colors.HexColor("#222222")
GRID = colors.HexColor("#DDE4EE")
SOFT = colors.HexColor("#F4F7FB")
GOOD_BG = colors.HexColor("#EEF8EF")
BAD_BG = colors.HexColor("#FDF1F1")
ARABIC_RE = re.compile(r"[؀-ۿ]")
_fonts_registered = False


def _register_fonts() -> bool:
    global _fonts_registered
    if _fonts_registered:
        return True
    try:
        pdfmetrics.registerFont(TTFont("Amiri", os.path.join(FONT_DIR, "Amiri-Regular.ttf")))
        pdfmetrics.registerFont(TTFont("Amiri-Bold", os.path.join(FONT_DIR, "Amiri-Bold.ttf")))
        _fonts_registered = True
    except Exception as e:
        logger.warning("Arabic font not available: %s", e)
    return _fonts_registered


def _get_display(text: str) -> str:
    # bidi.algorithm implements the full Unicode bidi algorithm, including bracket mirroring
    try:
        from bidi.algorithm import get_display
    except ImportError:
        from bidi import get_display
    return get_display(text)


def _shape(text: str) -> str:
    """Arabic letter shaping + bidi reordering for one visual line."""
    import arabic_reshaper
    return _get_display(arabic_reshaper.reshape(text))


class RTLParagraph(Flowable):
    """Right-to-left paragraph: wraps in logical order, then reorders each line for display."""

    def __init__(self, text, font="Amiri", size=10, leading=None, color=INK, align="right",
                 space_before=0, space_after=4, lines=None):
        super().__init__()
        self.text = str(text)
        self.font, self.size = font, size
        self.leading = leading or size * 1.55
        self.color, self.align = color, align
        self.space_before, self.space_after = space_before, space_after
        self._lines = lines
        self._width = 0

    def _break(self, width):
        import arabic_reshaper
        words = arabic_reshaper.reshape(self.text.replace("\n", " ")).split()
        lines, cur = [], ""
        for w in words:
            trial = f"{cur} {w}".strip()
            if pdfmetrics.stringWidth(trial, self.font, self.size) <= width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines or [""]

    def wrap(self, aw, ah):
        self._width = aw
        if self._lines is None:
            self._lines = self._break(aw)
        return aw, self.space_before + len(self._lines) * self.leading + self.space_after

    def split(self, aw, ah):
        lines = self._lines if self._lines is not None else self._break(aw)
        fit = int((ah - self.space_before) // self.leading)
        if fit <= 0:
            return []
        if fit >= len(lines):
            return [self]
        kw = dict(font=self.font, size=self.size, leading=self.leading, color=self.color, align=self.align)
        return [RTLParagraph(self.text, space_before=self.space_before, space_after=0, lines=lines[:fit], **kw),
                RTLParagraph(self.text, space_before=0, space_after=self.space_after, lines=lines[fit:], **kw)]

    def draw(self):
        c = self.canv
        c.setFont(self.font, self.size)
        c.setFillColor(self.color)
        total = self.space_before + len(self._lines) * self.leading + self.space_after
        for i, line in enumerate(self._lines):
            y = total - self.space_before - (i + 1) * self.leading + (self.leading - self.size) * 0.55
            visual = _get_display(line)
            if self.align == "center":
                c.drawCentredString(self._width / 2, y, visual)
            else:
                c.drawRightString(self._width, y, visual)


class ReportBuilder:
    """Creates paragraphs/tables in the right direction and font for the report language."""

    STYLES = {  # size, leading, color, bold, space_before, space_after
        "title": (24, 30, BRAND, True, 0, 4), "subtitle": (11, 15, MUTED, False, 0, 4),
        "h1": (15, 20, BRAND, True, 6, 10), "h2": (11.5, 15, ACCENT, True, 10, 6),
        "body": (9.5, 13.5, INK, False, 0, 4), "small": (8.5, 11.5, MUTED, False, 0, 4),
        "bullet": (9.5, 13.5, INK, False, 0, 3), "th": (9.5, 12, colors.white, True, 0, 0),
        "td": (9.5, 13, INK, False, 0, 0), "tdb": (9.5, 13, INK, True, 0, 0),
    }

    def __init__(self, lang: str):
        self.lang = lang
        self.rtl = lang == "ar" and _register_fonts()
        if lang == "ar" and not self.rtl:
            self.lang = "en"
        self._pstyles = {}
        for name, (size, leading, color, bold, sb, sa) in self.STYLES.items():
            self._pstyles[name] = ParagraphStyle(
                name, fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=size, leading=leading,
                textColor=color, spaceBefore=sb, spaceAfter=sa,
                alignment=TA_CENTER if name in ("title", "subtitle") else TA_LEFT,
                leftIndent=14 if name == "bullet" else 0, bulletIndent=4 if name == "bullet" else 0)

    def t(self, key):
        return L(self.lang, key)

    def p(self, text, kind="body", ltr=False):
        """Paragraph; English content inside an Arabic report (e.g. the transcript) can be forced LTR."""
        text = "" if text is None else str(text)
        if self.rtl and not ltr and (ARABIC_RE.search(text) or kind in ("title", "subtitle", "h1", "h2")):
            size, leading, color, bold, sb, sa = self.STYLES[kind]
            if kind == "bullet":
                text = "• " + text
            return RTLParagraph(text, font="Amiri-Bold" if bold else "Amiri", size=size + 1, leading=leading * 1.25,
                                color=color, align="center" if kind in ("title", "subtitle") else "right",
                                space_before=sb, space_after=sa)
        clean = escape(text.encode("latin-1", "replace").decode("latin-1"))
        style = self._pstyles[kind]
        if self.rtl and not ltr and kind != "bullet":  # numbers/English inside an Arabic table cell
            style = ParagraphStyle(kind + "_r", parent=style, alignment=2)
        if kind == "bullet":
            return Paragraph(clean, style, bulletText="•")
        return Paragraph(clean, style)

    def table(self, rows, widths, header=True, zebra=True, bg=None):
        if self.rtl:
            rows = [list(reversed(r)) for r in rows]
            widths = list(reversed(widths))
        t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
        style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.5, GRID),
                 ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                 ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]
        if header:
            style.append(("BACKGROUND", (0, 0), (-1, 0), BRAND))
        if bg is not None:
            style.append(("BACKGROUND", (0, 1 if header else 0), (-1, -1), bg))
        elif zebra:
            style += [("BACKGROUND", (0, r), (-1, r), SOFT) for r in range(1 if header else 0, len(rows)) if r % 2 == 0]
        t.setStyle(TableStyle(style))
        return t


def _chart_text(text: str, lang: str) -> str:
    return _shape(text) if lang == "ar" and ARABIC_RE.search(text) else text


def _chart_font(lang: str):
    if lang != "ar":
        return None
    from matplotlib.font_manager import FontProperties
    return FontProperties(fname=os.path.join(FONT_DIR, "Amiri-Regular.ttf"))


def _fig_to_buffer(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=200)
    plt.close(fig)
    buf.seek(0)
    return buf


def _chart_scores(composite: Dict, lang: str) -> io.BytesIO:
    fp = _chart_font(lang)
    labels = [_chart_text(L(lang, k), lang) for k in ("confidence", "anxiety", "hesitation")]
    values = [composite["confidence"], composite["anxiety"], composite["hesitation"]]
    fig, ax = plt.subplots(figsize=(5.2, 2.6))
    bars = ax.barh(labels, values, color=["#2E7D32", "#C62828", "#EF6C00"], height=0.55)
    ax.set_xlim(0, 1)
    ax.invert_yaxis()
    if fp:
        for lbl in ax.get_yticklabels():
            lbl.set_fontproperties(fp)
            lbl.set_fontsize(12)
    for b, v in zip(bars, values):
        ax.text(min(v + 0.02, 0.9), b.get_y() + b.get_height() / 2, f"{v:.2f}", va="center", fontsize=10)
    ax.set_title(_chart_text(L(lang, "chart_vocal"), lang), fontsize=11 if not fp else 13, fontproperties=fp)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", alpha=0.3)
    return _fig_to_buffer(fig)


def _chart_talk_time(utterances: List[Dict], lang: str) -> io.BytesIO:
    fp = _chart_font(lang)
    totals: Dict[str, float] = {}
    for u in utterances:
        totals[u["role"]] = totals.get(u["role"], 0.0) + (u["end"] - u["start"]) / 1000
    fig, ax = plt.subplots(figsize=(3.2, 2.6))
    _, texts, _ = ax.pie(list(totals.values()), labels=[_chart_text(L(lang, r), lang) for r in totals],
                         autopct="%1.0f%%", colors=["#1F6FEB", "#9DB9E8", "#CCCCCC"][: len(totals)],
                         startangle=90, wedgeprops={"linewidth": 1, "edgecolor": "white"})
    if fp:
        for tx in texts:
            tx.set_fontproperties(fp)
            tx.set_fontsize(12)
    ax.set_title(_chart_text(L(lang, "chart_talk"), lang), fontsize=11 if not fp else 13, fontproperties=fp)
    return _fig_to_buffer(fig)


def _chart_questions(qa: List[Dict], lang: str) -> Optional[io.BytesIO]:
    scored = [q for q in qa if q.get("score") is not None]
    if not scored:
        return None
    fp = _chart_font(lang)
    fig, ax = plt.subplots(figsize=(6.6, 2.2))
    xs = [f"Q{q['index']}" for q in scored]
    ys = [q["score"] for q in scored]
    cols = ["#2E7D32" if s >= 7 else "#EF6C00" if s >= 5 else "#C62828" for s in ys]
    ax.bar(xs, ys, color=cols, width=0.6)
    ax.set_ylim(0, 10)
    for x, y in zip(xs, ys):
        ax.text(x, y + 0.2, str(y), ha="center", fontsize=9)
    ax.set_title(_chart_text(L(lang, "chart_q"), lang), fontsize=11 if not fp else 13, fontproperties=fp)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", alpha=0.3)
    return _fig_to_buffer(fig)


def create_pdf_report(analysis: Dict, output_path: str, lang: str = "en") -> None:
    rb = ReportBuilder(lang)
    lang = rb.lang
    T, P = rb.t, rb.p
    doc = SimpleDocTemplate(output_path, pagesize=letter, rightMargin=0.75 * inch, leftMargin=0.75 * inch,
                            topMargin=0.9 * inch, bottomMargin=0.8 * inch,
                            title="EvalBot Interview Analysis Report", author="EvalBot")
    ev = analysis["evaluation"]
    voice = analysis["voice_analysis"]
    score = analysis["suitability_score"]
    score_color = "#2E7D32" if score >= 65 else "#EF6C00" if score >= 50 else "#C62828"
    W = doc.width
    story: List = []

    def bullets(items):
        for it in items:
            story.append(P(it, "bullet"))

    def header_footer(canvas, d):
        canvas.saveState()
        top = letter[1] - 0.6 * inch
        canvas.setStrokeColor(ACCENT)
        canvas.setLineWidth(0.8)
        canvas.line(d.leftMargin, top, letter[0] - d.rightMargin, top)
        left_x, right_x = d.leftMargin, letter[0] - d.rightMargin
        header = T("header")
        footer = T("footer")
        page = f"{T('page')} {d.page}"
        if rb.rtl:
            canvas.setFont("Amiri-Bold", 9.5)
            canvas.setFillColor(BRAND)
            canvas.drawRightString(right_x, top + 6, _shape(header))
            canvas.setFont("Amiri", 9)
            canvas.setFillColor(MUTED)
            canvas.drawString(left_x, top + 6, analysis["generated_at"])
            canvas.drawRightString(right_x, 0.5 * inch, _shape(footer))
            canvas.drawString(left_x, 0.5 * inch, _shape(page))
        else:
            canvas.setFont("Helvetica-Bold", 8.5)
            canvas.setFillColor(BRAND)
            canvas.drawString(left_x, top + 6, header)
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(MUTED)
            canvas.drawRightString(right_x, top + 6, analysis["generated_at"])
            canvas.drawString(left_x, 0.5 * inch, footer)
            canvas.drawRightString(right_x, 0.5 * inch, page)
        canvas.restoreState()

    # ---- Page 1: overview ------------------------------------------------------------
    story += [Spacer(1, 0.25 * inch), P(T("report_title"), "title"), Spacer(1, 4),
              P(f"{T('candidate_id')}: {analysis['user_id']}   |   {T('generated')}: {analysis['generated_at']}", "subtitle"),
              Spacer(1, 0.3 * inch)]
    num = Paragraph(f"<font size=30 color='{score_color}'><b>{score:.0f}</b></font>"
                    f"<font size=12 color='#5B6573'> / 100</font>", ParagraphStyle("s", alignment=1, leading=36))
    content = ev.get("content_score") if ev.get("content_score") is not None else "n/a"
    detail = [P(T("suitability"), "tdb"), P(analysis["verdict"], "td"),
              P(T("score_basis").format(content=content), "small")]
    cells = [num, detail]
    widths = [1.8 * inch, W - 1.8 * inch]
    if rb.rtl:
        cells, widths = cells[::-1], widths[::-1]
    score_tbl = Table([cells], colWidths=widths)
    score_tbl.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1, GRID), ("BACKGROUND", (0, 0), (-1, -1), SOFT),
                                   ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 12),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 10)]))
    story += [score_tbl, Spacer(1, 0.25 * inch)]

    info = analysis["interview"]
    rows = [[P(T("interview"), "th"), P("", "th")],
            [P(T("duration"), "tdb"), P(f"{info['duration_seconds'] / 60:.1f} {T('minutes')}", "td")],
            [P(T("speaker_turns"), "tdb"), P(str(info["speaker_turns"]), "td")],
            [P(T("questions_answered"), "tdb"), P(str(len(analysis["qa_pairs"])), "td")],
            [P(T("speakers"), "tdb"), P(" / ".join(f"{s['speaker_name']} ({T(s['role'])})"
                                                 for s in analysis["speakers"].values()), "td")]]
    if "error" not in voice:
        rows.append([P(T("interviewee_time"), "tdb"),
                     P(f"{voice['speaking_time_seconds'] / 60:.1f} {T('minutes')}, {voice['word_count']} {T('words')}", "td")])
    story += [rb.table(rows, [2.3 * inch, W - 2.3 * inch]), Spacer(1, 0.2 * inch)]
    story.append(P(T("exec_summary"), "h1"))
    bullets(ev.get("executive_summary", []))
    story.append(PageBreak())

    # ---- Communication & vocal dynamics ------------------------------------------------
    story.append(P(T("comm_title"), "h1"))
    if "error" not in voice:
        it = voice["interpretation"]
        cs = voice["composite_scores"]
        top_f = ", ".join(f"'{k}' x{v}" for k, v in list(voice["filler_words"].items())[:5]) or T("none")
        mrows = [
            [P(T("metric"), "th"), P(T("value"), "th"), P(T("meaning"), "th")],
            [P(T("speaking_rate"), "tdb"), P(f"{voice['speaking_rate']:.2f} {T('wps')}", "td"), P(T("m_rate"), "td")],
            [P(T("fillers"), "tdb"), P(f"{voice['filler_ratio'] * 100:.1f}% {T('of_words')}", "td"),
             P(f"{T('most_frequent')}: {top_f}", "td")],
            [P(T("repetition"), "tdb"), P(f"{voice['repetition_score']:.3f}", "td"), P(T("m_rep"), "td")],
            [P(T("fluency"), "tdb"), P(T(it["fluency_level"]), "td"), P(T("m_flu"), "td")],
            [P(T("confidence"), "tdb"), P(f"{T(it['confidence_level'])} ({cs['confidence']:.2f})", "td"), P(T("m_conf"), "td")],
            [P(T("anxiety"), "tdb"), P(f"{T(it['anxiety_level'])} ({cs['anxiety']:.2f})", "td"), P(T("m_anx"), "td")],
            [P(T("pitch"), "tdb"), P(f"{voice['pitch_analysis']['mean_hz']:.0f} Hz (sd {voice['pitch_analysis']['std_dev_hz']:.0f})", "td"),
             P(T("m_pitch"), "td")],
        ]
        story += [rb.table(mrows, [1.5 * inch, 1.7 * inch, W - 3.2 * inch]), Spacer(1, 0.15 * inch)]
        imgs = [Image(_chart_scores(cs, lang), width=3.9 * inch, height=1.95 * inch),
                Image(_chart_talk_time(analysis["transcript"], lang), width=2.5 * inch, height=2.03 * inch)]
        cw = [4.1 * inch, W - 4.1 * inch]
        if rb.rtl:
            imgs, cw = imgs[::-1], cw[::-1]
        story += [Table([imgs], colWidths=cw), Spacer(1, 0.1 * inch)]
    else:
        story.append(P(voice["error"], "body"))
    if ev.get("communication"):
        story.append(P(T("observations"), "h2"))
        bullets(ev["communication"])
    if ev.get("communication_tip"):
        story.append(P(T("tip"), "h2"))
        story.append(P(ev["communication_tip"], "body"))

    # ---- Question-by-question feedback --------------------------------------------------
    qa = analysis["qa_pairs"]
    if qa:
        story.append(PageBreak())
        story.append(P(T("qa_title"), "h1"))
        chart = _chart_questions(qa, lang)
        if chart:
            story += [Image(chart, width=W, height=W * 2.2 / 6.6), Spacer(1, 0.1 * inch)]
        for q in qa:
            badge = f"{q['score']}/10" if q.get("score") is not None else ""
            head_color = (colors.HexColor("#2E7D32") if (q.get("score") or 0) >= 7 else
                          colors.HexColor("#EF6C00") if (q.get("score") or 0) >= 5 else colors.HexColor("#C62828"))
            answer = q["answer"] if len(q["answer"]) < 420 else q["answer"][:400].rsplit(" ", 1)[0] + " ..."
            rows = [[P(f"Q{q['index']}  {badge}", "th"), P(q["question"], "th", ltr=True)],
                    [P(T("answer"), "tdb"), P(answer, "td", ltr=True)]]
            if q.get("what_went_well"):
                rows.append([P(T("went_well"), "tdb"), P(q["what_went_well"], "td")])
            if q.get("what_to_improve"):
                rows.append([P(T("to_improve"), "tdb"), P(q["what_to_improve"], "td")])
            if q.get("improved_answer"):
                rows.append([P(T("better_answer"), "tdb"), P(q["improved_answer"], "td", ltr=True)])
            t = rb.table(rows, [1.35 * inch, W - 1.35 * inch], zebra=False)
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), head_color)]))
            if q.get("what_went_well"):
                t.setStyle(TableStyle([("BACKGROUND", (0, 2), (-1, 2), GOOD_BG)]))
            if q.get("what_to_improve"):
                t.setStyle(TableStyle([("BACKGROUND", (0, 3), (-1, 3), BAD_BG)]))
            story += [KeepTogether([t]), Spacer(1, 0.14 * inch)]

    # ---- Competencies ------------------------------------------------------------------
    if ev.get("strengths") or ev.get("weaknesses"):
        story.append(PageBreak())
        story.append(P(T("competency_title"), "h1"))
    if ev.get("strengths"):
        story.append(P(T("strengths"), "h2"))
        rows = [[P(T("competency"), "th"), P(T("assessment"), "th")]]
        for s in ev["strengths"]:
            rows.append([P(s["competency"], "tdb"),
                         [P(s["explanation"], "td"), P(f"{T('evidence')}: {s['evidence']}", "small")]])
        story += [rb.table(rows, [1.7 * inch, W - 1.7 * inch], bg=GOOD_BG), Spacer(1, 0.15 * inch)]
    if ev.get("weaknesses"):
        story.append(P(T("dev_areas"), "h2"))
        rows = [[P(T("area"), "th"), P(T("feedback"), "th")]]
        rows += [[P(w["area"], "tdb"), P(w["feedback"], "td")] for w in ev["weaknesses"]]
        story += [rb.table(rows, [1.7 * inch, W - 1.7 * inch], bg=BAD_BG), Spacer(1, 0.15 * inch)]

    # ---- Role fit, recommendations, next steps -----------------------------------------
    if ev.get("role_fit") or ev.get("recommendations") or ev.get("next_steps"):
        story.append(PageBreak())
    if ev.get("role_fit"):
        story.append(P(T("role_fit"), "h1"))
        bullets(ev["role_fit"])
    if ev.get("recommendations"):
        story.append(P(T("recs"), "h1"))
        rows = [[P(T("rec_area"), "th"), P(T("recommendation"), "th"), P(T("how_to"), "th")]]
        rows += [[P(T(r["category"]), "tdb"), P(r["recommendation"], "td"), P(r["how_to"], "td")]
                 for r in ev["recommendations"]]
        story += [rb.table(rows, [1.4 * inch, 2.6 * inch, W - 4.0 * inch]), Spacer(1, 0.15 * inch)]
    if ev.get("next_steps"):
        story.append(P(T("next_steps"), "h1"))
        bullets(ev["next_steps"])

    # ---- Appendix: transcript (always left-to-right, it's the original English) ----------
    story.append(PageBreak())
    story.append(P(T("appendix"), "h1"))
    story.append(P(T("appendix_note"), "small"))
    rows = [[P(T("time"), "th"), P(T("role"), "th"), P(T("text"), "th")]]
    for u in analysis["transcript"]:
        m, s = divmod(int(u["start"] / 1000), 60)
        rows.append([P(f"{m:02d}:{s:02d}", "td"), P(T(u["role"]), "tdb"), P(u["text"], "td", ltr=True)])
    story.append(rb.table(rows, [0.6 * inch, 1.0 * inch, W - 1.6 * inch]))
    if not ev.get("ai_generated", True):
        story += [Spacer(1, 0.2 * inch), P(T("ai_unavailable"), "small")]

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
                      progress=None, lang: str = "en") -> Dict:
    """Run the full pipeline. Returns paths to the PDF and JSON reports plus a short summary."""
    lang = lang if lang in LABELS else "en"

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
            "speaker": speakers[u["speaker"]]["speaker_name"], "label": u["speaker"],
            "role": speakers[u["speaker"]]["role"], "start": u["start"], "end": u["end"], "text": u["text"],
            "confidence": round(float(u.get("confidence", 0)), 3), "prosodic_features": u["prosodic_features"],
        } for u in utterances]

        step("Analyzing the interviewee's voice")
        voice = analyze_interviewee_voice(y, sr, clean_utts)

        analysis = {
            "user_id": user_id, "language": lang,
            "generated_at": time.strftime("%Y-%m-%d"),
            "interview": {"duration_seconds": round(len(y) / sr, 1), "speaker_turns": len(clean_utts),
                          "language": transcript.get("language_code", "en")},
            "speakers": speakers, "voice_analysis": voice, "transcript": clean_utts,
            "qa_pairs": build_qa_pairs(clean_utts),
            "models": {
                "transcription": "AssemblyAI universal-2",
                "speaker_embeddings": "nvidia/speakerverification_en_titanet_large",
                "speaker_index": "pinecone" if PINECONE_API_KEY else "built-in",
                "role_classifier": "RandomForest (TF-IDF + handcrafted), trained on MIT interview transcripts",
                "role_classifier_heldout_accuracy": getattr(get_role_classifier(), "heldout_accuracy_", None),
                "evaluation": GEMINI_MODEL if GEMINI_API_KEY else None,
            },
        }

        step("Generating AI evaluation")
        evaluation = generate_evaluation(analysis, lang)
        if evaluation is None:
            evaluation = fallback_evaluation(analysis, lang)
        else:
            evaluation["ai_generated"] = True
            by_index = {q.get("index"): q for q in evaluation.get("questions", [])}
            for p in analysis["qa_pairs"]:
                fb = by_index.get(p["index"], {})
                p.update({k: fb.get(k) for k in ("score", "what_went_well", "what_to_improve", "improved_answer")})
                if p.get("score") is not None:
                    p["score"] = int(max(0, min(10, p["score"])))
        evaluation.pop("questions", None)
        analysis["evaluation"] = evaluation
        provisional = evaluation.get("content_score") is None
        analysis["suitability_score"] = calculate_acceptance_probability(voice, evaluation.get("content_score"))
        analysis["verdict"] = verdict_for(analysis["suitability_score"], lang, provisional)

        step("Building PDF report")
        base = f"{user_id}_{uuid.uuid4().hex[:8]}"
        os.makedirs(output_dir, exist_ok=True)
        pdf_path = os.path.abspath(os.path.join(output_dir, f"{base}_report.pdf"))
        json_path = os.path.abspath(os.path.join(output_dir, f"{base}_analysis.json"))
        create_pdf_report(analysis, pdf_path, lang)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(convert_to_serializable(analysis), f, indent=2, ensure_ascii=False)

        step("Done")
        return {"pdf_path": pdf_path, "json_path": json_path, "suitability_score": analysis["suitability_score"],
                "verdict": analysis["verdict"], "summary": evaluation.get("executive_summary", []),
                "voice": voice.get("interpretation", {}), "lang": lang}
    finally:
        if wav_file and os.path.exists(wav_file):
            os.remove(wav_file)


# --------------------------------------------------------------------------------------
# Practice mode: one question, one recorded answer, instant feedback
# --------------------------------------------------------------------------------------
QUESTION_BANK = {
    "General": [
        "Tell me about yourself.",
        "Why are you interested in this role?",
        "Where do you see yourself in five years?",
        "What are your greatest strengths?",
        "What is your biggest weakness, and how are you working on it?",
        "Why should we hire you?",
    ],
    "Behavioral": [
        "Tell me about a time you faced a difficult challenge at work or university. How did you handle it?",
        "Describe a situation where you disagreed with a teammate. What did you do?",
        "Tell me about a time you made a mistake. What did you learn?",
        "Give an example of a time you led a team or took initiative.",
        "Describe a time you had to meet a tight deadline.",
        "Tell me about a time you had to learn something new quickly.",
    ],
    "Data Engineering": [
        "Explain the difference between batch and stream processing, and when you would use each.",
        "How would you design a data pipeline that ingests data from several sources into a data warehouse?",
        "What is the difference between a data lake and a data warehouse?",
        "How do you make sure the data in your pipeline is accurate and of good quality?",
        "Explain how Apache Spark processes data in a distributed way.",
        "What role does Apache Kafka play in a real-time data architecture?",
    ],
    "Software Engineering": [
        "How do you design a REST API that other teams will rely on?",
        "Describe how you debug a problem that only happens in production.",
        "What is the difference between a process and a thread?",
        "How do you approach writing tests for your code?",
        "Tell me about a technical decision you made and the trade-offs you considered.",
        "How would you scale a web service that is getting slow under load?",
    ],
    "AI / Machine Learning": [
        "Explain overfitting and how you prevent it.",
        "How would you evaluate a classification model on an imbalanced dataset?",
        "Walk me through a machine learning project you built from data to deployment.",
        "What is the difference between supervised and unsupervised learning?",
        "How would you explain a model's prediction to a non-technical stakeholder?",
        "What are embeddings and where have you used them?",
    ],
}

PRACTICE_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "description": "0-10 overall quality of the answer"},
        "relevance": {"type": "string", "enum": ["on_topic", "partially", "off_topic"]},
        "summary": {"type": "string"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "improvements": {"type": "array", "items": {"type": "string"}},
        "delivery_tip": {"type": "string"},
        "improved_answer": {"type": "string"},
    },
    "required": ["score", "relevance", "summary", "strengths", "improvements", "delivery_tip", "improved_answer"],
}


def generate_practice_questions(role: str, count: int = 5) -> List[str]:
    role = (role or "").strip()[:80]
    if not role:
        return []
    result = _gemini_json(
        f"Write {count} realistic job interview questions for a candidate applying as: {role}.\n"
        "Mix behavioral and role-specific technical questions, suitable for an entry-level to mid-level "
        "candidate. Each question should be answerable in 1-2 minutes. Write them in English.",
        {"type": "object", "properties": {"questions": {"type": "array", "items": {"type": "string"}}},
         "required": ["questions"]}, temperature=0.8)
    return [q.strip() for q in (result or {}).get("questions", []) if q.strip()][:count]


def evaluate_practice_answer(audio_path: str, question: str, lang: str = "en", role: str = "") -> Dict:
    lang = lang if lang in LABELS else "en"
    wav_file = convert_to_wav(audio_path)
    try:
        y, sr = librosa.load(wav_file, sr=16000)
        if len(y) < sr:
            raise ValueError("The recording is too short. Please answer for at least a few seconds.")
        transcript = transcribe(wav_file, speakers_expected=None, diarize=False)
        words = transcript.get("words") or []
        text = (transcript.get("text") or "").strip()
        if not words or not text:
            raise ValueError("No speech was detected. Check your microphone and try again.")
        start, end = words[0]["start"], words[-1]["end"]
        utt = {"role": "Interviewee", "start": start, "end": end, "text": text,
               "prosodic_features": extract_prosodic_features(y, sr, start, end)}
        voice = analyze_interviewee_voice(y, sr, [utt])
        metrics = {k: voice.get(k) for k in ("speaking_rate", "filler_ratio", "filler_words", "interpretation")}
        feedback = _gemini_json(
            f"""You are an encouraging but honest interview coach. A candidate{f' applying for: {role}' if role else ''}
answered one interview question out loud. Evaluate the answer.

- Judge relevance, structure (e.g. STAR), specificity and impact. Be concrete and kind.
- 2-4 strengths and 2-4 improvements, each one sentence.
- delivery_tip: one tip based on the voice metrics (pace, filler words, confidence).
- improved_answer: a stronger version (4-6 sentences, first person) that keeps the candidate's own facts;
  use placeholders like [number] where a detail is missing. Keep it in English.
{_language_rule(lang)}
Question: {question}
Answer (transcribed): {text}
Answer length: {(end - start) / 1000:.0f} seconds
Voice metrics: {json.dumps(metrics)}
""", PRACTICE_SCHEMA)
        if feedback:
            feedback["score"] = int(max(0, min(10, feedback.get("score", 0))))
            feedback["ai_generated"] = True
        else:
            feedback = {"ai_generated": False, "score": None, "summary": fallback_evaluation(
                {"voice_analysis": voice}, lang)["communication"][0] if "error" not in voice else "",
                "strengths": [], "improvements": [], "delivery_tip": "", "improved_answer": "", "relevance": None}
        return {"question": question, "transcript": text, "duration_seconds": round((end - start) / 1000, 1),
                "voice": voice, "feedback": feedback, "lang": lang}
    finally:
        if os.path.exists(wav_file):
            os.remove(wav_file)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("usage: python process_interview.py <audio-file> [user_id] [en|ar]")
        sys.exit(1)
    out = process_interview(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "candidate",
                            lang=sys.argv[3] if len(sys.argv) > 3 else "en")
    print(json.dumps(out, indent=2, ensure_ascii=False))
