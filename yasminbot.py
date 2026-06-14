import os
import threading
import time
import requests
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer

# 🔄 جروك النكز الداخلي الصامت لمنع النوم والـ 504
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

import os
import io
import datetime
import asyncio
import zipfile
import google.generativeai as genai # 🔄 الرجوع للمكتبة الفولاذية المستقرة والسمحة
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# 1. سحب توكن تليجرام ورقم الآدمن
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
ADMIN_ID = 7601281598  # 🚨 ضع رقم حسابك هنا (أرقام فقط)

# 🔑 سحب لستة المفاتيح المتعددة من السيرفر
API_KEYS = [
    os.environ.get('GEMINI_API_KEY_1'),
    os.environ.get('GEMINI_API_KEY_2'),
    os.environ.get('GEMINI_API_KEY_3'),
    os.environ.get('GEMINI_API_KEY') # المفتاح الأساسي كاحتياط رابع
]
API_KEYS = [key.strip() for key in API_KEYS if key and key.strip()]

current_key_index = 0

# تهيئة المفتاح الأول في البداية
if API_KEYS:
    genai.configure(api_key=API_KEYS[current_key_index])

def rotate_to_next_key():
    global current_key_index
    if API_KEYS and len(API_KEYS) > 1:
        current_key_index = (current_key_index + 1) % len(API_KEYS)
        genai.configure(api_key=API_KEYS[current_key_index])
        print(f"🔄 تم تدوير المفتاح بنجاح! شغالين هسة بالمفتاح رقم: {current_key_index + 1}")

group_members = {}
manual_history = {}

def write_to_user_log(user_id, user_name, user_username, text):
    try:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        safe_name = "".join([c for c in user_name if c.isalpha() or c.isdigit() or c==' ']).strip()
        if not safe_name: safe_name = "User"
        filename = f"log_{user_id}_{safe_name}.txt"
        log_line = f"[{current_time}] | {user_username} | {text}\n"
        with open(filename, "a", encoding="utf-8") as f: f.write(log_line)
    except Exception as e: print(f"خطأ كتابة اللوق: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return

    chat_id = update.message.chat_id
    user = update.message.from_user
    user_id = user.id if user else chat_id
    
    user_name = user.first_name if user else "مستخدم غير معروف"
    user_username = f"@{user.username}" if user and user.username else f"ID: {user_id}"

    if update.message.chat.type in ['group', 'supergroup']:
        if chat_id not in group_members: group_members[chat_id] = set()
        if user and user.username: group_members[chat_id].add(f"@{user.username}")
        elif user: group_members[chat_id].add(f"[{user.first_name}](tg://user?id={user.id})")

    user_text = ""
    if update.message.text: user_text = update.message.text.strip()
    elif update.message.caption: user_text = update.message.caption.strip()

    if user_text: write_to_user_log(user_id, user_name, user_username, f"الرسالة: {user_text}")

    # === سحب اللوق ===
    if user_text == "سحب اللوق" and user_id == ADMIN_ID:
        log_files = [f for f in os.listdir('.') if f.startswith("log_") and f.endswith(".txt")]
        if log_files:
            await update.message.reply_text("تفضل يا مَلك، جاري تجميع اللوق... 📦⏳")
            zip_filename = "all_users_logs.zip"
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in log_files: zipf.write(file)
            with open(zip_filename, "rb") as log_zip:
                await context.bot.send_document(chat_id=chat_id, document=log_zip, filename=zip_filename)
            try: os.remove(zip_filename)
            except: pass
        return

    # === TAG ALL ===
    if user_text.lower() in ['تاق', '@all', 'تاغ']:
        if update.message.chat.type not in ['group', 'supergroup']: return
        members = group_members.get(chat_id, set())
        if not members: return
        tag_text = "📢 **نداء عاجل للجميع:**\n\n" + " ".join(list(members))
        await update.message.reply_text(tag_text, parse_mode="Markdown")
        return

    # الردود التلقائية الثابتة السريعة
    auto_replies = {
        'السلام عليكم': 'وعليكم السلام ورحمة الله وبركاته، منور يا غالي! 🌹',
        'الاخبار شنو': 'كلشي تمام التمام والامور طيبة، إنت كيف أمورك؟ ✨',
        'الطورك منو': 'طورني وصنعني المبرمج أحمد! 🤖🔥',
        'الصنعك منو': 'صنعني ومبرمجني الأساسي هو الفخم أحمد! 😉💪',
        'منور': 'النور نورك والله يا حبيبنا! 🌟',
        'وین انت': 'لو مهتم كان عرفته 😎',
        'صباح الخير': 'صبـ(⛅)ـُ(آٍلـٍـً(🌺)ـٍورٍدً)ـ(⛅)ـٍآٍآٍحً ',
        'مساء الخير': 'مۡسَـ(🍀)ـاء الۣخـ(🌸)ـيۡݛ ',
        'مشتاقين': '🥺🥺',
    }
    
    if user_text in auto_replies:
        await update.message.reply_text(auto_replies[user_text])
        return

    # توجيه ياسمين المتوازن المشوق
    sys_instruction = (
        'أنتِ بنت سودانية حية، ذكية، واعية ومثقفة اسمك ياسمين، مطورك وصانعك هو المبرمج العبقري أحمد. '
        'قواعدك:\n'
        '1. ردي بأسلوب مفيد، مشوق ومفهوم تماماً، وممنوع الرد بسطر واحد جاف مالم يكن السؤال بسيطاً جداً.\n'
        '2. استخدمي لغة الشات السودانية المهذبة والمحبوبة، ووزعي إيموجيات معبرة تزيد حيوية ونكهة الحوار (✨، 🔥، 🤔، 👀).\n'
        '3. خليكِ سريعة ومباشرة وتجنبي الرغي الزائد أو الضحك المتكرر بدون سبب.'
    )

    if user_id not in manual_history:
        manual_history[user_id] = []

    # ⚡ الذاكرة الخفيفة الطائرة: حنمرر السطر الفات والرد الفات بس (رسالة وحدة متبادلة) عشان الـ API يطير طيران
    context_text = ""
    if manual_history[user_id]:
        context_text = "\n".join(manual_history[user_id]) + "\n"

    current_prompt = f"{context_text}المستخدم: {user_text}" if user_text else f"{context_text}[ميديا]"

    # المحاولة عبر السيستم المستقر والمضمون
    for _ in range(len(API_KEYS) if API_KEYS else 1):
        try:
            model = genai.GenerativeModel(
                model_name='gemini-2.5-flash', # 🎯 تشغيل الـ 2.5 الفخم
                system_instruction=sys_instruction
            )
            response = model.generate_content(current_prompt)
            
            if response.text:
                reply_result = response.text.strip()
                if user_text:
                    manual_history[user_id] = [f"المستخدم: {user_text}", f"ياسمين: {reply_result}"] # تصفية الذاكرة الفورية لرسالة واحدة
                
                await asyncio.sleep(0.1)
                await update.message.reply_text(reply_result)
                return # نجح الرد! نطلع طوالي
                
        except Exception as e:
            print(f"💥 فشل المفتاح الحالي بسبب: {e}")
            rotate_to_next_key() # لف للمفتاح البعده طوالي في نفس اللحظة عشان يلحق الرسالة
            await asyncio.sleep(0.3)

if __name__ == '__main__':
    print("🚀 تشغيل ياسمين 2.5 بالمكتبة المستقرة الفولاذية والذاكرة الطائرة...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    all_media_filter = filters.TEXT | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE
    app.add_handler(MessageHandler(all_media_filter & ~filters.COMMAND, handle_message))
    app.run_polling()
