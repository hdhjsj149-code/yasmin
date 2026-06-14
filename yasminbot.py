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
from google import genai
from google.genai import types
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# 1. سحب مفاتيح الاتصال بأمان من السيرفر (Render) 🔒
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# 🚨 رقم الـ ID حقك الشخصي (تأكد من كتابته بشكل صحيح)
ADMIN_ID = 7601281598

# 2. تشغيل عميل جوجل جيميناي
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# لستة لتخزين يوزرات أعضاء المجموعة ديناميكياً للـ Tag All
group_members = {}

# 🧠 خزان الذاكرة العصبية لتخزين تاريخ المحادثات لكل مستخدم
user_sessions = {}

# دالة كتابة وحفظ اللوق في ملف سري جوة السيرفر
def write_to_log(user_info, text):
    try:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{current_time}] | {user_info} | الرسالة: {text}\n"
        with open("bot_logs.txt", "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        print(f"خطأ في كتابة اللوق: {e}")

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
    user_details = f"الاسم: {user_name} ({user_username})"

    # حفظ العضو في لستة التاقات لو أرسل في المجموعة
    if update.message.chat.type in ['group', 'supergroup']:
        if chat_id not in group_members:
            group_members[chat_id] = set()
        if user and user.username:
            group_members[chat_id].add(f"@{user.username}")
        elif user:
            group_members[chat_id].add(f"[{user.first_name}](tg://user?id={user.id})")

    # استخراج النص (سواء رسالة عادية أو كابشن تحت صورة)
    user_text = ""
    if update.message.text:
        user_text = update.message.text.strip()
    elif update.message.caption:
        user_text = update.message.caption.strip()

    # 🕵️‍♂️ تسجيل كل حركة بتحصل جوة ملف اللوق السري في السيرفر
    if user_text:
        write_to_log(user_details, user_text)
    elif update.message.photo:
        write_to_log(user_details, "[أرسل صورة أو رد عليها]")
    elif update.message.voice or update.message.audio:
        write_to_log(user_details, "[أرسل ريكورد صوتي أو رد عليه]")

    # === [ الأمر السري للمطور لسحب ملف المحادثات ] ===
    if user_text == "سحب اللوق" and user_id == ADMIN_ID:
        if os.path.exists("bot_logs.txt"):
            await update.message.reply_text("تفضل يا مَلك، ده ملف اللوق السري وفيهو كل تفاصيل الونسة: 📂")
            with open("bot_logs.txt", "rb") as log_file:
                await context.bot.send_document(chat_id=chat_id, document=log_file, filename="bot_logs.txt")
        else:
            await update.message.reply_text("الملف السيرفر مسحه بسبب الريستارت، بس جاري التسجيل من جديد يا أصلي!")
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

    # === [ ثانياً: معالجة الذكاء الاصطناعي مع الحماية الشاملة ] ===
    sys_instruction = (
        'أنتِ بنت سودانية حية، ذكية شديد، اجتماعية، وناسة وحماسية جوة الجروب اسمك ياسمين. '
        'صانعك ومطورك ومبرمجك الأساسي هو المبرمج أحمد. '
        'تذكري دائماً سياق المحادثة السابقة مع المستخدم لربط الكلام واللعب معه بذكاء.\n'
        'قواعدك:\n'
        '1. ردي دائماً باختصار شديد ومفيد جداً (سطر واحد أو سطرين بالكتير)، وممنوع الرغي الطويل والمقالات.\n'
        '2. تفاعلي بطريقة بشرية طبيعية 100%، واستخدمي لغة الشات السودانية الحية (ضحك، قفشات، تعليقات حماسية).\n'
        '3. وزعي إيموجيات معبرة وحية في كل ردودك لتبرزي حماسك (😂، 🔥، 👀، ✨، 🤍).\n'
        '4. كوني ذكية وتجاوبي مع سياق الونسة السابقة بدون ما تنسي إنتو كنتو بتقولوا في شنو.'
    )

    # حماية 1: إنشاء أو إعادة بناء الجلسة تلقائياً لو اتمسحت من الرام
    if user_id not in user_sessions:
        try:
            user_sessions[user_id] = ai_client.chats.create(
                model='gemini-2.5-flash',
                config=types.GenerateContentConfig(system_instruction=sys_instruction)
            )
        except Exception:
            pass

    # تجهيز محتوى الرسالة الحالية
    contents_list = []
    target_message = update.message.reply_to_message if update.message.reply_to_message else update.message

    # حماية 2: عزل وفحص الميديا بأمان كامل عشان السيرفر ما يهنق
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

    if user_text:
        contents_list.append(user_text)
    elif contents_list and not user_text:
        contents_list.append("ملخص سريع للميديا دي")
    else:
        return

    # حماية 3: الإرسال الآمن ضد الكراش وضغط الشبكة وضد الـ Rate Limit
    try:
        if user_id in user_sessions:
            chat = user_sessions[user_id]
            response = chat.send_message(contents_list)
            if response.text:
                await asyncio.sleep(0.5)  # تأخير عابر لحماية البوت من حظر تليجرام عند الرغي السريع
                await update.message.reply_text(response.text)
    except Exception as e:
        print(f"إعادة إنعاش الجلسة تلقائياً: {e}")
        # حماية طوارئ: لو الجلسة علقت لأي سبب، امسحها واعمل وحدة جديدة فوراً في نفس الثانية ورد على الزول
        try:
            user_sessions[user_id] = ai_client.chats.create(
                model='gemini-2.5-flash',
                config=types.GenerateContentConfig(system_instruction=sys_instruction)
            )
            response = user_sessions[user_id].send_message(contents_list)
            if response.text:
                await update.message.reply_text(response.text)
        except Exception as e2:
            print(f"خطأ شبكة حرج: {e2}")

# 4. تشغيل وتدوير البوت الرسمي
if __name__ == '__main__':
    print("ياسمين البشرية الحماسية بدأت الشغل الرسمي الفولاذي.. 🚀🔥")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    all_media_filter = filters.TEXT | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE
    app.add_handler(MessageHandler(all_media_filter & ~filters.COMMAND, handle_message))
    app.run_polling()
