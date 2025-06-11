# app.py
from flask import Flask, request, jsonify, send_from_directory
import requests
import os
import time
import glob
import logging
from dotenv import load_dotenv

# Imports for STT (Hugging Face Transformers)
from transformers import pipeline, AutoProcessor, AutoModelForSpeechSeq2Seq
import torch

# Imports for TTS (Cartesia.ai)
from cartesia import Cartesia

# These specific imports from cartesia.tts are not strictly necessary for client.tts.bytes()
# from cartesia.tts import OutputFormat_Wav, TtsRequestIdSpecifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()  # Load environment variables

app = Flask(__name__, static_folder='static')

# --- Global Model Loading ---
# STT Model Loading (Hugging Face Whisper)
HF_STT_MODEL_NAME = os.getenv('HF_STT_MODEL_NAME', 'openai/whisper-tiny')
device = "cuda:0" if torch.cuda.is_available() else "cpu"
torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

stt_pipe = None
try:
    logger.info(f"Loading Hugging Face STT model: {HF_STT_MODEL_NAME} to device: {device}...")
    stt_pipe = pipeline(
        "automatic-speech-recognition",
        model=HF_STT_MODEL_NAME,
        chunk_length_s=30,
        device=device,
        torch_dtype=torch_dtype,
    )
    logger.info("Hugging Face STT model loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load Hugging Face STT model {HF_STT_MODEL_NAME}: {e}. STT will not work.")
    stt_pipe = None
    import traceback

    logger.error(f"Full traceback for STT model loading: {traceback.format_exc()}")

# Cartesia.ai TTS Client Initialization
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY")
CARTESIA_TTS_MODEL_ID = os.getenv("CARTESIA_TTS_MODEL_ID", "sonic-english")
CARTESIA_TTS_VOICE_ID = os.getenv("CARTESIA_TTS_VOICE_ID", "c2ac25f9-ecc4-4f56-9095-651354df60c0")  # Default voice ID

cartesia_client = None
if CARTESIA_API_KEY:
    try:
        cartesia_client = Cartesia(api_key=CARTESIA_API_KEY)
        logger.info("Cartesia.ai client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Cartesia.ai client: {e}. TTS will not work.")
        cartesia_client = None
        import traceback

        logger.error(f"Full traceback for Cartesia client init: {traceback.format_exc()}")
else:
    logger.error("CARTESIA_API_KEY not set. Cartesia.ai TTS will not work.")

EXTERNAL_EVALUATION_API_URL = os.getenv('EXTERNAL_EVALUATION_API_URL')


def cleanup_old_audio_files(directory="static/audio"):
    """Deletes old audio files from the specified directory."""
    if os.path.exists(directory):
        for file in glob.glob(os.path.join(directory, "*.wav")) + glob.glob(os.path.join(directory, "*.mp3")):
            try:
                os.remove(file)
                logger.info(f"Deleted old audio file: {file}")
            except Exception as e:
                logger.error(f"Error deleting {file}: {e}")
    else:
        os.makedirs(directory, exist_ok=True)


def cleanup_temp_answer_files(directory="/tmp"):
    """Cleans up temporary user answer audio files."""
    if os.path.exists(directory):
        for file in glob.glob(os.path.join(directory, "answer_*.wav")) + \
                    glob.glob(os.path.join(directory, "answer_*.mp3")):
            try:
                os.remove(file)
                logger.info(f"Deleted temporary answer file: {file}")
            except Exception as e:
                logger.error(f"Error deleting temp answer file {file}: {e}")
    else:
        os.makedirs(directory, exist_ok=True)


@app.route('/')
def index():
    """
    Base route for the API. Cleans up old audio files.
    """
    cleanup_old_audio_files()
    cleanup_temp_answer_files()
    return "Welcome to the Interviewer AI API (Cartesia TTS / Hugging Face STT)! Use /api/start-interview to begin."


@app.route('/static/<path:filename>')
def serve_static(filename):
    """Route to serve static files (like audio files)."""
    return send_from_directory('static', filename)


def text_to_audio_cartesia(text: str, filename: str) -> str | None:
    """
    Converts text to speech using Cartesia.ai and saves the audio to a local file.

    Args:
        text (str): The text to be converted.
        filename (str): The full path to the output audio file (e.g., 'static/audio/question_123.wav').

    Returns:
        str: The path to the audio file if successful, or None if it fails.
    """
    if cartesia_client is None:
        logger.error("Cartesia.ai client not initialized. Cannot perform text-to-audio.")
        return None

    try:
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        logger.info(
            f"Calling Cartesia.ai for text: '{text[:50]}...' with model '{CARTESIA_TTS_MODEL_ID}' and voice '{CARTESIA_TTS_VOICE_ID}'.")

        response = cartesia_client.tts.bytes(
            model_id=CARTESIA_TTS_MODEL_ID,
            transcript=text,
            voice={
                "mode": "id",
                "id": CARTESIA_TTS_VOICE_ID,
            },
            output_format={
                "container": "wav",
                "sample_rate": 16000,
                "encoding": "pcm_s16le",
            },
            language="en",
            speed='slow' # Added speed parameter back
        )

        audio_bytes = b''
        for chunk in response:
            audio_bytes += chunk

        with open(filename, 'wb') as f:
            f.write(audio_bytes)

        if os.path.exists(filename) and os.path.getsize(filename) > 0:
            logger.info(f"Successfully created local audio file (Cartesia TTS): {filename}")
            return filename
        else:
            logger.error(f"Failed to create audio file (Cartesia TTS) or it's empty: {filename}")
            return None

    except Exception as e:
        logger.error(f"Error in text_to_audio_cartesia for '{text[:50]}...': {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return None


def transcribe_audio_hf(audio_file_path: str) -> str | None:
    """
    Transcribes a local audio file to text using a Hugging Face STT model.
    """
    if stt_pipe is None:
        logger.error("Hugging Face STT pipeline not loaded. Cannot perform transcription.")
        return None
    try:
        logger.info(f"Transcribing audio file: {audio_file_path} using Hugging Face STT.")
        output = stt_pipe(audio_file_path, generate_kwargs={"task": "transcribe"})
        transcribed_text = output["text"]
        logger.info(f"Hugging Face STT transcription successful: {transcribed_text[:100]}...")
        return transcribed_text.strip()
    except Exception as e:
        logger.error(f"Error transcribing audio file {audio_file_path} using Hugging Face STT: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return None


@app.route('/api/start-interview', methods=['POST'])
def start_interview_api():
    """
    API endpoint to start an interview.
    Fetches questions from an external service, converts each question to an audio file
    using Cartesia.ai, stores it locally, and returns a list of questions with their local audio URLs.
    """
    try:
        if not request.is_json:
            logger.warning("Received non-JSON request to /api/start-interview")
            return jsonify({'error': 'Request must be JSON'}), 400

        data = request.get_json()
        track_id = data.get('track_id', '1')
        difficulty = data.get('difficulty', 'beginner')
        num_questions = data.get('num_questions', 3)

        logger.info(
            f"Received request for interview: track_id={track_id}, difficulty={difficulty}, num_questions={num_questions}")

        api_base_url = os.getenv('API_BASE_URL', 'https://evalboot-eb9306b2f856.herokuapp.com')
        question_api_url = f"{api_base_url}/ggenerate-questions"

        response = requests.get(question_api_url, params={
            'track_id': track_id,
            'difficulty': difficulty,
            'num_questions': num_questions
        }, timeout=30)

        response.raise_for_status()
        api_data = response.json()
        logger.debug(f"External Question API raw response: {api_data}")

        questions_with_audio_urls = []

        if 'topics' in api_data:
            for topic_obj_from_api in api_data['topics']:
                topic_name = topic_obj_from_api.get('topic', 'General Topics')
                for question_data_from_api in topic_obj_from_api.get('questions', []):

                    question_text = question_data_from_api.get("question", "")
                    gemini_answer = question_data_from_api.get("gemini_answer", "")
                    classification = question_data_from_api.get("classification", "General")

                    if not question_text:
                        logger.warning(f"Skipping empty question in topic '{topic_name}'")
                        continue

                    full_speech_text = f"{question_text}"

                    audio_filename = f"static/audio/question_{int(time.time() * 1000)}_{len(questions_with_audio_urls)}.wav"

                    # Use Cartesia.ai for text-to-audio
                    audio_file_path = text_to_audio_cartesia(full_speech_text, audio_filename)

                    if audio_file_path:
                        questions_with_audio_urls.append({
                            'id': question_data_from_api.get('id', len(questions_with_audio_urls)),
                            'question_text': question_text,
                            'audio_url': f'/{audio_file_path}',
                            'question_number': len(questions_with_audio_urls) + 1,
                            'gemini_answer': gemini_answer,
                            'question_topic': topic_name,
                            'question_classification': classification
                        })
                    else:
                        logger.error(f"Failed to generate audio for question: {question_text[:50]}...")
                        return jsonify({'error': f'Failed to generate audio for a question'}), 500

            if not questions_with_audio_urls:
                logger.error("No questions were extracted or generated with audio from the API response.")
                return jsonify({
                    'error': 'No valid questions could be generated with audio. Response structure might be unexpected.'}), 404

            logger.info(f"Successfully generated {len(questions_with_audio_urls)} questions with audio (Cartesia TTS).")
            return jsonify({
                'status': 'success',
                'message': 'Interview questions and audio URLs generated successfully',
                'interview_data': {
                    'total_questions': len(questions_with_audio_urls),
                    'questions': questions_with_audio_urls
                }
            }), 200

    except requests.exceptions.Timeout:
        logger.error("Timeout connecting to the question generation service.")
        return jsonify({'error': 'Question generation service took too long to respond'}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Error in API request to question generation service: {str(e)}")
        return jsonify({'error': 'Failed to connect to the question generation service', 'details': str(e)}), 503
    except Exception as e:
        logger.error(f"An unexpected error occurred in /api/start-interview: {str(e)}")
        return jsonify({'error': 'An internal server error occurred', 'details': str(e)}), 500


@app.route('/api/submit-answers', methods=['POST'])  # Changed endpoint name to submit-answers
def submit_answers():  # Changed function name to submit_answers
    try:
        # Check if the request body is JSON
        if not request.is_json:
            logger.warning("Received non-JSON request to /api/submit-answers. Expected JSON array of answers.")
            return jsonify({'error': 'Request must be JSON'}), 400

        data_list = request.get_json()  # Get list of answers from the request body

        if not isinstance(data_list, list):
            logger.warning("Received non-list data to /api/submit-answers. Expected JSON array of answers.")
            return jsonify({'error': 'Request body must be a JSON array of answers'}), 400

        if not data_list:
            logger.warning("Received empty list to /api/submit-answers.")
            return jsonify({'status': 'success', 'message': 'No answers provided.'}), 200

        all_results = []  # To store results for all submitted answers

        for answer_data in data_list:
            audio_url_from_client = answer_data.get('audio_url')  # Extract audio_url
            question_id = answer_data.get('question_id', 'unknown')
            question_text_from_client = answer_data.get('question_text', 'No question text provided for evaluation')
            gemini_answer_from_client = answer_data.get('gemini_answer', '')
            question_topic_from_client = answer_data.get('question_topic', 'General Topics')
            question_classification_from_client = answer_data.get('classification',
                                                                  'General')  # Corrected field name to 'classification'

            # Input validation for essential fields within each answer_data
            if not audio_url_from_client:
                logger.warning(f"No 'audio_url' provided for question_id {question_id}. Skipping this answer.")
                all_results.append({
                    'question_id': question_id,
                    'status': 'error',
                    'message': 'No audio_url provided for this answer.'
                })
                continue  # Skip to the next answer in the list

            # Download the audio file from the provided URL
            # Ensure unique temporary file names
            temp_local_audio_path = f"/tmp/answer_{question_id}_{int(time.time() * 1000)}.wav"

            try:
                logger.info(f"Attempting to download audio from URL: {audio_url_from_client}")
                audio_response = requests.get(audio_url_from_client, timeout=10)
                audio_response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

                os.makedirs(os.path.dirname(temp_local_audio_path), exist_ok=True)
                with open(temp_local_audio_path, 'wb') as f:
                    f.write(audio_response.content)
                logger.info(f"Successfully downloaded audio to: {temp_local_audio_path}")

            except requests.exceptions.RequestException as e:
                logger.error(f"Error downloading audio from {audio_url_from_client} for question_id {question_id}: {e}")
                all_results.append({
                    'question_id': question_id,
                    'status': 'error',
                    'message': f'Failed to download audio from URL: {e}'
                })
                continue  # Skip to the next answer
            except Exception as e:
                logger.error(f"Unexpected error during audio download for question_id {question_id}: {e}")
                all_results.append({
                    'question_id': question_id,
                    'status': 'error',
                    'message': f'An unexpected error occurred during audio download: {e}'
                })
                continue  # Skip to the next answer

            # Transcribe the downloaded audio
            transcribed_text = transcribe_audio_hf(temp_local_audio_path)

            # Clean up temporary audio file after transcription
            try:
                os.remove(temp_local_audio_path)
                logger.info(f"Deleted temporary local audio file: {temp_local_audio_path}")
            except Exception as e:
                logger.warning(f"Could not delete temporary local audio file {temp_local_audio_path}: {e}")

            if transcribed_text:
                if not EXTERNAL_EVALUATION_API_URL:
                    logger.error(
                        f"EXTERNAL_EVALUATION_API_URL is not set. Cannot perform evaluation for question_id {question_id}.")
                    all_results.append({
                        'question_id': question_id,
                        'status': 'error',
                        'message': 'Evaluation service URL not configured.'
                    })
                    continue  # Skip to the next answer

                evaluation_payload = {
                    "topics": [
                        {
                            "topic": question_topic_from_client,
                            "questions": [
                                {
                                    "question": question_text_from_client,
                                    "gemini_answer": gemini_answer_from_client,
                                    "user_answer": transcribed_text,
                                    "topic": question_topic_from_client,  # Repeated as per API schema
                                    "classification": question_classification_from_client  # Send classification
                                }
                            ]
                        }
                    ]
                }
                # Log the user_answer content, handling potential empty strings
                user_answer_for_log = evaluation_payload['topics'][0]['questions'][0].get('user_answer', 'N/A')
                logger.info(
                    f"Sending data to external evaluation API for question_id {question_id}: {user_answer_for_log[:50]}...")

                try:
                    evaluation_response = requests.post(EXTERNAL_EVALUATION_API_URL, json=evaluation_payload,
                                                        timeout=20)
                    evaluation_response.raise_for_status()

                    full_evaluation_output = evaluation_response.json()
                    logger.info(
                        f"Received full evaluation output for question_id {question_id}: {full_evaluation_output}")

                    extracted_result = {}
                    # Safely extract results from the complex structure
                    if full_evaluation_output and isinstance(full_evaluation_output,
                                                             dict) and 'topics' in full_evaluation_output and \
                            isinstance(full_evaluation_output['topics'], list) and len(
                        full_evaluation_output['topics']) > 0 and \
                            'questions' in full_evaluation_output['topics'][0] and \
                            isinstance(full_evaluation_output['topics'][0]['questions'], list) and len(
                        full_evaluation_output['topics'][0]['questions']) > 0:

                        question_output_data = full_evaluation_output['topics'][0]['questions'][0]
                        extracted_result['score'] = question_output_data.get('score')
                        extracted_result['score_explanation'] = question_output_data.get('score_explanation')
                        extracted_result['links'] = question_output_data.get('links', [])
                        extracted_result['gemini_answer'] = question_output_data.get('gemini_answer')
                        extracted_result['question_topic'] = question_output_data.get('topic')
                        extracted_result['question_classification'] = question_output_data.get('classification')

                    else:
                        logger.warning(
                            f"Could not extract evaluation result for question_id {question_id}. Response format might be unexpected or empty.")
                        extracted_result = {"error": "Unexpected evaluation API response format",
                                            "full_response": full_evaluation_output}

                    all_results.append({
                        'question_id': question_id,
                        'status': 'success',
                        'transcribed_text': transcribed_text,
                        'evaluation_result': extracted_result
                    })
                except requests.exceptions.Timeout:
                    logger.error(f"Timeout connecting to the external evaluation API for question_id {question_id}.")
                    all_results.append({
                        'question_id': question_id,
                        'status': 'error',
                        'message': 'Evaluation service timed out.'
                    })
                except requests.exceptions.RequestException as e:
                    logger.error(f"Error connecting to external evaluation API for question_id {question_id}: {e}")
                    all_results.append({
                        'question_id': question_id,
                        'status': 'error',
                        'message': f'Failed to connect to evaluation service: {e}'
                    })
                except Exception as e:
                    logger.error(
                        f"Unexpected error when calling external evaluation API for question_id {question_id}: {e}")
                    all_results.append({
                        'question_id': question_id,
                        'status': 'error',
                        'message': f'An unexpected error occurred during evaluation: {e}'
                    })
            else:  # If transcription failed
                all_results.append({
                    'question_id': question_id,
                    'status': 'error',
                    'message': 'Failed to transcribe audio.'
                })

        return jsonify(all_results), 200  # Return list of results

    except Exception as e:
        logger.error(f"An unexpected error occurred in /api/submit-answers: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify({'error': 'An internal server error occurred during answer submission', 'details': str(e)}), 500


if __name__ == '__main__':
    logger.info("Starting Interviewer AI API locally (Cartesia TTS / Hugging Face STT)...")
    os.makedirs('static/audio', exist_ok=True)
    os.makedirs('/tmp', exist_ok=True)

    app.run(host='0.0.0.0', port=5001, debug=True)