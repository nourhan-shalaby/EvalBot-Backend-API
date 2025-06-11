# test_submit.py
import requests
import os

# تأكدي أن Flask API يعمل على هذا المنفذ
API_URL = "http://127.0.0.1:5001/api/submit-answer-audio"

# المسار الفعلي لملف الصوت الذي تريدين إرساله
# استخدمي أحد الملفات التي تم توليدها في 'static/audio'
# أو أي ملف WAV/MP3 قصير لديك
AUDIO_FILE_PATH = r"D:\InterviewerAI_Project_Final\static\audio\question_1749062113462_2.wav" # <<<< غيّري هذا المسار لملف موجود لديك

# تأكدي أن هذه البيانات تتوافق مع استجابة /api/start-interview
QUESTION_ID = "2" # غيري ليتناسب مع السؤال الذي اخترتيه
QUESTION_TEXT = "What is the purpose of a confusion matrix?" # غيري ليتناسب مع السؤال الذي اخترتيه
GEMINI_ANSWER = "A confusion matrix shows how well a classification model is performing. It shows the counts of true positives, true negatives, false positives, and false negatives. This helps understand the types of errors the model is making." # غيري ليتناسب مع السؤال الذي اخترتيه
QUESTION_TOPIC = "machine learning" # غيري ليتناسب مع السؤال الذي اخترتيه
QUESTION_CLASSIFICATION = "Beginner" # غيري ليتناسب مع السؤال الذي اخترتيه

def test_submit_answer_audio():
    if not os.path.exists(AUDIO_FILE_PATH):
        print(f"Error: Audio file not found at {AUDIO_FILE_PATH}")
        return

    try:
        with open(AUDIO_FILE_PATH, 'rb') as audio_file:
            # اقرئي محتويات الملف الصوتية كـ binary data
            audio_bytes = audio_file.read()

            # أرسلي البيانات الأخرى في الـ Headers
            headers = {
                'Content-Type': 'audio/wav', # أو 'audio/mpeg' إذا كان الملف MP3
                'X-Question-Id': str(QUESTION_ID), # حوليها إلى string
                'X-Question-Text': QUESTION_TEXT,
                'X-Gemini-Answer': GEMINI_ANSWER,
                'X-Question-Topic': QUESTION_TOPIC,
                'X-Question-Classification': QUESTION_CLASSIFICATION,
            }

            print(f"Sending request to: {API_URL}")
            print(f"File: {AUDIO_FILE_PATH} ({len(audio_bytes)} bytes)")
            print(f"Headers: {headers}")

            # أرسلي الـ binary data مباشرة كـ body
            response = requests.post(API_URL, data=audio_bytes, headers=headers)

            print(f"\nResponse Status Code: {response.status_code}")
            # حاول طباعة json إذا كان موجوداً وإلا اطبع النص
            try:
                print(f"Response Body: {response.json()}")
            except requests.exceptions.JSONDecodeError:
                print(f"Response Body (text): {response.text}")


    except requests.exceptions.ConnectionError as e:
        print(f"Error: Could not connect to the server. Is Flask app running? {e}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending request: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == '__main__':
    test_submit_answer_audio()