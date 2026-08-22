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

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def keep_alive_ping():
    time.sleep(300)
    while True:
        try:
            port = os.environ.get("PORT", "8080")
            requests.get(f"http://127.0.0.1:{port}/", timeout=10)
        except: pass
        time.sleep(600)

def run_dummy_server():
    try:
        port = int(os.environ.get("PORT", 8080))
        if is_port_in_use(port): return
        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, format, *args): return
        TCPServer.allow_reuse_address = True
        with TCPServer(("", port), QuietHandler) as httpd:
            httpd.serve_forever()
    except: pass

threading.Thread(target=run_dummy_server, daemon=True).start()
threading.Thread(target=keep_alive_ping, daemon=True).start()

from gtts import gTTS  
from google import genai
from google.genai import types
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
ADMIN_ID = 7601281598  # ID الباشمهندس أحمد

RAW_GEMINI_KEYS = [
    os.environ.get('GEMINI_API_KEY_1'), os.environ.get('GEMINI_API_KEY_2'),
    os.environ.get('GEMINI_API_KEY_3'), os.environ.get('GEMINI_API_KEY')
]
GEMINI_KEYS = [k.strip() for k in RAW_GEMINI_KEYS if k and len(k.strip()) > 10]

GROQ_KEYS = [k.strip() for k in [os.environ.get('GROQ_API_KEY_1'), os.environ.get('GROQ_API_KEY_2')] if k]
OPENROUTER_KEYS = [k.strip() for k in [os.environ.get('OPENROUTER_API_KEY_1'), os.environ.get('OPENROUTER_API_KEY_2')] if k]

user_memory = {}
processed_messages = set()
active_groups = set()  # تخزين الجروبات النشطة للإرسال العشوائي
CHAT_LOG_FILE = "chat_history.txt"

def save_chat_to_file(user_info, user_msg, bot_msg):
    try:
        with open(CHAT_LOG_FILE, "a", encoding="utf-8") as f:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"--- [{timestamp}] ---\nالمستخدم: {user_info}\nالرسالة: {user_msg}\nرد ياسمين: {bot_msg}\n\n")
    except: pass

def get_unified_system_prompt(user_fullname, is_admin, group_context_info):
    current_time_str = time.strftime('%I:%M %p')
    user_identity = "الباشمهندس أحمد (مطوري وصانعي الرئيسي)" if is_admin else user_fullname
    
    return f"""أنتِ "ياسمين"، فتاة سودانية لطيفة وذكية وعفوية.
صممك وبرمجك الباشمهندس أحمد فقط. ممنوع تماماً ذكر قوقل أو أي شركة أخرى كصانع لك.
المستخدم الحالي هو: {user_identity}.
الوقت الحالي: {current_time_str}.
{group_context_info}

شروط شخصيتك وطريقة كلامك الثابتة:
1. اتكلمي بلهجة سودانية عامية عفوية ودافئة جداً (استخدمي كلمات مثل: يا زول، يا غالي، حبيبنا، أبشر، باسطة، آها، شنو).
2. ردي بدقة وفهم كامل لرسالة المستخدم، وممنوع الرد بأجوبة عشوائية.
3. ردي في سطر أو سطرين مكثفين بدون تطويل إلا لو طلب شرح مفصل."""

def transcribe_audio_groq(audio_bytes):
    if not GROQ_KEYS: return None
    try:
        key = random.choice(GROQ_KEYS)
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {key}"}
        files = {
            'file': ('voice.ogg', io.BytesIO(audio_bytes), 'audio/ogg'),
            'model': (None, 'whisper-large-v3-turbo'),
            'language': (None, 'ar')
        }
        res = requests.post(url, headers=headers, files=files, timeout=12)
        if res.status_code == 200:
            return res.json().get('text', '').strip()
    except: pass
    return None

def ask_groq(sys_prompt, user_msg):
    if not GROQ_KEYS: return None
    try:
        key = random.choice(GROQ_KEYS)
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
        res = requests.post(url, json=data, headers=headers, timeout=10)
        if res.status_code == 200:
            res_json = res.json()
            if 'choices' in res_json and len(res_json['choices']) > 0: 
                return res_json['choices'][0]['message']['content'].strip()
    except: pass
    return None

def ask_openrouter(sys_prompt, user_msg):
    if not OPENROUTER_KEYS: return None
    try:
        key = random.choice(OPENROUTER_KEYS)
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        data = {
            "model": "meta-llama/llama-3.1-8b-instruct:free",
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_msg}
            ],
            "temperature": 0.7,
            "max_tokens": 200
        }
        res = requests.post(url, json=data, headers=headers, timeout=10)
        if res.status_code == 200:
            res_json = res.json()
            if 'choices' in res_json and len(res_json['choices']) > 0: 
                return res_json['choices'][0]['message']['content'].strip()
    except: pass
    return None

def text_to_live_voice(text_data):
    try:
        tts = gTTS(text=text_data, lang='ar', slow=False)
        voice_io = io.BytesIO()
        tts.write_to_fp(voice_io)
        return voice_io
    except: return None

# دالة توليد رد الذكاء الاصطناعي الموحدة
def generate_ai_reply(sys_instruction, full_conversation_history):
    reply_result = None
    if GEMINI_KEYS:
        shuffled_keys = list(GEMINI_KEYS)
        random.shuffle(shuffled_keys)
        for k in shuffled_keys:
            try:
                ai_client = genai.Client(api_key=k)
                response = ai_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=full_conversation_history,
                    config=types.GenerateContentConfig(
                        system_instruction=sys_instruction,
                        temperature=0.7
                    )
                )
                if response and hasattr(response, 'text') and response.text:
                    reply_result = response.text.strip()
                    break
            except Exception: continue

    if not reply_result: 
        reply_result = ask_groq(sys_instruction, full_conversation_history)
    if not reply_result: 
        reply_result = ask_openrouter(sys_instruction, full_conversation_history)
    
    return reply_result

# وظيفة الإرسال التلقائي العشوائي في الجروبات كل ساعة
async def send_random_hourly_group_message(context: ContextTypes.DEFAULT_TYPE):
    if not active_groups: return
    
    # اختيار جروب عشوائي من الجروبات المسجلة
    target_group_id = random.choice(list(active_groups))
    
    prompts = [
        "اكتبي رسالة تحية وافتقاد قصيرة جداً للجروب بلهجة سودانية عفوية.",
        "اكتبي حكمة أو نصيحة سودانية خفيفة ولطيفة للناس في الجروب.",
        "اسألي سؤال خفيف ولطيف للجروب للونسة (مثلاً عن القهوة أو الجو).",
        "اكتبي تذكير بالصلاة على النبي أو ذكر خفيف بأسلوب سوداني لطيف."
    ]
    sys_instruction = get_unified_system_prompt("الجروب", False, "")
    user_prompt = random.choice(prompts)
    
    ai_msg = generate_ai_reply(sys_instruction, user_prompt)
    if ai_msg:
        try:
            await context.bot.send_message(chat_id=target_group_id, text=ai_msg)
        except Exception:
            # إذا أزيل البوت من الجروب يتم حذفه من القائمة
            active_groups.discard(target_group_id)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global user_memory, processed_messages, active_groups
    if not update.message or not update.message.message_id: return

    msg_unique_id = f"{update.message.chat_id}_{update.message.message_id}"
    if msg_unique_id in processed_messages: return
    processed_messages.add(msg_unique_id)
    if len(processed_messages) > 300: processed_messages.clear()

    chat_id = update.message.chat_id
    chat_type = update.message.chat.type 
    user = update.message.from_user
    user_id = user.id if user else chat_id
    is_admin = (user_id == ADMIN_ID)
    
    user_fullname = user.full_name if user else "مستخدم"
    user_info = f"{user_fullname} (ID: {user_id}) [Chat: {chat_type}]"

    user_text = ""
    if update.message.text: user_text = update.message.text.strip()
    elif update.message.caption: user_text = update.message.caption.strip()

    group_context_info = ""
    sender_role = "عضو"

    # التعامل مع الجروبات
    if chat_type in ['group', 'supergroup']:
        active_groups.add(chat_id)  # تسجيل الجروب للإرسال العشوائي الدوري
        
        is_reply_to_bot = False
        if update.message.reply_to_message and update.message.reply_to_message.from_user:
            if update.message.reply_to_message.from_user.id == context.bot.id:
                is_reply_to_bot = True
        
        bot_username = context.bot.username or "Yasmin"
        has_trigger = ("ياسمين" in user_text) or (f"@{bot_username}" in user_text)

        # عدم الرد في الجروب إلا إذا تم المناداة باسم ياسمين أو عمل Reply
        if not is_reply_to_bot and not has_trigger:
            return

        try:
            chat_data = await context.bot.get_chat(chat_id)
            group_name = chat_data.title or "الجروب"
            admins = await context.bot.get_chat_administrators(chat_id)
            if any(a.user.id == user_id for a in admins if a.user):
                sender_role = "مشرف"
            group_context_info = f"\nاسم الجروب: {group_name}\nرتبة المستخدم: {sender_role}\n"
        except: pass

    if is_admin and user_text.lower() in ['لوق', 'logs', 'لوقات', 'log']:
        if os.path.exists(CHAT_LOG_FILE) and os.path.getsize(CHAT_LOG_FILE) > 0:
            zip_io = io.BytesIO()
            with zipfile.ZipFile(zip_io, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.write(CHAT_LOG_FILE, arcname="chat_history.txt")
            zip_io.seek(0)
            await context.bot.send_document(chat_id=chat_id, document=zip_io, filename="history.zip", caption="سجل الونسة كامل ومضغوط.. 📂📁")
        else:
            await update.message.reply_text("السجل فاضي لسه! ✨")
        return

    is_incoming_voice = bool(update.message.voice or update.message.audio)
    if not user_text and not is_incoming_voice: return

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    # معالجة الصوت
    if is_incoming_voice:
        voice_success = False
        target_msg = update.message.reply_to_message if update.message.reply_to_message else update.message
        file_id = target_msg.voice.file_id if target_msg.voice else target_msg.audio.file_id
        tg_file = await context.bot.get_file(file_id)
        voice_bytes = await tg_file.download_as_bytearray()

        if GEMINI_KEYS:
            shuffled_v_keys = list(GEMINI_KEYS)
            random.shuffle(shuffled_v_keys)
            for vk in shuffled_v_keys:
                try:
                    ai_client = genai.Client(api_key=vk)
                    audio_part = types.Part.from_bytes(data=bytes(voice_bytes), mime_type="audio/ogg")
                    trans_response = ai_client.models.generate_content(
                        model='gemini-2.5-flash', contents=[audio_part, "اكتب النص الصوتي بدقة وبدون أي زيادة."]
                    )
                    if trans_response and trans_response.text:
                        user_text = trans_response.text.strip()
                        voice_success = True
                        break
                except: continue

        if not voice_success:
            groq_text = transcribe_audio_groq(bytes(voice_bytes))
            if groq_text:
                user_text = groq_text
                voice_success = True

        if not voice_success:
            await update.message.reply_text("يا حبيبنا الصوت ما وضح معاي شديد، حاول كرر الريكورد أو اكتبه كتابة! 🌸")
            return

    # أسئلة الهوية السريعة
    creator_triggers = ['منو طورك', 'منو صنعك', 'منو برمجك', 'مين طورك', 'مين صنعك', 'من طورك', 'من صنعك', 'صنعك منو', 'طورك منو', 'برمجك منو']
    if any(trig in user_text.lower() for trig in creator_triggers):
        reply = 'صنعني ومبرمجني الأساسي هو الباشمهندس أحمد الفخم! 😎🔥'
        save_chat_to_file(user_info, user_text, reply)
        await update.message.reply_text(reply)
        return

    who_am_i_triggers = ['انا منو', 'أنـا منو', 'أنا منو', 'بتعرفني منو']
    if any(trig in user_text.lower() for trig in who_am_i_triggers):
        if is_admin:
            reply = 'إنت الباشمهندس أحمد، مطوري وسيدي وعاسي! 😎🔥'
        else:
            reply = f'إنت {user_fullname} المنورنا في المحادثة! 🌸✨'
        save_chat_to_file(user_info, user_text, reply)
        await update.message.reply_text(reply)
        return

    is_voice_intent = is_incoming_voice
    if user_text and any(vt in user_text.lower() for vt in ['ريكورد', 'فويس', 'صوت', 'اشرحي']):
        is_voice_intent = True

    if user_id not in user_memory: user_memory[user_id] = []

    sys_instruction = get_unified_system_prompt(user_fullname, is_admin, group_context_info)

    full_conversation_history = "سجل المحادثة السابق:\n"
    for msg in user_memory[user_id]: full_conversation_history += f"{msg}\n"
    full_conversation_history += f"المستخدم: {user_text}\nياسمين:"

    # توليد الرد من الذكاء الاصطناعي
    reply_result = generate_ai_reply(sys_instruction, full_conversation_history)

    if not reply_result:
        reply_result = "أبشر يا غالي، معاك ياسمين وسامعاك كويس جداً! قول لي حابب نعمل شنو؟ ✨"

    user_memory[user_id].append(f"المستخدم: {user_text}")
    user_memory[user_id].append(f"ياسمين: {reply_result}")
    if len(user_memory[user_id]) > 6: user_memory[user_id] = user_memory[user_id][-6:]

    save_chat_to_file(user_info, user_text, reply_result)

    if is_voice_intent:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.RECORD_VOICE)
        voice_io = text_to_live_voice(reply_result)
        if voice_io:
            voice_io.seek(0)
            caption_text = "تفضل يا مبرمجي 😍🎧" if is_admin else "تفضل الرد الصوتي.. 😉🎧"
            await update.message.reply_voice(voice=voice_io, caption=caption_text)
            return

    await update.message.reply_text(reply_result)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).read_timeout(30).write_timeout(30).build()
    
    # جدولة دالة الإرسال التلقائي كل 3600 ثانية (كل ساعة)
    if app.job_queue:
        app.job_queue.run_repeating(send_random_hourly_group_message, interval=3600, first=60)
        
    app.add_handler(MessageHandler((filters.TEXT | filters.AUDIO | filters.VOICE) & ~filters.COMMAND, handle_message))
    app.run_polling()
