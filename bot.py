import asyncio
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
# 1) Create a bot with BotFather
# 2) Put your bot token below OR set it as an environment variable named BOT_TOKEN
BOT_TOKEN = os.getenv("BOT_TOKEN", "8685207379:AAGWWjzY9nN8ubErlkzTpa7FZUtVxqLk8CU")

# Folder for temporary files
BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
OUTPUT_DIR = BASE_DIR / "outputs"

# Audio settings
AUDIO_EXTENSION = ".mp3"
AUDIO_BITRATE = "192k"


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
def ensure_directories() -> None:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)



def check_ffmpeg_installed() -> bool:
    return shutil.which("ffmpeg") is not None



def safe_stem(filename: str | None, fallback: str) -> str:
    if not filename:
        return fallback
    stem = Path(filename).stem.strip()
    if not stem:
        return fallback
    cleaned = "".join(ch for ch in stem if ch.isalnum() or ch in ("_", "-", " ")).strip()
    return cleaned or fallback



def convert_video_to_mp3(input_path: Path, output_path: Path) -> None:
    command = [
        "/usr/bin/env", "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-map_metadata", "-1",
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
        raise RuntimeError(result.stderr.strip() or "FFmpeg conversion failed.")

async def cleanup_files(*paths: Path) -> None:
    for path in paths:
        try:
            if path.exists():
                path.unlink()
        except Exception as exc:
            logger.warning("Failed to delete %s: %s", path, exc)


# =========================
# Command Handlers
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = (
        "Hi! Send me a video and I will convert it to MP3 audio.\n\n"
        "Commands:\n"
        "/start - Show this message\n"
        "/help - Show help"
    )
    await update.message.reply_text(message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = (
        "How to use this bot:\n"
        "1. Send a video file to the bot\n"
        "2. Wait a few seconds\n"
        "3. The bot will send back an MP3 audio file\n\n"
        "Requirements:\n"
        "- FFmpeg must be installed on your computer/server\n"
        "- Your bot token must be set correctly"
    )
    await update.message.reply_text(message)


# =========================
# Video Handler
# =========================
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    telegram_file = None
    original_name = None

    if update.message.video:
        telegram_file = await update.message.video.get_file()
        original_name = update.message.video.file_name
    elif update.message.document:
        mime_type = update.message.document.mime_type or ""
        filename = update.message.document.file_name or ""
        if not (
            mime_type.startswith("video/")
            or filename.lower().endswith((".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"))
        ):
            await update.message.reply_text("Please send a video file.")
            return
        telegram_file = await update.message.document.get_file()
        original_name = filename
    else:
        await update.message.reply_text("Please send a video file.")
        return

    status_message = await update.message.reply_text("Converting your video to MP3...")

    fallback_name = f"video_{update.message.message_id}"
    base_name = safe_stem(original_name, fallback_name)

    input_extension = Path(original_name).suffix if original_name else ".mp4"
    if not input_extension:
        input_extension = ".mp4"

    input_path = DOWNLOAD_DIR / f"{base_name}{input_extension}"
    output_path = OUTPUT_DIR / f"{base_name}{AUDIO_EXTENSION}"

    try:
        await telegram_file.download_to_drive(custom_path=str(input_path))

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, convert_video_to_mp3, input_path, output_path)

        with output_path.open("rb") as audio_file:
            await update.message.reply_audio(
                audio=audio_file,
                filename=output_path.name,
                title=base_name,
            )

        await status_message.edit_text("Done. Your MP3 is ready.")

    except Exception as exc:
        logger.exception("Conversion failed: %s", exc)
        await status_message.edit_text(f"Conversion failed. Error: {exc}")

    finally:
        await cleanup_files(input_path, output_path)


# =========================
# Main
# =========================
def main() -> None:
    if BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
        raise ValueError("Please set your bot token in BOT_TOKEN or as an environment variable.")

    ensure_directories()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(
        MessageHandler(filters.VIDEO | filters.Document.ALL, handle_video)
    )

    logger.info("Bot is running...")
    application.run_polling()


if __name__ == "__main__":
    main()
