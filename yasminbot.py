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
from google import genai
from google.genai import types
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# 1. سحب مفاتيح الاتصال بأمان من السيرفر (Render) 🔒
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# 2. تشغيل عميل جوجل جيميناي
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# لستة لتخزين يوزرات أعضاء المجموعة ديناميكياً للـ Tag All
group_members = {}

# دالة استقبال ومعالجة الرسائل والميديا
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    chat_id = update.message.chat_id
    user = update.message.from_user
    
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

    # === [ أولاً: لستة الردود التلقائية الثابتة (القديمة + الفاضية) ] ===
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
        
        # باقي الـ 35 خانة الفاضية جاهزة لتعديلك
        'الكلمة 23': 'الرد هنا 23',
        'الكلمة 24': 'الرد هنا 24',
        'الكلمة 25': 'الرد هنا 25',
        'الكلمة 26': 'الرد هنا 26',
        'الكلمة 27': 'الرد هنا 27',
        'الكلمة 28': 'الرد هنا 28',
        'الكلمة 29': 'الرد هنا 29',
        'الكلمة 30': 'الرد هنا 30',
        'الكلمة 31': 'الرد هنا 31',
        'الكلمة 32': 'الرد هنا 32',
        'الكلمة 33': 'الرد هنا 33',
        'الكلمة 34': 'الرد هنا 34',
        'الكلمة 35': 'الرد هنا 35',
    }
    
    if user_text in auto_replies:
        await update.message.reply_text(auto_replies[user_text])
        return

    # === [ ثانياً: معالجة الذكاء الاصطناعي مع شرط العلامة المنقوطة (;) ] ===
    if user_text.startswith(';'):
        cleaned_text = user_text[1:].strip()
        
        contents_list = []
        mime_type = None
        file_bytes = None
        
        target_message = update.message
        if update.message.reply_to_message:
            target_message = update.message.reply_to_message

        # فحص وتحميل الصور والريكوردات الخفيفة بحذر عشان السيرفر ما يقع
        try:
            if target_message.photo:
                file_id = target_message.photo[-1].file_id
                mime_type = "image/jpeg"
            elif target_message.voice:
                file_id = target_message.voice.file_id
                mime_type = "audio/ogg"
            elif target_message.audio:
                file_id = target_message.audio.file_id
                mime_type = "audio/mpeg"
            else:
                file_id = None

            if file_id:
                tg_file = await context.bot.get_file(file_id)
                # حماية السيرفر: لو الملف أكبر من 5 ميجا بايت ارفض عشان السيرفر ما ينهج
                if tg_file.file_size > 5 * 1024 * 1024:
                    await update.message.reply_text("الملف ده حجمه كبير شديد على السيرفر المجاني يا غالي! 😅")
                    return
                
                out = io.BytesIO()
                await tg_file.download_to_memory(out)
                file_bytes = out.getvalue()
                
                contents_list.append(
                    types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
                )

        except Exception as e:
            print(f"خطأ ميديا خفيف: {e}")
            # بنتجاوز الخطأ ونخلي البوت يكمل بالنص بس بدل ما يعلق

        if cleaned_text:
            contents_list.append(cleaned_text)
        elif file_bytes and not cleaned_text:
            contents_list.append("أعطني ملخص سريع ومفيد للميديا دي")
        else:
            return 

        # إرسال الطلب النهائي الخفيف والسريع لجيميناي
        try:
            response = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=contents_list,
                config=types.GenerateContentConfig(
                    system_instruction=(
                        'أنتِ بوت تليجرام سريع اسمك ياسمين، صانعك ومطورك هو المبرمج أحمد. '
                        'ردي دائماً بإجابات معقولة، مباشرة، ومتوسطة الطول وبدون رغي زائد. '
                        'استخدمي العامية السودانية الودودة والمفهومة دائماً.'
                    )
                )
            )
            if response.text:
                await update.message.reply_text(response.text)
            else:
                await update.message.reply_text("سمعت وشفت، بس ما قدرت أطلع نص واصح!")
            
        except Exception as e:
            print(f"جيميناي تايم آوت: {e}")
            await update.message.reply_text("عطل خفيف في الشبكة، أرسل رسالتك تاني هسة حترد!")
    else:
        return

# 4. تشغيل وتدوير البوت
if __name__ == '__main__':
    print("ياسمين السريعة والمحمية بدأت الشغل.. 🚀🌺")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    all_media_filter = filters.TEXT | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE
    app.add_handler(MessageHandler(all_media_filter & ~filters.COMMAND, handle_message))
    app.run_polling()
