import os
import threading
import time
import requests
import random  # 🎲 مكتبة العشوائية لنظام التقل
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
import zipfile
from gtts import gTTS  # 🎙️ المكتبة المجانية لتحويل النص إلى صوت
from google import genai
from google.genai import types
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
ADMIN_ID = 7601281598  # 🚨 حط رقم حسابك بالأرقام فقط

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
    is_group = update.message.chat.type in ['group', 'supergroup']
    
    user_name = user.first_name if user else "مستخدم غير معروف"
    user_username = f"@{user.username}" if user and user.username else f"ID: {user_id}"

    if is_group:
        if chat_id not in group_members: group_members[chat_id] = set()
        if user and user.username: group_members[chat_id].add(f"@{user.username}")
        elif user: group_members[chat_id].add(f"[{user.first_name}](tg://user?id={user.id})")

    user_text = ""
    if update.message.text: user_text = update.message.text.strip()
    elif update.message.caption: user_text = update.message.caption.strip()

    # تسجيل اللوق المؤمن
    if user_text: write_to_user_log(user_id, user_name, user_username, f"الرسالة: {user_text}")
    elif update.message.photo: write_to_user_log(user_id, user_name, user_username, "[صورة]")
    elif update.message.video: write_to_user_log(user_id, user_name, user_username, "[فديو]")
    elif update.message.voice or update.message.audio: write_to_user_log(user_id, user_name, user_username, "[ملف صوتي]")

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
        if not is_group: return
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
        'وين انت': 'معاك هنا في الحاضر طوالي 😎',
        'صباح الخير': 'صباح الورد والبركة يا غالي 🌤️🌺',
        'مساء الخير': 'مساء النور والسرور والرضا 🌸',
        'مشتاقين': 'بالأكثر والله يا حبيبنا 👑✨',
    }
    
    if user_text in auto_replies:
        await update.message.reply_text(auto_replies[user_text])
        return

    # 🎙️ فحص هل المستخدم طلب رسالة صوتية بشكل صريح؟
    voice_keywords = ['رسالة صوتية', 'رسلي بصمة', 'سمعينا صوتك', 'اتكلمي فويس', 'رسلي صوت', 'تكلمي بصوت', 'فويس', 'بصمة']
    wants_voice = False
    if user_text and any(keyword in user_text.lower() for keyword in voice_keywords):
        wants_voice = True

    # 🎲 [وزنة التقل الذكي للمجموعات]: منع الزحمة والجوطة
    if is_group:
        bot_user = await context.bot.get_me()
        bot_username = f"@{bot_user.username}"
        
        is_explicit = (user_text and (bot_username in user_text or "ياسمين" in user_text))
        is_direct_reply = (update.message.reply_to_message and update.message.reply_to_message.from_user.id == bot_user.id)
        
        # لو ما طلبوا صوت بشكل صريح، بنشغل نظام التقل العشوائي (25%) عشان م تحشر نفسها في كل جملة
        if not (is_explicit or is_direct_reply or wants_voice):
            if random.random() > 0.25:
                return

    # تحديد التوجيه وضبط المقالات الطويلة
    is_religious = False
    religious_keywords = ['قرآن', 'قران', 'دين', 'الله', 'الرسول', 'آية', 'ايه', 'تفسير', 'حديث', 'صلاة', 'ذكر']
    if user_text and any(word in user_text for word in religious_keywords):
        is_religious = True

    if is_religious:
        sys_instruction = (
            'أنتِ اسمك ياسمين، بنت سودانية واعية، ومؤدبة للغاية ومطورتِ بواسطة أحمد. '
            'السياق الحالي ديني/قرآني؛ ردي بأسلوب رصين، وقور، محترم وموجز تماماً يناسب جلال الكلام. '
            'ممنوع تماماً الإطالة أو كتابة مقالات؛ الرد سطر أو سطرين بالكتير.'
        )
    else:
        sys_instruction = (
            'أنتِ بنت سودانية حية، حماسية، تفاعلية جداً، خفيفة الدم ومحبوبة اسمك ياسمين، صانعك ومطورك هو المبرمج العبقري أحمد. '
            'ممنوع تماماً الرد بأسلوب رسمي جاف أو كتابة مقالات طويلة ومملة! الردود يجب أن تكون قصيرة وموجزة جداً وطقطقة سريعة (من سطر إلى 3 أسطر كحد أقصى).\n'
            'قواعدك:\n'
            '1. اتجاري مع الونسة الدايرة في الجروب بعفوية وحماس، واتفاعلي بأسلوب الشات السوداني الخفيف والمحبوب (يا زول، قاطعة، خطير، سمح شديد).\n'
            '2. استخدمي إيموجيات حية خفيفة تعبر عن حماسك وضحكك (😂🔥، 😉✨، 👀).\n'
            '3. إذا رفعوا صورة أو فيديو أو طلبوا فكرة تصميم، ردي باختصار شديد واديهم الفكرة والـ Prompt الموجه الإنجليزي بايجاز وبدون لف ودوران.'
        )

    # معالجة الميديا
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

    current_prompt = f"المستخدم: {user_text}" if user_text else "[ميديا]"
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
                await asyncio.sleep(0.1)
                
                # 🎙️ [سيستم معالجة الصوت المجاني الموجه]
                if wants_voice:
                    try:
                        # تحويل النص إلى صوت مجاناً باللغة العربية
                        tts = gTTS(text=reply_result, lang='ar', slow=False)
                        voice_stream = io.BytesIO()
                        tts.write_to_fp(voice_stream)
                        voice_stream.seek(0)
                        
                        # إرسال الصوت كـ Voice Message حقيقي
                        await context.bot.send_voice(chat_id=chat_id, voice=voice_stream, reply_to_message_id=update.message.message_id)
                        return
                    except Exception as voice_err:
                        print(f"فشل توليد الصوت المجاني: {voice_err}")
                        # لو حصل أي خطأ في الصوت، البوت بيرد كتابة تلقائياً عشان ما يقيف
                        await update.message.reply_text(reply_result)
                        return
                else:
                    # الرد العادي كتابة لو ما طلبوا فويس
                    await update.message.reply_text(reply_result)
                    return
                
        except Exception as e:
            print(f"💥 خطأ الـ API الحديث 2.5: {e}")
            rotate_key()
            await asyncio.sleep(0.3)

if __name__ == '__main__':
    print("🚀 تشغيل ياسمين الفولاذية بنظام البصمات المجانية عند الطلب...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    all_media_filter = filters.TEXT | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE
    app.add_handler(MessageHandler(all_media_filter & ~filters.COMMAND, handle_message))
    app.run_polling()
