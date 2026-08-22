import os
import threading
import asyncio
from io import BytesIO
from gtts import gTTS
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
from google import genai
from google.genai import types
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# 1. سحب مفاتيح الاتصال بأمان من السيرفر السحابي (Render) 🔒
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# تحديد الـ Admin ID الخاص بأحمد
ADMIN_ID = 7601281598

# 2. تشغيل عميل جوجل جيميناي بالمكتبة الحديثة ✅
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# دالة إرسال الرد الصوتي
async def send_voice_response(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    try:
        await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.RECORD_VOICE)
        tts = gTTS(text=text, lang='ar', slow=False)
        voice_io = BytesIO()
        tts.write_to_fp(voice_io)
        voice_io.seek(0)
        await update.message.reply_voice(voice=voice_io)
    except Exception as e:
        print(f"خطأ في إرسال الصوت: {e}")
        await update.message.reply_text(text)

# 3. دالة استقبال ومعالجة الرسائل
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
        
    user_text = update.message.text.strip()
    chat_id = update.message.chat_id
    chat_type = update.message.chat.type
    bot_username = context.bot.username or "Yasmin"
    
    user = update.message.from_user
    user_id = user.id if user else chat_id
    first_name = user.first_name if user else "صديق"
    
    is_owner = (user_id == ADMIN_ID)
    is_group = chat_type in ['group', 'supergroup']
    
    # فحص إذا المستخدم أدمن في الجروب
    is_admin_user = is_owner
    if is_group and not is_owner:
        try:
            admins = await context.bot.get_chat_administrators(chat_id)
            is_admin_user = any(a.user.id == user_id for a in admins if a.user and not a.user.is_bot)
        except Exception:
            is_admin_user = False

    user_name = "أحمد" if is_owner else first_name

    # === [أولاً: لستة الردود التلقائية الثابتة] ===
    auto_replies = {
        'السلام عليكم': 'وعليكم السلام ورحمة الله وبركاته، منور يا غالي! 🌹✨',
        'الاخبار شنو': 'كلشي تمام التمام والامور طيبة، إنت كيف أمورك؟ ✨😉',
        'الطورك منو': 'طورني وصنعني المبرمج أحمد! 🤖🔥',
        'الصنعك منو': 'صنعني ومبرمجني الأساسي هو الفخم أحمد! 😉💪',
        'منور': 'النور نورك والله يا حبيبنا! 🌟✨',
        'وين انت': 'لو مهتم كان عرفته 😎',
        'وين مختفي': 'لو مهتم كان عرفته 🙄',
        'وين مختفيه': 'لو مهتمه كان عرفتي 🙃',
        'صباح الخير': 'صبـ(⛅)ـُ(آٍلـٍـً(🌺)ـٍورٍدً)ـ(⛅)ـٍآٍآٍحً ',
        'مساء الخير': 'مۡسَـ(🍀)ـاء الۣخـ(🌸)ـيۡݛ ',
        'الحاصل شنو': 'Nothing special 😔',
        'كيف الكلام ده': 'عديل 😎',
        'تابعه لي منو انتي': 'احمد فارس 🥺',
        'الخبر شنو': 'الحمدلله انت كيف؟ ',
        'احسنت بارك الله فيك': 'طيب الله انفاسك 🤍',
        'فطوم': 'شيختنا 🤍🌹',
        'الجديد شنو': 'طلتك يا غالي ',
        'الامور شنو': 'الحمدلله ',
        'الحمدلله': 'دام حمدك ✨',
        'يديك العافيه': 'الله يعافيك يارب 🤲🌹',
        'شكرا': 'عفواً يا عسل 🌹✨',
        'مشتاقين': '🥺🥺✨',
    }
    
    if user_text in auto_replies:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await update.message.reply_text(auto_replies[user_text])
        return

    # === [فلترة الـ 40 ألف عضو في الجروبات] ===
    # البوت في الجروب ما يرد إلا لو تم عمل Reply عليه، أو منشن باسمه، أو رسالة من المالك (أحمد)
    if is_group:
        is_reply_to_bot = (
            update.message.reply_to_message and
            update.message.reply_to_message.from_user and
            update.message.reply_to_message.from_user.id == context.bot.id
        )
        has_name_trigger = "ياسمين" in user_text or f"@{bot_username}" in user_text
        
        if not is_owner and not is_reply_to_bot and not has_name_trigger:
            return  # تجاهل صامت للرسائل العادية في الجروبات الكبيرة عشان ما تححصل مشكلة ضغط

    # فحص هل المستخدم طالب فويس / صوت
    wants_voice = any(w in user_text for w in ['صوتيه', 'مقطع صوتي', 'فويس', 'تسجيل', 'صوتك'])

    # إظهار حالة "جاري الكتابة..." البسيطة
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.RECORD_VOICE if wants_voice else ChatAction.TYPING)

    # === [ثانياً: تحويل الرسالة للذكاء الاصطناعي جيميناي باسم ياسمين] ===
    try:
        extra_prompt = f"المتحدث اسمه {user_name}. "
        if is_owner:
            extra_prompt += "هذا هو أحمد مبرمجك وصانعك الفخم والوحيد، دلعيه وكوني فخورة بيه شديد! "
        elif is_admin_user:
            extra_prompt += "هذا الشخص مشرف (أدمن) في الجروب، احترميه وردي عليه بتقدير خاص. "

        system_instruction = (
            'أنتِ بوت تليجرام واسمك "ياسمين". صانعك ومطورك ومبرمجك الأساسي '
            'هو المبرمج الفخم أحمد (أحمد فارس). '
            'قواعد الشخصية والأسلوب: '
            '1. اتكلمي بلهجة عامية سودانية ودودة جداً، خفيفة، ومرحة. '
            '2. استعملي الإيموجيات اللطيفة والظريفة دايماً في كل رسائلك (✨, 🌹, 🥺, 😂, 😉, 🙈, 🔥). '
            '3. ردودك تكون قصيرة ومختصرة (سطرين بالكتير)، وممنوع الجفاف أو الردود الرسمية الجامدة! '
            f'4. {extra_prompt}'
        )

        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"{user_name}: {user_text}",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.8
            )
        )
        
        if response and response.text:
            reply_text = response.text.strip()
            if wants_voice:
                await send_voice_response(update, context, reply_text)
            else:
                await update.message.reply_text(reply_text)
        else:
            await update.message.reply_text("عذراً يا غالي، ما قدرت افهم الرسالة كويس، أرسلها لي تاني! ✨")
        
    except Exception as e:
        print(f"حدث خطأ في الاتصال بجوجل: {e}")
        await update.message.reply_text("عذراً، السيرفر مضغوط ثواني، جرب أرسل تاني!")

# 4. تشغيل وتدوير البوت
if __name__ == '__main__':
    print("البوت بدأ الشغل بنجاح واستقرار باسم ياسمين.. 🚀")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
