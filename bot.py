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
BOT_TOKEN = os.getenv("BOT_TOKEN")

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
OUTPUT_DIR = BASE_DIR / "outputs"

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


def safe_stem(filename, fallback):
    if not filename:
        return fallback

    stem = Path(filename).stem.strip()

    cleaned = "".join(
        ch for ch in stem if ch.isalnum() or ch in ("_", "-", " ")
    ).strip()

    return cleaned or fallback


def convert_video_to_mp3(input_path, output_path, ffmpeg_bin):

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


async def cleanup_files(*paths):
    for path in paths:
        try:
            if path.exists():
                path.unlink()
        except Exception as exc:
            logger.warning("Failed deleting %s: %s", path, exc)


def is_supported_video(filename, mime_type):
    allowed = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v")
    return mime_type.startswith("video/") or filename.lower().endswith(allowed)


# =========================
# Commands
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "Send me a video and I will convert it to MP3."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "How to use:\n\n"
        "1. Send a video\n"
        "2. Wait a moment\n"
        "3. Receive MP3"
    )


# =========================
# Video handler
# =========================
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):

    ffmpeg_bin = resolve_ffmpeg()

    if not ffmpeg_bin:
        await update.message.reply_text("FFmpeg not installed.")
        return

    telegram_file = None
    original_name = None

    if update.message.video:

        telegram_file = await update.message.video.get_file()
        original_name = update.message.video.file_name

    elif update.message.document:

        mime = update.message.document.mime_type or ""
        name = update.message.document.file_name or ""

        if not is_supported_video(name, mime):
            await update.message.reply_text("Send a video file.")
            return

        telegram_file = await update.message.document.get_file()
        original_name = name

    else:
        await update.message.reply_text("Send a video file.")
        return

    fallback = f"video_{update.message.message_id}"
    base_name = safe_stem(original_name, fallback)

    input_ext = Path(original_name).suffix if original_name else ".mp4"

    input_path = DOWNLOAD_DIR / f"{base_name}_{update.message.message_id}{input_ext}"
    output_path = OUTPUT_DIR / f"{base_name}_{update.message.message_id}.mp3"

    status = await update.message.reply_text("Converting to MP3...")

    try:

        await telegram_file.download_to_drive(custom_path=str(input_path))

        loop = asyncio.get_running_loop()

        await loop.run_in_executor(
            None,
            convert_video_to_mp3,
            input_path,
            output_path,
            ffmpeg_bin,
        )

        with open(output_path, "rb") as audio:

            await update.message.reply_audio(
                audio=audio,
                filename=output_path.name,
                title=base_name,
            )

        await status.edit_text("Done!")

    except Exception as e:

        logger.exception(e)
        await status.edit_text(f"Error: {e}")

    finally:

        await cleanup_files(input_path, output_path)


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

    application.add_handler(
        MessageHandler(filters.VIDEO | filters.Document.ALL, handle_video)
    )

    logger.info("Bot running...")

    application.run_polling()


if __name__ == "__main__":
    main()
