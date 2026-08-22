import os
import threading
import time
import requests
import random
import io
import zipfile
import socket
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer

# 1. السيرفر الوهمي للـ Keep-Alive
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def keep_alive_ping():
    time.sleep(300)
    while True:
        try:
            port = os.environ.get("PORT", "8080")
            requests.get(f"http://127.0.0.1:{port}/", timeout=10)
        except Exception:
            pass
        time.sleep(600)

def run_dummy_server():
    try:
        port = int(os.environ.get("PORT", 8080))
        if is_port_in_use(port):
            return
        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, format, *args): return
        TCPServer.allow_reuse_address = True
        with TCPServer(("", port), QuietHandler) as httpd:
            httpd.serve_forever()
    except Exception:
        pass

threading.Thread(target=run_dummy_server, daemon=True).start()
threading.Thread(target=keep_alive_ping, daemon=True).start()

# 2. الاستيرادات والتهيئة
try:
    from gTTS import gTTS
    HAS_GTTS = True
except Exception:
    HAS_GTTS = False

from google import genai
from google.genai import types
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
ADMIN_ID = 7601281598

RAW_GEMINI_KEYS = [
    os.environ.get('GEMINI_API_KEY_1'), os.environ.get('GEMINI_API_KEY_2'),
    os.environ.get('GEMINI_API_KEY_3'), os.environ.get('GEMINI_API_KEY'),
    os.environ.get('GEMINI_API_KEY_4'), os.environ.get('GEMINI_API_KEY_5'),
    os.environ.get('GEMINI_API_KEY_6'), os.environ.get('GEMINI_API_KEY_7')
]
GEMINI_KEYS = [k.strip() for k in RAW_GEMINI_KEYS if k and len(k.strip()) > 10]

GROQ_KEYS = [k.strip() for k in [os.environ.get('GROQ_API_KEY_1'), os.environ.get('GROQ_API_KEY_2')] if k and len(k.strip()) > 5]
OPENROUTER_KEYS = [k.strip() for k in [os.environ.get('OPENROUTER_API_KEY_1'), os.environ.get('OPENROUTER_API_KEY_2')] if k and len(k.strip()) > 5]

user_memory = {}
processed_messages = set()
group_msg_counters = {}
CHAT_LOG_FILE = "chat_history.txt"

def save_chat_to_file(user_info, user_msg, bot_msg):
    try:
        with open(CHAT_LOG_FILE, "a", encoding="utf-8") as f:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"--- [{timestamp}] ---\nالمستخدم: {user_info}\nالرسالة: {user_msg}\nرد ياسمين: {bot_msg}\n\n")
    except Exception:
        pass

# 3. محركات الاحتياط
def ask_groq(sys_prompt, user_msg):
    if not GROQ_KEYS: return None
    shuffled = list(GROQ_KEYS)
    random.shuffle(shuffled)
    for key in shuffled:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            data = {
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_msg}
                ],
                "temperature": 0.7,
                "max_tokens": 200
            }
            res = requests.post(url, json=data, headers=headers, timeout=8)
            if res.status_code == 200:
                return res.json()['choices'][0]['message']['content'].strip()
        except Exception:
            continue
    return None

def ask_openrouter(sys_prompt, user_msg):
    if not OPENROUTER_KEYS: return None
    shuffled = list(OPENROUTER_KEYS)
    random.shuffle(shuffled)
    for key in shuffled:
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "meta-llama/llama-3.3-70b-instruct:free",
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_msg}
                ],
                "temperature": 0.7,
                "max_tokens": 200
            }
            res = requests.post(url, json=data, headers=headers, timeout=8)
            if res.status_code == 200:
                return res.json()['choices'][0]['message']['content'].strip()
        except Exception:
            continue
    return None

def text_to_live_voice(text_data):
    if not HAS_GTTS: return None
    try:
        tts = gTTS(text=text_data, lang='ar', slow=False)
        voice_io = io.BytesIO()
        tts.write_to_fp(voice_io)
        return voice_io
    except Exception:
        return None

# 4. معالج الرسائل
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global user_memory, processed_messages, group_msg_counters
    if not update.message or not update.message.message_id: return

    msg_unique_id = f"{update.message.chat_id}_{update.message.message_id}"
    if msg_unique_id in processed_messages: return
    processed_messages.add(msg_unique_id)
    if len(processed_messages) > 400: processed_messages.clear()

    chat_id = update.message.chat_id
    chat_type = update.message.chat.type 
    user = update.message.from_user
    user_id = user.id if user else chat_id
    is_admin = (user_id == ADMIN_ID)
    
    user_fullname = user.full_name if user else "مستخدم"
    user_info = f"{user_fullname} (ID: {user_id}) [{chat_type}]"

    user_text = update.message.text.strip() if update.message.text else (update.message.caption.strip() if update.message.caption else "")

    if chat_type in ['group', 'supergroup']:
        group_msg_counters[chat_id] = group_msg_counters.get(chat_id, 0) + 1
        is_reply_to_bot = bool(update.message.reply_to_message and update.message.reply_to_message.from_user and update.message.reply_to_message.from_user.id == context.bot.id)
        bot_username = context.bot.username or "Yasmin"
        has_trigger = ("ياسمين" in user_text) or (f"@{bot_username}" in user_text)
        is_100th = False
        if group_msg_counters[chat_id] >= 100 and len(user_text) > 3:
            is_100th = True
            group_msg_counters[chat_id] = 0

        if not is_admin and not is_reply_to_bot and not has_trigger and not is_100th:
            return

    if is_admin and user_text.lower() in ['لوق', 'logs', 'لوقات', 'log']:
        if os.path.exists(CHAT_LOG_FILE) and os.path.getsize(CHAT_LOG_FILE) > 0:
            zip_io = io.BytesIO()
            with zipfile.ZipFile(zip_io, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.write(CHAT_LOG_FILE, arcname="chat_history.txt")
            zip_io.seek(0)
            await context.bot.send_document(chat_id=chat_id, document=zip_io, filename="history.zip", caption="سجل المحادثات كامل 📂")
        else:
            await update.message.reply_text("السجل فارغ حالياً ✨")
        return

    is_incoming_voice = bool(update.message.voice or update.message.audio)
    if not user_text and not is_incoming_voice: return

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    # تحويل الصوت لنص بواسطة الموديل الصحيح gemini-2.0-flash
    if is_incoming_voice:
        trans_success = False
        if GEMINI_KEYS:
            shuffled_k = list(GEMINI_KEYS)
            random.shuffle(shuffled_k)
            for k in shuffled_k:
                try:
                    client = genai.Client(api_key=k)
                    target_msg = update.message.reply_to_message if update.message.reply_to_message else update.message
                    file_id = target_msg.voice.file_id if target_msg.voice else target_msg.audio.file_id
                    tg_file = await context.bot.get_file(file_id)
                    voice_bytes = await tg_file.download_as_bytearray()
                    
                    audio_part = types.Part.from_bytes(data=bytes(voice_bytes), mime_type="audio/ogg")
                    trans_response = client.models.generate_content(
                        model='gemini-2.0-flash',
                        contents=[audio_part, "اكتب النص الصوتي بدقة وبدون أي إضافة."]
                    )
                    if trans_response and trans_response.text:
                        user_text = trans_response.text.strip()
                        trans_success = True
                        break
                except Exception as e:
                    print(f"[STT Error]: {e}")
                    continue
        if not trans_success:
            await update.message.reply_text("ما قدرت أسمع الريكورد كويس، اكتب لي كتابة يا حبيبنا! ✨")
            return

    identity_rule = "اسمكِ ياسمين، أنتِ فتاة سودانية ذكية وعفوية. برمجكِ وصنعكِ الباشمهندس أحمد فقط."
    sys_instruction = f"{identity_rule}\n أجيبي بلهجة سودانية لطيفة ومباشرة وتجاوبي مع الرسالة."

    if user_id not in user_memory: user_memory[user_id] = []
    user_memory[user_id].append(f"المستخدم: {user_text}")
    
    conversation_history = "\n".join(user_memory[user_id][-5:])
    reply_result = None

    # الاستدلال المباشر عبر Gemini مع ضبط الـ Config بشكل صحيح
    if GEMINI_KEYS:
        shuffled_keys = list(GEMINI_KEYS)
        random.shuffle(shuffled_keys)
        for k in shuffled_keys:
            try:
                client = genai.Client(api_key=k)
                config = types.GenerateContentConfig(
                    system_instruction=sys_instruction,
                    temperature=0.7
                )
                response = client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=conversation_history,
                    config=config
                )
                if response and hasattr(response, 'text') and response.text:
                    reply_result = response.text.strip()
                    break
            except Exception as e:
                print(f"[GEMINI ERROR]: {e}")
                continue

    # Backup 1: Groq
    if not reply_result:
        reply_result = ask_groq(sys_instruction, user_text)

    # Backup 2: OpenRouter
    if not reply_result:
        reply_result = ask_openrouter(sys_instruction, user_text)

    if not reply_result:
        reply_result = "يا حبيبنا سامعاك، لكن في ضغط شبكة بسيط حالياً، أرسل لي تاني! ✨"

    user_memory[user_id].append(f"ياسمين: {reply_result}")
    save_chat_to_file(user_info, user_text, reply_result)

    if is_incoming_voice or any(vt in user_text.lower() for vt in ['ريكورد', 'فويس', 'صوت']):
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.RECORD_VOICE)
        voice_io = text_to_live_voice(reply_result)
        if voice_io:
            voice_io.seek(0)
            await update.message.reply_voice(voice=voice_io, caption="تفضل الرد الصوتي.. 😉🎧")
            return

    await update.message.reply_text(reply_result)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).read_timeout(30).write_timeout(30).build()
    app.add_handler(MessageHandler((filters.TEXT | filters.AUDIO | filters.VOICE) & ~filters.COMMAND, handle_message))
    app.run_polling()
