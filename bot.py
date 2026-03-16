import asyncio
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

from telegram import Update
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

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
OUTPUT_DIR = BASE_DIR / "outputs"
DATA_DIR = BASE_DIR / "data"
USERS_FILE = DATA_DIR / "users.json"

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
# Helpers
# =========================
def ensure_directories():
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not USERS_FILE.exists():
        USERS_FILE.write_text("[]", encoding="utf-8")


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

    # Remove extension if user typed it
    name = Path(name).stem.strip()

    cleaned = "".join(
        ch for ch in name if ch.isalnum() or ch in (" ", "_", "-")
    ).strip()

    # Avoid extremely long filenames
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


def load_users() -> set:
    try:
        data = json.loads(USERS_FILE.read_text(encoding="utf-8"))
        return set(data if isinstance(data, list) else [])
    except Exception as exc:
        logger.warning("Could not load users.json: %s", exc)
        return set()


def save_users(users: set):
    try:
        USERS_FILE.write_text(
            json.dumps(sorted(list(users)), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("Could not save users.json: %s", exc)


def register_user(user_id: int):
    users = load_users()
    users.add(user_id)
    save_users(users)


def get_users_count() -> int:
    return len(load_users())


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
            "kind": "video",
        }

    if message.audio:
        return {
            "file_id": message.audio.file_id,
            "original_name": message.audio.file_name or f"audio_{message.message_id}.mp3",
            "kind": "audio",
        }

    if message.voice:
        return {
            "file_id": message.voice.file_id,
            "original_name": f"voice_{message.message_id}.ogg",
            "kind": "voice",
        }

    if message.document and is_supported_media(message):
        return {
            "file_id": message.document.file_id,
            "original_name": message.document.file_name or f"file_{message.message_id}",
            "kind": "document",
        }

    return None


# =========================
# Commands
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user:
        register_user(update.effective_user.id)

    await update.message.reply_text(
        "Hi! Send me a video or audio file.\n\n"
        "Then I will ask:\n"
        '"Send a name for the audio."\n\n'
        "After that, I will convert it to MP3."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user:
        register_user(update.effective_user.id)

    await update.message.reply_text(
        "How to use:\n\n"
        "1. Send a video or audio\n"
        "2. Send a name for the audio\n"
        "3. Receive your MP3\n\n"
        "Commands:\n"
        "/start - Start the bot\n"
        "/help - Show help\n"
        "/users - Show total users\n"
        "/cancel - Cancel current action"
    )


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user:
        register_user(update.effective_user.id)

    count = get_users_count()
    await update.message.reply_text(f"Total users: {count}")


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("pending_media", None)
    await update.message.reply_text("Cancelled.")


# =========================
# Media handler
# =========================
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user:
        register_user(update.effective_user.id)

    ffmpeg_bin = resolve_ffmpeg()
    if not ffmpeg_bin:
        await update.message.reply_text("FFmpeg not installed.")
        return

    media_info = extract_media_info(update)
    if not media_info:
        await update.message.reply_text("Send a video or audio file.")
        return

    context.user_data["pending_media"] = media_info

    await update.message.reply_text("Send a name for the audio.")


# =========================
# Name handler
# =========================
async def handle_audio_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user:
        register_user(update.effective_user.id)

    pending_media = context.user_data.get("pending_media")
    if not pending_media:
        await update.message.reply_text("Send a video or audio file first.")
        return

    ffmpeg_bin = resolve_ffmpeg()
    if not ffmpeg_bin:
        await update.message.reply_text("FFmpeg not installed.")
        return

    requested_name = sanitize_filename(
        update.message.text,
        fallback=f"audio_{update.message.message_id}",
    )

    original_name = pending_media["original_name"]
    input_ext = Path(original_name).suffix or ".mp4"

    input_path = DOWNLOAD_DIR / f"{requested_name}_{update.message.message_id}{input_ext}"
    output_path = OUTPUT_DIR / f"{requested_name}_{update.message.message_id}{AUDIO_EXTENSION}"

    status = await update.message.reply_text("Converting to MP3...")

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
            await update.message.reply_audio(
                audio=audio_file,
                filename=f"{requested_name}{AUDIO_EXTENSION}",
                title=requested_name,
            )

        await status.edit_text("Done!")

    except Exception as exc:
        logger.exception("Conversion failed: %s", exc)
        await status.edit_text(f"Error: {exc}")

    finally:
        context.user_data.pop("pending_media", None)
        await cleanup_files(input_path, output_path)


# =========================
# Fallback handler
# =========================
async def unsupported_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user:
        register_user(update.effective_user.id)

    if context.user_data.get("pending_media"):
        await update.message.reply_text("Send a text name for the audio.")
    else:
        await update.message.reply_text("Send a video or audio file.")


# =========================
# Main
# =========================
def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN missing.")

    ensure_directories()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("cancel", cancel_command))

    # First: media
    application.add_handler(
        MessageHandler(
            filters.VIDEO | filters.AUDIO | filters.VOICE | filters.Document.ALL,
            handle_media,
        )
    )

    # Then: filename text
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_audio_name)
    )

    # Fallback
    application.add_handler(MessageHandler(~filters.COMMAND, unsupported_message))

    logger.info("Bot running...")
    application.run_polling()


if __name__ == "__main__":
    main()
