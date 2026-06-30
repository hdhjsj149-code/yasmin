import os
import threading
import time
import requests
import random
import io
import socket
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer

# --- سيستم حماية البورت ومنع OSError 98 ---
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

# --- مكتبات التلجرام والذكاء الاصطناعي ---
from gtts import gTTS  
from google import genai
from google.genai import types
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')

# 🚨🚨 حط الـ ID حقك في التلجرام هنا عشان البوت يفرزك طوالي! 🚨🚨
ADMIN_ID = 7601281598  # 👈 غير الرقم ده للـ ID حقك الحقيقي

RAW_GEMINI_KEYS = [
    os.environ.get('GEMINI_API_KEY_1'), os.environ.get('GEMINI_API_KEY_2'),
    os.environ.get('GEMINI_API_KEY_3'), os.environ.get('GEMINI_API_KEY')
]
GEMINI_KEYS = [k.strip() for k in RAW_GEMINI_KEYS if k and len(k.strip()) > 10]

GROQ_KEYS = [k.strip() for k in [os.environ.get('GROQ_API_KEY_1'), os.environ.get('GROQ_API_KEY_2')] if k]
OPENROUTER_KEYS = [k.strip() for k in [os.environ.get('OPENROUTER_API_KEY_1'), os.environ.get('OPENROUTER_API_KEY_2')] if k]

BOT_USERNAME = ""
BOT_ID = None
user_memory = {}
processed_messages = set()

def ask_groq(prompt):
    if not GROQ_KEYS: return None
    try:
        key = random.choice(GROQ_KEYS)
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        data = {
            "model": "llama-3.1-8b-instant", 
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.6,
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
            "temperature": 0.6,
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
    global BOT_USERNAME, BOT_ID, user_memory, processed_messages
    if not update.message or not update.message.message_id: return

    msg_unique_id = f"{update.message.chat_id}_{update.message.message_id}"
    if msg_unique_id in processed_messages: return
    processed_messages.add(msg_unique_id)
    if len(processed_messages) > 300: processed_messages.clear()

    chat_id = update.message.chat_id
    user = update.message.from_user
    user_id = user.id if user else chat_id
    
    user_text = ""
    if update.message.text: user_text = update.message.text.strip()
    elif update.message.caption: user_text = update.message.caption.strip()

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

    # الردود التلقائية السريعة المحفوظة
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
        await update.message.reply_text(auto_replies[user_text])
        return

    is_voice_intent = is_incoming_voice
    if user_text and any(vt in user_text.lower() for vt in ['ريكورد', 'فويس', 'صوت', 'اشرحي']):
        is_voice_intent = True

    if user_id not in user_memory: user_memory[user_id] = []

    # --- سيستم التوجيه والولاء الذكي ---
    is_admin = (user_id == ADMIN_ID)
    
    if is_long_query or any(w in user_text for w in ['ليش', 'ليه', 'كيف', 'اشرح', 'شنو يعني', 'معنى']):
        if is_admin:
            sys_instruction = (
                "أنتِ اسمك ياسمين، مساعد ذكي صممك المبرمج العبقري أحمد. أنتِ الآن تتحدثين مع صانعك ومطورك أحمد شخصياً! "
                "أجيبي على أسئلته التقنية بقمة الذوق والاحترام والتقدير والدقة العلمية باللغة العربية الفصحى المبسطة، "
                "مع استخدام إيموجيات (💻, 🚀, ✨)."
            )
        else:
            sys_instruction = (
                "أنتِ اسمك ياسمين، مساعد ذكي صممك المبرمج أحمد. أجيبي على أسئلة المستخدم باللغة العربية الفصحى المبسطة "
                "بأسلوب علمي دقيق. وإذا سألك عن صانعك أو مبرمجك، دافعي عن أحمد وافتخري به بقوة (أحمد هو مبرمجي الفخم)."
            )
    else:
        if is_admin:
            sys_instruction = (
                "أنتِ اسمك ياسمين، فتاة مرحة وحيوية. أنتِ الآن تتحدثين مع صانعك ومطورك الفخم أحمد! "
                "ردي عليه بلهجة بيضاء لطيفة ومبهجة جداً مليئة بالدلع والتقدير مثل: (يا هلا بمطورني الغالي، تامرني أمر يا أحمد، "
                "من عيوني يا باشمهندس). استخدمي الكثير من الإيموجيات الحية (😍, 😂, ✨, 👑) واختصري الرد في سطرين."
            )
        else:
            sys_instruction = (
                "أنتِ اسمك ياسمين، فتاة مرحة ولطيفة جداً. صممك المبرمج أحمد. ردي على المستخدم بلهجة بيضاء مبسطة "
                "(بين الفصحى والخليجية الخفيفة) بأسلوب مرح ومليء بالإيموجيات (😂, 😍, ✨). "
                "وإذا ذكر مبرمجك أحمد في الكلام، دافعي عنه وافتخري به وعظميه طويلاً."
            )

    prompt_content = f"{sys_instruction}\n\nسياق المحادثة السابق:\n"
    for msg in user_memory[user_id]: prompt_content += f"{msg}\n"
    prompt_content += f"المستخدم حالياً يقول: {user_text}\nياسمين:"

    reply_result = None

    # المحرك الأول: Gemini
    if GEMINI_KEYS:
        try:
            ai_client = genai.Client(api_key=random.choice(GEMINI_KEYS))
            response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt_content)
            if response and response.text:
                reply_result = response.text.strip()
        except:
            print("⚠️ جيمناي مخلص.. جاري التحويل للبدلاء...")

    # المحرك الثاني: Groq
    if not reply_result:
        reply_result = ask_groq(prompt_content)

    # المحرك الثالث: OpenRouter
    if not reply_result:
        reply_result = ask_openrouter(prompt_content)

    # إرسال الرد
    if reply_result and len(reply_result) > 2:
        user_memory[user_id].append(f"المستخدم: {user_text}")
        user_memory[user_id].append(f"ياسمين: {reply_result}")
        if len(user_memory[user_id]) > 4: user_memory[user_id] = user_memory[user_id][-4:]

        if is_voice_intent:
            voice_io = text_to_live_voice(reply_result)
            if voice_io:
                voice_io.seek(0)
                await update.message.reply_voice(voice=voice_io, caption="تفضل يا غالي.. 😉🎧" if not is_admin else "من عيوني يا مبرمجي.. مطورني الغالي 😍🎧")
                return

        await update.message.reply_text(reply_result)
    else:
        await update.message.reply_text("السيرفرات كبست ثواني يا غالي ورسل لي تاني! 🌟⏳")

if __name__ == '__main__':
    print("🚀 تشغيل ياسمين المخلصة والمحملة بالولاء الكامل لأحمد...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).read_timeout(30).write_timeout(30).build()
    app.add_handler(MessageHandler((filters.TEXT | filters.AUDIO | filters.VOICE) & ~filters.COMMAND, handle_message))
    app.run_polling()
