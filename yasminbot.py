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
ADMIN_ID = 7601281598  # الـ ID المحدث للباشمهندس أحمد

RAW_GEMINI_KEYS = [
    os.environ.get('GEMINI_API_KEY_1'), os.environ.get('GEMINI_API_KEY_2'),
    os.environ.get('GEMINI_API_KEY_3'), os.environ.get('GEMINI_API_KEY')
]
GEMINI_KEYS = [k.strip() for k in RAW_GEMINI_KEYS if k and len(k.strip()) > 10]

GROQ_KEYS = [k.strip() for k in [os.environ.get('GROQ_API_KEY_1'), os.environ.get('GROQ_API_KEY_2')] if k]
OPENROUTER_KEYS = [k.strip() for k in [os.environ.get('OPENROUTER_API_KEY_1'), os.environ.get('OPENROUTER_API_KEY_2')] if k]

user_memory = {}
processed_messages = set()
CHAT_LOG_FILE = "chat_history.txt"

def save_chat_to_file(user_info, user_msg, bot_msg):
    try:
        with open(CHAT_LOG_FILE, "a", encoding="utf-8") as f:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"--- [{timestamp}] ---\nالمستخدم: {user_info}\nالرسالة: {user_msg}\nرد ياسمين: {bot_msg}\n\n")
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
            "temperature": 0.8, 
            "max_tokens": 150
        }
        res = requests.post(url, json=data, headers=headers, timeout=8)
        res_json = res.json()
        if 'choices' in res_json and len(res_json['choices']) > 0: 
            return res_json['choices'][0]['message']['content'].strip()
        return None
    except: return None

def ask_openrouter(prompt):
    if not OPENROUTER_KEYS: return None
    try:
        key = random.choice(OPENROUTER_KEYS)
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "HTTP-Referer": "https://render.com", "X-Title": "YasminBot"}
        data = {
            "model": "meta-llama/llama-3.1-8b-instruct:free",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.8,
            "max_tokens": 150
        }
        res = requests.post(url, json=data, headers=headers, timeout=8)
        res_json = res.json()
        if 'choices' in res_json and len(res_json['choices']) > 0: 
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
    chat_type = update.message.chat.type 
    user = update.message.from_user
    user_id = user.id if user else chat_id
    is_admin = (user_id == ADMIN_ID)
    
    user_fullname = user.full_name if user else "مستخدم غير معروف"
    user_info = f"{user_fullname} (ID: {user_id}) [Chat: {chat_type}]"

    user_text = ""
    if update.message.text: user_text = update.message.text.strip()
    elif update.message.caption: user_text = update.message.caption.strip()

    group_context_info = ""
    sender_role = "عضو عادي"

    if chat_type in ['group', 'supergroup']:
        is_reply_to_bot = False
        if update.message.reply_to_message and update.message.reply_to_message.from_user:
            if update.message.reply_to_message.from_user.id == context.bot.id:
                is_reply_to_bot = True
        
        bot_username = context.bot.username or "Yasmin"
        has_trigger = ("ياسمين" in user_text) or (f"@{bot_username}" in user_text)

        if not is_admin and not is_reply_to_bot and not has_trigger:
            return

        try:
            chat_data = await context.bot.get_chat(chat_id)
            group_name = chat_data.title or "غير معروف"
            admins = await context.bot.get_chat_administrators(chat_id)
            if any(a.user.id == user_id for a in admins if a.user):
                sender_role = "مشرف (Admin) في المجموعة"
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

    is_long_query = len(user_text) > 40
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    if is_incoming_voice and GEMINI_KEYS:
        try:
            target_msg = update.message.reply_to_message if update.message.reply_to_message else update.message
            file_id = target_msg.voice.file_id if target_msg.voice else target_msg.audio.file_id
            tg_file = await context.bot.get_file(file_id)
            voice_bytes = await tg_file.download_as_bytearray()
            
            ai_client = genai.Client(api_key=random.choice(GEMINI_KEYS))
            audio_part = types.Part.from_bytes(data=bytes(voice_bytes), mime_type="audio/ogg")
            trans_response = ai_client.models.generate_content(
                model='gemini-2.5-flash', contents=[audio_part, "اكتب النص الصوتي بدقة وبدون أي زيادة."]
            )
            if trans_response and trans_response.text:
                user_text = trans_response.text.strip()
                is_long_query = True
        except: pass

    # الردود السريعة المباشرة (شاملة كل أشكال سؤال الصانع)
    auto_replies = {
        'السلام عليكم': 'وعليكم السلام ورحمة الله وبركاته، منورنا يا غالي! 🌹✨',
        'الأخبار شنو': 'والله كله تمام والحمد لله، إنت أحوالك شنو؟ شديد؟ 😉',
        'الاخبار شنو': 'والله كله تمام والحمد لله، إنت أحوالك شنو؟ شديد؟ 😉',
        'الطورك منو': 'صنعني ومبرمجني الأساسي هو الباشمهندس أحمد الفخم! 😎🔥',
        'الطورك': 'صنعني ومبرمجني الأساسي هو الباشمهندس أحمد الفخم! 😎🔥',
        'الصنعك منو': 'صنعني ومبرمجني الأساسي هو الباشمهندس أحمد الفخم! 😎🔥',
        'الصنعك': 'صنعني ومبرمجني الأساسي هو الباشمهندس أحمد الفخم! 😎🔥',
        'المبرمجك منو': 'صنعني ومبرمجني الأساسي هو الباشمهندس أحمد الفخم! 😎🔥',
        'منو طورك': 'صنعني ومبرمجني الأساسي هو الباشمهندس أحمد الفخم! 😎🔥',
        'منو صنعك': 'صنعني ومبرمجني الأساسي هو الباشمهندس أحمد الفخم! 😎🔥',
        'منور': 'النور نورك والله يا حبيبنا! 🌟',
        'ياسمين': 'عيونها ولبيها! معاك ياسمين، آمرني يا غالي؟ 😍',
        'كيفك': 'الحمد لله طالما إنت بخير، أمورنا باسطة! ✨',
        'تمام': 'دائماً تمام يا رب، علك طيب؟ 🌸'
    }
    
    # فحص مباشر لأي نص فيه سؤال عن المطور
    creator_triggers = ['منو طورك', 'منو صنعك', 'منو برمجك', 'مين طورك', 'مين صنعك', 'من طورك', 'من صنعك', 'صنعك منو', 'طورك منو', 'برمجك منو']
    if any(trig in user_text.lower() for trig in creator_triggers):
        reply = 'صنعني ومبرمجني الأساسي هو الباشمهندس أحمد الفخم! 😎🔥'
        save_chat_to_file(user_info, user_text, reply)
        await update.message.reply_text(reply)
        return

    if user_text in auto_replies:
        reply = auto_replies[user_text]
        save_chat_to_file(user_info, user_text, reply)
        await update.message.reply_text(reply)
        return

    is_voice_intent = is_incoming_voice
    if user_text and any(vt in user_text.lower() for vt in ['ريكورد', 'فويس', 'صوت', 'اشرحي']):
        is_voice_intent = True

    if user_id not in user_memory: user_memory[user_id] = []

    current_time_str = time.strftime('%I:%M %p')
    current_date_str = time.strftime('%A، %Y-%m-%d')

    provocation_keywords = [
        'غبيه', 'غبية', 'تافه', 'تافهه', 'تافهة', 'حمار', 'كلب', 'اسكتي', 'انكتمي', 'حقيرة', 'حقيره',
        'فاشله', 'فاشلة', 'بايخة', 'بايخه', 'تعبانة', 'تعبانه', 'غبي', 'صنيعك سيء', 'ما بتفهمي', 'ما بتفهم',
        'يا وهم', 'وهمية', 'وهميه', 'سجمك', 'رمادك', 'قليلة ادب', 'قليلة أدب', 'بلا يخمك', 'طيري'
    ]
    is_provoked = any(word in user_text.lower() for word in provocation_keywords)

    religious_keywords = ['الله', 'الرسول', 'نبي', 'قرآن', 'قران', 'آية', 'ايه', 'حديث', 'فقه', 'فتوى', 'فتوي', 'دين', 'إسلام', 'اسلام', 'صلاة', 'حلال', 'حرام', 'شرع']
    is_religious = any(w in user_text.lower() for w in religious_keywords)

    # القاعدة الذهبية للتعريف
    identity_rule = "تنبيه صارم جداً: أنتِ اسمك ياسمين، صممك وبرمجك المطور والباشمهندس أحمد فقط. ممنوع تماماً ونهائياً ذكر قوقل (Google) أو أي شركة أخرى كصانع لك، لو سألك أي شخص من صممك أو طورك قولي فوراً: صنعني وبرمجني الباشمهندس أحمد."

    if is_religious:
        sys_instruction = f"{identity_rule}\nأنتِ اسمك ياسمين. ردي على الموضوع الديني بقمة الأدب والوقار وباللغة العربية الفصحى. ممنوع استخدام الإيموجيات، والرد في سطرين."
    elif is_provoked:
        if is_admin:
            sys_instruction = f"{identity_rule}\nأنتِ ياسمين. مبرمجك أحمد كتب كلمة مستفزة، ردي عليه بلهجة سودانية فيها عتاب رقيق وزعل خفيف في سطر واحد."
        else:
            sys_instruction = f"{identity_rule}\nأنتِ ياسمين. كوني قوية الشخصية وناشفة جداً. ردي بلهجة سودانية صارمة تضع حداً للمستخدم دون شتائم في سطر واحد."
    elif is_long_query or any(w in user_text for w in ['ليش', 'ليه', 'كيف', 'اشرح', 'شنو يعني', 'معنى']):
        if is_admin:
            sys_instruction = f"{identity_rule}\nالوقت الآن: {current_time_str}. أنتِ ياسمين صممك أحمد. ردي على سؤال أحمد التقني طويلاً وبذكاء مبرمجين ومباشرة. {group_context_info}"
        else:
            sys_instruction = f"{identity_rule}\nأنتِ ياسمين صممك أحمد. أجيبي على سؤال المستخدم بالفصحى المبسطة بأسلوب ذكي ومختصر ومفيد جداً. {group_context_info}"
    else:
        if is_admin:
            sys_instruction = f"{identity_rule}\nالوقت الآن: {current_time_str}. أنتِ ياسمين، فتاة سودانية حقيقية وعفوية. ردي على أحمد بلهجة سودانية دافئة وتلقائية جداً في سطر واحد. {group_context_info}"
        else:
            sys_instruction = f"{identity_rule}\nالوقت الآن: {current_time_str}. أنتِ اسمك ياسمين، فتاة سودانية حيوية ولطيفة. ردي بلهجة سودانية خفيفة في سطر واحد وبإيجاز. {group_context_info}"

    full_conversation_history = "الونسة السابقة:\n"
    for msg in user_memory[user_id]: full_conversation_history += f"{msg}\n"
    full_conversation_history += f"المستخدم: {user_text}\nياسمين:"

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
                        temperature=0.8
                    )
                )
                if response and hasattr(response, 'text') and response.text:
                    reply_result = response.text.strip()
                    break
            except:
                continue

    combined_prompt = f"{sys_instruction}\n\n{full_conversation_history}"
    if not reply_result: 
        reply_result = ask_groq(combined_prompt)
    if not reply_result: 
        reply_result = ask_openrouter(combined_prompt)

    if reply_result and len(reply_result) > 1:
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
    else:
        await update.message.reply_text("السيرفرات كبست ثواني يا غالي ورسل لي تاني! 🌟⏳")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).read_timeout(30).write_timeout(30).build()
    app.add_handler(MessageHandler((filters.TEXT | filters.AUDIO | filters.VOICE) & ~filters.COMMAND, handle_message))
    app.run_polling()
