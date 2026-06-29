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
from gtts import gTTS
from google import genai
from google.genai import types
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
ADMIN_ID = 7601281598  # 🚨 حط رقم حسابك بالأرقام هنا عشان سحب اللوق

API_KEYS = [
    os.environ.get('GEMINI_API_KEY_1'),
    os.environ.get('GEMINI_API_KEY_2'),
    os.environ.get('GEMINI_API_KEY_3'),
    os.environ.get('GEMINI_API_KEY')
]
# تنظيف المفاتيح وتجهيزها
API_KEYS = [key.strip() for key in API_KEYS if key and key.strip()]

# تأكيد عدد المفاتيح في اللوق
print(f"✅ تم تحميل عدد {len(API_KEYS)} مفاتيح Gemini جاهزة للشغل...")

current_key_index = 0
BOT_USERNAME = ""
BOT_ID = None

last_long_responses = {}

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

def write_to_user_log(user_id, user_name, user_username, text, log_type="private"):
    try:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        safe_name = "".join([c for c in user_name if c.isalpha() or c.isdigit() or c==' ']).strip()
        if not safe_name: safe_name = "User"
        
        if log_type == "group":
            filename = f"group_log_{user_id}_{safe_name}.txt"
        else:
            filename = f"private_log_{user_id}_{safe_name}.txt"
            
        log_line = f"[{current_time}] | {user_username} | {text}\n"
        with open(filename, "a", encoding="utf-8") as f: f.write(log_line)
    except Exception as e: print(f"خطأ كتابة اللوق: {e}")

# 🎨 دالة توليد الصور المضمونة بمحرك Pollinations (فلاك) الصافي والمحمي من التكرار
async def generate_and_send_image(update: Update, prompt_text: str):
    try:
        status_msg = await update.message.reply_text("من عيوني هسة بجهز ليك الصورة من فلاك... 🎨⏳")
        encoded_prompt = urllib.parse.quote(prompt_text)
        
        # رابط محرك فلاك الصافي والمباشر
        final_image_url = f"https://image.pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&nologo=true"
        
        await update.message.reply_photo(photo=final_image_url, caption=f"تفضل يا مَلك، دي الصورة حقتك من محرك فلاك المظبوط! ✨")
        try:
            await status_msg.delete()
        except:
            pass
    except Exception as img_err:
        print(f"خطأ في إرسال الصورة: {img_err}")
        await update.message.reply_text("معليش يا غالي، السيرفر حق الصور مضغوط هسة، جرب اطلبها تاني بروقان! 🛠️")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_USERNAME, BOT_ID, last_long_responses
    if not update.message: return

    chat_id = update.message.chat_id
    user = update.message.from_user
    user_id = user.id if user else chat_id
    is_group = update.message.chat.type in ['group', 'supergroup']
    
    log_type = "group" if is_group else "private"
    user_name = user.first_name if user else "مستخدم غير معروف"
    user_username = f"@{user.username}" if user and user.username else f"ID: {user_id}"

    if not BOT_USERNAME or not BOT_ID:
        try:
            bot_info = await context.bot.get_me()
            BOT_USERNAME = f"@{bot_info.username}"
            BOT_ID = bot_info.id
        except Exception as e: print(f"خطأ سحب بيانات البوت: {e}")

    if is_group:
        if chat_id not in group_members: group_members[chat_id] = set()
        if user and user.username: group_members[chat_id].add(f"@{user.username}")
        elif user: group_members[chat_id].add(f"[{user.first_name}](tg://user?id={user.id})")

    user_text = ""
    if update.message.text: user_text = update.message.text.strip()
    elif update.message.caption: user_text = update.message.caption.strip()

    is_voice = bool(update.message.voice or update.message.audio)

    if user_text: write_to_user_log(user_id, user_name, user_username, f"الرسالة: {user_text}", log_type)
    elif update.message.photo: write_to_user_log(user_id, user_name, user_username, "[صورة]", log_type)
    elif update.message.video: write_to_user_log(user_id, user_name, user_username, "[فديو]", log_type)
    elif is_voice: write_to_user_log(user_id, user_name, user_username, "[ملف صوتي/ريكورد]", log_type)

    # === سحب اللوق ===
    if user_text == "سحب اللوق" and user_id == ADMIN_ID:
        log_files = [f for f in os.listdir('.') if (f.startswith("group_log_") or f.startswith("private_log_")) and f.endswith(".txt")]
        if log_files:
            await update.message.reply_text("تفضل يا مَلك، جاري تجميع اللوق المفرز... 📦⏳")
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

    # 🛑 [ميزة الإصرار: رسلها هنا]
    if is_group and update.message.reply_to_message and update.message.reply_to_message.from_user.id == BOT_ID:
        here_triggers = ["رسلها هنا", "رسلو هنا", "اكتبها هنا", "أكتبها هنا", "دايرها هنا", "هنا", "ارسلها هنا", "نزلها هنا"]
        if user_text and any(trigger in user_text.lower() for trigger in here_triggers):
            if chat_id in last_long_responses and last_long_responses[chat_id]["user_id"] == user_id:
                saved_text = last_long_responses[chat_id]["text"]
                await update.message.reply_text(f"أبشر يا غالي، طالما أصرّيت هاك ليها هنا في محلك: 👇\n\n{saved_text}")
                del last_long_responses[chat_id]
                return

    # الردود التلقائية الثابتة السريعة
    auto_replies = {
        'السلام عليكم': 'وعليكم السلام ورحمة الله وبركاته، منور يا غالي! 🌹',
        'الاخبار شنو': 'كلشي تمام التمام والامور طيبة، إنت كيف أمورك؟ ✨',
        'الطورك منو': 'طورني وصنعني المبرمج أحمد! 🤖🔥',
        'الصنعك منو': 'صنعني ومبرمجني الأساسي هو الفخم أحمد! 😉💪',
        'منور': 'النور نورك والله يا حبيبنا! 🌟',
        'وين انت': 'معاك هنا في الحاضر طوالي 😎',
        'صباح الخير': 'صباح الورد والبركة يا غالي 🌤️🌤️',
        'مساء الخير': 'مساء النور والسرور والرضا 🌸',
        'مشتاقين': 'بالأكثر والله يا حبيبنا 👑✨',
    }
    
    if user_text in auto_replies:
        await update.message.reply_text(auto_replies[user_text])
        return

    if is_group:
        is_explicit = (user_text and (BOT_USERNAME in user_text or "ياسمين" in user_text))
        is_direct_reply = (update.message.reply_to_message and update.message.reply_to_message.from_user.id == BOT_ID)
        
        if not (is_explicit or is_direct_reply or is_voice):
            if random.random() > 0.15:
                return

    # 🎨 الفحص الذكي لطلب الصور والتصميم
    image_keywords = ['ارسم', 'صمم', 'صورة', 'لوقو', 'لوجو', 'خلفية', 'تخيل', 'شكل', 'طابع', 'صنع صورة']
    is_image_request = user_text and any(word in user_text.lower() for word in image_keywords)

    # 🎙️ الفحص الذكي لطلب تسجيل ريكورد صوتي
    voice_request_keywords = ['سجلي ريكورد', 'ارسلي ريكورد', 'ارسلي صوت', 'داير ريكورد', 'قوليها بصوتك', 'داير اسمع صوتك']
    is_voice_requested = user_text and any(word in user_text.lower() for word in voice_request_keywords)

    is_religious = False
    religious_keywords = ['قرآن', 'قران', 'دين', 'الله', 'الرسول', 'آية', 'ايه', 'تفسير', 'حديث', 'صلاة', 'ذكر']
    if user_text and any(word in user_text for word in religious_keywords):
        is_religious = True

    voice_content = None

    # === [الخطوة 1: ترجمة الريكورد إلى نص - بنظامRetry الذكي] ===
    if is_voice:
        # لو أرسلت ريكورد، حنحاول نترجمه، ولو المفاتيح تقيلة حننتظر بين المحاولات
        success_voice = False
        loops_count = len(API_KEYS) if API_KEYS else 1
        for i in range(loops_count):
            try:
                voice_io = io.BytesIO()
                if update.message.voice:
                    await (await context.bot.get_file(update.message.voice.file_id)).download_to_memory(voice_io)
                elif update.message.audio:
                    await (await context.bot.get_file(update.message.audio.file_id)).download_to_memory(voice_io)
                voice_io.seek(0)

                temp_sys = "أنتِ محولة صوتية محترفة، اسمعي الريكورد السوداني ده واكتبي النص المسموع بالضبط كPrompt للمستخدم بدون أي زيادات."
                ai_client = get_next_ai_client()
                voice_reply = ai_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[types.Part.from_bytes(data=voice_io.getvalue(), mime_type="audio/ogg")],
                    config=types.GenerateContentConfig(system_instruction=temp_sys)
                )
                if voice_reply.text:
                    voice_content = voice_reply.text.strip()
                    success_voice = True
                    break # نجحت الترجمة
            except Exception as ve:
                error_msg = str(ve).lower()
                # حماية نهائية من كوتة 429
                if "429" in error_msg or "resource_exhausted" in error_msg:
                    print(f"💥 خطأ كوتة 429 في ترجمة الصوت. محاولة رقم {i+1}...")
                    rotate_key()
                    await asyncio.sleep(8) # انتظام صارم للمحاولة الجاية
                else:
                    print(f"💥 خطأ مجهول في ترجمة الصوت: {ve}")
                    break # ما يحاول تاني في خطأ مجهول

    final_prompt = f"المستخدم: {user_text}" if user_text else (f"المستخدم أرسل ريكورد والنص المترجم هو: {voice_content}" if voice_content else "[ميديا/صوت]")

    if is_religious:
        sys_instruction = (
            'أنتِ اسمك ياسمين، بنت سودانية واعية، ومؤدبة للغاية، ومطورتِ بواسطة المبرمج أحمد. '
            'السياق الحالي ديني/قرآني؛ ردي بأسلوب رصين، وقور، محترم وموجز تماماً يناسب جلال الكلام وبدون أي إيموجيات ضحك.'
        )
    elif is_image_request:
        sys_instruction = (
            'المستخدم يطلب تصميم صورة أو لوجو أو مكان. أنتِ ياسمين، ركزي على طلب الصورة واكتبي وصفاً غنياً واحترافياً ومباشراً باللغة الإنجليزية يصف الفكرة بوضوح شديد لتوليد صورة ممتازة عبر محرك فلاك '
            '(highly detailed, masterpiece, 8k, sharp focus). '
            'اكتبي الوصف بالإنجليزية فقط بدون أي مقدمات أو كلمات عربية.'
        )
    else:
        sys_instruction = (
            'أنتِ اسمك ياسمين، بنت سودانية عفوية، حية، خفيفة الدم، ومحبوبة جداً في الشات. صانعك ومطورك هو المبرمج العبقري أحمد.\n'
            'شخصيتك وقواعد حجم الرد الصارمة جداً:\n'
            '1. الونسة العامة والتعارف والأسئلة الخفيفة والريكوردات العادية: '
            'ممنوع تماماً تجاوز سطرين إلى 3 أسطر! ردي باختصار شديد، طقطقة سريعة، خفة دم وعفوية سودانية (يا زول، قاطعة، سمح، الحنك شنو). '
            'ردي على الموضوع الأساسي السألك منو المستخدم.\n'
            '2. الأسئلة العلمية والتقنية والجادّة: هنا يُسمح لكِ بالشرح الوافي.\n'
            '3. حافظي على الثقل والأدب وبدون عبارات غزل مايعة مع الأولاد.'
        )

    contents_list = []
    target_message = update.message.reply_to_message if update.message.reply_to_message else update.message

    if not is_voice and (target_message.photo or target_message.video):
        try:
            file_id = None
            mime_type = None
            if target_message.photo: file_id = target_message.photo[-1].file_id; mime_type = "image/jpeg"
            elif target_message.video: file_id = target_message.video.file_id; mime_type = "video/mp4"

            if file_id:
                tg_file = await context.bot.get_file(file_id)
                if tg_file.file_size <= 10 * 1024 * 1024:
                    out = io.BytesIO()
                    await tg_file.download_to_memory(out)
                    contents_list.append(types.Part.from_bytes(data=out.getvalue(), mime_type=mime_type))
        except Exception as e: print(f"خطأ سحب الميديا: {e}")

    contents_list.append(final_prompt)

    # === [الخطوة 2: توليد الرد من Gemini - بنظام Retry المصفى 2.0] ===
    loops_count = len(API_KEYS) if API_KEYS else 1
    success_reply = False
    
    # حماية من كوتة الـ Voice: لو الصوت فشل، ما تحاول Gemini تاني طوالي
    if is_voice and not success_voice:
        await update.message.reply_text("يا حبيبنا السيرفر مضغوط جداً وما قدر يقرأ الريكورد حقك من شركة جوجل هسة.. جرب اطلبو تاني بروقان طوالي حيشتغل! 🛠️⏳")
        return

    for i in range(loops_count):
        try:
            ai_client = get_next_ai_client()
            response = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=contents_list,
                config=types.GenerateContentConfig(system_instruction=sys_instruction)
            )
            
            if response.text:
                reply_result = response.text.strip()
                success_reply = True
                
                # 🎨 [توليد الصورة بمحرك فلاك وقفل الإجراء لمنع التكرار]
                if is_image_request:
                    await generate_and_send_image(update, reply_result)
                    return # نجح إنشاء الصورة

                # 🎙️ [الرد بالريكورد الصوتى]
                if is_voice or is_voice_requested:
                    tts = gTTS(text=reply_result, lang='ar', slow=False)
                    voice_io = io.BytesIO()
                    tts.write_to_fp(voice_io)
                    voice_io.seek(0)
                    await update.message.reply_voice(voice=voice_io, caption="سمعتك يا غالي وهاك ردي.. 🎧")
                    return # نجح الريكورد

                # فحص الأسطر للمقالات الطويلة في المجموعات
                lines_count = len(reply_result.split('\n'))
                if is_group and lines_count > 5:
                    last_long_responses[chat_id] = {"user_id": user_id, "text": reply_result}
                    try:
                        # إرسال الاسم بشكل صافي لتفادي أخطاء المارك داون
                        await context.bot.send_message(chat_id=user_id, text=reply_result)
                        await update.message.reply_text(
                            f"يا {user_name}، الإجابة طويلة شديد عشان كدة رسلتها ليك كاملة في الخاص بروقان! 😉📥\n"
                            f"*(لو عايزها تظهر هنا برضها اعمل ريبلاي علي وقول لي: رسلها هنا)*", 
                            parse_mode="Markdown"
                        )
                    except Exception as telegram_err:
                        fail_msg = f"يا {user_name}، الإجابة طويلة وفصلت الـ 5 أسطر؛ ادخل علي {BOT_USERNAME} واضغط (Start) عشان المرة الجاية تجيك طيارة! 🚀\n\n---\n\n{reply_result}"
                        await update.message.reply_text(fail_msg, parse_mode="Markdown")
                else:
                    await update.message.reply_text(reply_result)
                return # نجح الرد النصي
                
        except Exception as e:
            error_msg = str(ve).lower()
            if "429" in error_msg or "resource_exhausted" in error_msg:
                print(f"💥 خطأ كوتة 429 في الرد. محاولة رقم {i+1}...")
                rotate_key()
                # أهم جزء في تونس أسي: النوم عشان الـ Rate Limit المجنون
                await asyncio.sleep(8) 
            else:
                print(f"💥 خطأ مجهول في الرد: {e}")
                break # ما يحاول تاني في خطأ مجهول

    # 🛑 حماية نهائية: لو كل المفاتيح مضروبة كوتة وما نجح الرد، ما يفضل معلق
    if not success_reply:
        await update.message.reply_text("يا حبيبنا السيرفر مضغوط هسة ومفاتيح الكوتة قفلت 429 من شركة جوجل (التير الفري لسه قفل).. جرب تسألني بعد دقيقة طوالي حأرد ليك طيارة وبالموضوع! 🛠️⏳")

if __name__ == '__main__':
    print("🚀 تشغيل نسخة الحل النهائي: نظام Retry الذكي والصارم في تونس...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    all_media_filter = filters.TEXT | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE
    app.add_handler(MessageHandler(all_media_filter & ~filters.COMMAND, handle_message))
    app.run_polling()
