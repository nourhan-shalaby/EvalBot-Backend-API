FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg libsndfile1 sox curl build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser
WORKDIR /app
RUN mkdir -p /app/temp_files /app/processed_audio /app/models /app/static/outputs /tmp/matplotlib \
    && chown -R appuser:appuser /app /tmp/matplotlib

ENV MPLCONFIGDIR=/tmp/matplotlib \
    HF_HOME=/app/.cache/huggingface \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

USER appuser
ENV PATH="/home/appuser/.local/bin:${PATH}"

COPY --chown=appuser:appuser requirements.txt .
RUN pip install --user --upgrade pip \
    && pip install --user "Cython==0.29.36" "setuptools<70" wheel \
    && pip install --user --no-build-isolation "youtokentome==1.0.6" \
    && pip install --user -r requirements.txt

COPY --chown=appuser:appuser . .

# Train the role classifier and download the speaker model at build time,
# so the Space is ready as soon as it starts
RUN python -c "import process_interview as p; p.get_role_classifier(); p._get_speaker_model()"

EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=10s CMD curl -f http://localhost:7860/health || exit 1
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
