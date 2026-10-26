# EvalBot: Interview Audio Analysis Service

Live demo: [huggingface.co/spaces/EvalBot/Audio-EvalBot](https://huggingface.co/spaces/EvalBot/Audio-EvalBot)

Upload a recorded job interview and get a full candidate evaluation: who said what, how the candidate sounded, and an AI-written assessment, delivered as a PDF report and JSON.

Part of **EvalBot**, a graduation project at the Faculty of Computers and Artificial Intelligence, Benha University. This folder is deployed as a Docker Space on Hugging Face.

## Pipeline

| Step | What happens | Tools |
|---|---|---|
| 1. Conversion | Any audio/video file to 16 kHz mono WAV | ffmpeg |
| 2. Transcription | Speech-to-text with speaker diarization (filler words kept) | AssemblyAI |
| 3. Prosody | Pitch and intensity per utterance | librosa |
| 4. Speaker identification | One voice embedding per speaker, matched against or enrolled into a vector index, so returning speakers are recognized | NVIDIA NeMo TitaNet, Pinecone |
| 5. Role classification | Decides which speaker is the interviewer and which is the candidate | Random Forest (TF-IDF + handcrafted features) trained on ~3,000 labeled utterances from the MIT Interview dataset; ~92% utterance accuracy on held-out interviews, aggregated per speaker |
| 6. Voice analysis | Speaking rate, filler words, repetition, pitch, jitter/shimmer, and confidence, anxiety and hesitation scores | librosa, NumPy |
| 7. Evaluation | Structured assessment: summary, strengths with evidence, development areas, role fit, recommendations, next steps, content score | Gemini (JSON schema output) |
| 8. Report | Multi-page PDF with tables, charts and an annotated transcript, plus a JSON export | ReportLab, Matplotlib |

The **suitability score** (0-100) combines answer content (60%, from the AI evaluation) and vocal delivery (40%). If the AI evaluation is unavailable, the report is marked as provisional and based on voice only.

## API

### `POST /process-audio`
Form fields: `user_id` and either `file` (upload) or `file_url`.

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
- `POST /jobs` (same form fields) returns `{"job_id": "..."}`
- `GET /jobs/{job_id}` returns status, the current step and, when done, the result

### `GET /health`
Shows which external services are configured.

## Configuration

Set these as **Secrets** in the Space settings. Never put keys in the code.

| Secret | Required | Used for |
|---|---|---|
| `ASSEMBLYAI_API_KEY` | yes | Transcription and diarization |
| `GEMINI_API_KEY` | recommended | AI evaluation (without it, the report covers voice metrics only) |
| `PINECONE_API_KEY` | optional | Persistent speaker identification |

Optional variables: `GEMINI_MODEL` (default `gemini-2.5-flash`), `PINECONE_INDEX`, `BASE_URL`, `MAX_UPLOAD_MB`.

## Run locally

```bash
docker build -t evalbot-audio .
docker run -p 7860:7860 -e ASSEMBLYAI_API_KEY=... -e GEMINI_API_KEY=... -e PINECONE_API_KEY=... evalbot-audio
# open http://localhost:7860
```

Or without Docker: `python process_interview.py interview.mp3 candidate_42`.

## Notes and limitations
- English interviews with two speakers work best.
- The confidence, anxiety and hesitation scores are heuristics computed from the voice signal. They support a human reviewer and are not a hiring decision.
- The Space runs on free CPU hardware and sleeps when idle; the first request after a pause takes a minute to wake it up.
