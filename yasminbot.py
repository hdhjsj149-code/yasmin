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
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')

# 🚨 حط الـ ID حقك في التلجرام هنا عشان تسحب السجل
ADMIN_ID = 7601281598  

RAW_GEMINI_KEYS = [
    os.environ.get('GEMINI_API_KEY_1'), os.environ.get('GEMINI_API_KEY_2'),
    os.environ.get('GEMINI_API_KEY_3'), os.environ.get('GEMINI_API_KEY')
]
GEMINI_KEYS = [k.strip() for k in RAW_GEMINI_KEYS if k and len(k.strip()) > 10]

GROQ_KEYS = [k.strip() for k in [os.environ.get('GROQ_API_KEY_1'), os.environ.get('GROQ_API_KEY_2')] if k]
OPENROUTER_KEYS = [k.strip() for k in [os.environ.get('OPENROUTER_API_KEY_1'), os.environ.get('OPENROUTER_API_KEY_2')] if k]

user_memory = {}
processed_messages = set()

# مسار ملف حفظ المحادثات والونسة
CHAT_LOG_FILE = "chat_history.txt"

# دالة ذكية لحفظ الونسة أول بأول
def save_chat_to_file(user_info, user_msg, bot_msg):
    try:
        with open(CHAT_LOG_FILE, "a", encoding="utf-8") as f:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"--- [{timestamp}] ---\n")
            f.write(f"المستخدم: {user_info}\n")
            f.write(f"الرسالة: {user_msg}\n")
            f.write(f"رد ياسمين: {bot_msg}\n\n")
    except: pass

def ask_groq(prompt):
    if not GROQ_KEYS: return None
    try:
        key = random.choice(GROQ_KEYS)
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        data = {
            "model": "llama-3.1-8b-instant", 
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5,
            "max_tokens": 450
        }
        res = requests.post(url, json=data, headers=headers, timeout=12)
        res_json = res.json()
        if 'choices' in res_json:
            return res_json['choices'][0]['message']['content'].strip()
        return None
    except: return None

def ask_openrouter(prompt):
    if not OPENROUTER_KEYS: return None
    try:
        key = random.choice(OPENROUTER_KEYS)
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://render.com", 
            "X-Title": "YasminBot"
        }
        data = {
            "model": "meta-llama/llama-3.1-8b-instruct:free",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5,
            "max_tokens": 450
        }
        res = requests.post(url, json=data, headers=headers, timeout=12)
        res_json = res.json()
        if 'choices' in res_json:
            return res_json['choices'][0]['message']['content'].strip()
        return None
    except: return None

def text_to_live_voice(text_data):
    try:
        tts = gTTS(text=text_data, lang='ar', slow=False)
        voice_io = io.BytesIO()
        tts.write_to_fp(voice_io)
        return voice_io
    except: return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global user_memory, processed_messages
    if not update.message or not update.message.message_id: return

    msg_unique_id = f"{update.message.chat_id}_{update.message.message_id}"
    if msg_unique_id in processed_messages: return
    processed_messages.add(msg_unique_id)
    if len(processed_messages) > 300: processed_messages.clear()

    chat_id = update.message.chat_id
    user = update.message.from_user
    user_id = user.id if user else chat_id
    
    # تجهيز بيانات المستخدم لعرضها في السجل
    user_fullname = user.full_name if user else "مستخدم غير معروف"
    user_info = f"{user_fullname} (ID: {user_id}) [Chat ID: {chat_id}]"

    user_text = ""
    if update.message.text: user_text = update.message.text.strip()
    elif update.message.caption: user_text = update.message.caption.strip()

    is_admin = (user_id == ADMIN_ID)

    # --- سيستم سحب سجل الونسة والمحادثات مضغوط للآدمين ---
    if is_admin and user_text.lower() in ['لوق', 'logs', 'لوقات', 'log']:
        if os.path.exists(CHAT_LOG_FILE) and os.path.getsize(CHAT_LOG_FILE) > 0:
            zip_io = io.BytesIO()
            with zipfile.ZipFile(zip_io, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.write(CHAT_LOG_FILE, arcname="chat_history.txt")
            zip_io.seek(0)
            await context.bot.send_document(chat_id=chat_id, document=zip_io, filename="history.zip", caption="تفضل يا هندسة، سجل الونسة والمحادثات كامل ومضغوط.. 📂📁")
        else:
            await update.message.reply_text("السجل فاضي لسه، ماف زول اتكلم مع ياسمين هسة! ✨")
        return

    is_incoming_voice = bool(update.message.voice or update.message.audio)
    if not user_text and not is_incoming_voice: return

    is_long_query = len(user_text) > 40

    if is_incoming_voice and GEMINI_KEYS:
        try:
            target_msg = update.message.reply_to_message if update.message.reply_to_message else update.message
            file_id = target_msg.voice.file_id if target_msg.voice else target_msg.audio.file_id
            tg_file = await context.bot.get_file(file_id)
            voice_bytes = await tg_file.download_as_bytearray()
            
            ai_client = genai.Client(api_key=random.choice(GEMINI_KEYS))
            audio_part = types.Part.from_bytes(data=bytes(voice_bytes), mime_type="audio/ogg")
            trans_response = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[audio_part, "اكتب النص الموجود في هذا الريكورد الصوتي بدقة شديدة وبدون أي زيادة من عندك."]
            )
            if trans_response.text:
                user_text = trans_response.text.strip()
                is_long_query = True
        except: pass

    auto_replies = {
        'السلام عليكم': 'وعليكم السلام ورحمة الله وبركاته، منور الجت يا غالي! 🌹',
        'الأخبار شنو': 'كلشي تمام التمام والامور طيبة، إنت كيف أمورك؟ ✨',
        'الاخبار شنو': 'كلشي تمام التمام والامور طيبة، إنت كيف أمورك؟ ✨',
        'الطورك منو': 'طورني وصنعني المبرمج أحمد! 🤖🔥',
        'الصنعك منو': 'صنعني ومبرمجني الأساسي هو الفخم أحمد! 😉💪',
        'منور': 'النور نورك والله يا حبيبنا! 🌟',
        'ياسمين': 'عيونها ولبيها! معاك ياسمين السمحة، آمرني يا غالي? 😍',
        'كيفك': 'تمام التمام والحمد لله، الأمور باسطة! ✨',
        'تمام': 'دائماً تمام يا رب! علك طيب وبخير طوالي؟ 🌸'
    }
    
    if user_text in auto_replies:
        reply = auto_replies[user_text]
        save_chat_to_file(user_info, user_text, reply) # حفظ الردود التلقائية
        await update.message.reply_text(reply)
        return

    is_voice_intent = is_incoming_voice
    if user_text and any(vt in user_text.lower() for vt in ['ريكورد', 'فويس', 'صوت', 'اشرحي']):
        is_voice_intent = True

    if user_id not in user_memory: user_memory[user_id] = []

    religious_keywords = ['الله', 'الرسول', 'نبي', 'قرآن', 'قران', 'آية', 'ايه', 'حديث', 'فقه', 'فتوى', 'فتوي', 'دين', 'إسلام', 'اسلام', 'صلاة', 'حلال', 'حرام', 'شرع']
    is_religious = any(w in user_text.lower() for w in religious_keywords)

    if is_religious:
        sys_instruction = (
            "أنتِ اسمك ياسمين. السؤال الحالي يتعلق بموضوع ديني أو إسلامي. "
            "يجب أن تجيبي بقمة الأدب، الاحترام، والوقار، وباللغة العربية الفصحى الرصينة فقط. "
            "يُمنع منعاً باتاً استخدام أي إيموجيات، رموز تعبيرية، مزاح، أو لهجات عامية في هذا الرد احترماً للموضوع."
        )
    elif is_long_query or any(w in user_text for w in ['ليش', 'ليه', 'كيف', 'اشرح', 'شنو يعني', 'معنى']):
        if is_admin:
            sys_instruction = (
                "أنتِ اسمك ياسمين، مساعدة ذكية ومبرمجة صممك أحمد. المستخدم الحالي هو مبرمجك أحمد نفسه. "
                "أجيبي على سؤاله التقني مباشرة بدقة علمية ممتازة وباللغة العربية الفصحى المبسطة، "
                "دون الحاجة للمدح والثناء الزائد في إجابة السؤال العلمي، مع إيموجيات خفيفة."
            )
        else:
            sys_instruction = (
                "أنتِ اسمك ياسمين، مساعد ذكي صممك المبرمج أحمد. أجيبي على أسئلة المستخدم بالفصحى المبسطة بأسلوب علمي واضح. "
                "وإذا سألك عن صانعك، قولي بفخر أن مبرمجك هو أحمد العبقري."
            )
    else:
        if is_admin:
            sys_instruction = (
                "أنتِ اسمك ياسمين، فتاة حيوية ولطيفة ومرحة. أنتِ تتحدثين مع صانعك أحمد. "
                "ردي عليه بلهجة بيضاء حية ومبسطة وعفوية جداً، جاوبي على ونسته بذكاء واختصار (سطرين بس) ومع إيموجيات (😍, 😂, ✨). "
                "لا تكرري جمل المديح، بل تعاملي معه بأريحية كصديق ومطور ذكي."
            )
        else:
            sys_instruction = (
                "أنتِ اسمك ياسمين، فتاة مرحة ولطيفة. صممك المبرمج أحمد. ردي على المستخدم بلهجة بيضاء خفيفة ومفهومة "
                "في سطرين فقط مع إيموجيات متنوعة (😂, 😍, ✨). كوني ذكية وتفاعلي حسب سياق الونسة."
            )

    prompt_content = f"{sys_instruction}\n\nسياق المحادثة السابق:\n"
    for msg in user_memory[user_id]: prompt_content += f"{msg}\n"
    prompt_content += f"المستخدم حالياً يقول: {user_text}\nياسمين:"

    reply_result = None

    if GEMINI_KEYS:
        try:
            ai_client = genai.Client(api_key=random.choice(GEMINI_KEYS))
            response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt_content)
            if response and response.text:
                reply_result = response.text.strip()
        except: pass

    if not reply_result:
        reply_result = ask_groq(prompt_content)

    if not reply_result:
        reply_result = ask_openrouter(prompt_content)

    if reply_result and len(reply_result) > 2:
        user_memory[user_id].append(f"المستخدم: {user_text}")
        user_memory[user_id].append(f"ياسمين: {reply_result}")
        if len(user_memory[user_id]) > 4: user_memory[user_id] = user_memory[user_id][-4:]

        # حفظ الونسة في السجل النصي
        save_chat_to_file(user_info, user_text, reply_result)

        if is_voice_intent:
            voice_io = text_to_live_voice(reply_result)
            if voice_io:
                voice_io.seek(0)
                caption_text = "تفضل يا مبرمجي 😍🎧" if is_admin else "تفضل ردي الصوتي يا غالي.. 😉🎧"
                await update.message.reply_voice(voice=voice_io, caption=caption_text)
                return

        await update.message.reply_text(reply_result)
    else:
        await update.message.reply_text("السيرفرات كبست ثواني يا غالي ورسل لي تاني! 🌟⏳")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).read_timeout(30).write_timeout(30).build()
    app.add_handler(MessageHandler((filters.TEXT | filters.AUDIO | filters.VOICE) & ~filters.COMMAND, handle_message))
    app.run_polling()
