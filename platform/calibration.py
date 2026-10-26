"""Human-calibrated interview scores.

Models trained to predict the ratings that panels of human raters gave to 138 real mock
interviews (MIT Interview Dataset, ~9 raters per interview). The same feature extractor
is used for training and at runtime, so the model sees identical inputs in both places.
"""
import os
import re
from typing import Dict, List, Optional

import joblib
import librosa
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(HERE, "assets", "models", "calibrated_scores.joblib")

# ---------------------------------------------------------------------------------------
# Text features (from the candidate's words)
# ---------------------------------------------------------------------------------------
FILLERS = re.compile(r"\b(um+|uh+|uhm+|er+|ah+|hmm+|like|you know|i mean|kind of|sort of|basically|actually)\b")
POS = set("good great love enjoy excited happy interesting passion passionate fun amazing excellent best success "
          "successful proud glad".split())
NEG = set("bad hard difficult problem problems stress stressed worried hate fail failed failure wrong sorry "
          "unfortunately".split())
TENTATIVE = set("maybe perhaps guess probably possibly somewhat seems".split())
WE = {"we", "us", "our", "team", "together"}
I_WORDS = {"i", "me", "my", "i'm", "i've", "myself"}


def text_features(turns: List[str]) -> Dict[str, float]:
    text = " ".join(turns).lower()
    words = re.findall(r"[a-z']+", text)
    n = max(len(words), 1)
    sents = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    return {
        "txt_words": len(words),
        "txt_words_per_turn": len(words) / max(len(turns), 1),
        "txt_type_token": len(set(words)) / n,
        "txt_filler_rate": len(FILLERS.findall(text)) / n,
        "txt_i_rate": sum(w in I_WORDS for w in words) / n,
        "txt_we_rate": sum(w in WE for w in words) / n,
        "txt_pos_rate": sum(w in POS for w in words) / n,
        "txt_neg_rate": sum(w in NEG for w in words) / n,
        "txt_tentative_rate": sum(w in TENTATIVE for w in words) / n,
        "txt_number_rate": len(re.findall(r"\b\d+\b|\b(one|two|three|four|five|ten|hundred|percent)\b", text)) / n,
        "txt_avg_word_len": float(np.mean([len(w) for w in words])) if words else 0.0,
        "txt_avg_sentence_len": len(words) / max(len(sents), 1),
        "txt_long_word_rate": sum(len(w) >= 7 for w in words) / n,
        "txt_because_rate": len(re.findall(r"\b(because|so that|therefore|which meant|as a result)\b", text)) / n,
    }


# ---------------------------------------------------------------------------------------
# Voice features (from the candidate's audio segments)
# ---------------------------------------------------------------------------------------
def _sample_segments(segments: List[np.ndarray], sr: int, max_seconds: float = 90.0) -> List[np.ndarray]:
    """Evenly sample segments so pitch tracking stays fast on long interviews."""
    total = sum(len(s) for s in segments) / sr
    if total <= max_seconds:
        return segments
    step = total / max_seconds
    out, acc, nxt = [], 0.0, 0.0
    for s in segments:
        if acc >= nxt:
            out.append(s)
            nxt += step * len(s) / sr
        acc += len(s) / sr
    return out


def voice_features(y: np.ndarray, sr: int, utterances: List[Dict]) -> Dict[str, float]:
    cand = [u for u in utterances if u["role"] == "Interviewee"]
    other = [u for u in utterances if u["role"] != "Interviewee"]
    seg = lambda u: y[int(u["start"] * sr / 1000): int(u["end"] * sr / 1000)]
    segs = [s for s in (seg(u) for u in cand) if len(s) > sr // 5]
    cand_time = sum((u["end"] - u["start"]) / 1000 for u in cand)
    other_time = sum((u["end"] - u["start"]) / 1000 for u in other)
    f = {
        "voc_talk_share": cand_time / max(cand_time + other_time, 1e-6),
        "voc_turn_len_mean": cand_time / max(len(cand), 1),
        "voc_turns_per_min": len(cand) / max((cand_time + other_time) / 60, 1e-6),
    }
    if not segs:
        return f

    # pauses inside the candidate's speech
    speech, pauses = 0.0, []
    for s in segs:
        iv = librosa.effects.split(s, top_db=32, frame_length=1024, hop_length=256)
        speech += sum(e - b for b, e in iv) / sr
        pauses += [(b2 - e1) / sr for (_, e1), (b2, _) in zip(iv[:-1], iv[1:]) if (b2 - e1) / sr >= 0.25]
    f.update({
        "voc_speech_ratio": speech / max(cand_time, 1e-6),
        "voc_pauses_per_min": len(pauses) / max(cand_time / 60, 1e-6),
        "voc_pause_mean": float(np.mean(pauses)) if pauses else 0.0,
        "voc_long_pause_rate": sum(p >= 1.0 for p in pauses) / max(cand_time / 60, 1e-6),
    })

    # loudness dynamics
    rms = np.concatenate([librosa.feature.rms(y=s, frame_length=1024, hop_length=256)[0] for s in segs])
    rms_db = 20 * np.log10(rms + 1e-5)
    voiced_db = rms_db[rms_db > np.percentile(rms_db, 30)]
    f.update({
        "voc_loud_std_db": float(voiced_db.std()),
        "voc_loud_range_db": float(np.percentile(voiced_db, 95) - np.percentile(voiced_db, 10)),
        "voc_shimmer": float(np.mean(np.abs(np.diff(rms))) / (rms.mean() + 1e-9)),
    })

    # spectral brightness
    cent = np.concatenate([librosa.feature.spectral_centroid(y=s, sr=sr, n_fft=1024, hop_length=512)[0] for s in segs])
    f["voc_centroid_mean"] = float(cent.mean())
    f["voc_centroid_std"] = float(cent.std())

    # pitch (pYIN on an even sample of up to 90 s)
    pitches = []
    for s in _sample_segments(segs, sr):
        f0, voiced, _ = librosa.pyin(s, fmin=70, fmax=400, sr=sr, frame_length=1024, hop_length=256)
        pitches.append(f0[voiced & ~np.isnan(f0)])
    p = np.concatenate(pitches) if pitches else np.array([])
    if len(p) > 10:
        semis = 12 * np.log2(p / np.median(p))
        f.update({
            "voc_pitch_median": float(np.median(p)),
            "voc_pitch_semitone_std": float(semis.std()),
            "voc_pitch_range_semis": float(np.percentile(semis, 95) - np.percentile(semis, 5)),
            "voc_jitter": float(np.mean(np.abs(np.diff(p))) / p.mean()),
            "voc_voiced_ratio": len(p) / max(sum(len(s) for s in _sample_segments(segs, sr)) / 256, 1),
        })
    return f


def extract_features(y: np.ndarray, sr: int, utterances: List[Dict], candidate_texts: List[str]) -> Dict[str, float]:
    f = voice_features(y, sr, utterances)
    t = text_features(candidate_texts)
    cand_time = sum((u["end"] - u["start"]) / 1000 for u in utterances if u["role"] == "Interviewee")
    f["voc_speaking_rate"] = t["txt_words"] / max(cand_time, 1e-6)
    f.update(t)
    return f


# ---------------------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------------------
TRAIT_LABELS = {
    "en": {"Overall": "Overall impression", "RecommendHiring": "Hiring recommendation", "Excited": "Enthusiasm",
           "EngagingTone": "Engaging tone", "Friendly": "Friendliness", "NoFillers": "Few filler words",
           "StructuredAnswers": "Structured answers", "Calm": "Calmness", "Focused": "Focus",
           "Engaged": "Engagement", "Paused": "Good use of pauses", "NotAwkward": "Ease / not awkward",
           "Colleague": "Would be a good colleague", "Authentic": "Authenticity", "NotStressed": "Not stressed",
           "Smiled": "Smiling (heard in the voice)", "EyeContact": "Eye contact", "SpeakingRate": "Speaking pace"},
    "ar": {"Overall": "الانطباع العام", "RecommendHiring": "التوصية بالتعيين", "Excited": "الحماس",
           "EngagingTone": "نبرة جذابة", "Friendly": "الود", "NoFillers": "قلة كلمات الحشو",
           "StructuredAnswers": "تنظيم الإجابات", "Calm": "الهدوء", "Focused": "التركيز",
           "Engaged": "التفاعل", "Paused": "حسن استخدام التوقف", "NotAwkward": "الأريحية",
           "Colleague": "زميل عمل جيد", "Authentic": "المصداقية", "NotStressed": "عدم التوتر",
           "Smiled": "الابتسام (من نبرة الصوت)", "EyeContact": "التواصل البصري", "SpeakingRate": "سرعة الكلام"},
}

_bundle = None


def _load():
    global _bundle
    if _bundle is None and os.path.exists(MODEL_PATH):
        _bundle = joblib.load(MODEL_PATH)
    return _bundle


def available() -> bool:
    return _load() is not None


def predict(features: Dict[str, float], lang: str = "en") -> Optional[Dict]:
    """Predict human-panel ratings (1-7 scale) and place them against the 138 reference interviews."""
    b = _load()
    if b is None:
        return None
    from math import erf, sqrt

    x = np.array([[features.get(c, np.nan) for c in b["feature_names"]]], dtype=float)
    if "feature_bounds" in b:  # keep inputs inside the range seen in training (no wild extrapolation)
        lo, hi = np.array(b["feature_bounds"][0]), np.array(b["feature_bounds"][1])
        x = np.where(np.isnan(x), x, np.clip(x, lo, hi))
    labels = TRAIT_LABELS.get(lang, TRAIT_LABELS["en"])
    traits = []
    for name, m in b["models"].items():
        pred = float(np.clip(m["model"].predict(x)[0], 1, 7))
        z = (pred - m["ref_mean"]) / (m["ref_std"] + 1e-9)
        pct = 50 * (1 + erf(z / sqrt(2)))
        traits.append({"trait": name, "label": labels.get(name, name), "score_1_7": round(pred, 2),
                       "percentile": int(round(pct)), "model_r": round(m["cv_r"], 2),
                       "human_r": round(m.get("human_r", float("nan")), 2)})
    order = b.get("display_order", [t["trait"] for t in traits])
    traits.sort(key=lambda t: order.index(t["trait"]) if t["trait"] in order else 99)
    return {"traits": traits, "reference": b["reference"], "version": b["version"]}


def model_card(lang: str = "en") -> Optional[Dict]:
    """Validation results of the shipped models, for the public 'science' section."""
    b = _load()
    if b is None:
        return None
    labels = TRAIT_LABELS.get(lang, TRAIT_LABELS["en"])
    order = b.get("display_order", list(b["models"]))
    traits = sorted(b["models"].items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else 99)
    return {"reference": b["reference"], "version": b["version"],
            "traits": [{"trait": k, "label": labels.get(k, k), "model_r": round(m["cv_r"], 2),
                        "human_r": round(m.get("human_r", 0), 2)} for k, m in traits]}
