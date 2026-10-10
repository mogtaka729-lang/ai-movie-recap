from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import subprocess
import requests

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/process', methods=['POST'])
def process_video():
    try:
        api_key = request.form.get('api_key')
        speed = float(request.form.get('speed', 1.0))
        tone = request.form.get('tone', 'warm')
        blur_active = request.form.get('blur_active', 'true')
        video_file = request.files.get('video')

        if not video_file or not api_key:
            return jsonify({'error': 'API Key နှင့် Video ဖိုင် လိုအပ်ပါသည်'}), 400

        input_path = os.path.join(UPLOAD_FOLDER, 'input.mp4')
        output_path = os.path.join(UPLOAD_FOLDER, 'recap_bypass.mp4')
        audio_path = os.path.join(UPLOAD_FOLDER, 'audio.mp3')
        
        video_file.save(input_path)

        print("⚡ Extracting Audio...")
        subprocess.run(["ffmpeg", "-y", "-i", input_path, "-vn", "-ar", "16000", "-ac", "1", audio_path], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        print("🎙️ Groq AI Translating...")
        headers = {"Authorization": f"Bearer {api_key.strip()}"}
        english_transcript = ""

        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 1000:
            whisper_url = "https://api.groq.com/openai/v1/audio/translations"
            try:
                with open(audio_path, "rb") as f:
                    w_res = requests.post(whisper_url, headers=headers, files={"file": f}, data={"model": "whisper-large-v3"}, timeout=40)
                if w_res.status_code == 200:
                    english_transcript = w_res.json().get("text", "").strip()
            except Exception:
                pass

        chosen_model = "llama-3.3-70b-versatile"
        try:
            m_res = requests.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=8)
            if m_res.status_code == 200:
                models_data = [m["id"] for m in m_res.json().get("data", []) if not any(x in m["id"].lower() for x in ["whisper", "guard"])]
                for pref in ["llama-3.3-70b-versatile", "openai/gpt-oss-20b", "llama3-70b-8192"]:
                    if pref in models_data:
                        chosen_model = pref
                        break
        except Exception:
            pass

        prompt = f"ဒီဗီဒီယိုထဲက တရုတ်စကားပြော ဘာသာပြန်ချက်များ ဖြစ်သည်:\n'{english_transcript}'\n\nတာဝန်: ဒီအချက်အလက်ကို အခြေခံပြီး စိတ်ဝင်စားဖွယ် Movie Recap Script ကို သဘာဝကျသော မြန်မာစကားပြေဖြင့် ရေးပေးပါ။ ဇာတ်လမ်းအညွှန်း စာသားသီးသန့်သာ ထုတ်ပေးပါ။"
        chat_url = "https://api.groq.com/openai/v1/chat/completions"
        c_res = requests.post(chat_url, headers=headers, json={"model": chosen_model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.6}, timeout=30)
        script_text = c_res.json()["choices"][0]["message"]["content"] if c_res.status_code == 200 else "ဇာတ်လမ်းအညွှန်း ထုတ်ယူရာတွင် အခက်အခဲရှိသော်လည်း ဗီဒီယို Edit ပြီးစီးပါပြီ။"

        print("🎬 Rendering Video...")
        vf_list = [f"setpts={1.0/speed}*PTS"]
        if tone == 'warm': vf_list.append("colorbalance=rs=0.12:gs=0.04:bs=-0.12,eq=saturation=1.25:contrast=1.08")
        elif tone == 'cool': vf_list.append("colorbalance=rs=-0.10:gs=0.02:bs=0.15,eq=saturation=1.1:contrast=1.05")
        elif tone == 'vivid': vf_list.append("eq=saturation=1.45:contrast=1.15")
        else: vf_list.append("eq=saturation=1.15:contrast=1.05")
        
        base_vf = ",".join(vf_list)
        if blur_active == 'true': filter_complex = f"[0:v]{base_vf}[base];[base]crop=iw:ih*0.16:0:ih*0.82,boxblur=15:5[blurred_sub];[base][blurred_sub]overlay=0:H*0.82[v];[0:a]atempo={speed}[a]"
        else: filter_complex = f"[0:v]{base_vf}[v];[0:a]atempo={speed}[a]"

        subprocess.run(["ffmpeg", "-y", "-i", input_path, "-filter_complex", filter_complex, "-map", "[v]", "-map", "[a]", "-preset", "veryfast", "-crf", "22", output_path], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        download_url = f"{request.host_url}download"
        return jsonify({'success': True, 'script': script_text, 'download_url': download_url})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download')
def download():
    output_path = os.path.join(UPLOAD_FOLDER, 'recap_bypass.mp4')
    return send_file(output_path, as_attachment=True, download_name='Render_Edited_Recap.mp4')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
