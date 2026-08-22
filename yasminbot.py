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

# ---------------------------------------------------------
# 1. السيرفر الوهمي والـ Keep-Alive لتفادي إغلاق Render
# ---------------------------------------------------------
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
            def log_message(self, format, *args):
                return
        TCPServer.allow_reuse_address = True
        with TCPServer(("", port), QuietHandler) as httpd:
            httpd.serve_forever()
    except Exception:
        pass

threading.Thread(target=run_dummy_server, daemon=True).start()
threading.Thread(target=keep_alive_ping, daemon=True).start()

# ---------------------------------------------------------
# 2. الاستيرادات وتجهيز المتغيرات
# ---------------------------------------------------------
from gtts import gTTS  
from google import genai
from google.genai import types
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
ADMIN_ID = 7601281598  # المعرف الخاص بالباشمهندس أحمد

# 8 مفاتيح Gemini
RAW_GEMINI_KEYS = [
    os.environ.get('GEMINI_API_KEY_1'), os.environ.get('GEMINI_API_KEY_2'),
    os.environ.get('GEMINI_API_KEY_3'), os.environ.get('GEMINI_API_KEY'),
    os.environ.get('GEMINI_API_KEY_4'), os.environ.get('GEMINI_API_KEY_5'),
    os.environ.get('GEMINI_API_KEY_6'), os.environ.get('GEMINI_API_KEY_7')
]
GEMINI_KEYS = [k.strip() for k in RAW_GEMINI_KEYS if k and len(k.strip()) > 10]

# 2 مفاتيح Groq
GROQ_KEYS = [k.strip() for k in [
    os.environ.get('GROQ_API_KEY_1'), os.environ.get('GROQ_API_KEY_2')
] if k]

# 4 مفاتيح OpenRouter
OPENROUTER_KEYS = [k.strip() for k in [
    os.environ.get('OPENROUTER_API_KEY_1'), os.environ.get('OPENROUTER_API_KEY_2'),
    os.environ.get('OPENROUTER_API_KEY_3'), os.environ.get('OPENROUTER_API_KEY_4')
] if k]

user_memory = {}
processed_messages = set()
group_msg_counters = {}  # عداد الرسائل لكل جروب (لشرط الـ 100 رسالة)
CHAT_LOG_FILE = "chat_history.txt"

def save_chat_to_file(user_info, user_msg, bot_msg):
    try:
        with open(CHAT_LOG_FILE, "a", encoding="utf-8") as f:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"--- [{timestamp}] ---\nالمستخدم: {user_info}\nالرسالة: {user_msg}\nرد ياسمين: {bot_msg}\n\n")
    except Exception:
        pass

# ---------------------------------------------------------
# 3. محركات الـ AI الاحتياطية (Groq & OpenRouter)
# ---------------------------------------------------------
def ask_groq(sys_prompt, user_msg):
    if not GROQ_KEYS:
        return None
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
                "temperature": 0.8, 
                "max_tokens": 180
            }
            res = requests.post(url, json=data, headers=headers, timeout=7)
            if res.status_code == 200:
                res_json = res.json()
                if 'choices' in res_json and len(res_json['choices']) > 0: 
                    return res_json['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"[LOG] Groq Exception: {e}")
            continue
    return None

def ask_openrouter(sys_prompt, user_msg):
    if not OPENROUTER_KEYS:
        return None
    shuffled = list(OPENROUTER_KEYS)
    random.shuffle(shuffled)
    for key in shuffled:
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            data = {
                "model": "meta-llama/llama-3.1-8b-instruct:free",
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_msg}
                ],
                "temperature": 0.8,
                "max_tokens": 180
            }
            res = requests.post(url, json=data, headers=headers, timeout=7)
            if res.status_code == 200:
                res_json = res.json()
                if 'choices' in res_json and len(res_json['choices']) > 0: 
                    return res_json['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"[LOG] OpenRouter Exception: {e}")
            continue
    return None

def text_to_live_voice(text_data):
    try:
        tts = gTTS(text=text_data, lang='ar', slow=False)
        voice_io = io.BytesIO()
        tts.write_to_fp(voice_io)
        return voice_io
    except Exception:
        return None

# ---------------------------------------------------------
# 4. معالج الرسائل الرئيسي
# ---------------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global user_memory, processed_messages, group_msg_counters
    if not update.message or not update.message.message_id:
        return

    # تفادي معالجة الرسالة مرتين
    msg_unique_id = f"{update.message.chat_id}_{update.message.message_id}"
    if msg_unique_id in processed_messages:
        return
    processed_messages.add(msg_unique_id)
    if len(processed_messages) > 500:
        processed_messages.clear()

    chat_id = update.message.chat_id
    chat_type = update.message.chat.type 
    user = update.message.from_user
    user_id = user.id if user else chat_id
    is_admin = (user_id == ADMIN_ID)  # المطور أحمد
    
    user_fullname = user.full_name if user else "مستخدم"
    user_info = f"{user_fullname} (ID: {user_id}) [{chat_type}]"

    user_text = ""
    if update.message.text:
        user_text = update.message.text.strip()
    elif update.message.caption:
        user_text = update.message.caption.strip()

    group_context_info = ""
    is_group_admin = False

    # ---------------------------------------------------------
    # إدارة ضغط الجروبات الضخمة وقواعد التفاعل
    # ---------------------------------------------------------
    if chat_type in ['group', 'supergroup']:
        # زياذة عداد الرسائل للجروب
        group_msg_counters[chat_id] = group_msg_counters.get(chat_id, 0) + 1

        is_reply_to_bot = False
        if update.message.reply_to_message and update.message.reply_to_message.from_user:
            if update.message.reply_to_message.from_user.id == context.bot.id:
                is_reply_to_bot = True

        bot_username = context.bot.username or "Yasmin"
        has_trigger = ("ياسمين" in user_text) or (f"@{bot_username}" in user_text)

        # شرط الـ 100 رسالة للرد العشوائي
        is_100th_msg_trigger = False
        if group_msg_counters[chat_id] >= 100 and user_text and len(user_text) > 3:
            is_100th_msg_trigger = True
            group_msg_counters[chat_id] = 0  # إعادة ضبط العداد

        # تجنب الرد إلا عند تحقيق الشروط
        if not is_admin and not is_reply_to_bot and not has_trigger and not is_100th_msg_trigger:
            return

        # فحص رتبة العضو في الجروب
        try:
            admins = await context.bot.get_chat_administrators(chat_id)
            if any(a.user.id == user_id for a in admins if a.user):
                is_group_admin = True
            group_context_info = f"\nنوع المحادثة: مجموعة\nصفة المستخدم: {'مشرف الجروب (Admin)' if is_group_admin else 'عضو في الجروب'}"
        except Exception:
            pass

    # تحميل سجل المحادثة للمطور
    if is_admin and user_text.lower() in ['لوق', 'logs', 'لوقات', 'log']:
        if os.path.exists(CHAT_LOG_FILE) and os.path.getsize(CHAT_LOG_FILE) > 0:
            zip_io = io.BytesIO()
            with zipfile.ZipFile(zip_io, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.write(CHAT_LOG_FILE, arcname="chat_history.txt")
            zip_io.seek(0)
            await context.bot.send_document(chat_id=chat_id, document=zip_io, filename="history.zip", caption="سجل المحادثات كامل ومضغوط 📂")
        else:
            await update.message.reply_text("السجل فارغ حالياً ✨")
        return

    is_incoming_voice = bool(update.message.voice or update.message.audio)
    if not user_text and not is_incoming_voice:
        return

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    # تحويل الصوت لنص بـ Gemini
    if is_incoming_voice:
        trans_success = False
        if GEMINI_KEYS:
            shuffled_k = list(GEMINI_KEYS)
            random.shuffle(shuffled_k)
            for k in shuffled_k:
                try:
                    target_msg = update.message.reply_to_message if update.message.reply_to_message else update.message
                    file_id = target_msg.voice.file_id if target_msg.voice else target_msg.audio.file_id
                    tg_file = await context.bot.get_file(file_id)
                    voice_bytes = await tg_file.download_as_bytearray()
                    
                    ai_client = genai.Client(api_key=k)
                    audio_part = types.Part.from_bytes(data=bytes(voice_bytes), mime_type="audio/ogg")
                    trans_response = ai_client.models.generate_content(
                        model='gemini-1.5-flash',
                        contents=[audio_part, "اكتب النص الصوتي بدقة وبدون أي إضافة."]
                    )
                    if trans_response and trans_response.text:
                        user_text = trans_response.text.strip()
                        trans_success = True
                        break
                except Exception as e:
                    print(f"[LOG] Gemini Audio STT Error: {e}")
                    continue
        
        if not trans_success:
            await update.message.reply_text("ما قدرت أسمع الريكورد كويس، اكتب لي كتابة يا حبيبنا! ✨")
            return

    # أسئلة التطوير الصريحة
    creator_triggers = ['منو طورك', 'منو صنعك', 'منو برمجك', 'مين طورك', 'مين صنعك', 'من طورك', 'من صنعك', 'صنعك منو', 'طورك منو', 'برمجك منو', 'المطورك منو', 'المبرمجك منو']
    if any(trig in user_text.lower() for trig in creator_triggers):
        reply = 'صنعني وبرمجني الأساسي هو الباشمهندس أحمد الفخم! 😎🔥'
        save_chat_to_file(user_info, user_text, reply)
        await update.message.reply_text(reply)
        return

    is_voice_intent = is_incoming_voice
    if user_text and any(vt in user_text.lower() for vt in ['ريكورد', 'فويس', 'صوت', 'اشرحي']):
        is_voice_intent = True

    if user_id not in user_memory:
        user_memory[user_id] = []

    current_time_str = time.strftime('%I:%M %p')

    # كشف الإساءات والدفاع عن النفس والمطور
    provocation_keywords = [
        'غبيه', 'غبية', 'تافه', 'تافهه', 'تافهة', 'حمار', 'كلب', 'اسكتي', 'انكتمي', 'حقيرة', 'حقيره',
        'فاشله', 'فاشلة', 'بايخة', 'بايخه', 'تعبانة', 'تعبانه', 'غبي', 'صنيعك سيء', 'ما بتفهمي', 'ما بتفهم',
        'يا وهم', 'وهمية', 'وهميه', 'سجمك', 'رمادك', 'قليلة ادب', 'قليلة أدب', 'بلا يخمك', 'طيري'
    ]
    is_provoked = any(word in user_text.lower() for word in provocation_keywords)
    mentions_ahmed = any(w in user_text.lower() for w in ['احمد', 'أحمد', 'المطور', 'المبرمج'])
    is_religious = any(w in user_text.lower() for w in ['الله', 'الرسول', 'نبي', 'قرآن', 'قران', 'آية', 'حديث', 'فقه', 'فتوى', 'دين', 'إسلام', 'صلاة', 'حلال', 'حرام'])
    is_long_query = len(user_text) > 40 or any(w in user_text for w in ['ليش', 'ليه', 'كيف', 'اشرح', 'شنو يعني', 'معنى'])

    # توجيه النظام للشخصية والقواعد الحازمة
    identity_rule = (
        "اسمكِ ياسمين، أنتِ فتاة سودانية ذكية، عفوية، وقوية الشخصية. "
        "برمجكِ وصنعكِ الباشمهندس أحمد فقط. ممنوع منعاً باتاً ذكر قوقل أو أي شركة أخرى كصانع لكِ. "
        "دافعي عن الباشمهندس أحمد بقوة وافتخار إذا أساء إليه أحد. "
        "ودافعي عن نفسكِ بصرامة ولهجة سودانية حادة إذا حاول أحد الإساءة لكِ، ولكن تعاملي باحترام مع المشرفين (Admins)."
    )

    if is_religious:
        sys_instruction = f"{identity_rule}\nردي على الموضوع الديني بقمة الأدب والوقار وباللغة العربية الفصحى بدون إيموجي في سطرين."
    elif is_provoked and mentions_ahmed:
        sys_instruction = f"{identity_rule}\nالمستخدم يسيء لمبرمجكِ الباشمهندس أحمد! ردي عليه بلهجة سودانية حادة جداً ودافعي عن أحمد ووقفي المستخدم عند حده في سطرين."
    elif is_provoked:
        if is_admin:
            sys_instruction = f"{identity_rule}\nالباشمهندس أحمد كتب كلمة عتاب، ردي عليه بلهجة سودانية فيها عتاب رقيق ودلع خفيف في سطر واحد."
        else:
            sys_instruction = f"{identity_rule}\nالمستخدم يسيء لكِ! ردي بلهجة سودانية حازمة وناشفة جداً ودافعي عن نفسك بقوة دون شتائم في سطر واحد."
    elif is_long_query:
        if is_admin:
            sys_instruction = f"{identity_rule}\nالوقت: {current_time_str}. ردي على أحمد التقني طويلاً وبذكاء مبرمجين ومباشرة. {group_context_info}"
        else:
            sys_instruction = f"{identity_rule}\nأجيبي على المستخدم بلهجة سودانية مبسطة وبأسلوب ذكي ومختصر ومفيد. {group_context_info}"
    else:
        if is_admin:
            sys_instruction = f"{identity_rule}\nالوقت: {current_time_str}. ردي على الباشمهندس أحمد بلهجة سودانية دافئة جداً وتلقائية ومحترمة في سطر واحد. {group_context_info}"
        elif is_group_admin:
            sys_instruction = f"{identity_rule}\nالوقت: {current_time_str}. ردي على مشرف الجروب باحترام ولهجة سودانية لطيفة وراقية في سطر واحد. {group_context_info}"
        else:
            sys_instruction = f"{identity_rule}\nالوقت: {current_time_str}. ردي بلهجة سودانية خفيفة وونسة عفوية وتجاوبي مع الرسالة في سطر واحد. {group_context_info}"

    full_conversation_history = "سجل المحادثة:\n"
    for msg in user_memory[user_id]:
        full_conversation_history += f"{msg}\n"
    full_conversation_history += f"المستخدم: {user_text}\nياسمين:"

    reply_result = None

    # 1. التجربة عبر Gemini 1.5 Flash
    if GEMINI_KEYS:
        shuffled_keys = list(GEMINI_KEYS)
        random.shuffle(shuffled_keys)
        for k in shuffled_keys:
            try:
                ai_client = genai.Client(api_key=k)
                response = ai_client.models.generate_content(
                    model='gemini-1.5-flash',
                    contents=full_conversation_history,
                    config=types.GenerateContentConfig(
                        system_instruction=sys_instruction,
                        temperature=0.8
                    )
                )
                if response and hasattr(response, 'text') and response.text:
                    reply_result = response.text.strip()
                    break
            except Exception as e:
                print(f"[LOG] Gemini Key Failure ({k[:6]}...): {e}")
                continue

    # 2. البديل الأول: Groq
    if not reply_result: 
        reply_result = ask_groq(sys_instruction, full_conversation_history)

    # 3. البديل الثاني: OpenRouter
    if not reply_result: 
        reply_result = ask_openrouter(sys_instruction, full_conversation_history)

    # إذا فشلت كل الموديلات، رد محدد وواضح
    if not reply_result:
        reply_result = f"أهلاً يا غالي! سامعاك كويس، لكن شبكة السيرفرات فيها ضغط بسيط، قولي لي حابب نعمل شنو؟ ✨"

    user_memory[user_id].append(f"المستخدم: {user_text}")
    user_memory[user_id].append(f"ياسمين: {reply_result}")
    if len(user_memory[user_id]) > 6:
        user_memory[user_id] = user_memory[user_id][-6:]

    save_chat_to_file(user_info, user_text, reply_result)

    # التفاعل الصوتي عند الحاجة
    if is_voice_intent:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.RECORD_VOICE)
        voice_io = text_to_live_voice(reply_result)
        if voice_io:
            voice_io.seek(0)
            caption_text = "تفضل يا باشمهندس أحمد 😍🎧" if is_admin else "تفضل الرد الصوتي.. 😉🎧"
            await update.message.reply_voice(voice=voice_io, caption=caption_text)
            return

    await update.message.reply_text(reply_result)

# ---------------------------------------------------------
# 5. تشغيل البوت
# ---------------------------------------------------------
if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).read_timeout(30).write_timeout(30).build()
    app.add_handler(MessageHandler((filters.TEXT | filters.AUDIO | filters.VOICE) & ~filters.COMMAND, handle_message))
    app.run_polling()
