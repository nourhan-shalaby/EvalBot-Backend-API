"""EvalBot platform API: candidates, mock interviews, companies, jobs and reviews."""
import json
import logging
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
import csv
import io
from datetime import date, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

import calibration as cal
import process_interview as pi
from . import ai, insights
from .core import current_user, dumps, get_file, public_config, put_file, q, q1, recruiter

logger = logging.getLogger("evalbot.routes")
router = APIRouter(prefix="/api")
_workers = ThreadPoolExecutor(max_workers=int(os.getenv("PLATFORM_WORKERS", "2")))
MAX_FOLLOWUPS = 2
MAX_AUDIO_MB = 25


# --------------------------------------------------------------------------------------
# Public
# --------------------------------------------------------------------------------------
@router.get("/config")
def config():
    return {**public_config(), "calibrated_model": cal.available()}


@router.get("/model-card")
def model_card(lang: str = "en"):
    return cal.model_card("ar" if lang == "ar" else "en") or {"traits": []}


@router.get("/catalog")
def catalog():
    return ai.catalog()


JOB_PUBLIC_COLS = ("j.id, j.title, j.track, j.level, j.location, j.work_mode, j.employment_type, j.salary, j.skills, "
                   "j.deadline, j.share_token, j.created_at, j.answer_seconds, jsonb_array_length(j.questions) as question_count, "
                   "c.name as company, c.website, c.industry, c.size as company_size, c.about as company_about, "
                   "c.location as company_location, j.require_camera, j.record_video")
ACCEPTING = "(j.status = 'open' and (j.deadline is null or j.deadline >= current_date))"


@router.get("/public/jobs/{token}")
def public_job(token: str):
    j = q1(f"update jobs j set views = views + 1 from companies c where c.id = j.company_id and j.share_token = %s "
           f"returning {JOB_PUBLIC_COLS}, j.description, j.status, {ACCEPTING} as accepting", [token])
    if not j:
        raise HTTPException(404, "This job link is not valid")
    return j


@router.get("/board")
def job_board(search: str = "", track: str = "", level: str = "", work_mode: str = "", employment_type: str = ""):
    """Open public jobs from all companies (no sign-in needed)."""
    where, params = [ACCEPTING, "j.visibility = 'public'"], {}
    if search.strip():
        where.append("(j.title ilike %(s)s or j.description ilike %(s)s or c.name ilike %(s)s or j.skills::text ilike %(s)s "
                     "or j.location ilike %(s)s)")
        params["s"] = f"%{search.strip()[:80]}%"
    for col, val in (("track", track), ("level", level), ("work_mode", work_mode), ("employment_type", employment_type)):
        if val:
            where.append(f"j.{col} = %({col})s")
            params[col] = val
    return q(f"select {JOB_PUBLIC_COLS}, left(j.description, 260) as snippet, "
             f"(select count(*) from sessions s where s.job_id = j.id) as applicants "
             f"from jobs j join companies c on c.id = j.company_id where {' and '.join(where)} "
             f"order by j.created_at desc limit 200", params)


# --------------------------------------------------------------------------------------
# Profile & company
# --------------------------------------------------------------------------------------
class ProfileIn(BaseModel):
    full_name: Optional[str] = None
    headline: Optional[str] = None
    target_track: Optional[str] = None
    locale: Optional[str] = None
    role: Optional[str] = None


@router.get("/me")
def me(user: Dict = Depends(current_user)):
    company = q1("select * from companies where id = %s", [user["company_id"]]) if user.get("company_id") else None
    out = {k: v for k, v in user.items() if k not in ("cv_text", "cv")}
    return {**out, "company": company, "has_cv": bool(user.get("cv"))}


@router.patch("/me")
def update_me(body: ProfileIn, user: Dict = Depends(current_user)):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if "role" in fields and fields["role"] != user["role"]:
        if fields["role"] != "candidate" or user.get("company_id"):
            raise HTTPException(400, "Company accounts are created from the company setup page")
    if fields:
        sets = ", ".join(f"{k} = %({k})s" for k in fields)
        q(f"update profiles set {sets} where id = %(id)s", {**fields, "id": user["id"]})
    return me(q1("select * from profiles where id = %s", [user["id"]]))


# --------------------------------------------------------------------------------------
# CV profile
# --------------------------------------------------------------------------------------
MAX_CV_MB = 5


@router.get("/cv")
def get_cv(user: Dict = Depends(current_user)):
    return {"cv": user.get("cv"), "updated_at": user.get("cv_updated_at"), "has_text": bool(user.get("cv_text"))}


@router.post("/cv")
def upload_cv(file: UploadFile = File(...), user: Dict = Depends(current_user)):
    data = file.file.read(MAX_CV_MB * 1024 * 1024 + 1)
    if len(data) > MAX_CV_MB * 1024 * 1024:
        raise HTTPException(413, "The CV file is larger than 5 MB")
    name = (file.filename or "").lower()
    if not name.endswith((".pdf", ".docx", ".txt")):
        raise HTTPException(400, "Upload a PDF, Word (.docx) or text file")
    try:
        text = insights.cv_text_from_file(data, name)
    except Exception:
        raise HTTPException(400, "We couldn't read this file. Try exporting your CV as PDF again.")
    if len(text) < 80:
        raise HTTPException(400, "We couldn't find text in this file. If it's a scanned image, upload a text-based PDF or Word file.")
    cv = insights.parse_cv(text)
    if not cv:
        raise HTTPException(503, "The CV reader is busy. Try again in a minute.")
    q("update profiles set cv=%s, cv_text=%s, cv_updated_at=now(), "
      "headline=coalesce(nullif(headline, ''), %s) where id=%s", [cv, text, (cv.get("headline") or "")[:160], user["id"]])
    return {"cv": cv, "has_text": True}


@router.delete("/cv")
def delete_cv(user: Dict = Depends(current_user)):
    q("update profiles set cv=null, cv_text=null, cv_updated_at=null where id=%s", [user["id"]])
    return {"ok": True}


class CompanyIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    website: Optional[str] = Field(None, max_length=200)
    about: Optional[str] = Field(None, max_length=2000)
    industry: Optional[str] = Field(None, max_length=80)
    size: Optional[str] = Field(None, max_length=20)
    location: Optional[str] = Field(None, max_length=120)


@router.post("/companies")
def create_company(body: CompanyIn, user: Dict = Depends(current_user)):
    if user.get("company_id"):  # fields that are not sent keep their current value
        c = q1("update companies set name=%s, website=coalesce(%s, website), about=coalesce(%s, about), "
               "industry=coalesce(%s, industry), size=coalesce(%s, size), location=coalesce(%s, location) where id=%s returning *",
               [body.name, body.website, body.about, body.industry, body.size, body.location, user["company_id"]])
    else:
        if user["role"] == "candidate" and q1("select 1 from sessions where user_id=%s limit 1", [user["id"]]):
            raise HTTPException(400, "This account is already used for interviews. Create a separate account for your company.")
        c = q1("insert into companies (name, website, about, industry, size, location, created_by) "
               "values (%s, %s, %s, %s, %s, %s, %s) returning *",
               [body.name, body.website, body.about, body.industry, body.size, body.location, user["id"]])
        q("update profiles set role='recruiter', company_id=%s where id=%s", [c["id"], user["id"]])
    return c


# --------------------------------------------------------------------------------------
# Question generation
# --------------------------------------------------------------------------------------
class QuestionsIn(BaseModel):
    track: str = "general"
    level: str = "junior"
    interview_type: str = "mixed"
    count: int = Field(6, ge=3, le=12)
    custom_role: str = ""
    cv_text: str = ""
    jd_text: str = ""


@router.post("/questions/generate")
def generate(body: QuestionsIn, user: Dict = Depends(current_user)):
    return {"questions": ai.generate_questions(body.track, body.level, body.interview_type, body.count,
                                               body.custom_role, body.cv_text, body.jd_text)}


# --------------------------------------------------------------------------------------
# Sessions (mock interviews and job interviews)
# --------------------------------------------------------------------------------------
class SessionIn(QuestionsIn):
    language: str = "en"
    questions: Optional[List[Dict]] = None
    use_cv: bool = False
    record_video: bool = False


def _can_view(session: Dict, user: Dict) -> bool:
    if session["user_id"] == user["id"]:
        return True
    if session.get("job_id") and user["role"] == "recruiter":
        return bool(q1("select 1 from jobs where id=%s and company_id=%s", [session["job_id"], user.get("company_id")]))
    return False


def _session(sid: str, user: Dict, owner_only: bool = False) -> Dict:
    s = q1("select * from sessions where id = %s", [sid])
    if not s or (owner_only and s["user_id"] != user["id"]) or not _can_view(s, user):
        raise HTTPException(404, "Interview not found")
    return s


@router.post("/sessions")
def create_session(body: SessionIn, user: Dict = Depends(current_user)):
    if body.use_cv and not body.cv_text.strip() and user.get("cv_text"):
        body.cv_text = user["cv_text"]
    plan = body.questions or ai.generate_questions(body.track, body.level, body.interview_type, body.count,
                                                   body.custom_role, body.cv_text, body.jd_text)
    plan = [{"text": p["text"].strip()[:500], "kind": p.get("kind", "custom"), "skill": p.get("skill", ""),
             "rubric": p.get("rubric", "")} for p in plan if p.get("text", "").strip()]
    ctx = {"plan": plan, "role": ai.role_name(body.track, body.custom_role), "answer_seconds": 120,
           "has_cv": bool(body.cv_text.strip()), "has_jd": bool(body.jd_text.strip()), "followups": 0,
           "record_video": body.record_video}
    s = q1("insert into sessions (user_id, mode, track, level, interview_type, language, context) "
           "values (%s, 'mock', %s, %s, %s, %s, %s) returning *",
           [user["id"], body.track, body.level, body.interview_type, body.language if body.language in ("en", "ar") else "en", ctx])
    return s


class ApplyIn(BaseModel):
    language: str = "en"


@router.post("/jobs/apply/{token}")
def apply_job(token: str, body: ApplyIn, user: Dict = Depends(current_user)):
    if user["role"] == "recruiter":
        raise HTTPException(403, "Company accounts can't apply to jobs. Use a personal account to apply.")
    j = q1(f"select j.*, {ACCEPTING} as accepting from jobs j where j.share_token = %s", [token])
    if not j:
        raise HTTPException(404, "This job is not accepting interviews")
    existing = q1("select * from sessions where job_id=%s and user_id=%s order by created_at desc limit 1", [j["id"], user["id"]])
    if existing:
        return existing
    if not j["accepting"]:
        raise HTTPException(400, "This job is not accepting interviews")
    plan = [{"text": x["text"], "kind": x.get("kind", "custom"), "skill": x.get("skill", ""),
             "rubric": x.get("rubric", "")} for x in j["questions"]]
    ctx = {"plan": plan, "role": j["title"], "answer_seconds": j["answer_seconds"], "followups": 0,
           "job_title": j["title"], "no_followups": True, "require_camera": bool(j.get("require_camera")),
           "record_video": bool(j.get("record_video"))}
    return q1("insert into sessions (user_id, job_id, mode, track, level, interview_type, language, context) "
              "values (%s, %s, 'job', %s, %s, 'job', %s, %s) returning *",
              [user["id"], j["id"], j["track"], j["level"], body.language if body.language in ("en", "ar") else "en", ctx])


@router.get("/sessions")
def list_sessions(user: Dict = Depends(current_user)):
    return q("select s.id, s.mode, s.track, s.level, s.interview_type, s.status, s.overall_score, s.created_at, "
             "s.completed_at, s.context->>'role' as role, j.title as job_title, "
             "(select count(*) from answers a where a.session_id = s.id) as answered, "
             "jsonb_array_length(s.context->'plan') as planned "
             "from sessions s left join jobs j on j.id = s.job_id where s.user_id = %s order by s.created_at desc limit 100",
             [user["id"]])


@router.get("/applications")
def my_applications(user: Dict = Depends(current_user)):
    return q("select s.id, s.status, s.overall_score, s.created_at, s.completed_at, j.title, j.share_token, j.location, "
             "j.work_mode, j.employment_type, c.name as company, coalesce(r.status, 'new') as review_status, "
             "(select count(*) from answers a where a.session_id = s.id) as answered, "
             "jsonb_array_length(s.context->'plan') as planned "
             "from sessions s join jobs j on j.id = s.job_id join companies c on c.id = j.company_id "
             "left join reviews r on r.session_id = s.id where s.user_id = %s order by s.created_at desc", [user["id"]])


@router.get("/sessions/{sid}")
def get_session(sid: str, user: Dict = Depends(current_user)):
    s = _session(sid, user)
    s["answers"] = q("select id, idx, question, kind, is_followup, duration_s, transcript, voice, presence, feedback, "
                     "score, media, audio_path is not null as has_audio, created_at from answers where session_id=%s order by idx", [sid])
    if s.get("job_id"):
        s["job"] = q1("select j.title, c.name as company from jobs j join companies c on c.id=j.company_id where j.id=%s", [s["job_id"]])
    if s["user_id"] != user["id"]:
        c = q1("select full_name, email, headline, cv, cv_text from profiles where id=%s", [s["user_id"]])
        job = q1("select skills from jobs where id=%s", [s["job_id"]]) if s.get("job_id") else None
        s["candidate"] = {"full_name": c["full_name"], "email": c["email"], "headline": c["headline"], "cv": c["cv"],
                          "skill_match": insights.skill_match((job or {}).get("skills") or [], c["cv"], c["cv_text"] or "")}
    return s


@router.get("/sessions/{sid}/next")
def next_question(sid: str, user: Dict = Depends(current_user)):
    s = _session(sid, user, owner_only=True)
    plan = s["context"]["plan"]
    done = {r["idx"] for r in q("select idx from answers where session_id=%s", [sid])}
    for i, p in enumerate(plan):
        if i not in done:
            return {"done": False, "idx": i, "total": len(plan), "question": p["text"], "kind": p.get("kind"),
                    "is_followup": p.get("is_followup", False), "answer_seconds": s["context"].get("answer_seconds", 120)}
    return {"done": True, "total": len(plan)}


def _process_answer(sid: str, idx: int, blob: bytes, suffix: str):
    try:
        s = q1("select * from sessions where id=%s", [sid])
        plan = s["context"]["plan"]
        question = plan[idx]
        tr = ai.transcribe_answer(blob, suffix)
        if tr.get("silent"):
            fb = {"score": 0, "relevance": "off_topic", "summary": "No answer was detected in this recording.",
                  "strengths": [], "improvements": ["Make sure your microphone is working and answer out loud."],
                  "delivery_tip": "", "improved_answer": "", "followup_question": "", "ai_generated": False}
        else:
            ctx = s["context"]
            allow = (not ctx.get("no_followups") and ctx.get("followups", 0) < MAX_FOLLOWUPS
                     and not question.get("is_followup"))
            fb = ai.evaluate_answer(question, tr["transcript"], tr["voice"], ctx.get("role", ""), s["level"] or "junior",
                                    s["language"], allow)
        fb["skill"] = question.get("skill", "")
        q("update answers set transcript=%s, duration_s=%s, voice=%s, feedback=%s, score=%s where session_id=%s and idx=%s",
          [tr.get("transcript"), tr.get("duration_s"), tr.get("voice"), fb, fb.get("score"), sid, idx])
        fu = (fb.get("followup_question") or "").strip()
        if fu:
            # append the follow-up to the plan (atomic jsonb append, guarded by the follow-up counter)
            q("update sessions set context = jsonb_set(jsonb_set(context, '{plan}', (context->'plan') || %s::jsonb), "
              "'{followups}', to_jsonb(coalesce((context->>'followups')::int, 0) + 1)) "
              "where id=%s and status='in_progress' and coalesce((context->>'followups')::int, 0) < %s",
              [dumps([{"text": fu, "kind": "followup", "skill": question.get("skill", ""), "rubric": "",
                       "is_followup": True, "followup_of": idx}]), sid, MAX_FOLLOWUPS])
    except Exception as e:
        logger.exception("Answer processing failed")
        q("update answers set feedback=%s where session_id=%s and idx=%s",
          [{"error": str(e)[:300], "ai_generated": False}, sid, idx])


@router.post("/sessions/{sid}/answers")
def upload_answer(sid: str, idx: int = Form(...), file: UploadFile = File(...), presence: str = Form(""),
                  user: Dict = Depends(current_user)):
    s = _session(sid, user, owner_only=True)
    if s["status"] != "in_progress":
        raise HTTPException(400, "This interview is already finished")
    plan = s["context"]["plan"]
    if idx < 0 or idx >= len(plan):
        raise HTTPException(400, "Unknown question")
    blob = file.file.read(MAX_AUDIO_MB * 1024 * 1024 + 1)
    if len(blob) > MAX_AUDIO_MB * 1024 * 1024:
        raise HTTPException(413, "Recording is too large")
    suffix = os.path.splitext(file.filename or "")[1].lower() or ".webm"
    media = "video" if (file.content_type or "").startswith("video/") else "audio"
    path = put_file(f"sessions/{sid}/answer_{idx}{suffix}", blob, file.content_type or "audio/webm")
    try:
        pres = json.loads(presence) if presence else None
    except ValueError:
        pres = None
    q("insert into answers (session_id, idx, question, kind, is_followup, audio_path, presence, media) "
      "values (%s,%s,%s,%s,%s,%s,%s,%s) "
      "on conflict (session_id, idx) do update set audio_path=excluded.audio_path, presence=excluded.presence, "
      "media=excluded.media, transcript=null, feedback=null, score=null",
      [sid, idx, plan[idx]["text"], plan[idx].get("kind"), bool(plan[idx].get("is_followup")), path, pres, media])
    _workers.submit(_process_answer, sid, idx, blob, suffix)
    return {"ok": True, "idx": idx}


@router.get("/sessions/{sid}/answers/{idx}/audio")
def answer_audio(sid: str, idx: int, user: Dict = Depends(current_user)):
    _session(sid, user)
    a = q1("select audio_path, media from answers where session_id=%s and idx=%s", [sid, idx])
    if not a or not a["audio_path"]:
        raise HTTPException(404)
    ext = os.path.splitext(a["audio_path"])[1].lstrip(".") or "webm"
    if a.get("media") == "video":
        mime = "video/mp4" if ext in ("mp4", "m4a") else "video/webm"
    else:
        mime = {"m4a": "audio/mp4", "mp4": "audio/mp4", "ogg": "audio/ogg", "mp3": "audio/mpeg", "wav": "audio/wav"}.get(ext, "audio/webm")
    return Response(get_file(a["audio_path"]), media_type=mime)


def _finish(sid: str):
    try:
        deadline = time.time() + 240
        while time.time() < deadline:
            pending = q1("select count(*) as n from answers where session_id=%s and feedback is null", [sid])["n"]
            if pending == 0:
                break
            time.sleep(3)
        s = q1("select * from sessions where id=%s", [sid])
        answers = q("select * from answers where session_id=%s order by idx", [sid])
        lang = s["language"]
        role = s["context"].get("role", "")

        # voice + calibrated scores over all answers
        audio = ai.session_audio([get_file(a["audio_path"]) for a in answers if a.get("audio_path") and a.get("transcript")])
        voice, calibrated, y_dur = {"error": "No recorded answers"}, None, 0
        texts = [a["transcript"] for a in answers if a.get("transcript")]
        if audio:
            y, sr, utts = audio
            y_dur = len(y) / sr
            for u, t in zip(utts, texts):
                u["text"] = t
                u["prosodic_features"] = pi.extract_prosodic_features(y, sr, u["start"], u["end"])
            voice = pi.analyze_interviewee_voice(y, sr, utts)
            try:
                calibrated = cal.predict(cal.extract_features(y, sr, utts, texts), lang)
            except Exception:
                logger.exception("Calibrated scoring failed")

        scored = [a["score"] for a in answers if a.get("score") is not None]
        content = round(sum(scored) / len(scored) * 10, 1) if scored else None
        delivery = None
        if calibrated:
            pick = [t["percentile"] for t in calibrated["traits"] if t["trait"] in ("Overall", "EngagingTone", "Excited", "NoFillers", "Calm")]
            delivery = round(sum(pick) / len(pick), 1) if pick else None
        if delivery is None and "error" not in voice:
            delivery = pi.calculate_acceptance_probability(voice, None)
        overall = round(0.65 * content + 0.35 * delivery, 1) if content is not None and delivery is not None else (content or delivery)

        camera = insights.camera_summary(answers)
        integ = insights.integrity(answers, camera, bool(s["context"].get("require_camera")))
        rubric = {}
        for k in ("clarity", "example_quality", "structure", "outcome"):
            vals = [(a.get("feedback") or {}).get("rubric", {}).get(k) for a in answers]
            vals = [v for v in vals if isinstance(v, (int, float))]
            rubric[k] = round(sum(vals) / len(vals), 1) if vals else None
        summary = ai.summarize_session(role, s["level"] or "junior", lang, answers, voice, calibrated, s["mode"] == "job",
                                       camera) or {}
        report = {"overall": overall, "content_score": content, "delivery_score": delivery, "calibrated": calibrated,
                  "voice": voice, "summary": summary, "duration_s": round(y_dur, 1), "camera": camera,
                  "integrity": integ, "rubric": rubric}

        # PDF (reuses the interview report layout)
        pdf_path = None
        try:
            pdf_path = _build_pdf(sid, s, answers, report)
        except Exception:
            logger.exception("PDF build failed")
        q("update sessions set status='completed', overall_score=%s, report=%s, pdf_path=%s, completed_at=now() where id=%s",
          [overall, report, pdf_path, sid])
    except Exception as e:
        logger.exception("Finishing session failed")
        q("update sessions set status='failed', error=%s where id=%s", [str(e)[:500], sid])


PDF_TXT = {
    "en": {"cam": "Camera analysis", "cam_note": "Computed on the candidate's device; facial expressions are context, not a measure of ability.",
           "metric": "Measure", "value": "Value", "eye": "Looking at the camera", "face": "Face in frame", "smile": "Smiling",
           "emo": "Facial expressions (share of the interview)", "emotion": "Expression", "share": "Share",
           "integ": "Interview integrity", "integ_note": "Automatic flags for human review, not proof of misconduct.",
           "iscore": "Integrity score", "risk": "Review priority", "flag": "Flag", "count": "Times",
           "soft": "Soft skills", "skill": "Skill", "score": "Score", "evidence": "Evidence",
           "rubric": "Answer quality (average of all answers)", "nonverbal": "Non-verbal behaviour",
           "low": "Low", "medium": "Medium", "high": "High", "none": "No flags were raised."},
    "ar": {"cam": "تحليل الكاميرا", "cam_note": "محسوبة على جهاز المرشح؛ تعابير الوجه سياق وليست مقياساً للكفاءة.",
           "metric": "المقياس", "value": "القيمة", "eye": "النظر إلى الكاميرا", "face": "ظهور الوجه", "smile": "الابتسام",
           "emo": "تعابير الوجه (نسبتها من المقابلة)", "emotion": "التعبير", "share": "النسبة",
           "integ": "نزاهة المقابلة", "integ_note": "تنبيهات آلية للمراجعة البشرية، وليست دليلاً على الغش.",
           "iscore": "درجة النزاهة", "risk": "أولوية المراجعة", "flag": "التنبيه", "count": "عدد المرات",
           "soft": "المهارات الشخصية", "skill": "المهارة", "score": "الدرجة", "evidence": "الدليل",
           "rubric": "جودة الإجابات (متوسط كل الإجابات)", "nonverbal": "السلوك غير اللفظي",
           "low": "منخفضة", "medium": "متوسطة", "high": "مرتفعة", "none": "لم تظهر أي تنبيهات."},
}
EMO_TXT = {"en": {"neutral": "Neutral", "happy": "Happy", "surprised": "Surprised", "sad": "Sad", "angry": "Angry",
                  "fearful": "Fearful", "disgusted": "Disgusted"},
           "ar": {"neutral": "محايد", "happy": "سعيد", "surprised": "مندهش", "sad": "حزين", "angry": "غاضب",
                  "fearful": "خائف", "disgusted": "مشمئز"}}
FLAG_TXT = {"en": {"multiple_faces": "More than one person in view", "second_voice": "Another voice in the answer",
                   "voice_without_lips": "Voice heard while lips were still", "tab_hidden": "Left the interview tab",
                   "reading_pattern": "Eye movement like reading", "looking_away": "Looked away for a while",
                   "no_face": "Face left the camera", "fullscreen_exit": "Exited full screen"},
            "ar": {"multiple_faces": "أكثر من شخص أمام الكاميرا", "second_voice": "صوت شخص آخر في الإجابة",
                   "voice_without_lips": "صوت مسموع والشفاه لا تتحرك", "tab_hidden": "مغادرة صفحة المقابلة",
                   "reading_pattern": "حركة عين تشبه القراءة", "looking_away": "النظر بعيداً لفترة",
                   "no_face": "خروج الوجه من الكاميرا", "fullscreen_exit": "الخروج من ملء الشاشة"}}
SOFT_TXT = {"en": {"communication": "Communication", "teamwork": "Teamwork", "conflict_resolution": "Conflict resolution",
                   "time_management": "Time management", "adaptability": "Adaptability", "leadership": "Leadership",
                   "problem_solving": "Problem solving", "emotional_intelligence": "Emotional intelligence",
                   "clarity": "Clarity", "example_quality": "Example quality", "structure": "Structure", "outcome": "Outcome"},
            "ar": {"communication": "التواصل", "teamwork": "العمل الجماعي", "conflict_resolution": "حل الخلافات",
                   "time_management": "إدارة الوقت", "adaptability": "التكيّف", "leadership": "القيادة",
                   "problem_solving": "حل المشكلات", "emotional_intelligence": "الذكاء العاطفي",
                   "clarity": "الوضوح", "example_quality": "جودة الأمثلة", "structure": "التنظيم", "outcome": "النتيجة"}}


def _pdf_sections(report: Dict, lang: str, for_recruiter: bool) -> List[Dict]:
    L, E, F, S = PDF_TXT[lang], EMO_TXT[lang], FLAG_TXT[lang], SOFT_TXT[lang]
    out = []
    rub = report.get("rubric") or {}
    if any(v is not None for v in rub.values()):
        out.append({"title": L["rubric"], "header": [L["metric"], L["score"]], "widths": [0.6, 0.4],
                    "rows": [[S[k], f"{v}/10"] for k, v in rub.items() if v is not None]})
    soft = (report.get("summary") or {}).get("soft_skills") or []
    if soft:
        out.append({"title": L["soft"], "header": [L["skill"], L["score"], L["evidence"]], "widths": [0.25, 0.12, 0.63],
                    "rows": [[S.get(x["skill"], x["skill"]), f"{x['score']}/10", x.get("comment", "")] for x in soft]})
    cam = report.get("camera")
    if cam:
        rows = [[L["eye"], f"{round(100 * (cam.get('eye_contact') or 0))}%"], [L["face"], f"{round(100 * (cam.get('face_visible') or 0))}%"],
                [L["smile"], f"{round(100 * (cam.get('smile') or 0))}%"]]
        out.append({"title": L["cam"], "note": L["cam_note"], "header": [L["metric"], L["value"]], "widths": [0.6, 0.4], "rows": rows})
        if cam.get("emotions"):
            em = sorted(cam["emotions"].items(), key=lambda kv: -kv[1])
            out.append({"title": L["emo"], "header": [L["emotion"], L["share"]], "widths": [0.6, 0.4],
                        "rows": [[E.get(k, k), f"{round(100 * v)}%"] for k, v in em if v >= 0.01]})
        nv = (report.get("summary") or {}).get("nonverbal")
        if nv:
            out.append({"title": L["nonverbal"], "bullets": [nv]})
    integ = report.get("integrity")
    if integ and (for_recruiter or integ.get("counts")):
        rows = [[L["iscore"], f"{integ['score']}/100"], [L["risk"], L[integ["level"]]]]
        out.append({"title": L["integ"], "note": L["integ_note"], "header": [L["metric"], L["value"]], "widths": [0.6, 0.4], "rows": rows})
        if integ.get("counts"):
            out.append({"title": "", "header": [L["flag"], L["count"]], "widths": [0.7, 0.3],
                        "rows": [[F.get(k, k), n] for k, n in sorted(integ["counts"].items(), key=lambda kv: -kv[1])]})
        else:
            out.append({"title": "", "bullets": [L["none"]]})
    return out


def _build_pdf(sid: str, s: Dict, answers: List[Dict], report: Dict) -> str:
    lang = s["language"]
    summ = report["summary"] or {}
    transcript, qa, t = [], [], 0
    for i, a in enumerate(answers):
        dur = int((a.get("duration_s") or 0) * 1000)
        transcript.append({"role": "Interviewer", "start": t, "end": t + 4000, "text": a["question"]})
        transcript.append({"role": "Interviewee", "start": t + 4000, "end": t + 4000 + dur, "text": a.get("transcript") or ""})
        fb = a.get("feedback") or {}
        qa.append({"index": i + 1, "question": a["question"], "answer": a.get("transcript") or "(no answer)",
                   "score": a.get("score"), "what_went_well": " ".join(fb.get("strengths", [])),
                   "what_to_improve": " ".join(fb.get("improvements", [])), "improved_answer": fb.get("improved_answer", ""),
                   "answer_start": t + 4000})
        t += 4000 + dur + 1000
    voice = report["voice"]
    analysis = {
        "user_id": (q1("select coalesce(full_name, email) as n from profiles where id=%s", [s["user_id"]]) or {}).get("n") or "candidate",
        "generated_at": time.strftime("%Y-%m-%d"), "language": lang,
        "interview": {"duration_seconds": report.get("duration_s") or 0, "speaker_turns": len(transcript), "language": "en"},
        "speakers": {"A": {"speaker_name": "EvalBot", "role": "Interviewer"}, "B": {"speaker_name": "Candidate", "role": "Interviewee"}},
        "voice_analysis": voice, "transcript": transcript, "qa_pairs": qa,
        "evaluation": {"content_score": report.get("content_score"), "executive_summary": summ.get("executive_summary", []),
                       "communication": [], "communication_tip": "", "strengths": summ.get("strengths", []),
                       "weaknesses": summ.get("weaknesses", []), "role_fit": summ.get("role_fit", []),
                       "recommendations": summ.get("recommendations", []), "next_steps": summ.get("next_steps", []),
                       "ai_generated": bool(summ)},
        "suitability_score": report.get("overall") or 0,
        "verdict": summ.get("headline") or pi.verdict_for(report.get("overall") or 0, lang),
        "calibrated": report.get("calibrated"),
        "extra_sections": _pdf_sections(report, lang, s["mode"] == "job"),
    }
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        out = tmp.name
    try:
        pi.create_pdf_report(analysis, out, lang)
        with open(out, "rb") as f:
            return put_file(f"sessions/{sid}/report.pdf", f.read(), "application/pdf")
    finally:
        os.remove(out)


@router.post("/sessions/{sid}/finish")
def finish(sid: str, user: Dict = Depends(current_user)):
    s = _session(sid, user, owner_only=True)
    if s["status"] == "in_progress":
        if not q1("select 1 from answers where session_id=%s", [sid]):
            raise HTTPException(400, "Answer at least one question first")
        q("update sessions set status='processing' where id=%s", [sid])
        _workers.submit(_finish, sid)
    return {"ok": True}


@router.get("/sessions/{sid}/pdf")
def session_pdf(sid: str, user: Dict = Depends(current_user)):
    s = _session(sid, user)
    if not s.get("pdf_path"):
        raise HTTPException(404, "The report is not ready")
    return Response(get_file(s["pdf_path"]), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="evalbot-report-{sid[:8]}.pdf"'})


@router.delete("/sessions/{sid}")
def delete_session(sid: str, user: Dict = Depends(current_user)):
    _session(sid, user, owner_only=True)
    q("delete from sessions where id=%s", [sid])
    return {"ok": True}


@router.get("/stats")
def stats(user: Dict = Depends(current_user)):
    done = q("select id, overall_score, created_at, track, report->'calibrated' as calibrated, report->>'content_score' as content "
             "from sessions where user_id=%s and status='completed' order by created_at", [user["id"]])
    skills = q("select a.feedback->>'skill' as skill, avg(a.score) as avg, count(*) as n from answers a "
               "join sessions s on s.id=a.session_id where s.user_id=%s and a.score is not null and coalesce(a.feedback->>'skill','') <> '' "
               "group by 1 order by n desc limit 8", [user["id"]])
    answered = q1("select count(*) as n, coalesce(sum(duration_s),0) as secs from answers a join sessions s on s.id=a.session_id "
                  "where s.user_id=%s", [user["id"]])
    return {"interviews": len(done), "answers": answered["n"], "speaking_minutes": round(float(answered["secs"]) / 60, 1),
            "average": round(sum(d["overall_score"] or 0 for d in done) / len(done), 1) if done else None,
            "best": max((d["overall_score"] or 0 for d in done), default=None),
            "trend": [{"date": d["created_at"].strftime("%Y-%m-%d"), "score": d["overall_score"], "track": d["track"]} for d in done[-20:]],
            "skills": [{"skill": r["skill"], "avg": round(float(r["avg"]), 1), "n": r["n"]} for r in skills]}


# --------------------------------------------------------------------------------------
# Recruiters: jobs, candidates, reviews
# --------------------------------------------------------------------------------------
class JobIn(BaseModel):
    title: str = Field(min_length=2, max_length=140)
    track: str = "general"
    level: str = "junior"
    description: str = ""
    questions: List[Dict] = Field(min_length=1, max_length=15)
    answer_seconds: int = Field(120, ge=30, le=600)
    status: str = "open"
    location: Optional[str] = Field(None, max_length=120)
    work_mode: str = "onsite"
    employment_type: str = "full_time"
    salary: Optional[str] = Field(None, max_length=80)
    skills: List[str] = Field(default_factory=list, max_length=20)
    deadline: Optional[date] = None
    visibility: str = "public"
    require_camera: bool = False
    record_video: bool = False

    def clean(self) -> Dict:
        d = self.model_dump()
        d["status"] = d["status"] if d["status"] in ("draft", "open", "closed") else "open"
        d["work_mode"] = d["work_mode"] if d["work_mode"] in ("onsite", "remote", "hybrid") else "onsite"
        d["employment_type"] = d["employment_type"] if d["employment_type"] in ("full_time", "part_time", "internship", "contract") else "full_time"
        d["visibility"] = "link" if d["visibility"] == "link" else "public"
        d["skills"] = [x.strip()[:40] for x in d["skills"] if x and x.strip()][:20]
        d["questions"] = _clean_questions(d["questions"])
        d["require_camera"] = bool(d["require_camera"] or d["record_video"])  # a video interview needs the camera
        return d


JOB_FIELDS = ["title", "track", "level", "description", "questions", "answer_seconds", "status", "location", "work_mode",
              "employment_type", "salary", "skills", "deadline", "visibility", "require_camera", "record_video"]


def _clean_questions(qs: List[Dict]) -> List[Dict]:
    return [{"text": x["text"].strip()[:500], "kind": x.get("kind", "custom"), "skill": x.get("skill", ""),
             "rubric": x.get("rubric", "")} for x in qs if x.get("text", "").strip()]


@router.get("/jobs")
def list_jobs(user: Dict = Depends(recruiter)):
    return q("select j.*, (select count(*) from sessions s where s.job_id=j.id) as applicants, "
             "(select count(*) from sessions s where s.job_id=j.id and s.status='completed') as completed "
             "from jobs j where j.company_id=%s order by j.created_at desc", [user["company_id"]])


@router.post("/jobs")
def create_job(body: JobIn, user: Dict = Depends(recruiter)):
    d = body.clean()
    cols = ", ".join(JOB_FIELDS)
    vals = ", ".join(f"%({k})s" for k in JOB_FIELDS)
    return q1(f"insert into jobs (company_id, created_by, {cols}) values (%(company_id)s, %(created_by)s, {vals}) returning *",
              {**d, "company_id": user["company_id"], "created_by": user["id"]})


def _job(jid: str, user: Dict) -> Dict:
    j = q1("select * from jobs where id=%s and company_id=%s", [jid, user["company_id"]])
    if not j:
        raise HTTPException(404, "Job not found")
    return j


@router.get("/jobs/{jid}")
def get_job(jid: str, user: Dict = Depends(recruiter)):
    return _job(jid, user)


@router.put("/jobs/{jid}")
def update_job(jid: str, body: JobIn, user: Dict = Depends(recruiter)):
    _job(jid, user)
    d = body.clean()
    sets = ", ".join(f"{k} = %({k})s" for k in JOB_FIELDS)
    return q1(f"update jobs set {sets} where id = %(jid)s returning *", {**d, "jid": jid})


@router.delete("/jobs/{jid}")
def delete_job(jid: str, user: Dict = Depends(recruiter)):
    """Delete a job together with its interviews (only possible while nobody has been hired for it)."""
    _job(jid, user)
    if q1("select 1 from sessions s join reviews r on r.session_id = s.id where s.job_id = %s and r.status = 'hired'", [jid]):
        raise HTTPException(400, "Someone was hired for this job. Close it instead of deleting it.")
    q("delete from sessions where job_id = %s", [jid])
    q("delete from jobs where id = %s", [jid])
    return {"ok": True}


@router.get("/jobs/{jid}/candidates")
def job_candidates(jid: str, user: Dict = Depends(recruiter)):
    _job(jid, user)
    rows = q("select s.id, s.status, s.overall_score, s.created_at, s.completed_at, "
             "s.report->>'content_score' as content_score, s.report->>'delivery_score' as delivery_score, "
             "s.report->'summary'->>'hiring_signal' as hiring_signal, s.report->'summary'->>'headline' as headline, "
             "(s.report->'integrity'->>'score')::int as integrity_score, s.report->'integrity'->>'level' as integrity_level, "
             "p.full_name, p.email, p.cv, p.cv_text, coalesce(r.status, 'new') as review_status, r.rating, r.notes "
             "from sessions s join profiles p on p.id=s.user_id left join reviews r on r.session_id=s.id "
             "where s.job_id=%s order by s.overall_score desc nulls last, s.created_at", [jid])
    job_skills = (q1("select skills from jobs where id=%s", [jid]) or {}).get("skills") or []
    for r in rows:
        m = insights.skill_match(job_skills, r.pop("cv"), r.pop("cv_text") or "")
        r["cv_match"] = m["percent"] if m else None
    return rows


class ReviewIn(BaseModel):
    status: str = "new"
    rating: Optional[int] = Field(None, ge=1, le=5)
    notes: Optional[str] = None


@router.put("/reviews/{sid}")
def review(sid: str, body: ReviewIn, user: Dict = Depends(recruiter)):
    s = _session(sid, user)
    if not s.get("job_id"):
        raise HTTPException(400, "Only job interviews can be reviewed")
    if body.status not in ("new", "shortlisted", "rejected", "hired"):
        raise HTTPException(400, "Invalid status")
    return q1("insert into reviews (session_id, reviewer_id, status, rating, notes) values (%s,%s,%s,%s,%s) "
              "on conflict (session_id) do update set status=excluded.status, rating=excluded.rating, notes=excluded.notes, "
              "reviewer_id=excluded.reviewer_id, updated_at=now() returning *",
              [sid, user["id"], body.status, body.rating, body.notes])


# --------------------------------------------------------------------------------------
# Recruiters: analytics
# --------------------------------------------------------------------------------------
def _f(v, nd=1):
    return None if v is None else round(float(v), nd)


def _analytics(company_id: str, job_id: Optional[str], lang: str) -> Dict:
    """Hiring analytics for a whole company, or for one job when job_id is given."""
    F = "j.company_id = %(c)s" + (" and j.id = %(j)s" if job_id else "")
    p = {"c": company_id, "j": job_id}
    jobs = q1(f"select count(*) as jobs, count(*) filter (where {ACCEPTING}) as open_jobs, coalesce(sum(views), 0) as views "
              f"from jobs j where {F}", p)
    t = q1(f"select count(*) as applicants, count(distinct s.user_id) as people, "
           f"count(*) filter (where s.status = 'completed') as completed, "
           f"count(*) filter (where s.status in ('in_progress', 'processing')) as in_progress, "
           f"avg(s.overall_score) filter (where s.status = 'completed') as avg_score, "
           f"percentile_cont(0.5) within group (order by s.overall_score) filter (where s.status = 'completed') as median_score, "
           f"max(s.overall_score) as best_score, "
           f"count(*) filter (where r.status in ('shortlisted', 'hired')) as shortlisted, "
           f"count(*) filter (where r.status = 'hired') as hired, count(*) filter (where r.status = 'rejected') as rejected, "
           f"count(*) filter (where s.status = 'completed' and coalesce(r.status, 'new') = 'new') as to_review, "
           f"count(*) filter (where s.report->'integrity'->>'level' in ('medium', 'high')) as flagged, "
           f"percentile_cont(0.5) within group (order by extract(epoch from (s.completed_at - s.created_at)) / 60) "
           f"filter (where s.status = 'completed' and s.completed_at - s.created_at between interval '0' and interval '1 day') as avg_minutes "
           f"from sessions s join jobs j on j.id = s.job_id left join reviews r on r.session_id = s.id where {F}", p)

    # applications per day, last 30 days
    since = date.today() - timedelta(days=29)
    days = {r["d"]: r for r in q(f"select s.created_at::date as d, count(*) as n, count(*) filter (where s.status = 'completed') as c "
                                 f"from sessions s join jobs j on j.id = s.job_id where {F} and s.created_at >= %(since)s "
                                 f"group by 1", {**p, "since": since})}
    timeline = [{"date": (since + timedelta(days=i)).isoformat(),
                 "applicants": days.get(since + timedelta(days=i), {}).get("n", 0),
                 "completed": days.get(since + timedelta(days=i), {}).get("c", 0)} for i in range(30)]

    done = q(f"select s.overall_score as score, s.report->'summary'->>'hiring_signal' as signal, "
             f"s.report->'calibrated'->'traits' as traits from sessions s join jobs j on j.id = s.job_id "
             f"where {F} and s.status = 'completed'", p)
    buckets = [{"range": f"{b}-{b + 9 if b < 90 else 100}", "count": 0} for b in range(0, 100, 10)]
    signals = {"strong_yes": 0, "yes": 0, "maybe": 0, "no": 0}
    trait_sum: Dict[str, List[float]] = {}
    for d in done:
        if d["score"] is not None:
            buckets[min(int(d["score"] // 10), 9)]["count"] += 1
        if d["signal"] in signals:
            signals[d["signal"]] += 1
        for tr in d["traits"] or []:
            trait_sum.setdefault(tr["trait"], []).append(tr["percentile"])
    labels = cal.TRAIT_LABELS.get(lang, cal.TRAIT_LABELS["en"])
    traits = sorted([{"trait": k, "label": labels.get(k, k), "avg_percentile": round(sum(v) / len(v)), "n": len(v)}
                     for k, v in trait_sum.items()], key=lambda x: -x["avg_percentile"])

    skills = q(f"select a.feedback->>'skill' as skill, round(avg(a.score)::numeric, 1) as avg, count(*) as n "
               f"from answers a join sessions s on s.id = a.session_id join jobs j on j.id = s.job_id "
               f"where {F} and a.score is not null and coalesce(a.feedback->>'skill', '') <> '' "
               f"group by 1 order by n desc, avg desc limit 10", p)

    top = q(f"select s.id, s.overall_score, s.completed_at, s.report->>'content_score' as content_score, "
            f"s.report->>'delivery_score' as delivery_score, s.report->'summary'->>'hiring_signal' as hiring_signal, "
            f"s.report->'summary'->>'headline' as headline, p.full_name, p.email, p.headline as candidate_headline, "
            f"s.report->'integrity'->>'level' as integrity_level, "
            f"j.id as job_id, j.title as job_title, coalesce(r.status, 'new') as review_status, r.rating "
            f"from sessions s join jobs j on j.id = s.job_id join profiles p on p.id = s.user_id "
            f"left join reviews r on r.session_id = s.id where {F} and s.status = 'completed' "
            f"order by s.overall_score desc nulls last limit 10", p)

    per_job = [] if job_id else q(
        f"select j.id, j.title, j.status, j.views, j.created_at, j.deadline, {ACCEPTING} as accepting, "
        f"count(s.id) as applicants, count(s.id) filter (where s.status = 'completed') as completed, "
        f"round(avg(s.overall_score) filter (where s.status = 'completed')::numeric, 1) as avg_score, "
        f"max(s.overall_score) as best_score, count(r.session_id) filter (where r.status in ('shortlisted', 'hired')) as shortlisted, "
        f"count(r.session_id) filter (where r.status = 'hired') as hired "
        f"from jobs j left join sessions s on s.job_id = j.id left join reviews r on r.session_id = s.id "
        f"where {F} group by j.id order by j.created_at desc", p)

    applicants = t["applicants"] or 0
    views = max(int(jobs["views"]), applicants)  # people who apply from a shared link may never load the job page
    return {
        "totals": {"jobs": jobs["jobs"], "open_jobs": jobs["open_jobs"], "views": views,
                   "applicants": applicants, "people": t["people"], "completed": t["completed"],
                   "in_progress": t["in_progress"], "shortlisted": t["shortlisted"], "hired": t["hired"],
                   "rejected": t["rejected"], "to_review": t["to_review"], "flagged": t["flagged"],
                   "avg_score": _f(t["avg_score"]), "median_score": _f(t["median_score"]), "best_score": _f(t["best_score"]),
                   "completion_rate": round(100 * t["completed"] / applicants) if applicants else None,
                   "avg_minutes": _f(t["avg_minutes"])},
        "funnel": [{"stage": "views", "count": views}, {"stage": "started", "count": applicants},
                   {"stage": "completed", "count": t["completed"]}, {"stage": "shortlisted", "count": t["shortlisted"]},
                   {"stage": "hired", "count": t["hired"]}],
        "timeline": timeline, "distribution": buckets, "signals": signals, "traits": traits,
        "skills": [{"skill": r["skill"], "avg": float(r["avg"]), "n": r["n"]} for r in skills],
        "top": top, "jobs": per_job,
    }


@router.get("/company/stats")
def company_stats(lang: str = "en", user: Dict = Depends(recruiter)):
    return _analytics(user["company_id"], None, "ar" if lang == "ar" else "en")


@router.get("/jobs/{jid}/stats")
def job_stats(jid: str, lang: str = "en", user: Dict = Depends(recruiter)):
    _job(jid, user)
    return _analytics(user["company_id"], jid, "ar" if lang == "ar" else "en")


@router.get("/jobs/{jid}/candidates.csv")
def job_candidates_csv(jid: str, user: Dict = Depends(recruiter)):
    j = _job(jid, user)
    rows = job_candidates(jid, user)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["rank", "name", "email", "interview_status", "overall_score", "content_score", "delivery_score",
                "evalbot_signal", "integrity_score", "cv_skill_match_pct", "decision", "rating", "notes", "applied_at", "report_url"])
    for i, r in enumerate(rows, 1):
        w.writerow([i, r["full_name"] or "", r["email"] or "", r["status"], _f(r["overall_score"]) or "",
                    r["content_score"] or "", r["delivery_score"] or "", r["hiring_signal"] or "",
                    r["integrity_score"] if r["integrity_score"] is not None else "", r["cv_match"] if r["cv_match"] is not None else "",
                    r["review_status"],
                    r["rating"] or "", (r["notes"] or "").replace("\n", " "), r["created_at"].strftime("%Y-%m-%d %H:%M"),
                    f"/app/report/{r['id']}"])
    name = "".join(ch if ch.isalnum() else "-" for ch in j["title"])[:40] or "job"
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="evalbot-{name}-candidates.csv"'})
