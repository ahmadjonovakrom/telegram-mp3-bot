import asyncio
import logging
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# =========================
# Configuration
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8368997991

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
OUTPUT_DIR = BASE_DIR / "outputs"
DATA_DIR = BASE_DIR / "data"
DB_FILE = DATA_DIR / "bot.db"

AUDIO_EXTENSION = ".mp3"
AUDIO_BITRATE = "192k"
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")

# =========================
# Logging
# =========================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# =========================
# Texts
# =========================
TEXTS = {
    "en": {
        "choose_bot_language": "Choose bot language",
        "welcome": (
            "Welcome to VideoToMP3Bot.\n\n"
            "Send me a video or audio file.\n"
            "Then I’ll ask you to name the MP3.\n"
            "After that, I’ll convert it for you."
        ),
        "help": (
            "How to use:\n\n"
            "1. Send a video or audio file\n"
            "2. Enter a name for the MP3\n"
            "3. Receive your converted file"
        ),
        "help_buttons_user": (
            "\n\nButtons:\n"
            "• Help — show instructions\n"
            "• Language — change language\n"
            "• Cancel — stop current action"
        ),
        "help_buttons_admin": (
            "\n\nButtons:\n"
            "• Help — show instructions\n"
            "• Language — change language\n"
            "• Stats — show bot statistics\n"
            "• Cancel — stop current action"
        ),
        "cancelled": "Cancelled.\n\nSend a new video or audio whenever you’re ready.",
        "send_supported": "Please send a supported video or audio file.",
        "send_name": "Send a name for the audio.",
        "send_name_as_text": "Please send the audio name as text.\n\nExample: lesson 5",
        "send_first": "Please send a video or audio file first.",
        "ffmpeg_missing": "FFmpeg is not installed on the server.",
        "converting": "Converting to MP3...\nPlease wait a moment.",
        "done": "Done.",
        "send_another": "Send another video or audio file whenever you want.",
        "try_again": "Please try again with another file.",
        "generic_error": "Something went wrong during conversion.",
        "begin_with_file": "Please send a video or audio file to begin.",
        "stats_unavailable": "This button is not available.",
        "choose_language": "Choose a language.",
        "language_saved": "Language updated.",
        "stats": "Users: {users}\nTotal conversions: {total}\nConversions today: {today}\nMost active user conversions: {top}",
        "btn_help": "Help",
        "btn_language": "Language",
        "btn_stats": "Stats",
        "btn_cancel": "Cancel",
    },
    "uz": {
        "choose_bot_language": "Bot tilini tanlang",
        "welcome": (
            "VideoToMP3Bot ga xush kelibsiz.\n\n"
            "Menga video yoki audio fayl yuboring.\n"
            "Keyin men MP3 nomini so‘rayman.\n"
            "Shundan so‘ng uni siz uchun MP3 ga aylantiraman."
        ),
        "help": (
            "Foydalanish yo‘li:\n\n"
            "1. Video yoki audio fayl yuboring\n"
            "2. MP3 uchun nom kiriting\n"
            "3. Tayyor faylni qabul qiling"
        ),
        "help_buttons_user": (
            "\n\nTugmalar:\n"
            "• Yordam — yo‘riqnoma\n"
            "• Til — tilni o‘zgartirish\n"
            "• Bekor qilish — joriy amalni bekor qilish"
        ),
        "help_buttons_admin": (
            "\n\nTugmalar:\n"
            "• Yordam — yo‘riqnoma\n"
            "• Til — tilni o‘zgartirish\n"
            "• Statistika — bot statistikasi\n"
            "• Bekor qilish — joriy amalni bekor qilish"
        ),
        "cancelled": "Bekor qilindi.\n\nTayyor bo‘lsangiz, yangi video yoki audio yuboring.",
        "send_supported": "Iltimos, mos video yoki audio fayl yuboring.",
        "send_name": "Audio uchun nom yuboring.",
        "send_name_as_text": "Iltimos, audio nomini matn ko‘rinishida yuboring.\n\nMasalan: lesson 5",
        "send_first": "Avval video yoki audio fayl yuboring.",
        "ffmpeg_missing": "Serverda FFmpeg o‘rnatilmagan.",
        "converting": "MP3 ga aylantirilmoqda...\nIltimos, biroz kuting.",
        "done": "Tayyor.",
        "send_another": "Xohlasangiz, yana video yoki audio yuborishingiz mumkin.",
        "try_again": "Iltimos, boshqa fayl bilan yana urinib ko‘ring.",
        "generic_error": "Aylantirish jarayonida xatolik yuz berdi.",
        "begin_with_file": "Boshlash uchun video yoki audio fayl yuboring.",
        "stats_unavailable": "Bu tugma siz uchun mavjud emas.",
        "choose_language": "Tilni tanlang.",
        "language_saved": "Til yangilandi.",
        "stats": "Foydalanuvchilar: {users}\nJami konvertatsiyalar: {total}\nBugungi konvertatsiyalar: {today}\nEng faol foydalanuvchi konvertatsiyasi: {top}",
        "btn_help": "Yordam",
        "btn_language": "Til",
        "btn_stats": "Statistika",
        "btn_cancel": "Bekor qilish",
    },
    "ru": {
        "choose_bot_language": "Выберите язык бота",
        "welcome": (
            "Добро пожаловать в VideoToMP3Bot.\n\n"
            "Отправьте мне видео или аудиофайл.\n"
            "Потом я попрошу вас указать имя MP3.\n"
            "После этого я конвертирую файл."
        ),
        "help": (
            "Как пользоваться:\n\n"
            "1. Отправьте видео или аудиофайл\n"
            "2. Введите название для MP3\n"
            "3. Получите готовый файл"
        ),
        "help_buttons_user": (
            "\n\nКнопки:\n"
            "• Помощь — инструкция\n"
            "• Язык — сменить язык\n"
            "• Отмена — отменить текущее действие"
        ),
        "help_buttons_admin": (
            "\n\nКнопки:\n"
            "• Помощь — инструкция\n"
            "• Язык — сменить язык\n"
            "• Статистика — статистика бота\n"
            "• Отмена — отменить текущее действие"
        ),
        "cancelled": "Отменено.\n\nКогда будете готовы, отправьте новое видео или аудио.",
        "send_supported": "Пожалуйста, отправьте поддерживаемый видео- или аудиофайл.",
        "send_name": "Отправьте название для аудио.",
        "send_name_as_text": "Пожалуйста, отправьте название аудио текстом.\n\nПример: lesson 5",
        "send_first": "Сначала отправьте видео или аудиофайл.",
        "ffmpeg_missing": "FFmpeg не установлен на сервере.",
        "converting": "Конвертация в MP3...\nПожалуйста, подождите.",
        "done": "Готово.",
        "send_another": "Можете отправить ещё одно видео или аудио.",
        "try_again": "Пожалуйста, попробуйте ещё раз с другим файлом.",
        "generic_error": "Во время конвертации произошла ошибка.",
        "begin_with_file": "Чтобы начать, отправьте видео или аудиофайл.",
        "stats_unavailable": "Эта кнопка вам недоступна.",
        "choose_language": "Выберите язык.",
        "language_saved": "Язык обновлён.",
        "stats": "Пользователи: {users}\nВсего конвертаций: {total}\nКонвертаций сегодня: {today}\nМаксимум у одного пользователя: {top}",
        "btn_help": "Помощь",
        "btn_language": "Язык",
        "btn_stats": "Статистика",
        "btn_cancel": "Отмена",
    },
}

# =========================
# UI
# =========================
def get_user_language(user_id: int) -> str:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            row = conn.execute(
                "SELECT language FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row and row[0] in TEXTS:
                return row[0]
    except Exception as exc:
        logger.warning("Could not get user language for %s: %s", user_id, exc)
    return "en"


def t(user_id: int, key: str) -> str:
    lang = get_user_language(user_id)
    return TEXTS.get(lang, TEXTS["en"])[key]


def get_main_keyboard(user_id: int):
    if user_id == ADMIN_ID:
        buttons = [
            [t(user_id, "btn_help"), t(user_id, "btn_language")],
            [t(user_id, "btn_stats"), t(user_id, "btn_cancel")],
        ]
    else:
        buttons = [
            [t(user_id, "btn_help"), t(user_id, "btn_language")],
            [t(user_id, "btn_cancel")],
        ]

    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def get_cancel_keyboard(user_id: int):
    return ReplyKeyboardMarkup(
        [[t(user_id, "btn_cancel")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


LANGUAGE_KEYBOARD = ReplyKeyboardMarkup(
    [["English", "Uzbek", "Russian"]],
    resize_keyboard=True,
)

# =========================
# Database
# =========================
def ensure_directories():
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                language TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def register_user(user_id: int):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, language) VALUES (?, '')",
            (user_id,),
        )
        conn.commit()


def has_language(user_id: int) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            row = conn.execute(
                "SELECT language FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return bool(row and row[0] in TEXTS)
    except Exception as exc:
        logger.warning("Could not check user language for %s: %s", user_id, exc)
        return False


def set_user_language(user_id: int, language_code: str):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, language) VALUES (?, ?)",
            (user_id, language_code),
        )
        conn.execute(
            "UPDATE users SET language = ? WHERE user_id = ?",
            (language_code, user_id),
        )
        conn.commit()


def log_conversion(user_id: int):
    now_utc = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT INTO conversions (user_id, created_at) VALUES (?, ?)",
            (user_id, now_utc),
        )
        conn.commit()


def get_users_count() -> int:
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
        return row[0] if row else 0


def get_total_conversions() -> int:
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute("SELECT COUNT(*) FROM conversions").fetchone()
        return row[0] if row else 0


def get_conversions_today() -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM conversions WHERE substr(created_at, 1, 10) = ?",
            (today,),
        ).fetchone()
        return row[0] if row else 0


def get_top_user_conversions() -> int:
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS conversion_count
            FROM conversions
            GROUP BY user_id
            ORDER BY conversion_count DESC
            LIMIT 1
            """
        ).fetchone()
        return row[0] if row else 0

# =========================
# Helpers
# =========================
def resolve_ffmpeg():
    candidates = [
        FFMPEG_PATH,
        shutil.which("ffmpeg"),
        "/usr/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
    ]

    for candidate in candidates:
        if not candidate:
            continue

        if candidate == "ffmpeg":
            found = shutil.which("ffmpeg")
            if found:
                return found
        else:
            if Path(candidate).exists():
                return str(candidate)

    return None


def sanitize_filename(name: str, fallback: str = "audio") -> str:
    if not name:
        return fallback

    name = Path(name).stem.strip()
    cleaned = "".join(
        ch for ch in name if ch.isalnum() or ch in (" ", "_", "-")
    ).strip()
    cleaned = cleaned[:80].strip()
    return cleaned or fallback


def convert_to_mp3(input_path: Path, output_path: Path, ffmpeg_bin: str):
    command = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-map_metadata",
        "-1",
        "-acodec",
        "libmp3lame",
        "-ab",
        AUDIO_BITRATE,
        str(output_path),
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())


async def cleanup_files(*paths: Path):
    for path in paths:
        try:
            if path and path.exists():
                path.unlink()
        except Exception as exc:
            logger.warning("Failed deleting %s: %s", path, exc)


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def is_supported_media(message) -> bool:
    if message.video or message.audio or message.voice:
        return True

    if message.document:
        mime = (message.document.mime_type or "").lower()
        name = (message.document.file_name or "").lower()

        allowed_video = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v")
        allowed_audio = (".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac")

        return (
            mime.startswith("video/")
            or mime.startswith("audio/")
            or name.endswith(allowed_video)
            or name.endswith(allowed_audio)
        )

    return False


def extract_media_info(update: Update) -> dict | None:
    message = update.message

    if message.video:
        return {
            "file_id": message.video.file_id,
            "original_name": message.video.file_name or f"video_{message.message_id}.mp4",
        }

    if message.audio:
        return {
            "file_id": message.audio.file_id,
            "original_name": message.audio.file_name or f"audio_{message.message_id}.mp3",
        }

    if message.voice:
        return {
            "file_id": message.voice.file_id,
            "original_name": f"voice_{message.message_id}.ogg",
        }

    if message.document and is_supported_media(message):
        return {
            "file_id": message.document.file_id,
            "original_name": message.document.file_name or f"file_{message.message_id}",
        }

    return None

# =========================
# Commands
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    register_user(user_id)

    context.user_data.pop("pending_media", None)
    context.user_data.pop("awaiting_language", None)

    if not has_language(user_id):
        context.user_data["awaiting_language"] = True
        await update.message.reply_text(
            TEXTS["en"]["choose_bot_language"],
            reply_markup=LANGUAGE_KEYBOARD,
        )
        return

    await update.message.reply_text(
        t(user_id, "welcome"),
        reply_markup=get_main_keyboard(user_id),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    register_user(user_id)

    text = t(user_id, "help")
    if is_admin(user_id):
        text += t(user_id, "help_buttons_admin")
    else:
        text += t(user_id, "help_buttons_user")

    await update.message.reply_text(
        text,
        reply_markup=get_main_keyboard(user_id),
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    register_user(user_id)

    if not is_admin(user_id):
        await update.message.reply_text(
            t(user_id, "stats_unavailable"),
            reply_markup=get_main_keyboard(user_id),
        )
        return

    text = t(user_id, "stats").format(
        users=get_users_count(),
        total=get_total_conversions(),
        today=get_conversions_today(),
        top=get_top_user_conversions(),
    )
    await update.message.reply_text(
        text,
        reply_markup=get_main_keyboard(user_id),
    )


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    register_user(user_id)
    context.user_data["awaiting_language"] = True

    await update.message.reply_text(
        t(user_id, "choose_language"),
        reply_markup=LANGUAGE_KEYBOARD,
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.pop("pending_media", None)
    context.user_data.pop("awaiting_language", None)

    await update.message.reply_text(
        t(user_id, "cancelled"),
        reply_markup=get_main_keyboard(user_id),
    )

# =========================
# Media
# =========================
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    register_user(user_id)

    ffmpeg_bin = resolve_ffmpeg()
    if not ffmpeg_bin:
        await update.message.reply_text(
            t(user_id, "ffmpeg_missing"),
            reply_markup=get_main_keyboard(user_id),
        )
        return

    media_info = extract_media_info(update)
    if not media_info:
        await update.message.reply_text(
            t(user_id, "send_supported"),
            reply_markup=get_main_keyboard(user_id),
        )
        return

    context.user_data["pending_media"] = media_info

    await update.message.reply_text(
        t(user_id, "send_name"),
        reply_markup=get_cancel_keyboard(user_id),
    )

# =========================
# Text
# =========================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    register_user(user_id)

    text = (update.message.text or "").strip()
    lower_text = text.lower()

    help_words = {"help", "yordam", "помощь"}
    language_words = {"language", "til", "язык"}
    stats_words = {"stats", "statistika", "статистика"}
    cancel_words = {"cancel", "bekor qilish", "отмена"}

    if lower_text in cancel_words:
        await cancel_command(update, context)
        return

    if lower_text in help_words:
        await help_command(update, context)
        return

    if lower_text in language_words:
        await language_command(update, context)
        return

    if lower_text in stats_words:
        await stats_command(update, context)
        return

    if context.user_data.get("awaiting_language"):
        mapping = {
            "english": "en",
            "uzbek": "uz",
            "russian": "ru",
        }
        language_code = mapping.get(lower_text)

        if language_code:
            set_user_language(user_id, language_code)
            context.user_data.pop("awaiting_language", None)

            await update.message.reply_text(
                t(user_id, "language_saved"),
                reply_markup=ReplyKeyboardRemove(),
            )

            await update.message.reply_text(
                t(user_id, "welcome"),
                reply_markup=get_main_keyboard(user_id),
            )
        else:
            await update.message.reply_text(
                TEXTS["en"]["choose_bot_language"],
                reply_markup=LANGUAGE_KEYBOARD,
            )
        return

    pending_media = context.user_data.get("pending_media")
    if not pending_media:
        await update.message.reply_text(
            t(user_id, "begin_with_file"),
            reply_markup=get_main_keyboard(user_id),
        )
        return

    ffmpeg_bin = resolve_ffmpeg()
    if not ffmpeg_bin:
        await update.message.reply_text(
            t(user_id, "ffmpeg_missing"),
            reply_markup=get_main_keyboard(user_id),
        )
        return

    requested_name = sanitize_filename(
        text,
        fallback=f"audio_{update.message.message_id}",
    )

    original_name = pending_media["original_name"]
    input_ext = Path(original_name).suffix or ".mp4"

    input_path = DOWNLOAD_DIR / f"{requested_name}_{update.message.message_id}{input_ext}"
    output_path = OUTPUT_DIR / f"{requested_name}_{update.message.message_id}{AUDIO_EXTENSION}"

    status = await update.message.reply_text(
        t(user_id, "converting"),
        reply_markup=ReplyKeyboardRemove(),
    )

    try:
        telegram_file = await context.bot.get_file(pending_media["file_id"])
        await telegram_file.download_to_drive(custom_path=str(input_path))

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            convert_to_mp3,
            input_path,
            output_path,
            ffmpeg_bin,
        )

        with open(output_path, "rb") as audio_file:
            await update.message.reply_document(
                document=audio_file,
                filename=f"{requested_name}{AUDIO_EXTENSION}",
            )

        log_conversion(user_id)

        await status.edit_text(t(user_id, "done"))
        await update.message.reply_text(
            t(user_id, "send_another"),
            reply_markup=get_main_keyboard(user_id),
        )

    except Exception as exc:
        logger.exception("Conversion failed: %s", exc)
        await status.edit_text(t(user_id, "generic_error"))
        await update.message.reply_text(
            t(user_id, "try_again"),
            reply_markup=get_main_keyboard(user_id),
        )

    finally:
        context.user_data.pop("pending_media", None)
        await cleanup_files(input_path, output_path)

# =========================
# Fallback
# =========================
async def unsupported_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    register_user(user_id)

    if context.user_data.get("pending_media"):
        await update.message.reply_text(
            t(user_id, "send_name_as_text"),
            reply_markup=get_cancel_keyboard(user_id),
        )
    else:
        await update.message.reply_text(
            t(user_id, "begin_with_file"),
            reply_markup=get_main_keyboard(user_id),
        )

# =========================
# Main
# =========================
def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN missing.")

    ensure_directories()
    init_db()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("language", language_command))
    application.add_handler(CommandHandler("cancel", cancel_command))

    application.add_handler(
        MessageHandler(
            filters.VIDEO | filters.AUDIO | filters.VOICE | filters.Document.ALL,
            handle_media,
        )
    )

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )

    application.add_handler(
        MessageHandler(
            ~(filters.TEXT | filters.VIDEO | filters.AUDIO | filters.VOICE | filters.Document.ALL),
            unsupported_message,
        )
    )

    logger.info("Bot running...")
    application.run_polling()


if __name__ == "__main__":
    main()
