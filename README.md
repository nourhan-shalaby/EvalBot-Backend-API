# EvalBot — Backend API

**EvalBot** is an AI-powered interview evaluation system: it runs spoken interviews, analyzes the candidate's recorded answers, and produces a detailed feedback report. It serves recruiters (faster, more consistent screening) and job seekers (a virtual interview coach).

This repository holds:
- the **Flask backend API** (root folder) that orchestrates the interview flow and connects the system's services: the mobile app, question generation, text-to-speech, speech-to-text, and answer evaluation
- the **EvalBot platform** ([`platform/`](platform/)): the web app, interview engine and analysis pipeline

> Bachelor's graduation project, Scientific Computing Department, Faculty of Computers and Artificial Intelligence, Benha University (June 2025). Supervised by Dr. Eman Monir.

---

## System architecture

```mermaid
flowchart LR
    APP[Mobile app<br/>Flutter] -->|start interview| API[EvalBot Backend API<br/>Flask]
    API -->|fetch questions| QG[Question generation<br/>RAG + Gemini]
    API -->|question text| TTS[Cartesia.ai<br/>Text-to-Speech]
    TTS -->|question audio| API
    APP -->|recorded answers| API
    API -->|speech-to-text| STT[Whisper<br/>Hugging Face]
    API -->|answer + reference| EV[Evaluation service<br/>NLP scoring]
    EV -->|score, explanation, resources| API
    APP -->|full interview audio| AUD[Audio analysis service<br/>FastAPI · Hugging Face Spaces]
    AUD -->|PDF + JSON report| APP
```

### EvalBot platform ([`platform/`](platform/))

The full EvalBot web platform, deployed on Hugging Face Spaces: accounts, spoken mock interviews for 30 career tracks with follow-up questions, per-answer feedback, delivery scores calibrated on 138 human-rated interviews, one-link hiring interviews with a ranked candidate list, and English/Arabic reports. See [`platform/README.md`](platform/README.md) for the architecture, the science and setup.

**Live:** [huggingface.co/spaces/EvalBot/Audio-EvalBot](https://huggingface.co/spaces/EvalBot/Audio-EvalBot)

---

## API endpoints

### `POST /api/start-interview`

Fetches questions from the question generation service, converts each one to speech with Cartesia.ai, and returns the questions with their audio URLs.

```json
// request
{ "track_id": "1", "difficulty": "beginner", "num_questions": 3 }

// response
{
  "status": "success",
  "interview_data": {
    "total_questions": 3,
    "questions": [
      {
        "id": 1,
        "question_number": 1,
        "question_text": "What is the purpose of a confusion matrix?",
        "audio_url": "/static/audio/question_1749062113462_0.wav",
        "gemini_answer": "...",
        "question_topic": "machine learning",
        "question_classification": "Beginner"
      }
    ]
  }
}
```

### `POST /api/submit-answers`

Takes a list of recorded answers. For each answer it downloads the audio, transcribes it with Whisper, and sends the transcript with the reference answer to the evaluation service.

```json
// request
[
  {
    "question_id": "1",
    "question_text": "What is the purpose of a confusion matrix?",
    "gemini_answer": "...",
    "question_topic": "machine learning",
    "classification": "Beginner",
    "audio_url": "https://.../answer_1.wav"
  }
]

// response
[
  {
    "question_id": "1",
    "status": "success",
    "transcribed_text": "...",
    "evaluation_result": {
      "score": "...",
      "score_explanation": "...",
      "links": ["..."],
      "question_topic": "machine learning",
      "question_classification": "Beginner"
    }
  }
]
```

### `GET /static/<path>`

Serves the generated question audio files.

---

## Running locally

**Requirements:** Python 3.9+

```bash
git clone https://github.com/nourhan-shalaby/EvalBot-Backend-API.git
cd EvalBot-Backend-API

python -m venv venv
source venv/bin/activate        # Windows: .\venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # then fill in your keys and service URLs
python app.py                   # http://localhost:5001
```

The Whisper model downloads on first run. To try the answer flow, run `python test_submit.py` with the API running.

**Production:** the included `Procfile` runs the app with `gunicorn app:app`.

### Environment variables

| Variable | Purpose |
|---|---|
| `CARTESIA_API_KEY` | Cartesia.ai text-to-speech |
| `CARTESIA_TTS_MODEL_ID`, `CARTESIA_TTS_VOICE_ID` | TTS model and voice (defaults provided) |
| `HF_STT_MODEL_NAME` | Whisper model (default `openai/whisper-tiny`) |
| `API_BASE_URL` | Question generation service |
| `EXTERNAL_EVALUATION_API_URL` | Answer evaluation service |
| `PORT`, `FLASK_DEBUG` | Server port (default 5001) and debug mode (default off) |

---

## Tech stack

Python · Flask · FastAPI · Hugging Face Transformers (Whisper) · Cartesia.ai · AssemblyAI · NVIDIA NeMo · Pinecone · librosa · scikit-learn · Gemini API · ReportLab · Docker · Hugging Face Spaces

## Related repositories

- Mobile app (Flutter): [Mohamed-Essam-Mohamed/EVALBOT-APP](https://github.com/Mohamed-Essam-Mohamed/EVALBOT-APP)
- Database: [MHMD-SAYID/GraduationProject](https://github.com/MHMD-SAYID/GraduationProject)

## Team

**Backend APIs, system integration & audio analysis:** Nourhan Saber Shalaby

Mohamed Mahmoud Mohamed · Mohamed Sayid Mohamed · Mohamed Mohamed Barakat · Mohamed Adel Hosny · Mohamed Essam Mohamed · Mohamed Mostafa Salama · Amr Mohamed Ahmed · Ibrahim Ahmed Mohamed · Elzahraa Eslam Marzouk

Supervised by **Dr. Eman Monir**, with Eng. Esraa Taher and Eng. Eman Naser.
