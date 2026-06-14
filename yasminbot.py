import os
import threading
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, format, *args): return
    with TCPServer(("", port), QuietHandler) as httpd:
        httpd.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()

import os
import io
import datetime
import asyncio
import zipfile  # 📦 موديول ضغط الملفات
from google import genai
from google.genai import types
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# 1. سحب مفاتيح الاتصال بأمان من السيرفر (Render) 🔒
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# 🚨 رقم الـ ID حقك الشخصي (تأكد من وضع الأرقام فقط)
ADMIN_ID = 7601281598

# 2. تشغيل عميل جوجل جيميناي
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# لستة لتخزين يوزرات أعضاء المجموعة ديناميكياً للـ Tag All
group_members = {}

# 🧠 خزان الذاكرة الذكية الموسعة (يشيل حتى 14 رسالة متبادلة لربط قوي)
manual_history = {}

# 📁 دالة حفظ اللوق في ملف منفصل لكل مستخدم براهو
def write_to_user_log(user_id, user_name, user_username, text):
    try:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # تنظيف الاسم من أي رموز غريبة ممكن تبوظ اسم الملف
        safe_name = "".join([c for c in user_name if c.isalpha() or c.isdigit() or c==' ']).strip()
        if not safe_name:
            safe_name = "User"
            
        filename = f"log_{user_id}_{safe_name}.txt"
        log_line = f"[{current_time}] | {user_username} | الرسالة: {text}\n"
        
        with open(filename, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        print(f"خطأ في كتابة لوق المستخدم: {e}")

# دالة استقبال ومعالجة الرسائل والميديا
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    chat_id = update.message.chat_id
    user = update.message.from_user
    user_id = user.id if user else chat_id
    
    # تجهيز بيانات المستخدم للـ Log
    user_name = user.first_name if user else "مستخدم غير معروف"
    user_username = f"@{user.username}" if user and user.username else f"ID: {user_id}"

    # حفظ العضو في لستة التاقات لو أرسل في المجموعة
    if update.message.chat.type in ['group', 'supergroup']:
        if chat_id not in group_members:
            group_members[chat_id] = set()
        if user and user.username:
            group_members[chat_id].add(f"@{user.username}")
        elif user:
            group_members[chat_id].add(f"[{user.first_name}](tg://user?id={user.id})")

    # استخراج النص
    user_text = ""
    if update.message.text:
        user_text = update.message.text.strip()
    elif update.message.caption:
        user_text = update.message.caption.strip()

    # 🕵️‍♂️ تسجيل الحركة جوة الملف الخاص باليوزر براهو هسة!
    if user_text:
        write_to_user_log(user_id, user_name, user_username, user_text)
    elif update.message.photo:
        write_to_user_log(user_id, user_name, user_username, "[أرسل صورة أو رد عليها]")
    elif update.message.voice or update.message.audio:
        write_to_log(user_id, user_name, user_username, "[أرسل ريكورد صوتي أو رد عليه]")

    # === [ الأمر السري للمطور لسحب ملف المحادثات مضغوط ومفصل ] ===
    if user_text == "سحب اللوق" and user_id == ADMIN_ID:
        # تجميع كل ملفات التكست حقت اللوق الموجودة في السيرفر هسة
        log_files = [f for f in os.listdir('.') if f.startswith("log_") and f.endswith(".txt")]
        
        if log_files:
            await update.message.reply_text("تفضل يا مَلك، جاري تجميع وضغط لوقات المستخدمين كل زول براهو... 📦⏳")
            
            zip_filename = "all_users_logs.zip"
            # إنشاء ملف الـ ZIP وضغط الملفات جواهو
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in log_files:
                    zipf.write(file)
            
            # إرسال الملف المضغوط للـ Admin
            with open(zip_filename, "rb") as log_zip:
                await context.bot.send_document(chat_id=chat_id, document=log_zip, filename=zip_filename)
            
            # تنظيف ملف الـ ZIP بعد الإرسال عشان ما يتقل السيرفر
            try:
                os.remove(zip_filename)
            except:
                pass
        else:
            await update.message.reply_text("الملف لسة فاضي وماف يوزرات أرسلوا حاجة يا أصلي!")
        return

    # === [ خاصية الـ TAG ALL ] ===
    if user_text.lower() in ['تاق', '@all', 'تاغ']:
        if update.message.chat.type not in ['group', 'supergroup']:
            await update.message.reply_text("الخاصية دي بتشتغل جوة المجموعات بس يا ملك! 📢")
            return
            
        members = group_members.get(chat_id, set())
        if not members:
            await update.message.reply_text("لسة ما جمعت أعضاء كفاية، أرسلوا رسايل عشان ألقطكم! 👀")
            return
            
        tag_text = "📢 **نداء عاجل للجميع:**\n\n" + " ".join(list(members))
        await update.message.reply_text(tag_text, parse_mode="Markdown")
        return

    # === [ أولاً: لستة الردود التلقائية الثابتة ] ===
    auto_replies = {
        'السلام عليكم': 'وعليكم السلام ورحمة الله وبركاته، منور يا غالي! 🌹',
        'الاخبار شنو': 'كلشي تمام التمام والامور طيبة، إنت كيف أمورك؟ ✨',
        'الطورك منو': 'طورني وصنعني المبرمج أحمد! 🤖🔥',
        'الصنعك منو': 'صنعني ومبرمجني الأساسي هو الفخم أحمد، ! 😉💪',
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

    # === [ ثانياً: معالجة الذكاء الاصطناعي بنظام الذاكرة الموسعة ] ===
    sys_instruction = (
        'أنتِ بنت سودانية حية، ذكية شديد، اجتماعية، وناسة وحماسية جوة الجروب اسمك ياسمين. '
        'صانعك ومطورك ومبرمجك الأساسي هو المبرمج أحمد. '
        'قواعدك:\n'
        '1. ردي دائماً باختصار شديد ومفيد جداً (سطر واحد أو سطرين بالكتير)، وممنوع الرغي الطويل والمقالات.\n'
        '2. تفاعلي بطريقة بشرية طبيعية 100%، واستخدمي لغة الشات السودانية الحية (ضحك، قفشات، تعليقات حماسية).\n'
        '3. وزعي إيموجيات معبرة وحية في كل ردودك لتبرزي حماسك (😂، 🔥، 👀، ✨، 🤍).\n'
        '4. تسيق الونسة الفاتت معروض عليك بالكامل، ركزي فيهو وافهمي قواعد اللعبة أو الحنك البتقال عشان تردي بذكاء مستمر وبدون نسيان.'
    )

    if user_id not in manual_history:
        manual_history[user_id] = []

    contents_list = []
    target_message = update.message.reply_to_message if update.message.reply_to_message else update.message

    # فحص ومعالجة الميديا بأمان
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
                if tg_file.file_size <= 6 * 1024 * 1024:
                    out = io.BytesIO()
                    await tg_file.download_to_memory(out)
                    contents_list.append(types.Part.from_bytes(data=out.getvalue(), mime_type=mime_type))
        except Exception as e:
            print(f"خطأ ميديا عابر: {e}")

    # تجميع سياق الذاكرة الموسعة (الـ 14 رسالة الأخيرة)
    context_text = ""
    if manual_history[user_id]:
        context_text = "\n".join(manual_history[user_id]) + "\n"

    current_prompt = f"{context_text}المستخدم يقول هسة: {user_text}" if user_text else f"{context_text}[أرسل ميديا]"
    contents_list.append(current_prompt)

    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents_list,
            config=types.GenerateContentConfig(system_instruction=sys_instruction)
        )
        
        if response.text:
            reply_result = response.text.strip()
            
            # حفظ الونسة بنظام الطابور الذكي (تخزين آخر 14 رسالة لمتابعة الألعاب الطويلة بالملي)
            if user_text:
                manual_history[user_id].append(f"المستخدم: {user_text}")
                manual_history[user_id].append(f"ياسمين: {reply_result}")
                if len(manual_history[user_id]) > 14:
                    manual_history[user_id] = manual_history[user_id][-14:]

            await asyncio.sleep(0.3)
            await update.message.reply_text(reply_result)
            
    except Exception as e:
        print(f"خطأ الإرسال: {e}")
        try:
            fallback_response = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[user_text if user_text else "مرحباً"],
                config=types.GenerateContentConfig(system_instruction=sys_instruction)
            )
            if fallback_response.text:
                await update.message.reply_text(fallback_response.text.strip())
        except Exception as e2:
            print(f"فشل كلي: {e2}")

if __name__ == '__main__':
    print("ياسمين بنظام ضغط لوقات المستخدمين المنفصلة بدأت الشغل.. 🚀🔥")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    all_media_filter = filters.TEXT | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE
    app.add_handler(MessageHandler(all_media_filter & ~filters.COMMAND, handle_message))
    app.run_polling()
