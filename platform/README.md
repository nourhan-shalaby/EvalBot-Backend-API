---
title: EvalBot - AI Interview Practice and Hiring
emoji: 🎤
colorFrom: green
colorTo: yellow
sdk: docker
app_port: 7860
pinned: true
short_description: AI mock interviews and hiring for every career track
---

# EvalBot

**Practice the interview before the interview.** EvalBot runs spoken mock interviews for 30 career tracks, listens to how you answer, and tells you exactly what to fix. Companies use the same engine to run one-link hiring interviews and get a ranked shortlist with reasons.

Its delivery scores are **calibrated on human judgment**: trained on 138 real mock interviews, each rated by nine people (MIT Interview Dataset).

English and Arabic throughout, including right-to-left PDF reports.

---

## What it does

### For job seekers
- **Any track, any level.** Data, backend, frontend, mobile, AI/ML, DevOps, security, design, product, marketing, sales, HR, finance and more, from internship to lead. Paste a job description or your CV and the questions are tailored to them.
- **A real conversation.** Questions are read aloud, you answer out loud, and EvalBot asks follow-up questions when an answer leaves something open.
- **Feedback you can act on.** Each answer gets a 0-10 score, what went well, what to improve, a delivery tip, and a stronger version of your answer built from your own facts.
- **Human-calibrated delivery scores** for 13 traits (overall impression, hiring recommendation, enthusiasm, engaging tone, structure, filler words, calmness and more), shown as your position among the 138 rated interviews.
- **Camera analysis, on the device:** facial expressions in 7 classes (neutral, happy, surprised, sad, angry, fearful, disgusted) with confidence, smoothed over time and shown as a timeline in 5-second segments; eye contact from iris position and head pose; smiling and face-in-frame. Only numbers leave the browser unless a video interview was requested.
- **Soft skills and answer quality:** every answer is scored for clarity, example quality, structure and outcome, and the interview is scored on the eight soft skills it gives evidence for (communication, teamwork, conflict resolution, time management, adaptability, leadership, problem solving, emotional intelligence).
- **CV profile:** upload a PDF or Word CV once; skills, experience, education, projects, certifications and languages are extracted and used to tailor practice questions.
- **Progress tracking:** score history, skill breakdown, and a learning plan for your track.

- **A job board:** browse open roles from companies on the platform (search, track, level, on-site/remote/hybrid, job type), apply with one spoken interview, and follow each application's status.

### For hiring teams
- Separate **company accounts** with their own workspace: company profile, job posts and analytics. Company accounts can't apply to jobs, and job seekers can't see company pages.
- Post a job with location, work mode, job type, salary, skills and a deadline, listed **publicly on the job board** or **private (link only)**.
- Create the interview with your own questions or AI-suggested ones and share **one link**.
- A **hiring dashboard**: applicants, completion rate, average and median score, a 30-day applications chart, the hiring funnel (viewed → started → completed → shortlisted → hired), score distribution, EvalBot hiring signals, the **top 10 candidates** across all jobs, the candidate pool's delivery profile and skill averages, and a per-job table. Each job has the same analytics plus search, a minimum-score filter and **CSV export**.
- Every applicant answers the **same questions with the same time limit**, whenever it suits them.
- A **ranked candidate list** with scores, a hiring signal, the written assessment, recordings and transcripts.
- **Monitored and video interviews (optional per job):** a camera-required interview flags moments for review, each with its time: looking away (iris offset over 0.2 or head turned over 15°), face out of frame, more than one person, a voice heard while the lips are still, another voice in the recording, reading-like eye movement, leaving the tab or full screen. These become an explainable **integrity score** with a review priority. Video answers can be recorded for the hiring team to watch.
- **CV match:** the candidate's CV profile next to the interview, with the share of the job's skills it covers.
- Shortlist, reject, rate and add notes. **People make the decision**; EvalBot informs it, and integrity flags are prompts for review, not verdicts.

---

## The science

| Trait | EvalBot (r) | A single human rater (r) |
|---|---|---|
| Few filler words | **0.61** | 0.52 |
| Good use of pauses | **0.55** | 0.15 |
| Structured answers | **0.47** | 0.37 |
| Calmness | **0.42** | 0.34 |
| Enthusiasm | 0.55 | 0.56 |
| Engaging tone | 0.54 | 0.62 |
| Hiring recommendation | 0.46 | 0.50 |
| Overall impression | 0.40 | 0.50 |

*Pearson correlation with the panel's average rating. EvalBot: 10-fold cross-validation grouped by participant, so the model is always tested on people it never saw (each participant was interviewed twice). Human rater: each Mechanical Turk rater's correlation with the average of the other raters.*

How the models were built:
1. The 138 recordings were diarized locally (energy VAD, NVIDIA TitaNet speaker embeddings, agglomerative clustering) to isolate the candidate's speech.
2. The **same feature extractor the app uses at runtime** (`calibration.py`) computed 30 voice and language features per interview: pitch variation, loudness dynamics, pauses, speaking rate, filler-word rate, vocabulary, sentence length, and more.
3. Per-trait Ridge or Extra-Trees models were selected by cross-validation; only traits with r ≥ 0.35 are shown in the app. Inputs are clipped to the training range to avoid extrapolation.

A research benchmark that also used the dataset's facial and PRAAT features reached r = 0.52 for both overall impression and hiring recommendation, and r ≈ 0.70 for enthusiasm, smiling and friendliness. Video features are not used in the deployed model yet.

The dataset itself is **not** included in this repository, as its license does not allow redistribution. Only trained models are shipped.

---

## Architecture

```
Browser (React + TypeScript + Tailwind, EN/AR, dark mode)
  ├─ interview room: speech synthesis, MediaRecorder, live waveform, MediaPipe face metrics
  └─ Supabase Auth (email/password, Google)
        │
FastAPI (this Space, Docker)
  ├─ /api/...      platform API: sessions, answers, reports, jobs, reviews
  ├─ pipeline      AssemblyAI transcription · librosa voice analysis · calibrated trait models
  │                Gemini (structured JSON) for questions, per-answer feedback and summaries
  │                ReportLab PDF (English / right-to-left Arabic)
  └─ /demo         standalone analyzer for a full recorded interview + single-question practice
        │
Supabase Postgres (data) + Supabase Storage or a private HF dataset (recordings, PDFs)
```

### Configuration (Space secrets)

| Secret | Purpose |
|---|---|
| `ASSEMBLYAI_API_KEY` | Speech-to-text and diarization |
| `GEMINI_API_KEY` | Questions, feedback and summaries |
| `DATABASE_URL` | Supabase Postgres connection string (transaction pooler) |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | Authentication (public values) |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-side storage access |
| `PINECONE_API_KEY` | Optional; a built-in vector index is used otherwise |

Large file storage (optional): set the variable `HF_STORAGE_REPO` (a private dataset, e.g. `EvalBot/evalbot-storage`) and the secret `HF_TOKEN` (a fine-grained token with write access to that dataset) to keep recordings and PDFs on Hugging Face instead of Supabase Storage. `/health` reports the active storage backend and database status; a scheduled ping to it keeps the Space and the free Supabase project awake.

Optional: `GEMINI_MODEL` (default `gemini-3.5-flash-lite`, with automatic fallback to other Flash models), `STORAGE_BUCKET`.

### Run locally

```bash
docker build -t evalbot .
docker run -p 7860:7860 --env-file .env evalbot   # open http://localhost:7860
```

For frontend development: `cd frontend && npm install && npm run dev` (proxies `/api` to the backend on port 7870).

---

## Credits

EvalBot began as a graduation project at the Faculty of Computers and Artificial Intelligence, Benha University (2025), and was continued as an open platform by Nourhan Saber.

Dataset: I. Naim, M. I. Tanveer, D. Gildea, M. E. Hoque, *Automated Analysis and Prediction of Job Interview Performance*, IEEE Transactions on Affective Computing. Arabic PDF font: Amiri (SIL Open Font License).
