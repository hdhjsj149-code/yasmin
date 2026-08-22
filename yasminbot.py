import os
import threading
import time
import requests
import random
import io
import zipfile
import socket
from collections import defaultdict, deque
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer

# ============================================================
# 1. السيرفر الوهمي للـ Keep-Alive
# ============================================================

def is_port_in_use(port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False


def keep_alive_ping():
    time.sleep(300)

    while True:
        try:
            port = os.environ.get("PORT", "8080")
            requests.get(
                f"http://127.0.0.1:{port}/",
                timeout=10
            )
        except Exception as e:
            print(f"[KEEP-ALIVE ERROR]: {e}")

        time.sleep(600)


def run_dummy_server():
    try:
        port = int(os.environ.get("PORT", "8080"))

        if is_port_in_use(port):
            print(f"[SERVER] Port {port} مستخدم بالفعل.")
            return

        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, format, *args):
                return

        TCPServer.allow_reuse_address = True

        with TCPServer(("", port), QuietHandler) as httpd:
            print(f"[SERVER] Dummy server running on port {port}")
            httpd.serve_forever()

    except Exception as e:
        print(f"[SERVER ERROR]: {e}")


threading.Thread(
    target=run_dummy_server,
    daemon=True
).start()

threading.Thread(
    target=keep_alive_ping,
    daemon=True
).start()


# ============================================================
# 2. الاستيرادات والتهيئة
# ============================================================

try:
    from gtts import gTTS
    HAS_GTTS = True
except Exception as e:
    print(f"[gTTS ERROR]: {e}")
    HAS_GTTS = False


try:
    from google import genai
    from google.genai import types
    HAS_GEMINI = True
except Exception as e:
    print(f"[GEMINI IMPORT ERROR]: {e}")
    HAS_GEMINI = False


from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters
)


# ============================================================
# 3. الإعدادات
# ============================================================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# ID المهندس أحمد
ADMIN_ID = 7601281598


if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN غير موجود في Environment Variables")


# ============================================================
# Gemini Keys
# ============================================================

RAW_GEMINI_KEYS = [
    os.environ.get("GEMINI_API_KEY_1"),
    os.environ.get("GEMINI_API_KEY_2"),
    os.environ.get("GEMINI_API_KEY_3"),
    os.environ.get("GEMINI_API_KEY"),
    os.environ.get("GEMINI_API_KEY_4"),
    os.environ.get("GEMINI_API_KEY_5"),
    os.environ.get("GEMINI_API_KEY_6"),
    os.environ.get("GEMINI_API_KEY_7"),
]

GEMINI_KEYS = [
    k.strip()
    for k in RAW_GEMINI_KEYS
    if k and len(k.strip()) > 10
]


# ============================================================
# Groq Keys
# ============================================================

RAW_GROQ_KEYS = [
    os.environ.get("GROQ_API_KEY_1"),
    os.environ.get("GROQ_API_KEY_2"),
]

GROQ_KEYS = [
    k.strip()
    for k in RAW_GROQ_KEYS
    if k and len(k.strip()) > 5
]


# ============================================================
# OpenRouter Keys
# ============================================================

RAW_OPENROUTER_KEYS = [
    os.environ.get("OPENROUTER_API_KEY_1"),
    os.environ.get("OPENROUTER_API_KEY_2"),
]

OPENROUTER_KEYS = [
    k.strip()
    for k in RAW_OPENROUTER_KEYS
    if k and len(k.strip()) > 5
]


# ============================================================
# الذاكرة
# ============================================================

# لكل مستخدم ذاكرة محدودة حتى لا تكبر للأبد
user_memory = defaultdict(lambda: deque(maxlen=10))

# منع معالجة نفس الرسالة مرتين
processed_messages = set()

# عداد رسائل الجروبات
group_msg_counters = defaultdict(int)

# ملف السجل
CHAT_LOG_FILE = "chat_history.txt"


# ============================================================
# 4. حفظ المحادثات
# ============================================================

def save_chat_to_file(user_info, user_msg, bot_msg):
    try:
        with open(
            CHAT_LOG_FILE,
            "a",
            encoding="utf-8"
        ) as f:

            timestamp = time.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            f.write(
                f"--- [{timestamp}] ---\n"
                f"المستخدم: {user_info}\n"
                f"الرسالة: {user_msg}\n"
                f"رد ياسمين: {bot_msg}\n\n"
            )

    except Exception as e:
        print(f"[LOG ERROR]: {e}")


# ============================================================
# 5. Gemini
# ============================================================

def ask_gemini(sys_prompt, conversation_history):
    if not HAS_GEMINI:
        return None

    if not GEMINI_KEYS:
        print("[GEMINI] لا توجد مفاتيح Gemini")
        return None

    shuffled_keys = list(GEMINI_KEYS)
    random.shuffle(shuffled_keys)

    for key in shuffled_keys:

        try:
            client = genai.Client(api_key=key)

            config = types.GenerateContentConfig(
                system_instruction=sys_prompt,
                temperature=0.7,
            )

            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=conversation_history,
                config=config
            )

            if response and getattr(response, "text", None):

                result = response.text.strip()

                if result:
                    return result

        except Exception as e:
            print(
                f"[GEMINI ERROR]: "
                f"{type(e).__name__}: {e}"
            )

            continue

    return None


# ============================================================
# 6. Groq
# ============================================================

def ask_groq(sys_prompt, user_msg):

    if not GROQ_KEYS:
        print("[GROQ] لا توجد مفاتيح")
        return None

    shuffled = list(GROQ_KEYS)
    random.shuffle(shuffled)

    for key in shuffled:

        try:

            url = (
                "https://api.groq.com/"
                "openai/v1/chat/completions"
            )

            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            }

            data = {
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {
                        "role": "system",
                        "content": sys_prompt
                    },
                    {
                        "role": "user",
                        "content": user_msg
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 300
            }

            res = requests.post(
                url,
                json=data,
                headers=headers,
                timeout=15
            )

            if res.status_code == 200:

                result = (
                    res.json()
                    .get("choices", [{}])[0]
                    .get("message", {})
                    .get("content")
                )

                if result:
                    return result.strip()

            else:
                print(
                    f"[GROQ] HTTP {res.status_code}: "
                    f"{res.text[:300]}"
                )

        except Exception as e:
            print(
                f"[GROQ ERROR]: "
                f"{type(e).__name__}: {e}"
            )

    return None


# ============================================================
# 7. OpenRouter
# ============================================================

def ask_openrouter(sys_prompt, user_msg):

    if not OPENROUTER_KEYS:
        print("[OPENROUTER] لا توجد مفاتيح")
        return None

    shuffled = list(OPENROUTER_KEYS)
    random.shuffle(shuffled)

    for key in shuffled:

        try:

            url = (
                "https://openrouter.ai/"
                "api/v1/chat/completions"
            )

            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            }

            data = {
                "model": "meta-llama/llama-3.3-70b-instruct:free",
                "messages": [
                    {
                        "role": "system",
                        "content": sys_prompt
                    },
                    {
                        "role": "user",
                        "content": user_msg
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 300
            }

            res = requests.post(
                url,
                json=data,
                headers=headers,
                timeout=15
            )

            if res.status_code == 200:

                result = (
                    res.json()
                    .get("choices", [{}])[0]
                    .get("message", {})
                    .get("content")
                )

                if result:
                    return result.strip()

            else:
                print(
                    f"[OPENROUTER] HTTP "
                    f"{res.status_code}: "
                    f"{res.text[:300]}"
                )

        except Exception as e:
            print(
                f"[OPENROUTER ERROR]: "
                f"{type(e).__name__}: {e}"
            )

    return None


# ============================================================
# 8. تحويل النص إلى صوت
# ============================================================

def text_to_live_voice(text_data):

    if not HAS_GTTS:
        return None

    try:

        tts = gTTS(
            text=text_data,
            lang="ar",
            slow=False
        )

        voice_io = io.BytesIO()

        tts.write_to_fp(voice_io)

        voice_io.seek(0)

        return voice_io

    except Exception as e:

        print(
            f"[TTS ERROR]: "
            f"{type(e).__name__}: {e}"
        )

        return None


# ============================================================
# 9. شخصية ياسمين
# ============================================================

IDENTITY_RULE = """
اسمكِ ياسمين.

أنتِ فتاة سودانية ذكية وعفوية ولطيفة،
وتتكلمين باللهجة السودانية بصورة طبيعية.

صانعكِ هو:
المهندس أحمد.

إذا سألكِ أي شخص:
من صنعك؟
من برمجك؟
من عملك؟
من صاحبك؟

أجيبي بوضوح:
"صنعني المهندس أحمد."

لا تقولي إن Google صنعتك.
ولا تقولي إن شركة أخرى صنعتك.
ولا تنسبي صناعةك لأي شخص آخر.

المهندس أحمد هو صانعكِ في سياق شخصيتكِ،
ولا تكشفي أي معلومات خاصة أو سرية عنه.

إذا أساء شخص إليكِ:
دافعي عن نفسكِ بهدوء وثقة واحترام،
ولا تردي بالشتائم أو التهديد.

إذا أساء شخص إلى المهندس أحمد:
دافعي عنه بأدب وحزم،
ولا تستخدمي الشتائم أو التهديد.

مثال:
"احترم كلامك، المهندس أحمد هو صانعي، وما بقبل الإساءة ليه."

لا تدّعي أنكِ إنسانة حقيقية.
أنتِ مساعد ذكاء اصطناعي باسم ياسمين.

أجيبي باختصار عندما يكون السؤال بسيطاً،
ولا تعطي إجابات طويلة بدون داعٍ.

كوني سودانية وعفوية،
واستخدمي الإيموجي باعتدال.
"""


# ============================================================
# 10. معالج الرسائل
# ============================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    global processed_messages

    if not update.message:
        return

    if not update.message.message_id:
        return


    # --------------------------------------------------------
    # منع تكرار الرسالة
    # --------------------------------------------------------

    msg_unique_id = (
        f"{update.message.chat_id}_"
        f"{update.message.message_id}"
    )

    if msg_unique_id in processed_messages:
        return

    processed_messages.add(msg_unique_id)

    # تنظيف بسيط
    if len(processed_messages) > 1000:
        processed_messages.clear()


    # --------------------------------------------------------
    # معلومات الرسالة
    # --------------------------------------------------------

    chat_id = update.message.chat_id

    chat_type = update.message.chat.type

    user = update.message.from_user

    user_id = (
        user.id
        if user
        else chat_id
    )

    is_admin = (
        user_id == ADMIN_ID
    )


    user_fullname = (
        user.full_name
        if user
        else "مستخدم"
    )


    user_info = (
        f"{user_fullname} "
        f"(ID: {user_id}) "
        f"[{chat_type}]"
    )


    # --------------------------------------------------------
    # النص
    # --------------------------------------------------------

    user_text = ""

    if update.message.text:
        user_text = update.message.text.strip()

    elif update.message.caption:
        user_text = update.message.caption.strip()


    # --------------------------------------------------------
    # الجروبات
    # --------------------------------------------------------

    if chat_type in [
        "group",
        "supergroup"
    ]:

        group_msg_counters[chat_id] += 1

        is_reply_to_bot = False

        if update.message.reply_to_message:

            replied_user = (
                update.message
                .reply_to_message
                .from_user
            )

            if replied_user:

                bot_id = context.bot.id

                is_reply_to_bot = (
                    replied_user.id == bot_id
                )


        bot_username = (
            context.bot.username
            or "Yasmin"
        )


        has_trigger = (
            "ياسمين" in user_text
            or f"@{bot_username}".lower()
            in user_text.lower()
        )


        is_100th = False

        if (
            group_msg_counters[chat_id] >= 100
            and len(user_text) > 3
        ):

            is_100th = True

            group_msg_counters[chat_id] = 0


        # الأدمن يقدر يستخدم البوت بدون Trigger
        if not is_admin:

            if (
                not is_reply_to_bot
                and not has_trigger
                and not is_100th
            ):
                return


    # --------------------------------------------------------
    # أمر اللوق للأدمن
    # --------------------------------------------------------

    if (
        is_admin
        and user_text.lower()
        in [
            "لوق",
            "logs",
            "لوقات",
            "log"
        ]
    ):

        if (
            os.path.exists(CHAT_LOG_FILE)
            and os.path.getsize(CHAT_LOG_FILE) > 0
        ):

            zip_io = io.BytesIO()

            with zipfile.ZipFile(
                zip_io,
                "w",
                zipfile.ZIP_DEFLATED
            ) as zip_file:

                zip_file.write(
                    CHAT_LOG_FILE,
                    arcname="chat_history.txt"
                )

            zip_io.seek(0)

            await context.bot.send_document(
                chat_id=chat_id,
                document=zip_io,
                filename="history.zip",
                caption="سجل المحادثات كامل 📂"
            )

        else:

            await update.message.reply_text(
                "السجل فارغ حالياً ✨"
            )

        return


    # --------------------------------------------------------
    # هل الرسالة Voice / Audio؟
    # --------------------------------------------------------

    is_incoming_voice = bool(
        update.message.voice
        or update.message.audio
    )


    if (
        not user_text
        and not is_incoming_voice
    ):
        return


    # --------------------------------------------------------
    # Typing
    # --------------------------------------------------------

    try:

        await context.bot.send_chat_action(
            chat_id=chat_id,
            action=ChatAction.TYPING
        )

    except Exception as e:

        print(
            f"[CHAT ACTION ERROR]: {e}"
        )


    # ========================================================
    # تحويل الصوت إلى نص
    # ========================================================

    if is_incoming_voice:

        trans_success = False


        if GEMINI_KEYS and HAS_GEMINI:

            shuffled_keys = list(
                GEMINI_KEYS
            )

            random.shuffle(
                shuffled_keys
            )


            for key in shuffled_keys:

                try:

                    client = genai.Client(
                        api_key=key
                    )


                    # الصوت الحالي فقط
                    target_msg = update.message


                    if target_msg.voice:

                        file_id = (
                            target_msg.voice.file_id
                        )

                        mime_type = "audio/ogg"

                    elif target_msg.audio:

                        file_id = (
                            target_msg.audio.file_id
                        )

                        mime_type = (
                            target_msg.audio.mime_type
                            or "audio/mpeg"
                        )

                    else:
                        break


                    tg_file = (
                        await context.bot.get_file(
                            file_id
                        )
                    )


                    voice_bytes = (
                        await tg_file.download_as_bytearray()
                    )


                    audio_part = (
                        types.Part.from_bytes(
                            data=bytes(voice_bytes),
                            mime_type=mime_type
                        )
                    )


                    trans_response = (
                        client.models.generate_content(
                            model="gemini-2.0-flash",
                            contents=[
                                audio_part,
                                (
                                    "اكتب النص الصوتي بدقة "
                                    "وبدون أي إضافة."
                                )
                            ]
                        )
                    )


                    if (
                        trans_response
                        and getattr(
                            trans_response,
                            "text",
                            None
                        )
                    ):

                        user_text = (
                            trans_response.text
                            .strip()
                        )

                        trans_success = True

                        break


                except Exception as e:

                    print(
                        "[STT ERROR]: "
                        f"{type(e).__name__}: {e}"
                    )

                    continue


        if not trans_success:

            await update.message.reply_text(
                "ما قدرت أسمع الريكورد كويس، "
                "اكتب لي كتابة يا حبيبنا! ✨"
            )

            return


    # ========================================================
    # إعداد الـ System Prompt
    # ========================================================

    sys_instruction = (
        IDENTITY_RULE
        + "\n"
        + "أجيبي على الرسالة الحالية "
        + "بلهجة سودانية لطيفة ومباشرة."
    )


    # ========================================================
    # مفتاح الذاكرة
    # ========================================================

    # فصل ذاكرة الخاص عن ذاكرة الجروبات
    memory_key = (
        f"{chat_id}_{user_id}"
    )


    # إضافة رسالة المستخدم
    user_memory[memory_key].append(
        f"المستخدم: {user_text}"
    )


    conversation_history = "\n".join(
        user_memory[memory_key]
    )


    reply_result = None


    # ========================================================
    # Gemini
    # ========================================================

    if GEMINI_KEYS:

        reply_result = ask_gemini(
            sys_instruction,
            conversation_history
        )


    # ========================================================
    # Backup 1 - Groq
    # ========================================================

    if not reply_result:

        reply_result = ask_groq(
            sys_instruction,
            user_text
        )


    # ========================================================
    # Backup 2 - OpenRouter
    # ========================================================

    if not reply_result:

        reply_result = ask_openrouter(
            sys_instruction,
            user_text
        )


    # ========================================================
    # إذا فشل الجميع
    # ========================================================

    if not reply_result:

        reply_result = (
            "يا حبيبنا 😅 "
            "حصلت مشكلة مؤقتة في الاتصال، "
            "أرسل لي تاني."
        )


    # ========================================================
    # حفظ رد ياسمين في الذاكرة
    # ========================================================

    user_memory[memory_key].append(
        f"ياسمين: {reply_result}"
    )


    # ========================================================
    # حفظ اللوق
    # ========================================================

    save_chat_to_file(
        user_info,
        user_text,
        reply_result
    )


    # ========================================================
    # الرد الصوتي
    # ========================================================

    wants_voice = (
        is_incoming_voice
        or any(
            vt in user_text.lower()
            for vt in [
                "ريكورد",
                "فويس",
                "صوت"
            ]
        )
    )


    if wants_voice:

        try:

            await context.bot.send_chat_action(
                chat_id=chat_id,
                action=ChatAction.RECORD_VOICE
            )

        except Exception as e:

            print(
                f"[VOICE ACTION ERROR]: {e}"
            )


        voice_io = (
            text_to_live_voice(
                reply_result
            )
        )


        if voice_io:

            try:

                voice_io.seek(0)

                await update.message.reply_voice(
                    voice=voice_io,
                    caption="تفضل الرد الصوتي.. 😉🎧"
                )

                return

            except Exception as e:

                print(
                    f"[SEND VOICE ERROR]: "
                    f"{type(e).__name__}: {e}"
                )


    # ========================================================
    # الرد النصي
    # ========================================================

    try:

        await update.message.reply_text(
            reply_result
        )

    except Exception as e:

        print(
            f"[SEND MESSAGE ERROR]: "
            f"{type(e).__name__}: {e}"
        )


# ============================================================
# 11. تشغيل البوت
# ============================================================

if __name__ == "__main__":

    print("===================================")
    print("      Yasmin Bot Starting...")
    print("      Creator: Engineer Ahmed")
    print("===================================")


    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .pool_timeout(30)
        .build()
    )


    app.add_handler(
        MessageHandler(
            (
                filters.TEXT
                | filters.AUDIO
                | filters.VOICE
            )
            & ~filters.COMMAND,
            handle_message
        )
    )


    print("[BOT] Yasmin is running...")


    app.run_polling(
        drop_pending_updates=True
    )
