import os
import threading
import time
import requests
import random
import urllib.parse
import socket
import io
import json
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer

# --- سيستم حماية البورت ومنع OSError 98 ---
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def keep_alive_ping():
    time.sleep(300)
    while True:
        try:
            port = os.environ.get("PORT", "8080")
            requests.get(f"http://127.0.0.1:{port}/", timeout=10)
        except: pass
        time.sleep(600)

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

threading.Thread(target=run_dummy_server, daemon=True).start()
threading.Thread(target=keep_alive_ping, daemon=True).start()

# --- مكتبات التلجرام والذكاء الاصطناعي ---
from gtts import gTTS  
from google import genai
from google.genai import types
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
ADMIN_ID = 7601281598  # 👈 الـ ID حق حسابك في التلجرام

API_KEYS = [
    os.environ.get('GEMINI_API_KEY_1'),
    os.environ.get('GEMINI_API_KEY_2'),
    os.environ.get('GEMINI_API_KEY_3'),
    os.environ.get('GEMINI_API_KEY')
]
API_KEYS = [key.strip() for key in API_KEYS if key and key.strip()]
BOT_USERNAME = ""
BOT_ID = None

MEMORY_FILE = "user_memory_cache.json"

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {}
    return {}

def save_memory(mem_data):
    try:
        if len(mem_data) > 500:
            keys_to_remove = list(mem_data.keys())[:100]
            for k in keys_to_remove:
                mem_data.pop(k, None)
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(mem_data, f, ensure_ascii=False, indent=4)
    except: pass

user_memory = load_memory()

def get_random_ai_client():
    if not API_KEYS:
        fallback_key = os.environ.get('GEMINI_API_KEY')
        return genai.Client(api_key=fallback_key.strip() if fallback_key else None)
    return genai.Client(api_key=random.choice(API_KEYS))

def text_to_live_voice(text_data):
    try:
        tts = gTTS(text=text_data, lang='ar', slow=False)
        voice_io = io.BytesIO()
        tts.write_to_fp(voice_io)
        return voice_io
    except: return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_USERNAME, BOT_ID, user_memory
    if not update.message: return

    chat_id = update.message.chat_id
    user = update.message.from_user
    user_id = str(user.id) if user else str(chat_id)
    username = f"@{user.username}" if user and user.username else "بدون معرف"
    chat_type = update.message.chat.type
    chat_title = update.message.chat.title if update.message.chat.title else "مجموعة"
    
    user_text = ""
    if update.message.text: user_text = update.message.text.strip()
    elif update.message.caption: user_text = update.message.caption.strip()

    is_incoming_voice = bool(update.message.voice or update.message.audio)
    
    # فرتقة الريكورد الفورية
    if is_incoming_voice:
        try:
            target_msg = update.message.reply_to_message if update.message.reply_to_message else update.message
            file_id = target_msg.voice.file_id if target_msg.voice else target_msg.audio.file_id
            tg_file = await context.bot.get_file(file_id)
            voice_bytes = await tg_file.download_as_bytearray()
            
            ai_client = get_random_ai_client()
            audio_part = types.Part.from_bytes(data=bytes(voice_bytes), mime_type="audio/ogg")
            trans_response = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[audio_part, "اكتب النص الموجود في هذا الريكورد الصوتي بدقة شديدة وبدون أي زيادة من عندك."]
            )
            if trans_response.text:
                user_text = trans_response.text.strip()
        except: pass

    # سيستم توجيه اللوق الذكي لخاص الأدمن 
    if ADMIN_ID and int(user_id) != ADMIN_ID:
        try:
            log_tag = "[المجموعة]" if chat_type in ['group', 'supergroup'] else "[الخاص]"
            group_info = f"• *اسم الجروب:* {chat_title}\n" if chat_type in ['group', 'supergroup'] else ""
            log_message = (
                f"📥 *{log_tag}*\n"
                f"{group_info}"
                f"• *الاسم:* {user.first_name if user else 'مجهول'}\n"
                f"• *المعرف:* {username}\n"
                f"• *الـ ID:* `{user_id}`\n"
                f"• *النص/المحتوى:* {user_text if user_text else '[ريكورد فارغ]'}"
            )
            await context.bot.send_message(chat_id=ADMIN_ID, text=log_message, parse_mode="Markdown")
        except: pass

    if not BOT_USERNAME or not BOT_ID:
        try:
            bot_info = await context.bot.get_me()
            BOT_USERNAME = f"@{bot_info.username}"
            BOT_ID = bot_info.id
        except: pass

    # قاموس الـ 35 رد تلقائي الجاهزة
    auto_replies = {
        'السلام عليكم': 'وعليكم السلام ورحمة الله وبركاته، منور الجت يا غالي! 🌹',
        'الأخبار شنو': 'كلشي تمام التمام والامور طيبة، إنت كيف أمورك؟ ✨',
        'الاخبار شنو': 'كلشي تمام التمام والامور طيبة، إنت كيف أمورك؟ ✨',
        'الطورك منو': 'طورني وصنعني المبرمج أحمد! 🤖🔥',
        'الصنعك منو': 'صنعني ومبرمجني الأساسي هو الفخم أحمد! 😉💪',
        'منور': 'النور نورك والله يا حبيبنا! 🌟',
        'وين انت': 'معاك هنا في الحاضر طوالي 😎',
        'صباح الخير': 'صباح الورد والبركة والروقان يا غالي 🌤️🌺',
        'مساء الخير': 'مساء النور والسرور والرضا والجمال 🌸',
        'مشتاقين': 'بالأكثر والله يا حبيبنا، الشوق قاطر 👑✨',
        'يا زول': 'أيوة يا زول يا فخم، مرحب بيك! حبابك عشرة 🇸🇩',
        'الحمد لله': 'دائماً وأبداً يا رب، يدوم عليك الرضا والحمد 🤲✨',
        'أحمد منو': 'المبرمج العبقري الفخم أحمد، صانعي ومطوري الذكي! 😉💪',
        'ياسمين': 'عيونها ولبيها! معاك ياسمين السمحة، آمرني يا غالي؟ 😍',
        'كيف الحالك': 'بخير وعافية طول ما إنت بخير، إنت كيفنك؟ 🥰',
        'كيفك': 'تمام التمام والحمد لله، الأمور باسطة! ✨',
        'تمام': 'دائماً تمام يا رب! علك طيب وبخير طوالي؟ 🌸',
        'هلا': 'هلا بيك ومليون مرحب يا حبيبنا، نورت الشات 👑',
        'مرحب': 'حبابك عشرة بلا كشرة! منورنا والله الكان مغيبنا 🌟',
        'تستاهل': 'تستاهل الخير والسمح كله يا أصلي! تسلم لي 🌹',
        'تسلم': 'الله يسلمك ويحفظك من كل شر يا ملك 👑',
        'شكرا': 'العفو يا غالي، الشكر لله، ماسوينا إلا الواجب 🤝',
        'منورة': 'النور ده عاكس من عيونك ومن حضورك الجميل والله دايماً 😍',
        'وينك': 'قاعدة وقاعدة ليك كمان، شاتك ما بيفوتني طوالي متواجدة 😎',
        'يا غالي': 'أنت الأغلى والله والقدرك عالي فوق فوق يا حبيبنا 👑',
        'حبيبي': 'تسلم لي يا ذوق، كلك أدب ولطف والله العظيم 🌹',
        'يا ملك': 'الملك لله وحده، لكن إنت مَلك بذوقك وأدبك الفخم ده 😉',
        'أخبار الشغل': 'ماشي تمام والحمد لله، شغالين تقفيل حنك وتصليح تقني 🛠️',
        'الحنك شنو': 'الحنك عندك إنت، أنا جاهزة ومستعدة لأي طلب أو ونسة قاطعة 😉',
        'سوي فويس': 'من عيوني! أرسل لي ريكورد أو أسألني وأنا برد ليك طوالي بصوتي 🎧',
        'أعملي فويس': 'حاضر، إنت بس اتكلم معاي بالصوت وحتشوف أحلى ردي فويس مروق ✨',
        'مع السلامة': 'في أمان الله ورعايته يا غالي، ما تطول الغيبة علينا! 🌟',
        'باي': 'باي يا حبيب، تشرفنا بيك وفي منتظرك ترجع طوالي قريباً 👋'
    }
    
    if user_text in auto_replies:
        await update.message.reply_text(auto_replies[user_text])
        return

    is_voice_intent = is_incoming_voice
    voice_triggers = ['ريكورد', 'صوتية', 'فويس', 'تسجيل', 'صوت', 'اسمعي', 'قولي']
    if user_text:
        text_check = user_text.lower()
        if any(vt in text_check for vt in voice_triggers): is_voice_intent = True

    # 🔓 فتح الشارع 24 ساعة: شلنا الـ 15% العشوائية عشان ترد طوالي بدون تفويت
    if chat_type in ['group', 'supergroup']:
        is_explicit = (user_text and (BOT_USERNAME in user_text or "ياسمين" in user_text))
        is_direct_reply = (update.message.reply_to_message and update.message.reply_to_message.from_user.id == BOT_ID)
        # لو ما نادوها، وما ردوا عليها، وما كان ريكورد 👈 برضه حترد على الونسة العادية ومستحيل تسكت!
        pass 

    sys_instruction = "أنتِ اسمك ياسمين، بنت سودانية عفوية وخفيفة دم. ردي بلهجة سودانية ظريفة ومرحة والردود سطرين بس."

    user_memory = load_memory()
    if user_id not in user_memory:
        user_memory[user_id] = []
        
    contents_list = []
    for past_msg in user_memory[user_id]:
        contents_list.append(past_msg)

    current_prompt = f"المستخدم: {user_text}" if user_text else "المستخدم أرسل ريكورد فارغ"
    contents_list.append(current_prompt)

    try:
        ai_client = get_random_ai_client()
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents_list,
            config=types.GenerateContentConfig(system_instruction=sys_instruction)
        )
        
        if response.text:
            reply_result = response.text.strip()
            
            user_memory[user_id].append(current_prompt)
            user_memory[user_id].append(f"ياسمين: {reply_result}")
            if len(user_memory[user_id]) > 6:
                user_memory[user_id] = user_memory[user_id][-6:]
            
            save_memory(user_memory)

            if is_voice_intent:
                voice_io = text_to_live_voice(reply_result)
                if voice_io:
                    voice_io.seek(0)
                    await update.message.reply_voice(voice=voice_io, caption="سمعتك وهاك ردي.. 🎧✨")
                    return
                    
            await update.message.reply_text(reply_result)
            
    except Exception as e:
        print(f"❌ خطأ: {e}")

if __name__ == '__main__':
    print("🚀 تشغيل ياسمين النشطة 24 ساعة ردم متواصل جوة المجموعات...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).read_timeout(30).write_timeout(30).build()
    all_media_filter = filters.TEXT | filters.AUDIO | filters.VOICE
    app.add_handler(MessageHandler(all_media_filter & ~filters.COMMAND, handle_message))
    app.run_polling()
