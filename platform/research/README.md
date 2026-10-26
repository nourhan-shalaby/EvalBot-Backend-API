# Research scripts

How the calibrated models were trained. They need a local copy of the MIT Interview Dataset (not included; see its license).

1. Convert the recordings to 16 kHz mono FLAC (`ffmpeg -i P1.wav -ac 1 -ar 16000 P1.flac`).
2. `python diarize.py` separates the candidate from the interviewer (writes `diar/*.json`).
3. `python train_calibration.py` extracts features with `calibration.py`, cross-validates per-trait models and writes `assets/models/calibrated_scores.joblib`.
4. `python benchmark.py` is the research benchmark using the dataset's own facial, smile and PRAAT features.

Put `turker_scores_full_interview.csv` and `interview_transcripts_by_turkers.csv` from the dataset next to the scripts.
