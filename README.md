# EvalBot Interviewer AI Backend API

This repository contains the Flask-based backend API for the EvalBot project. It is designed to facilitate AI-powered interview simulations by integrating advanced Speech-to-Text (STT) and Text-to-Speech (TTS) capabilities, creating an interactive and efficient interview experience. The API also handles the crucial task of sending user responses for comprehensive external AI-driven evaluation.

## ✨ Features

* **AI-Powered Question Generation:** Fetches dynamic interview questions based on specified tracks, difficulty levels, and number of questions from an external service.
* **Text-to-Speech (TTS) Integration:** Converts textual interview questions into natural-sounding audio using Cartesia.ai. This enhances the realism and interactivity of the interview process.
* **Speech-to-Text (STT) Transcription:** Transcribes user's audio responses into text using advanced models from Hugging Face Transformers, specifically leveraging the Whisper model (`openai/whisper-tiny`) for high accuracy.
* **External Evaluation Integration:** Forwards transcribed user answers, along with original question context, to a dedicated external AI evaluation API for detailed assessment and feedback.
* **Local Development Friendly:** Optimized for easy setup and development on local machines.
* **Collaboration Ready:** Supports `ngrok` for exposing the local development server to the internet, enabling seamless collaboration with frontend teams.

## 🚀 Getting Started

Follow these steps to set up and run the EvalBot Interviewer AI Backend API on your local machine.

### Prerequisites

Before you begin, ensure you have the following installed:

* **Python 3.9+**
* **`pip`** (Python package installer)
* **`ngrok`**: Download and install `ngrok` from [ngrok.com/download](https://ngrok.com/download). This is essential for exposing your local server to the internet for team collaboration.
* **API Keys/URLs:**
    * A **Cartesia.ai API Key** for Text-to-Speech functionality.
    * The **base URL for the external question generation API** (e.g., `https://evalboot-eb9306b2f856.herokuapp.com`).
    * The **URL for the external evaluation API**.

### Installation

1.  **Clone the repository:**
    ```bash
    git clone [[YOUR_REPOSITORY_LINK_HERE](https://github.com/nourhan-shalaby/EvalBot-Backend-API)]
    cd [EvalBot-Backend-API]
    ```
    *(Replace `[YOUR_REPOSITORY_LINK_HERE]` and `[YOUR_REPOSITORY_NAME]` with your actual repository details.)*

2.  **Create a virtual environment:**
    It's highly recommended to use a virtual environment to manage dependencies.
    ```bash
    python -m venv venv
    ```

3.  **Activate the virtual environment:**
    * **On macOS/Linux:**
        ```bash
        source venv/bin/activate
        ```
    * **On Windows:**
        ```bash
        .\venv\Scripts\activate
        ```

4.  **Install dependencies:**
    Install all required Python packages using `pip` and the `requirements.txt` file.
    ```bash
    pip install -r requirements.txt
    ```
    The `requirements.txt` includes:
    * `Flask`: The web framework for the API.
    * `requests`: For making HTTP requests to external services.
    * `python-dotenv`: For loading environment variables from a `.env` file.
    * `transformers==4.38.0`: Hugging Face's library for STT models (e.g., Whisper).
    * `accelerate==0.27.2`: A companion library for Transformers, optimizing model loading and execution.
    * `gunicorn`: A production-ready WSGI HTTP Server.
    * `setuptools`: For packaging Python projects.
    * `cartesia`: The client library for Cartesia.ai TTS service.

### Environment Variables

Create a `.env` file in the root directory of your project. This file will store your API keys and external service URLs securely.

```dotenv
# Cartesia.ai API Key for Text-to-Speech
CARTESIA_API_KEY="your_cartesia_api_key_here"

# Hugging Face STT Model Name (Default: openai/whisper-tiny)
HF_STT_MODEL_NAME="openai/whisper-tiny"

# Cartesia.ai TTS Model and Voice IDs (Defaults provided)
CARTESIA_TTS_MODEL_ID="sonic-english"
CARTESIA_TTS_VOICE_ID="c2ac25f9-ecc4-4f56-9095-651354df60c0" # A common default English voice

# Base URL for the external Question Generation API
API_BASE_URL="[https://evalboot-eb9306b2f856.herokuapp.com](https://evalboot-eb9306b2f856.herokuapp.com)"

# URL for the external Evaluation API
EXTERNAL_EVALUATION_API_URL="your_external_evaluation_api_url_here"
