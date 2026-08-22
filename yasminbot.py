import os
import threading
import time
import random
import socket
import asyncio
import sqlite3
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer

# --- [1. قاعدة البيانات الدائمة SQLite] ---
DB_FILE = "yasmin_memory.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            role TEXT,
            notes TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_user_profile(user_id, default_name, default_role):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT name, role, notes FROM user_profiles WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if row:
        conn.close()
        return {"name": row[0], "role": row[1], "notes": row[2]}
    else:
        cursor.execute('INSERT INTO user_profiles (user_id, name, role, notes) VALUES (?, ?, ?, ?)',
                       (user_id, default_name, default_role, ""))
        conn.commit()
        conn.close()
        return {"name": default_name, "role": default_role, "notes": ""}

def update_user_notes(user_id, new_note):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT notes FROM user_profiles WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    old_notes = row[0] if row and row[0] else ""
    updated_notes = (old_notes + " | " + new_note).strip(" | ")
    cursor.execute('UPDATE user_profiles SET notes = ? WHERE user_id = ?', (updated_notes, user_id))
    conn.commit()
    conn.close()

init_db()

# --- [2. السيرفر الوهمي للعمل على Render] ---
def run_dummy_server():
    try:
        port = int(os.environ.get("PORT", 8080))
        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, format, *args): return
        TCPServer.allow_reuse_address = True
        with TCPServer(("", port), QuietHandler) as httpd:
            httpd.serve_forever()
    except Exception:
        pass

threading.Thread(target=run_dummy_server, daemon=True).start()

# --- [3. المكتبات والإعدادات الأساسية] ---
from google import genai
from google.genai import types
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
ADMIN_ID = 7601281598  # الـ ID الخاص بـ أحمد

ai_client = genai.Client(api_key=GEMINI_API_KEY)

# متغيرات الذاكرة والمؤقتات
chat_histories = {}
group_mute_status = {}
group_message_counters = {}
last_spontaneous_time = {}

BASE_SYSTEM_INSTRUCTION = (
    'أنتِ بوت تليجرام واسمك ياسمين. صانعك ومطورك ومبرمجك الأساسي '
    'هو المبرمج أحمد. إذا سألك أي شخص من صنعك، من طورك، أو من مبرمجك، '
    'أخبره بفخر وثقة أن أحمد هو صانعك ومطورك. '
    'قواعد الشخصية: '
    '1. الردود قصيرة جداً ومختصرة (سطر أو سطرين بالكتير). '
    '2. اللهجة: عامية سودانية بسيطة، ودودة، ومرحة جداً وعفوية بدون تكلف أو رسميات. '
    '3. ركزي في الونسة وما تنسي الكلام الاتقال ليك قبل شوية.'
)

# --- [دالة مساعدة لإرسال حالة الكتابة بشكل غير معطل مستمر] ---
async def send_continuous_action(bot, chat_id, action_type=ChatAction.TYPING, duration=5.0):
    """ترسل حالة الكتابة أو تسجيل الصوت لتلجرام بصورة تضمن ظهورها طوال وقت تجهيز الرد"""
    start_time = time.time()
    while time.time() - start_time < duration:
        try:
            await bot.send_chat_action(chat_id=chat_id, action=action_type)
        except Exception:
            pass
        await asyncio.sleep(4.0)

# --- [4. دالة معالجة الرسائل] ---
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

    if is_group and not is_owner:
        try:
            admins = await context.bot.get_chat_administrators(chat_id)
            is_admin_user = any(a.user.id == user_id for a in admins if a.user and not a.user.is_bot)
        except Exception:
            is_admin_user = False

    default_role = "المطور والمالك" if is_owner else ("مشرف" if is_admin_user else "عضو")
    default_name = "أحمد" if is_owner else first_name
    profile = get_user_profile(user_id, default_name, default_role)

    # التحكم في السكوت والتشغيل
    if any(cmd in user_text for cmd in ['اسكتي', 'انكتمي', 'اصفي', 'ما تتكلمي', 'سكون']):
        if not is_group or is_admin_user:
            group_mute_status[chat_id] = True
            await update.message.reply_text("حاضر، صامتة وما بتكلم إلا تقول لي اتكلمي! 🤐")
            return

    if any(cmd in user_text for cmd in ['اتكلمي', 'اتكلمي عادي', 'واصلي', 'فك السكوت']):
        if not is_group or is_admin_user:
            group_mute_status[chat_id] = False
            await update.message.reply_text("حاضر يا غالي! رجعت معاكم تاني ✨")
            return

    if group_mute_status.get(chat_id, False):
        return

    # التلقين والحفظ الدائم
    if 'احفظي' in user_text or 'احفظ' in user_text:
        update_user_notes(user_id, user_text)
        await update.message.reply_text(f"حفظتها عندي في الذاكرة الدائمة يا {profile['name']} 👌✨")
        return

    # شروط التفاعل داخل الجروبات
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

    # === [أولاً: لستة الردود التلقائية الثابتة والـ 35 خانة الفاضية] ===
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
        
        # ⬇️ الـ 35 خانة الفاضية جاهزة لـ تعديلك ⬇️
        'الكلمة 18': 'الرد هنا 18',
        'الكلمة 19': 'الرد هنا 19',
        'الكلمة 20': 'الرد هنا 20',
        'الكلمة 21': 'الرد هنا 21',
        'الكلمة 22': 'الرد هنا 22',
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
        'الكلمة 35': 'الرد here 35',
    }

    if user_text in auto_replies:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1.2)
        await update.message.reply_text(auto_replies[user_text])
        return

    # إدارة ذاكرة المحادثة القريبة (آخر 6 رسائل)
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []

    history = chat_histories[chat_id]
    history.append({"role": "user", "parts": [{"text": f"المتحدث ({profile['name']}): {user_text}"}]})

    if len(history) > 6:
        chat_histories[chat_id] = history[-6:]
        history = chat_histories[chat_id]

    try:
        extra_info = f"المتحدث اسمه {profile['name']}. "
        if is_owner:
            extra_info += "هذا هو أحمد مبرمجك وصانعك الوحيد. "
        elif is_admin_user:
            extra_info += "هذا أدمن الجروب، احترميه وردي عليه بلطف. "

        if profile['notes']:
            extra_info += f"معلومات محفوظة عنه: ({profile['notes']})."

        full_system_instruction = BASE_SYSTEM_INSTRUCTION + "\n" + extra_info

        # تشغيل إشعار "جاري الكتابة..." في الخلفية
        action_task = asyncio.create_task(
            send_continuous_action(context.bot, chat_id, ChatAction.TYPING, duration=10.0)
        )

        # تشغيل طلب Gemini بشكل Async عبر Thread لتجنب تجميد البوت
        def call_gemini():
            return ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=history,
                config=types.GenerateContentConfig(
                    system_instruction=full_system_instruction,
                    temperature=0.7
                )
            )

        response = await asyncio.to_thread(call_gemini)

        # إلغاء مهمة الـ action بعد استلام الرد
        action_task.cancel()

        if response.text:
            reply_text = response.text.strip()
            history.append({"role": "model", "parts": [{"text": reply_text}]})
            await update.message.reply_text(reply_text)
        else:
            if not is_group:
                await update.message.reply_text("عذراً، لم أستطع فهم الرسالة، جرب صياغتها بطريقة أخرى.")

    except Exception as e:
        print(f"حدث خطأ في الاتصال بجوجل: {e}")
        if not is_group:
            await update.message.reply_text("عذراً، السيرفر مضغوط ثواني، جرب أرسل تاني!")

# --- [5. تشغيل وتدوير البوت] ---
if __name__ == '__main__':
    print("البوت بدأ الشغل بنجاح واستقرار باسم ياسمين.. 🚀")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
