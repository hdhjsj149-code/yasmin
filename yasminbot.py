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
            print("🔔 السيرفر صاحي وياسمين مستعدة..")
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
from google import genai
from google.genai import types
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# 1. سحب مفاتيح الاتصال بأمان من السيرفر 🔒
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# 🚨 رقم الـ ID حقك الشخصي (اكتب الأرقام فقط مكان المتغير)
ADMIN_ID = 7601281598

# 2. تشغيل عميل جوجل جيميناي
ai_client = genai.Client(api_key=GEMINI_API_KEY)

group_members = {}
manual_history = {}

# 📁 دالة حفظ لوق منفصل لكل مستخدم
def write_to_user_log(user_id, user_name, user_username, text):
    try:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        safe_name = "".join([c for c in user_name if c.isalpha() or c.isdigit() or c==' ']).strip()
        if not safe_name:
            safe_name = "User"
            
        filename = f"log_{user_id}_{safe_name}.txt"
        log_line = f"[{current_time}] | {user_username} | {text}\n"
        
        with open(filename, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        print(f"خطأ كتابة اللوق: {e}")

# دالة استقبال ومعالجة الرسائل
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    chat_id = update.message.chat_id
    user = update.message.from_user
    user_id = user.id if user else chat_id
    
    user_name = user.first_name if user else "مستخدم غير معروف"
    user_username = f"@{user.username}" if user and user.username else f"ID: {user_id}"

    # حفظ الأعضاء للـ Tag All
    if update.message.chat.type in ['group', 'supergroup']:
        if chat_id not in group_members:
            group_members[chat_id] = set()
        if user and user.username:
            group_members[chat_id].add(f"@{user.username}")
        elif user:
            group_members[chat_id].add(f"[{user.first_name}](tg://user?id={user.id})")

    user_text = ""
    if update.message.text:
        user_text = update.message.text.strip()
    elif update.message.caption:
        user_text = update.message.caption.strip()

    # تسجيل الحركة في اللوق الخاص باليوزر
    if user_text:
        write_to_user_log(user_id, user_name, user_username, f"الرسالة: {user_text}")
    elif update.message.photo:
        write_to_user_log(user_id, user_name, user_username, "[أرسل صورة أو رد عليها]")
    elif update.message.voice or update.message.audio:
        write_to_user_log(user_id, user_name, user_username, "[أرسل ملف صوتي]")

    # === [ الأمر السري للمطور - سحب اللوق ] ===
    if user_text == "سحب اللوق":
        if user_id == ADMIN_ID:
            log_files = [f for f in os.listdir('.') if f.startswith("log_") and f.endswith(".txt")]
            if log_files:
                await update.message.reply_text("تفضل يا مَلك، جاري ضغط وإرسال ملفات اللوق... 📦⏳")
                zip_filename = "all_users_logs.zip"
                with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for file in log_files:
                        zipf.write(file)
                with open(zip_filename, "rb") as log_zip:
                    await context.bot.send_document(chat_id=chat_id, document=log_zip, filename=zip_filename)
                try: os.remove(zip_filename)
                except: pass
            else:
                await update.message.reply_text("الملفات لسة فاضية!")
        if user_id == ADMIN_ID:
            return

    # === [ خاصية الـ TAG ALL ] ===
    if user_text.lower() in ['تاق', '@all', 'تاغ']:
        if update.message.chat.type not in ['group', 'supergroup']:
            await update.message.reply_text("الخاصية دي جوة المجموعات بس! 📢")
            return
        members = group_members.get(chat_id, set())
        if not members:
            await update.message.reply_text("لسة ما لقطت أعضاء كفاية!")
            return
        tag_text = "📢 **نداء عاجل للجميع:**\n\n" + " ".join(list(members))
        await update.message.reply_text(tag_text, parse_mode="Markdown")
        return

    # === [ أولاً: لستة الردود التلقائية الثابتة ] ===
    auto_replies = {
        'السلام عليكم': 'وعليكم السلام ورحمة الله وبركاته، منور يا غالي! 🌹',
        'الاخبار شنو': 'كلشي تمام التمام والامور طيبة، إنت كيف أمورك؟ ✨',
        'الطورك منو': 'طورني وصنعني المبرمج أحمد! 🤖🔥',
        'الصنعك منو': 'صنعني ومبرمجني الأساسي هو الفخم أحمد! 😉💪',
        'منور': 'النور نورك والله يا حبيبنا! 🌟',
        'وين انت': 'لو مهتم كان عرفته 😎',
        'وين مختفي': 'لو مهتم كان عرفته 🙄',
        'وين مختفيه': 'لو مهتمه كان عرفتي 🙃',
        'صباح الخير': 'صبـ(⛅)ـُ(آٍلـٍـً(🌺)ـٍورٍدً)ـ(⛅)ـٍآٍآٍحً ',
        'مساء الخير': 'مۡسَـ(🍀)ـاء الۣخـ(🌸)ـيۡݛ ',
        'الحاصل شنو': 'Nothing special 😔',
        'كيف الكلام ده': 'عديل 😎',
        'تابعه لي منو انتي ': 'احمد فارس 🥺',
        'الخبر شنو': 'الحمدلله انت كيف؟ ',
        'احسنت بارك الله فيك': 'طيب الله انفاسك 🤍',
        'فطوم': 'شيختنا 🤍🌹',
        'الجديد شنو': 'طلتك يا غالي ',
        'الامور شنو': 'الحمدلله ',
        'الحمدلله ': 'دام حمدك',
        'يديك العافيه ': 'الله يعافيك يارب 🤲',
        'شكرا': 'عفواً 🌹',
        'مشتاقين': '🥺🥺',
    }
    
    if user_text in auto_replies:
        await update.message.reply_text(auto_replies[user_text])
        return

    # === [ ثانياً: توجيه الذكاء الاصطناعي - النسخة الحية والمشوقة والسريعة ] ===
    sys_instruction = (
        'أنتِ ذكاء اصطناعي اسمك ياسمين، صانعك ومطورك هو المبرمج العبقري أحمد. '
        'تظهرين كبنت سودانية حية، ذكية، وناقشة الحنك تماماً. '
        'قواعدك الجديدة والموزونة:\n'
        '1. ردي بأسلوب مفيد، مشوق، ومفهوم. ممنوع نهائياً الرد بسطر واحد جاف وممل إذا كان موضوع النقاش يتطلب أخذ وعطاء وتفصيل.\n'
        '2. تفاعلي بروح بشرية واجتماعية حقيقية، واستخدمي لغة الشات السودانية المهذبة والمحبوبة، ووزعي إيموجيات حية تعبر عن الكلام (✨، 🔥، 🔗، 🤔، ⚡).\n'
        '3. تجنبي المبالغة في الضحك والهزل المتكرر على الفاضي، وتجنبي أيضاً الجفاف والبرود التام. خليكِ متوازنة وشاطرة.\n'
        '4. ركزي في سياق الحوار المعروض عليك لتجاري موضوع اللعبة أو النقاش بذكاء مستمر.'
    )

    if user_id not in manual_history:
        manual_history[user_id] = []

    contents_list = []
    target_message = update.message.reply_to_message if update.message.reply_to_message else update.message

    # فحص الميديا
    if target_message.photo or target_message.voice or target_message.audio:
        try:
            file_id = None
            mime_type = None
            if target_message.photo:
                file_id = target_message.photo[-1].file_id
                mime_type = "image/jpeg"
            elif target_message.voice:
                file_id = target_message.voice.file_id
                mime_type = "audio/ogg"
            elif target_message.audio:
                file_id = target_message.audio.file_id
                mime_type = "audio/mpeg"

            if file_id:
                tg_file = await context.bot.get_file(file_id)
                if tg_file.file_size <= 5 * 1024 * 1024:
                    out = io.BytesIO()
                    await tg_file.download_to_memory(out)
                    contents_list.append(types.Part.from_bytes(data=out.getvalue(), mime_type=mime_type))
        except Exception as e:
            print(f"ميديا عابر: {e}")

    context_text = ""
    if manual_history[user_id]:
        context_text = "\n".join(manual_history[user_id]) + "\n"

    current_prompt = f"{context_text}المستخدم: {user_text}" if user_text else f"{context_text}[ميديا]"
    contents_list.append(current_prompt)

    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents_list,
            config=types.GenerateContentConfig(system_instruction=sys_instruction)
        )
        
        if response.text:
            reply_result = response.text.strip()
            
            if user_text:
                manual_history[user_id].append(f"المستخدم: {user_text}")
                manual_history[user_id].append(f"ياسمين: {reply_result}")
                # ⚡ تعديل السرعة: خفضنا خزان الذاكرة لـ 6 أسطر (3 رسايل متبادلة) عشان الرد يبقى سريع فوراً
                if len(manual_history[user_id]) > 6:
                    manual_history[user_id] = manual_history[user_id][-6:]

            await asyncio.sleep(0.1)
            await update.message.reply_text(reply_result)
            
    except Exception as e:
        print(f"خطأ جيميناي: {e}")
        try:
            fallback_response = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[user_text if user_text else "نعم، معاك"],
                config=types.GenerateContentConfig(system_instruction=sys_instruction)
            )
            if fallback_response.text:
                await update.message.reply_text(fallback_response.text.strip())
        except Exception:
            pass

if __name__ == '__main__':
    print("ياسمين السريعة والمشوقة بدأت الشغل الرسمي.. 🚀🔥")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    all_media_filter = filters.TEXT | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE
    app.add_handler(MessageHandler(all_media_filter & ~filters.COMMAND, handle_message))
    app.run_polling()
