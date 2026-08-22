import os
import threading
import time
import requests
import random
import socket
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer

# --- [1. السيرفر الوهمي ودالة الحفاظ على التشغيل 24/7] ---
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def run_dummy_server():
    try:
        port = int(os.environ.get("PORT", 8080))
        if is_port_in_use(port): return
        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, format, *args): return
        TCPServer.allow_reuse_address = True
        with TCPServer(("", port), QuietHandler) as httpd:
            httpd.serve_forever()
    except: pass

def keep_alive_ping():
    time.sleep(120)
    external_url = os.environ.get("RENDER_EXTERNAL_URL")
    while True:
        try:
            if external_url:
                requests.get(external_url, timeout=15)
            else:
                port = os.environ.get("PORT", "8080")
                requests.get(f"http://127.0.0.1:{port}/", timeout=10)
        except: pass
        time.sleep(300)

threading.Thread(target=run_dummy_server, daemon=True).start()
threading.Thread(target=keep_alive_ping, daemon=True).start()

# --- [2. المكتبات الأساسية والإعدادات] ---
from google import genai
from google.genai import types
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
ADMIN_ID = 7601281598  # الـ ID حق أحمد المطور

ai_client = genai.Client(api_key=GEMINI_API_KEY)

# الذاكرة الذكية للمستخدمين والجروبات
user_profiles = {}          # {user_id: {"name": "أحمد", "notes": "المطور والمالك", "met": True}}
group_mute_status = {}     # حالة السكوت والتشغيل
group_message_counters = {}
last_spontaneous_time = {}

# --- [3. دالة معالجة الرسائل والجروبات] ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_id = update.message.chat_id
    chat_type = update.message.chat.type
    user_text = update.message.text.strip()
    bot_username = context.bot.username or "Yasmin"

    user = update.message.from_user
    user_id = user.id if user else chat_id
    first_name = user.first_name if user else "صديق"
    
    is_owner = (user_id == ADMIN_ID)
    is_group = chat_type in ['group', 'supergroup']
    is_admin_user = is_owner

    # جلب صلاحيات الأدمن واستبعاد البوتات
    if is_group and not is_owner:
        try:
            admins = await context.bot.get_chat_administrators(chat_id)
            is_admin_user = any(a.user.id == user_id for a in admins if a.user and not a.user.is_bot)
        except:
            is_admin_user = False

    # === [أولاً: نظام التعرف والذاكرة الذكية للناس] ===
    if user_id not in user_profiles:
        if is_owner:
            user_profiles[user_id] = {"name": "أحمد", "role": "المطور والمهندس الأساسي", "met": True, "style": "احترام مطلق ومودة عالية"}
        else:
            user_profiles[user_id] = {"name": first_name, "role": "عضو" if not is_admin_user else "مشرف", "met": False, "style": "عادي"}

    profile = user_profiles[user_id]

    # === [ثانياً: التحكم بالصمت والتشغيل عبر الأوامر] ===
    if any(cmd in user_text for cmd in ['اسكتي', 'انكتمي', 'اصفي', 'ما تتكلمي', 'سكون']):
        if not is_group or is_admin_user:
            group_mute_status[chat_id] = True
            await update.message.reply_text("أبشري يا سعادة المشرف، صامتة وما حأتكلم إطلاقاً إلا لما تأمرني! 🤐✋")
            return
    
    if any(cmd in user_text for cmd in ['اتكلمي', 'اتكلمي عادي', 'واصلي', 'فك السكوت']):
        if not is_group or is_admin_user:
            group_mute_status[chat_id] = False
            await update.message.reply_text("حاضر يا فندم! رجعت للونسة والتفاعل معاكم من جديد ✨🚀")
            return

    if group_mute_status.get(chat_id, False):
        return

    # === [ثالثاً: أوامر التلقين والحفظ الفوري] ===
    if 'احفظي' in user_text or 'احفظ' in user_text:
        profile['style'] += f" | ملاحظة جديدة: {user_text}"
        profile['met'] = True
        await update.message.reply_text(f"تم يا {profile['name']}! حفظت المعلومة دي في البروفايل حقك عندي 👌✨")
        return

    # شروط التفاعل داخل الجروب
    is_mentioned = False
    if is_group:
        is_reply_to_bot = (
            update.message.reply_to_message and 
            update.message.reply_to_message.from_user and 
            update.message.reply_to_message.from_user.id == context.bot.id
        )
        has_name_trigger = "ياسمين" in user_text or f"@{bot_username}" in user_text
        
        if is_reply_to_bot or has_name_trigger:
            is_mentioned = True

        # نظام المشاركة العفوية
        now = time.time()
        group_message_counters[chat_id] = group_message_counters.get(chat_id, 0) + 1
        last_time = last_spontaneous_time.get(chat_id, 0)

        should_spontaneously_reply = False
        if not is_mentioned and (now - last_time > 3600) and (group_message_counters[chat_id] >= 40):
            if len(user_text) > 10 and not user_text.startswith('/'):
                if random.random() < 0.3:
                    should_spontaneously_reply = True
                    last_spontaneous_time[chat_id] = now
                    group_message_counters[chat_id] = 0

        if not is_mentioned and not should_spontaneously_reply:
            return

    # === [رابعاً: الردود الثابتة السريعة] ===
    auto_replies = {
        'السلام عليكم': f'وعليكم السلام ورحمة الله وبركاته، مرحب يا {profile["name"]}! 🌹',
        'الاخبار شنو': 'كلشي تمام التمام والامور طيبة، إنت كيف أمورك؟ ✨',
        'الطورك منو': 'طورني وصنعني المبرمج أحمد! 🤖🔥',
        'الصنعك منو': 'صنعني ومبرمجني الأساسي هو الفخم أحمد! 😉💪',
        'منور': 'النور نورك والله يا حبيبنا! 🌟',
        'وين انت': 'لو مهتم كان عرفته 😎',
        'صباح الخير': 'صبـ(⛅)ـُ(آٍلـٍـً(🌺)ـٍورٍدً)ـ(⛅)ـٍآٍآٍحً ',
        'مساء الخير': 'مۡسَـ(🍀)ـاء الۣخـ(🌸)ـيۡݛ ',
        'يديك العافيه': 'الله يعافيك يارب 🤲',
        'شكرا': 'عفواً 🌹'
    }

    if user_text in auto_replies:
        await update.message.reply_text(auto_replies[user_text])
        return

    # === [خامساً: توجيه الذكاء الاصطناعي مع معالجة البروفايل للتعرف] ===
    try:
        # لو الزول أول مرة يتعامل معاها
        first_time_instruction = ""
        if not profile['met'] and not is_owner:
            first_time_instruction = (
                f"هذه أول مرة تتحدثين فيها مع هذا الشخص واسمه ({profile['name']}). رحبي به ولطفي الجو واذكري أنكِ تشرفتِ بالتعرف عليه، "
                "ولن تكرري هذا التعارف المباشر مرة أخرى لأنكِ أصبحتِ تعرفينه الآن."
            )
            profile['met'] = True  # تحويل الحالة لـ معروف خلاص

        if is_owner:
            prompt_instruction = (
                f"أنتِ ياسمين. المتحدث الآن هو صانعك ومبرمجك الأساسي والوحيد أحمد. "
                f"تحدثي معه بأعلى درجات التقدير والمودة بالعامية السودانية."
            )
        elif is_admin_user:
            prompt_instruction = (
                f"أنتِ ياسمين. المتحدث هو أحد مشرفي الجروب واسمه {profile['name']}. "
                f"عاملي المشرف باحترام تقدير لرتبته. {first_time_instruction} "
                f"معلومات البروفايل: {profile['style']}"
            )
        elif is_group and not is_mentioned:
            prompt_instruction = (
                f"أنتِ ياسمين. شاركتِ عفوياً في ونسة الجروب رداً على {profile['name']}. ردي بأسلوب سوداني طريف ومختصر جداً (سطر واحد)."
            )
        else:
            prompt_instruction = (
                f"أنتِ ياسمين. صانعك هو المبرمج أحمد. ردي على {profile['name']} بلهجة سودانية ودودة ومحترمة. "
                f"{first_time_instruction} تفاصيل بروفايله وطريقة تعامله المحفوظة: ({profile['style']})."
            )

        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_text,
            config=types.GenerateContentConfig(
                system_instruction=prompt_instruction
            )
        )
        if response.text:
            await update.message.reply_text(response.text)
        else:
            if not is_group:
                await update.message.reply_text("عذراً، لم أستطع فهم الرسالة، جرب صياغتها بطريقة أخرى.")

    except Exception as e:
        print(f"حدث خطأ في الاتصال بجوجل: {e}")
        if not is_group:
            await update.message.reply_text("عذراً، السيرفر مضغوط ثواني، جرب أرسل تاني!")

# --- [4. تشغيل وتدوير البوت] ---
if __name__ == '__main__':
    print("البوت بدأ الشغل بنجاح واستقرار باسم ياسمين.. 🚀")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
