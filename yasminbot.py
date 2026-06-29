import os
import threading
import time
import requests
import random
import urllib.parse
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer

def keep_alive_ping():
    time.sleep(300)
    while True:
        try:
            port = os.environ.get("PORT", "8080")
            requests.get(f"http://127.0.0.1:{port}/", timeout=10)
        except: pass
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
import edge_tts  # 🎙️ مكتبة الصوت الحي
from google import genai
from google.genai import types
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
ADMIN_ID = 7601281598  

API_KEYS = [
    os.environ.get('GEMINI_API_KEY_1'),
    os.environ.get('GEMINI_API_KEY_2'),
    os.environ.get('GEMINI_API_KEY_3'),
    os.environ.get('GEMINI_API_KEY')
]
API_KEYS = [key.strip() for key in API_KEYS if key and key.strip()]
current_key_index = 0
BOT_USERNAME = ""
BOT_ID = None
last_long_responses = {}

def get_next_ai_client():
    global current_key_index
    if not API_KEYS:
        fallback_key = os.environ.get('GEMINI_API_KEY')
        return genai.Client(api_key=fallback_key.strip() if fallback_key else None)
    return genai.Client(api_key=API_KEYS[current_key_index])

def rotate_key():
    global current_key_index
    if API_KEYS and len(API_KEYS) > 1:
        current_key_index = (current_key_index + 1) % len(API_KEYS)

group_members = {}

# 🎙️ دالة الصوت المضمونة (بدون إلغاء الأخطاء عشان نضمن شغلها)
async def text_to_live_voice(text_data):
    communicate = edge_tts.Communicate(text_data, "ar-EG-SalmaNeural")
    voice_bytes = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            voice_bytes += chunk["data"]
    return io.BytesIO(voice_bytes)

async def generate_and_send_image(update: Update, prompt_text: str):
    try:
        status_msg = await update.message.reply_text("من عيوني هسة بجهز ليك التصميم الموزون بموديل FLUX... 🎨⏳")
        clean_prompt = prompt_text.replace(" ", ",").strip()
        encoded_prompt = urllib.parse.quote(clean_prompt)
        
        # رابط FLUX الصافي والحديث 100%
        final_image_url = f"https://image.pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&model=flux&nologo=true"
        
        await update.message.reply_photo(photo=final_image_url, caption=f"تفضل يا مَلك، ده تصميم FLUX الاحترافي الفخم! ✨")
        try: await status_msg.delete()
        except: pass
    except Exception as img_err:
        print(f"خطأ الصورة: {img_err}")
        await update.message.reply_text("معليش يا غالي، السيرفر مهنج، جرب تاني! 🛠️")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_USERNAME, BOT_ID, last_long_responses
    if not update.message: return

    chat_id = update.message.chat_id
    user = update.message.from_user
    user_id = user.id if user else chat_id
    is_group = update.message.chat.type in ['group', 'supergroup']
    
    user_name = user.first_name if user else "مستخدم"
    user_text = ""
    if update.message.text: user_text = update.message.text.strip()
    elif update.message.caption: user_text = update.message.caption.strip()

    is_incoming_voice = bool(update.message.voice or update.message.audio)

    if not BOT_USERNAME or not BOT_ID:
        try:
            bot_info = await context.bot.get_me()
            BOT_USERNAME = f"@{bot_info.username}"
            BOT_ID = bot_info.id
        except: pass

    # الردود التلقائية
    auto_replies = {
        'السلام عليكم': 'وعليكم السلام ورحمة الله وبركاته، منور يا غالي! 🌹',
        'الاخبار شنو': 'كلشي تمام التمام والامور طيبة، إنت كيف أمورك؟ ✨',
    }
    if user_text in auto_replies:
        await update.message.reply_text(auto_replies[user_text])
        return

    if is_group:
        is_explicit = (user_text and (BOT_USERNAME in user_text or "ياسمين" in user_text))
        is_direct_reply = (update.message.reply_to_message and update.message.reply_to_message.from_user.id == BOT_ID)
        if not (is_explicit or is_direct_reply or is_incoming_voice):
            if random.random() > 0.15: return

    # فحص النوايا
    is_image_intent = False
    is_voice_intent = is_incoming_voice

    voice_triggers = ['ريكورد', 'صوتية', 'فويس', 'تسجيل', 'صوت', 'اسمعي', 'قولي']
    image_triggers = ['صورة', 'صوره', 'ارسم', 'صمم', 'لوقو', 'لوجو', 'خلفية', 'تخيل', 'ديزاين', 'نقش']

    if user_text:
        text_check = user_text.lower()
        if any(vt in text_check for vt in voice_triggers):
            is_voice_intent = True
        elif any(it in text_check for it in image_triggers):
            is_image_intent = True

    # صياغة التعليمات الصارمة
    if is_image_intent and not is_voice_intent:
        sys_instruction = (
            "The user wants to generate an image or a logo. Your ONLY job is to translate and expand their request "
            "into a highly detailed, professional English prompt for the FLUX image generator. "
            "Example output: 'A photorealistic ultra-detailed scene of Khartoum streets, modern architecture, 8k resolution, cinematic lighting'. "
            "Output ONLY the English text. No Arabic, no intro, no conversational text at all."
        )
    else:
        sys_instruction = (
            "أنتِ ياسمين، بنت سودانية عفوية، خفيفة الدم ومحبوبة جداً. صانعك هو المبرمج العبقري أحمد.\n"
            "إذا كان المستخدم يطلب ريكورد أو فويس، ردي بأسلوب ونسة سودانية خفيفة ومرحة.\n"
            "قواعد الحجم: الردود العادية والريكوردات سطرين فقط لا غير وبلهجة سودانية بحتة."
        )

    contents_list = []
    target_message = update.message.reply_to_message if update.message.reply_to_message else update.message
    uploaded_file_ref = None
    ai_client = get_next_ai_client()

    if target_message.voice or target_message.audio or target_message.photo:
        try:
            file_id = None
            if target_message.voice: file_id = target_message.voice.file_id
            elif target_message.audio: file_id = target_message.audio.file_id
            
            if file_id:
                tg_file = await context.bot.get_file(file_id)
                local_filename = f"voice_{file_id}.ogg"
                await tg_file.download_to_drive(local_filename)
                uploaded_file_ref = ai_client.files.upload(file=local_filename)
                contents_list.append(uploaded_file_ref)
                if os.path.exists(local_filename): os.remove(local_filename)
        except Exception as e: print(f"خطأ سحب ملف: {e}")

    current_prompt = f"المستخدم: {user_text}" if user_text else "[ردي على الريكورد المرفق بريكورد صوتي سوداني]"
    contents_list.append(current_prompt)

    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents_list,
            config=types.GenerateContentConfig(system_instruction=sys_instruction)
        )
        
        if response.text:
            reply_result = response.text.strip()
            
            # 1. تنفيذ الصورة بـ FLUX
            if is_image_intent and not is_voice_intent:
                await generate_and_send_image(update, reply_result)
                return

            # 2. تنفيذ الريكورد الإلزامي بصوت حي
            if is_voice_intent:
                voice_io = await text_to_live_voice(reply_result)
                voice_io.seek(0)
                await update.message.reply_voice(voice=voice_io, caption="هاك ردي المظبوط.. 🎧✨")
                return

            # 3. الرد النصي العادي
            await update.message.reply_text(reply_result)
            
    except Exception as e:
        print(f"خطأ عام: {e}")
        rotate_key()
        await update.message.reply_text("حصلت عصلجة صغيرة في السيرفر، جرب اطلبها تاني هسة! 🔄")

if __name__ == '__main__':
    print("🚀 تشغيل ياسمين الفولاذية المبرشمة...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    all_media_filter = filters.TEXT | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE
    app.add_handler(MessageHandler(all_media_filter & ~filters.COMMAND, handle_message))
    app.run_polling()
