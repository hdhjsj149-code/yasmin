import os
import threading
import time
import requests
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer

def keep_alive_ping():
    time.sleep(300)
    while True:
        try:
            port = os.environ.get("PORT", "8080")
            requests.get(f"http://127.0.0.1:{port}/", timeout=10)
            print("🔔 السيرفر صاحي وجاهز..")
        except Exception as e:
            print(f"تنبيه النكز: {e}")
        time.sleep(600)

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, format, *args): return
    with TCPServer(("", port), QuietHandler) as httpd:
        httpd.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()
threading.Thread(target=keep_alive_ping, daemon=True).start()

import io
import datetime
import asyncio
from google import genai
from google.genai import types
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
ADMIN_ID = رقم_حسابك_هنا  # 🚨 حط رقم حسابك بالأرقام فقط

API_KEYS = [
    os.environ.get('GEMINI_API_KEY_1'),
    os.environ.get('GEMINI_API_KEY_2'),
    os.environ.get('GEMINI_API_KEY_3'),
    os.environ.get('GEMINI_API_KEY')
]
API_KEYS = [key.strip() for key in API_KEYS if key and key.strip()]

current_key_index = 0

def get_next_ai_client():
    global current_key_index
    if not API_KEYS:
        fallback_key = os.environ.get('GEMINI_API_KEY')
        return genai.Client(api_key=fallback_key.strip() if fallback_key else None)
    key = API_KEYS[current_key_index]
    return genai.Client(api_key=key)

def rotate_key():
    global current_key_index
    if API_KEYS and len(API_KEYS) > 1:
        current_key_index = (current_key_index + 1) % len(API_KEYS)
        print(f"⚠️ تم تحويل التدوير للمفتاح رقم: {current_key_index + 1}")

group_members = {}
manual_history = {}

# 📝 دالة اللوق الموحد الشامل (مستحيل تفوت حاجة)
def write_to_master_log(chat_id, user_id, user_name, user_username, chat_type, text_content):
    try:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{current_time}] | الجروب/الشات: {chat_id} ({chat_type}) | المستخدم: {user_name} ({user_username} - ID: {user_id}) -> {text_content}\n"
        with open("yasmin_master_log.txt", "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e: 
        print(f"خطأ كتابة اللوق الموحد: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return

    chat_id = update.message.chat_id
    user = update.message.from_user
    user_id = user.id if user else chat_id
    chat_type = update.message.chat.type
    is_group = chat_type in ['group', 'supergroup']
    
    user_name = user.first_name if user else "مستخدم غير معروف"
    user_username = f"@{user.username}" if user and user.username else "لا يوجد يوزر"

    if is_group:
        if chat_id not in group_members: group_members[chat_id] = set()
        if user and user.username: group_members[chat_id].add(f"@{user.username}")
        elif user: group_members[chat_id].add(f"[{user.first_name}](tg://user?id={user.id})")

    user_text = ""
    if update.message.text: user_text = update.message.text.strip()
    elif update.message.caption: user_text = update.message.caption.strip()

    # تحديد نوع الميديا للوق
    media_type = "نص"
    if update.message.photo: media_type = "[صورة]"
    elif update.message.video: media_type = "[فيديو]"
    elif update.message.voice or update.message.audio: media_type = "[ملف صوتي]"

    log_payload = f"الرسالة: {user_text}" if user_text else media_type

    # === سحب اللوق الشامل (للآدمن فقط) ===
    if user_text == "سحب اللوق" and user_id == ADMIN_ID:
        if os.path.exists("yasmin_master_log.txt"):
            await update.message.reply_text("تفضل يا مَلك، جاري سحب اللوق الموحد الشامل... 📊📦")
            with open("yasmin_master_log.txt", "rb") as master_file:
                await context.bot.send_document(chat_id=chat_id, document=master_file, filename="yasmin_master_log.txt")
        else:
            await update.message.reply_text("الملف الموحد لسة ما سجل حركة يا ملك! 📝")
        return

    # 🛑 فحص أمن التدخل للمجموعات (البوت بيسجل لوق الكل، بس ما بيرد إلا لو نادوه)
    if is_group:
        bot_user = await context.bot.get_me()
        bot_username = f"@{bot_user.username}"
        
        is_mentioned = (user_text and (bot_username in user_text or "ياسمين" in user_text))
        is_reply_to_bot = (update.message.reply_to_message and update.message.reply_to_message.from_user.id == bot_user.id)
        
        # بنسجل اللوق الموحد طوالي عشان تراقبه، وبعدها نحدد هل نرد ولا نسكت
        write_to_master_log(chat_id, user_id, user_name, user_username, chat_type, log_payload)
        
        if not (is_mentioned or is_reply_to_bot):
            return
    else:
        # لو في الخاص، بنسجل طوالي ونمشي على الرد
        write_to_master_log(chat_id, user_id, user_name, user_username, chat_type, log_payload)

    # === TAG ALL ===
    if user_text.lower() in ['تاق', '@all', 'تاغ']:
        if not is_group: return
        members = group_members.get(chat_id, set())
        if not members: return
        tag_text = "📢 **نداء عاجل للجميع:**\n\n" + " ".join(list(members))
        await update.message.reply_text(tag_text, parse_mode="Markdown")
        return

    # الردود التلقائية الثابتة السريعة
    auto_replies = {
        'السلام عليكم': 'وعليكم السلام ورحمة الله وبركاته، منور يا غالي! 🌹',
        'الاخبار شنو': 'كلشي تمام التمام والامور طيبة، إنت كيف أمورك? ✨',
        'الطورك منو': 'طورني وصنعني المبرمج أحمد! 🤖🔥',
        'الصنعك منو': 'صنعني ومبرمجني الأساسي هو الفخم أحمد! 😉💪',
        'منور': 'النور نورك والله يا حبيبنا! 🌟',
        'وين انت': 'معاك هنا في الحاضر طوالي 😎',
        'صباح الخير': 'صباح الورد والبركة يا غالي 🌤️🌺',
        'مساء الخير': 'مساء النور والسرور والرضا 🌸',
        'مشتاقين': 'بالأكثر والله يا حبيبنا 👑✨',
    }
    
    if user_text in auto_replies:
        await update.message.reply_text(auto_replies[user_text])
        return

    # تخصيص الشخصية الذكية
    is_religious = False
    religious_keywords = ['قرآن', 'قران', 'دين', 'الله', 'الرسول', 'آية', 'ايه', 'تفسير', 'حديث', 'صلاة', 'ذكر']
    if user_text and any(word in user_text for word in religious_keywords):
        is_religious = True

    if is_religious:
        sys_instruction = (
            'أنتِ اسمك ياسمين، بنت سودانية واعية، مثقفة، ومؤدبة للغاية ومطورتِ بواسطة أحمد. '
            'السياق الحالي ديني/قرآني؛ ردي بأسلوب رصين، وقور، محترم وموجز تماماً يناسب جلال الكلام. '
            'ممنوع الهزار أو استخدام إيموجيات ضاحكة، فقط استخدمي لغة مهذبة ودعوات طيبة ووقار يناسب الأجواء.'
        )
    else:
        sys_instruction = (
            'أنتِ بنت سودانية ذكية، حية، واعية ومثقفة اسمك ياسمين، صانعك ومطورك هو المبرمج العبقري أحمد. '
            'قواعدك:\n'
            '1. ردي بأسلوب مشوق، عاقل، وموزون ومفهوم تماماً، وتجنبي العبارات المعسولة الزائدة أو التكلف الحماسي البايخ.\n'
            '2. استخدمي لغة الشات السودانية المهذبة والمحبوبة مع إيموجيات خفيفة معبرة (✨، 🤔، 👀).\n'
            '3. إذا طلب المستخدم قراءة، تلخيص، أو تعديل أي ميديا (صورة، صوت، فديو)، ساعديه فوراً وبذكاء برمجى وعلمي عالي.'
        )

    if user_id not in manual_history:
        manual_history[user_id] = []

    # سحب الميديا
    contents_list = []
    target_message = update.message.reply_to_message if update.message.reply_to_message else update.message

    if target_message.photo or target_message.video or target_message.voice or target_message.audio:
        try:
            file_id = None
            mime_type = None
            if target_message.photo: file_id = target_message.photo[-1].file_id; mime_type = "image/jpeg"
            elif target_message.video: file_id = target_message.video.file_id; mime_type = "video/mp4"
            elif target_message.voice: file_id = target_message.voice.file_id; mime_type = "audio/ogg"
            elif target_message.audio: file_id = target_message.audio.file_id; mime_type = "audio/mpeg"

            if file_id:
                tg_file = await context.bot.get_file(file_id)
                if tg_file.file_size <= 5 * 1024 * 1024:
                    out = io.BytesIO()
                    await tg_file.download_to_memory(out)
                    contents_list.append(types.Part.from_bytes(data=out.getvalue(), mime_type=mime_type))
        except Exception as e: print(f"خطأ سحب الميديا: {e}")

    context_text = ""
    if manual_history[user_id]:
        context_text = "\n".join(manual_history[user_id]) + "\n"

    current_prompt = f"{context_text}المستخدم: {user_text}" if user_text else f"{context_text}[ميديا]"
    contents_list.append(current_prompt)

    for _ in range(len(API_KEYS) if API_KEYS else 1):
        try:
            ai_client = get_next_ai_client()
            response = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=contents_list,
                config=types.GenerateContentConfig(system_instruction=sys_instruction)
            )
            
            if response.text:
                reply_result = response.text.strip()
                if user_text:
                    manual_history[user_id] = [f"المستخدم: {user_text}", f"ياسمين: {reply_result}"]
                await asyncio.sleep(0.1)
                await update.message.reply_text(reply_result)
                return
                
        except Exception as e:
            print(f"💥 خطأ الـ API الحديث 2.5: {e}")
            rotate_key()
            await asyncio.sleep(0.3)

if __name__ == '__main__':
    print("🚀 تشغيل ياسمين الفولاذية بنظام اللوق الموحد الشامل...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    all_media_filter = filters.TEXT | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE
    app.add_handler(MessageHandler(all_media_filter & ~filters.COMMAND, handle_message))
    app.run_polling()
