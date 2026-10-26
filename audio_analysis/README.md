# EvalBot: Interview Audio Analysis Service

Live demo: [huggingface.co/spaces/EvalBot/Audio-EvalBot](https://huggingface.co/spaces/EvalBot/Audio-EvalBot)

Two ways to use it:

- **Analyze an interview:** upload a recorded job interview (or try the built-in sample) and get a full candidate evaluation: who said what, how the candidate sounded, a score and feedback for every question, and an AI-written assessment. Results appear on the page with a transcript synced to the audio, and as a PDF report and JSON.
- **Practice mode:** pick a question (or generate questions for any job title), listen to it, record your answer with the microphone, and get instant feedback: a score, what went well, what to improve, a delivery tip, and a stronger version of your answer.

The interface and the reports are available in **English and Arabic** (the Arabic PDF is fully right-to-left).

Part of **EvalBot**, a graduation project at the Faculty of Computers and Artificial Intelligence, Benha University. This folder is deployed as a Docker Space on Hugging Face.

## Pipeline

| Step | What happens | Tools |
|---|---|---|
| 1. Conversion | Any audio/video file to 16 kHz mono WAV | ffmpeg |
| 2. Transcription | Speech-to-text with speaker diarization (filler words kept) | AssemblyAI |
| 3. Prosody | Pitch and intensity per utterance | librosa |
| 4. Speaker identification | One voice embedding per speaker, matched by cosine similarity against or enrolled into a vector index, so returning speakers are recognized | NVIDIA NeMo TitaNet; Pinecone, or a built-in NumPy vector index when Pinecone isn't configured |
| 5. Role classification | Decides which speaker is the interviewer and which is the candidate | Random Forest (TF-IDF + handcrafted features) trained on ~3,000 labeled utterances from the MIT Interview dataset; ~92% utterance accuracy on held-out interviews, aggregated per speaker |
| 6. Voice analysis | Speaking rate, filler words, repetition, pitch, jitter/shimmer, and confidence, anxiety and hesitation scores | librosa, NumPy |
| 7. Question pairing | Groups the transcript into question/answer pairs | Python |
| 8. Evaluation | Structured assessment: per-question score, what went well, what to improve and a stronger answer; summary, strengths with evidence, development areas, role fit, recommendations, next steps, content score. In English or Arabic | Gemini (JSON schema output) |
| 9. Report | Multi-page PDF (English, or right-to-left Arabic) with tables, charts, per-question feedback and an annotated transcript, plus a JSON export | ReportLab, Matplotlib, arabic-reshaper, python-bidi |

The **suitability score** (0-100) combines answer content (60%, from the AI evaluation) and vocal delivery (40%). If the AI evaluation is unavailable, the report is marked as provisional and based on voice only.

## API

### `POST /process-audio`
Form fields: `user_id`, either `file` (upload) or `file_url`, and optionally `lang` (`en` or `ar`).

```bash
curl -X POST https://evalbot-audio-evalbot.hf.space/process-audio \
  -F user_id=candidate_42 \
  -F file=@interview.mp3
```

```json
{
  "user_id": "candidate_42",
  "suitability_score": 81.3,
  "verdict": "Outstanding candidate, recommended for advancement.",
  "summary": "...",
  "pdf_url": "https://evalbot-audio-evalbot.hf.space/static/outputs/pdf/candidate_42_..._report.pdf",
  "json_url": "https://evalbot-audio-evalbot.hf.space/static/outputs/json/candidate_42_..._analysis.json"
}
```

### Background jobs (used by the web page)
- `POST /jobs` (same form fields, or `sample=true` for the demo interview) returns `{"job_id": "..."}`
- `GET /jobs/{job_id}` returns status, the current step and, when done, the result

### Practice mode
- `GET /practice/questions`: built-in question bank (General, Behavioral, Data Engineering, Software Engineering, AI / Machine Learning)
- `POST /practice/generate` (form field `role`): five AI-generated questions for a job title
- `POST /practice` (form fields `question`, `file`, optional `lang` and `role`): evaluates one recorded answer and returns the transcript, voice metrics and feedback, usually in 10-20 seconds

### `GET /health`
Shows which external services are configured.

## Configuration

Set these as **Secrets** in the Space settings. Never put keys in the code.

| Secret | Required | Used for |
|---|---|---|
| `ASSEMBLYAI_API_KEY` (or `ASSEMBLYAI_KEY`) | yes | Transcription and diarization |
| `GEMINI_API_KEY` | recommended | AI evaluation (without it, the report covers voice metrics only) |
| `PINECONE_API_KEY` | optional | Use Pinecone for speaker identification. Without it, a built-in vector index is used (saved to `/data` if the Space has persistent storage, otherwise reset on restart) |

Optional variables: `GEMINI_MODEL` (default `gemini-3.5-flash-lite`, with automatic fallback to other Flash models if it is slow or unavailable), `GEMINI_TIMEOUT_S` (default 60), `PINECONE_INDEX`, `BASE_URL`, `MAX_UPLOAD_MB`.

## Run locally

```bash
docker build -t evalbot-audio .
docker run -p 7860:7860 -e ASSEMBLYAI_API_KEY=... -e GEMINI_API_KEY=... -e PINECONE_API_KEY=... evalbot-audio
# open http://localhost:7860
```

Or without Docker: `python process_interview.py interview.mp3 candidate_42`.

## Notes and limitations
- Interviews and practice answers should be in English (the feedback and report can be in Arabic).
- Interviews with two speakers work best.
- The sample interview was generated with text-to-speech (Piper voices) for demonstration.
- The confidence, anxiety and hesitation scores are heuristics computed from the voice signal. They support a human reviewer and are not a hiring decision.
- The Space runs on free CPU hardware and sleeps when idle; the first request after a pause takes a minute to wake it up.
