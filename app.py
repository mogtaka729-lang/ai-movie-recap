import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)

# အရေးကြီးဆုံးအပိုင်း (Netlify ဘက်ကလာတဲ့ ချိတ်ဆက်မှုကို လက်ခံရန် CORS ဖွင့်ပေးခြင်း)
CORS(app)

# ဗီဒီယိုဖိုင် ခဏသိမ်းရန် နေရာ
UPLOAD_FOLDER = '/tmp'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def home():
    return "AI Movie Recap Server is Running Successfully!"

@app.route('/process', methods=['POST'])
def process_video():
    filepath = None
    try:
        # ၁။ ရှေ့ပိုင်း (App) ဆီကနေ အချက်အလက်များ လက်ခံရယူခြင်း
        api_key = request.form.get('api_key')
        if not api_key:
            return jsonify({"error": "Groq API Key is missing. Please provide your API key."}), 400

        if 'video' not in request.files:
            return jsonify({"error": "No video file uploaded."}), 400
            
        video_file = request.files['video']
        if video_file.filename == '':
            return jsonify({"error": "No video selected."}), 400

        # ၂။ ဗီဒီယိုဖိုင်ကို ဆာဗာပေါ်တွင် ခဏသိမ်းခြင်း
        filename = secure_filename(video_file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        video_file.save(filepath)

        # ၃။ Groq Whisper API ဖြင့် ဗီဒီယိုထဲက အသံကို စာသားပြောင်းခြင်း (Transcription)
        transcription_url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers_audio = {
            "Authorization": f"Bearer {api_key}"
        }
        
        with open(filepath, 'rb') as f:
            files = {
                'file': (filename, f, 'audio/mp4') 
            }
            data = {
                'model': 'whisper-large-v3'
            }
            response = requests.post(transcription_url, headers=headers_audio, files=files, data=data)
        
        if response.status_code != 200:
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({"error": f"Audio Transcription Failed: {response.text}"}), 500
            
        transcription_result = response.json()
        transcript_text = transcription_result.get('text', '')

        if not transcript_text:
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({"error": "Could not detect any speech in the video."}), 400

        # ၄။ Groq LLaMA ဖြင့် မြန်မာလို Movie Recap ဇာတ်လမ်းပြန်ပြောခြင်း (Summarization)
        chat_url = "https://api.groq.com/openai/v1/chat/completions"
        headers_chat = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        prompt = f"Please write a short, engaging, and professional movie recap script in the Myanmar (Burmese) language based on the following video transcript:\n\n{transcript_text}"
        
        chat_payload = {
            "model": "llama-3.1-8b-instant",  # <--- ဒီနေရာမှာ Groq ရဲ့ Model အသစ်ကို ပြောင်းပေးလိုက်ပါပြီ
            "messages": [
                {"role": "system", "content": "You are a professional movie recap script writer. Always respond in Myanmar (Burmese) language natively and naturally."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }
        
        chat_response = requests.post(chat_url, headers=headers_chat, json=chat_payload)
        
        # အလုပ်လုပ်ပြီးသွားရင် ဆာဗာပေါ်က ဗီဒီယိုဖိုင်ကို ပြန်ဖျက်ပစ်ပါမယ် (နေရာမပြည့်အောင်)
        if os.path.exists(filepath):
            os.remove(filepath)
            
        if chat_response.status_code != 200:
            return jsonify({"error": f"AI Summary Failed: {chat_response.text}"}), 500
            
        recap_result = chat_response.json()
        myanmar_recap = recap_result['choices'][0]['message']['content']

        # ၅။ ရှေ့ပိုင်း App ဆီသို့ မြန်မာစာသားများ ပြန်ပို့ပေးခြင်း
        return jsonify({
            "recap": myanmar_recap,
            "script": myanmar_recap 
        })

    except Exception as e:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
