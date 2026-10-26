"""Manual smoke test for the EvalBot backend.

1. Start the API:            python app.py
2. Start an interview:       POST /api/start-interview
3. Submit recorded answers:  POST /api/submit-answers  (this script)

Each answer needs a publicly reachable `audio_url`; the API downloads it,
transcribes it with Whisper, and forwards it to the evaluation service.
"""
import json
import os

import requests

API_URL = os.getenv("EVALBOT_API_URL", "http://127.0.0.1:5001")

answers = [
    {
        "question_id": "1",
        "question_text": "What is the purpose of a confusion matrix?",
        "gemini_answer": (
            "A confusion matrix shows how well a classification model performs by "
            "counting true positives, true negatives, false positives and false negatives."
        ),
        "question_topic": "machine learning",
        "classification": "Beginner",
        # Replace with a URL to a recorded answer (e.g. one returned by /api/start-interview)
        "audio_url": os.getenv("ANSWER_AUDIO_URL", "http://127.0.0.1:5001/static/audio/sample_answer.wav"),
    }
]


def main() -> None:
    print(f"POST {API_URL}/api/submit-answers")
    response = requests.post(f"{API_URL}/api/submit-answers", json=answers, timeout=120)
    print(f"Status: {response.status_code}")
    try:
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except ValueError:
        print(response.text)


if __name__ == "__main__":
    main()
