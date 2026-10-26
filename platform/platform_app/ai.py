"""Interview intelligence: tracks, question generation, answer evaluation, follow-ups, session summaries."""
import json
import logging
import os
import tempfile
from typing import Dict, List, Optional

import librosa
import numpy as np

import process_interview as pi

logger = logging.getLogger("evalbot.ai")

# --------------------------------------------------------------------------------------
# Catalog
# --------------------------------------------------------------------------------------
TRACKS = [
    # id, English, Arabic, group
    ("data_engineering", "Data Engineering", "هندسة البيانات", "tech"),
    ("data_analysis", "Data Analysis / BI", "تحليل البيانات", "tech"),
    ("data_science", "Data Science", "علم البيانات", "tech"),
    ("ai_ml", "AI / Machine Learning", "الذكاء الاصطناعي وتعلم الآلة", "tech"),
    ("backend", "Backend Development", "تطوير الـ Backend", "tech"),
    ("frontend", "Frontend Development", "تطوير الـ Frontend", "tech"),
    ("fullstack", "Full-Stack Development", "تطوير Full-Stack", "tech"),
    ("mobile", "Mobile Development (Android / iOS / Flutter)", "تطوير تطبيقات الموبايل", "tech"),
    ("devops_cloud", "DevOps & Cloud", "DevOps والحوسبة السحابية", "tech"),
    ("cybersecurity", "Cybersecurity", "الأمن السيبراني", "tech"),
    ("qa_testing", "Software Testing / QA", "اختبار البرمجيات", "tech"),
    ("embedded", "Embedded Systems & IoT", "الأنظمة المدمجة وإنترنت الأشياء", "tech"),
    ("networking", "Networking & IT Infrastructure", "الشبكات والبنية التحتية", "tech"),
    ("it_support", "IT Support", "الدعم الفني", "tech"),
    ("ui_ux", "UI / UX Design", "تصميم واجهات وتجربة المستخدم", "design"),
    ("graphic_design", "Graphic Design", "التصميم الجرافيكي", "design"),
    ("product_management", "Product Management", "إدارة المنتجات", "business"),
    ("project_management", "Project Management", "إدارة المشروعات", "business"),
    ("business_analysis", "Business Analysis", "تحليل الأعمال", "business"),
    ("marketing", "Marketing & Digital Marketing", "التسويق والتسويق الرقمي", "business"),
    ("sales", "Sales & Business Development", "المبيعات وتطوير الأعمال", "business"),
    ("hr", "Human Resources", "الموارد البشرية", "business"),
    ("finance", "Accounting & Finance", "المحاسبة والمالية", "business"),
    ("customer_service", "Customer Service", "خدمة العملاء", "business"),
    ("operations", "Operations & Supply Chain", "العمليات وسلاسل الإمداد", "business"),
    ("content", "Content Writing & Communication", "كتابة المحتوى والتواصل", "business"),
    ("teaching", "Teaching & Training", "التدريس والتدريب", "other"),
    ("engineering", "Engineering (Civil / Mechanical / Electrical)", "الهندسة (مدني / ميكانيكا / كهرباء)", "other"),
    ("healthcare", "Healthcare", "الرعاية الصحية", "other"),
    ("general", "General / Any role", "عام / أي وظيفة", "other"),
]
TRACK_NAMES = {t[0]: t[1] for t in TRACKS}
LEVELS = {"intern": "Internship", "junior": "Junior (0-2 years)", "mid": "Mid-level (2-5 years)",
          "senior": "Senior (5+ years)", "lead": "Lead / Manager"}
TYPES = {"mixed": "a balanced mix of technical, behavioral and motivation questions",
         "technical": "mostly technical / role-specific knowledge questions, plus one opening question",
         "behavioral": "behavioral questions (STAR) about past experiences, teamwork, conflict, failure, leadership",
         "hr": "HR / fit questions: motivation, career goals, culture fit, strengths and weaknesses, salary expectations",
         "case": "problem-solving / case / scenario questions where the candidate must reason out loud"}


def catalog() -> Dict:
    return {"tracks": [{"id": i, "en": en, "ar": ar, "group": g} for i, en, ar, g in TRACKS],
            "levels": list(LEVELS), "types": list(TYPES)}


def role_name(track: str, custom_role: str = "") -> str:
    return (custom_role or "").strip()[:80] or TRACK_NAMES.get(track, "General / Any role")


# --------------------------------------------------------------------------------------
# Question generation
# --------------------------------------------------------------------------------------
QUESTION_SCHEMA = {
    "type": "object",
    "properties": {"questions": {"type": "array", "items": {"type": "object", "properties": {
        "text": {"type": "string"},
        "kind": {"type": "string", "enum": ["opening", "technical", "behavioral", "situational", "motivation", "closing"]},
        "skill": {"type": "string", "description": "the competency this question tests, 1-3 words"},
        "rubric": {"type": "string", "description": "what a strong answer includes, 1-2 sentences"}},
        "required": ["text", "kind", "skill", "rubric"]}}},
    "required": ["questions"],
}


def generate_questions(track: str, level: str, itype: str, count: int = 6, custom_role: str = "",
                       cv_text: str = "", jd_text: str = "") -> List[Dict]:
    role = role_name(track, custom_role)
    ctx = ""
    if jd_text.strip():
        ctx += f"\nJob description (tailor questions to it):\n{jd_text.strip()[:4000]}\n"
    if cv_text.strip():
        ctx += f"\nCandidate CV (ask about their real experience where relevant):\n{cv_text.strip()[:4000]}\n"
    prompt = f"""You are an expert interviewer. Write {count} spoken interview questions for this interview:
- Role: {role}
- Level: {LEVELS.get(level, level)}
- Interview style: {TYPES.get(itype, TYPES['mixed'])}
{ctx}
Rules:
- Questions are asked out loud, so keep each one to one or two clear sentences; no code to read, no lists.
- Calibrate difficulty to the level. Technical questions must be specific to the role (real tools, concepts, trade-offs).
- Each question must be answerable in about 1-2 minutes of speaking.
- Start with a short opening question unless the style is purely technical; avoid near-duplicates.
- Write the questions in English.
"""
    res = pi._gemini_json(prompt, QUESTION_SCHEMA, temperature=0.8)
    qs = [q for q in (res or {}).get("questions", []) if q.get("text", "").strip()][:count]
    if not qs:  # offline fallback: built-in bank
        bank = pi.QUESTION_BANK["General"] + pi.QUESTION_BANK["Behavioral"]
        qs = [{"text": t, "kind": "behavioral", "skill": "communication", "rubric": ""} for t in bank[:count]]
    return qs


# --------------------------------------------------------------------------------------
# Answer evaluation (one recorded answer)
# --------------------------------------------------------------------------------------
SOFT_SKILLS = ["communication", "teamwork", "conflict_resolution", "time_management", "adaptability", "leadership",
               "problem_solving", "emotional_intelligence"]

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "description": "0-10"},
        "relevance": {"type": "string", "enum": ["on_topic", "partially", "off_topic"]},
        "summary": {"type": "string"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "improvements": {"type": "array", "items": {"type": "string"}},
        "delivery_tip": {"type": "string"},
        "improved_answer": {"type": "string"},
        "followup_question": {"type": "string", "description": "a natural probing follow-up, or empty string if not needed"},
        "rubric": {"type": "object", "properties": {
            "clarity": {"type": "integer", "description": "0-10, how clearly the thoughts are articulated"},
            "example_quality": {"type": "integer", "description": "0-10, relevance and depth of real examples"},
            "structure": {"type": "integer", "description": "0-10, logical flow (STAR where it fits)"},
            "outcome": {"type": "integer", "description": "0-10, a concrete result, resolution or learning"}},
            "required": ["clarity", "example_quality", "structure", "outcome"]},
        "soft_skills": {"type": "array", "items": {"type": "string", "enum": SOFT_SKILLS},
                        "description": "soft skills this answer gives real evidence of (may be empty)"},
    },
    "required": ["score", "relevance", "summary", "strengths", "improvements", "delivery_tip", "improved_answer",
                 "followup_question", "rubric", "soft_skills"],
}


def transcribe_answer(audio_bytes: bytes, suffix: str = ".webm") -> Dict:
    """Transcribe one answer and compute its voice metrics. Returns transcript, words, duration, voice."""
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        src = tmp.name
    wav = None
    try:
        wav = pi.convert_to_wav(src)
        y, sr = librosa.load(wav, sr=16000)
        if len(y) < sr:
            return {"transcript": "", "duration_s": len(y) / sr, "voice": {"error": "too short"}, "silent": True}
        tr = pi.transcribe(wav, speakers_expected=None, diarize=True)
        words = tr.get("words") or []
        text = (tr.get("text") or "").strip()
        if not words or not text:
            return {"transcript": "", "duration_s": len(y) / sr, "voice": {"error": "no speech"}, "silent": True}
        start, end = words[0]["start"], words[-1]["end"]
        utt = {"role": "Interviewee", "start": start, "end": end, "text": text,
               "prosodic_features": pi.extract_prosodic_features(y, sr, start, end)}
        voice = pi.analyze_interviewee_voice(y, sr, [utt])
        # integrity: a second voice speaking a substantial part of the answer
        counts: Dict[str, int] = {}
        for w in words:
            if w.get("speaker"):
                counts[w["speaker"]] = counts.get(w["speaker"], 0) + 1
        ranked = sorted(counts.values(), reverse=True)
        other = sum(ranked[1:])
        voice["speakers"] = len(counts) or 1
        voice["second_voice"] = bool(other >= 10 and other / max(1, len(words)) >= 0.25)
        return {"transcript": text, "duration_s": round((end - start) / 1000, 1), "voice": voice, "silent": False,
                "speech_start_ms": start, "speech_end_ms": end}
    finally:
        for p in (src, wav):
            if p and os.path.exists(p):
                os.remove(p)


def evaluate_answer(question: Dict, transcript: str, voice: Dict, role: str, level: str, lang: str,
                    allow_followup: bool) -> Dict:
    metrics = {k: voice.get(k) for k in ("speaking_rate", "filler_ratio", "interpretation")} if "error" not in voice else {}
    prompt = f"""You are a fair, encouraging but honest interview coach. A candidate for "{role}" ({LEVELS.get(level, level)})
answered this interview question out loud. Evaluate the answer.

Question: {question['text']}
What a strong answer includes: {question.get('rubric') or 'n/a'}
Answer (speech-to-text transcript): {transcript}
Voice metrics: {json.dumps(metrics)}

- score 0-10 for content quality: relevance, correctness, depth, structure (STAR where it fits), specificity.
- 2-4 strengths and 2-4 improvements, one sentence each, concrete and tied to what they said.
- delivery_tip: one tip from the voice metrics.
- improved_answer: a stronger version (4-6 sentences, first person) that keeps the candidate's own facts and uses
  placeholders like [number] for missing details. Keep it in English.
- rubric: clarity, example_quality, structure and outcome, each 0-10 (for purely technical answers, judge example_quality
  by the concreteness of the examples and outcome by whether the answer reaches a clear conclusion).
- soft_skills: which of {", ".join(SOFT_SKILLS)} the answer shows real evidence of (empty list if none).
- followup_question: {"one short probing follow-up a real interviewer would ask about something specific the candidate said (in English), or an empty string if the answer was complete" if allow_followup else "always an empty string"}.
{pi._language_rule(lang)}"""
    res = pi._gemini_json(prompt, ANSWER_SCHEMA)
    if not res:
        return {"score": None, "relevance": None, "summary": "", "strengths": [], "improvements": [],
                "delivery_tip": "", "improved_answer": "", "followup_question": "", "ai_generated": False}
    res["score"] = int(max(0, min(10, res.get("score", 0))))
    res["ai_generated"] = True
    if not allow_followup:
        res["followup_question"] = ""
    return res


# --------------------------------------------------------------------------------------
# Session summary
# --------------------------------------------------------------------------------------
SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "one-sentence overall verdict"},
        "executive_summary": {"type": "array", "items": {"type": "string"}},
        "strengths": {"type": "array", "items": {"type": "object", "properties": {
            "competency": {"type": "string"}, "explanation": {"type": "string"}, "evidence": {"type": "string"}},
            "required": ["competency", "explanation", "evidence"]}},
        "weaknesses": {"type": "array", "items": {"type": "object", "properties": {
            "area": {"type": "string"}, "feedback": {"type": "string"}}, "required": ["area", "feedback"]}},
        "role_fit": {"type": "array", "items": {"type": "string"}},
        "recommendations": {"type": "array", "items": {"type": "object", "properties": {
            "category": {"type": "string", "enum": ["Communication Skills", "Content Delivery", "Professional Presentation"]},
            "recommendation": {"type": "string"}, "how_to": {"type": "string"}},
            "required": ["category", "recommendation", "how_to"]}},
        "learning_plan": {"type": "array", "items": {"type": "object", "properties": {
            "topic": {"type": "string"}, "why": {"type": "string"}, "how": {"type": "string"}},
            "required": ["topic", "why", "how"]}},
        "next_steps": {"type": "array", "items": {"type": "string"}},
        "hiring_signal": {"type": "string", "enum": ["strong_yes", "yes", "maybe", "no"]},
        "soft_skills": {"type": "array", "items": {"type": "object", "properties": {
            "skill": {"type": "string", "enum": SOFT_SKILLS}, "score": {"type": "integer", "description": "0-10"},
            "comment": {"type": "string", "description": "one sentence with evidence"}},
            "required": ["skill", "score", "comment"]},
            "description": "only the soft skills the interview gave evidence about"},
        "nonverbal": {"type": "string", "description": "2-3 sentences on non-verbal behaviour from the camera metrics, or empty string if none"},
    },
    "required": ["headline", "executive_summary", "strengths", "weaknesses", "role_fit", "recommendations",
                 "learning_plan", "next_steps", "hiring_signal", "soft_skills", "nonverbal"],
}


def summarize_session(role: str, level: str, lang: str, answers: List[Dict], voice: Dict,
                      calibrated: Optional[Dict], for_recruiter: bool, camera: Optional[Dict] = None) -> Optional[Dict]:
    qa = "\n\n".join(f"[{i + 1}] Q: {a['question']}\nA: {a.get('transcript') or '(no answer)'}\n"
                     f"Score: {a.get('score')}/10; rubric: {json.dumps((a.get('feedback') or {}).get('rubric') or {})}"
                     for i, a in enumerate(answers))
    cam = ""
    if camera:
        cam = ("Camera metrics (computed on the candidate's device): " + json.dumps(
            {k: camera.get(k) for k in ("face_visible", "eye_contact", "smile", "emotions", "dominant_emotion")}) +
            "\nUse them only for the 'nonverbal' field, cautiously: expressions are not reliable signs of ability.")
    cal = ""
    if calibrated:
        cal = "Human-calibrated delivery scores (percentile vs 138 rated interviews): " + ", ".join(
            f"{t['trait']} {t['percentile']}th" for t in calibrated["traits"])
    vm = {k: voice.get(k) for k in ("speaking_rate", "filler_ratio", "interpretation")} if voice and "error" not in voice else {}
    audience = ("The report is read by the hiring team." if for_recruiter
                else "The report is read by the candidate, who wants to improve; next_steps are their practice steps.")
    prompt = f"""You are EvalBot, a senior interviewer and career coach. Write the final evaluation of this interview.
Role: {role} ({LEVELS.get(level, level)}). {audience}

- Base every point on the answers below (quote briefly as evidence) and the metrics. Do not invent facts.
- 3 bullets executive summary, 3-6 strengths, 3-6 weaknesses, 3 role-fit bullets, exactly 3 recommendations
  (one per category), a 3-5 item learning_plan of topics to study for this role, and 3-5 next_steps.
- hiring_signal: your recommendation for a {LEVELS.get(level, level)} {role} position.
- soft_skills: score 0-10 only those of {", ".join(SOFT_SKILLS)} the answers gave evidence about, each with evidence.
- nonverbal: {"2-3 sentences from the camera metrics" if camera else "an empty string (no camera)"}.
{pi._language_rule(lang)}
Voice metrics: {json.dumps(vm)}
{cal}
{cam}

Interview:
{qa}
"""
    return pi._gemini_json(prompt, SUMMARY_SCHEMA)


# --------------------------------------------------------------------------------------
# Session-level audio features for calibrated scores
# --------------------------------------------------------------------------------------
def session_audio(answer_audio: List[bytes]) -> Optional[tuple]:
    """Concatenate answer recordings into one 16 kHz signal with candidate utterances."""
    ys, utts, t = [], [], 0
    for blob in answer_audio:
        with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as tmp:
            tmp.write(blob)
            src = tmp.name
        try:
            wav = pi.convert_to_wav(src)
            y, sr = librosa.load(wav, sr=16000)
            os.remove(wav)
        finally:
            os.remove(src)
        iv = librosa.effects.split(y, top_db=35)
        if len(iv):
            y = y[iv[0][0]: iv[-1][1]]  # trim leading/trailing silence
        if len(y) < 16000:
            continue
        utts.append({"role": "Interviewee", "start": t, "end": t + int(len(y) / 16), "text": ""})
        ys.append(y)
        gap = np.zeros(8000, dtype=y.dtype)
        ys.append(gap)
        t += int(len(y) / 16) + 500
    if not ys:
        return None
    return np.concatenate(ys), 16000, utts
