"""EvalBot platform API: candidates, mock interviews, companies, jobs and reviews."""
import json
import logging
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

import calibration as cal
import process_interview as pi
from . import ai
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


@router.get("/public/jobs/{token}")
def public_job(token: str):
    j = q1("select j.id, j.title, j.track, j.level, j.description, j.answer_seconds, j.status, "
           "jsonb_array_length(j.questions) as question_count, c.name as company, c.website "
           "from jobs j join companies c on c.id = j.company_id where j.share_token = %s", [token])
    if not j:
        raise HTTPException(404, "This job link is not valid")
    return j


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
    return {**user, "company": company}


@router.patch("/me")
def update_me(body: ProfileIn, user: Dict = Depends(current_user)):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if "role" in fields and fields["role"] not in ("candidate", "recruiter"):
        raise HTTPException(400, "Invalid role")
    if fields:
        sets = ", ".join(f"{k} = %({k})s" for k in fields)
        q(f"update profiles set {sets} where id = %(id)s", {**fields, "id": user["id"]})
    return me(q1("select * from profiles where id = %s", [user["id"]]))


class CompanyIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    website: Optional[str] = None
    about: Optional[str] = None


@router.post("/companies")
def create_company(body: CompanyIn, user: Dict = Depends(current_user)):
    if user.get("company_id"):
        c = q1("update companies set name=%s, website=%s, about=%s where id=%s returning *",
               [body.name, body.website, body.about, user["company_id"]])
    else:
        c = q1("insert into companies (name, website, about, created_by) values (%s, %s, %s, %s) returning *",
               [body.name, body.website, body.about, user["id"]])
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
    plan = body.questions or ai.generate_questions(body.track, body.level, body.interview_type, body.count,
                                                   body.custom_role, body.cv_text, body.jd_text)
    plan = [{"text": p["text"].strip()[:500], "kind": p.get("kind", "custom"), "skill": p.get("skill", ""),
             "rubric": p.get("rubric", "")} for p in plan if p.get("text", "").strip()]
    ctx = {"plan": plan, "role": ai.role_name(body.track, body.custom_role), "answer_seconds": 120,
           "has_cv": bool(body.cv_text.strip()), "has_jd": bool(body.jd_text.strip()), "followups": 0}
    s = q1("insert into sessions (user_id, mode, track, level, interview_type, language, context) "
           "values (%s, 'mock', %s, %s, %s, %s, %s) returning *",
           [user["id"], body.track, body.level, body.interview_type, body.language if body.language in ("en", "ar") else "en", ctx])
    return s


class ApplyIn(BaseModel):
    language: str = "en"


@router.post("/jobs/apply/{token}")
def apply_job(token: str, body: ApplyIn, user: Dict = Depends(current_user)):
    j = q1("select * from jobs where share_token = %s", [token])
    if not j or j["status"] != "open":
        raise HTTPException(404, "This job is not accepting interviews")
    existing = q1("select * from sessions where job_id=%s and user_id=%s order by created_at desc limit 1", [j["id"], user["id"]])
    if existing:
        return existing
    plan = [{"text": x["text"], "kind": x.get("kind", "custom"), "skill": x.get("skill", ""),
             "rubric": x.get("rubric", "")} for x in j["questions"]]
    ctx = {"plan": plan, "role": j["title"], "answer_seconds": j["answer_seconds"], "followups": 0,
           "job_title": j["title"], "no_followups": True}
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


@router.get("/sessions/{sid}")
def get_session(sid: str, user: Dict = Depends(current_user)):
    s = _session(sid, user)
    s["answers"] = q("select id, idx, question, kind, is_followup, duration_s, transcript, voice, presence, feedback, "
                     "score, audio_path is not null as has_audio, created_at from answers where session_id=%s order by idx", [sid])
    if s.get("job_id"):
        s["job"] = q1("select j.title, c.name as company from jobs j join companies c on c.id=j.company_id where j.id=%s", [s["job_id"]])
    if s["user_id"] != user["id"]:
        s["candidate"] = q1("select full_name, email, headline from profiles where id=%s", [s["user_id"]])
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
    path = put_file(f"sessions/{sid}/answer_{idx}{suffix}", blob, file.content_type or "audio/webm")
    try:
        pres = json.loads(presence) if presence else None
    except ValueError:
        pres = None
    q("insert into answers (session_id, idx, question, kind, is_followup, audio_path, presence) values (%s,%s,%s,%s,%s,%s,%s) "
      "on conflict (session_id, idx) do update set audio_path=excluded.audio_path, presence=excluded.presence, "
      "transcript=null, feedback=null, score=null",
      [sid, idx, plan[idx]["text"], plan[idx].get("kind"), bool(plan[idx].get("is_followup")), path, pres])
    _workers.submit(_process_answer, sid, idx, blob, suffix)
    return {"ok": True, "idx": idx}


@router.get("/sessions/{sid}/answers/{idx}/audio")
def answer_audio(sid: str, idx: int, user: Dict = Depends(current_user)):
    _session(sid, user)
    a = q1("select audio_path from answers where session_id=%s and idx=%s", [sid, idx])
    if not a or not a["audio_path"]:
        raise HTTPException(404)
    ext = os.path.splitext(a["audio_path"])[1].lstrip(".") or "webm"
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

        summary = ai.summarize_session(role, s["level"] or "junior", lang, answers, voice, calibrated, s["mode"] == "job") or {}
        report = {"overall": overall, "content_score": content, "delivery_score": delivery, "calibrated": calibrated,
                  "voice": voice, "summary": summary, "duration_s": round(y_dur, 1)}

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
    return q1("insert into jobs (company_id, created_by, title, track, level, description, questions, answer_seconds, status) "
              "values (%s,%s,%s,%s,%s,%s,%s,%s,%s) returning *",
              [user["company_id"], user["id"], body.title, body.track, body.level, body.description,
               _clean_questions(body.questions), body.answer_seconds, body.status if body.status in ("draft", "open", "closed") else "open"])


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
    return q1("update jobs set title=%s, track=%s, level=%s, description=%s, questions=%s, answer_seconds=%s, status=%s "
              "where id=%s returning *", [body.title, body.track, body.level, body.description, _clean_questions(body.questions),
                                         body.answer_seconds, body.status, jid])


@router.get("/jobs/{jid}/candidates")
def job_candidates(jid: str, user: Dict = Depends(recruiter)):
    _job(jid, user)
    return q("select s.id, s.status, s.overall_score, s.created_at, s.completed_at, "
             "s.report->>'content_score' as content_score, s.report->>'delivery_score' as delivery_score, "
             "s.report->'summary'->>'hiring_signal' as hiring_signal, s.report->'summary'->>'headline' as headline, "
             "p.full_name, p.email, coalesce(r.status, 'new') as review_status, r.rating, r.notes "
             "from sessions s join profiles p on p.id=s.user_id left join reviews r on r.session_id=s.id "
             "where s.job_id=%s order by s.overall_score desc nulls last, s.created_at", [jid])


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
