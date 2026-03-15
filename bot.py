import asyncio
import logging
import os
import shutil
import subprocess
from pathlib import Path

from telegram import Update
from telegram.constants import ChatAction
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
BOT_TOKEN = os.getenv("BOT_TOKEN")  # NEVER hardcode your real token here

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
OUTPUT_DIR = BASE_DIR / "outputs"

AUDIO_EXTENSION = ".mp3"
AUDIO_BITRATE = "192k"

# Optional: set this in Render/Railway/etc. if PATH has issues
# Example: /usr/bin/ffmpeg
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
def ensure_directories() -> None:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def resolve_ffmpeg() -> str | None:
    """Return a usable ffmpeg executable path, or None if not found."""
    candidates = [
        FFMPEG_PATH,
        shutil.which("ffmpeg"),
        "/usr/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
    ]

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
        if candidate and candidate == "ffmpeg" and shutil.which("ffmpeg"):
            return shutil.which("ffmpeg")

    return None


def safe_stem(filename: str | None, fallback: str) -> str:
    if not filename:
        return fallback

    stem = Path(filename).stem.strip()
    if not stem:
        return fallback

    cleaned = "".join(
        ch for ch in stem if ch.isalnum() or ch in ("_", "-", " ")
    ).strip()

    return cleaned or fallback


def convert_video_to_mp3(input_path: Path, output_path: Path, ffmpeg_bin: str) -> None:
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
        raise RuntimeError(result.stderr.strip() or "FFmpeg conversion failed.")

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("Conversion failed: output MP3 file was not created.")


async def cleanup_files(*paths: Path) -> None:
    for path in paths:
        try:
            if path.exists():
                path.unlink()
        except Exception as exc:
            logger.warning("Failed to delete %s: %s", path, exc)


def is_supported_video(filename: str, mime_type: str) -> bool:
    allowed_exts = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v")
    return mime_type.startswith("video/") or filename.lower().endswith(allowed_exts)


# =========================
# Command Handlers
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    await update.message.reply_text(
        "Hi! Send me a video and I will convert it to MP3.\n\n"
        "Commands:\n"
        "/start - Show this message\n"
        "/help - Show help"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    await update.message.reply_text(
        "How to use this bot:\n"
        "1. Send a video file\n"
        "2. Wait a little\n"
        "3. I will send you back an MP3 file\n\n"
        "Important:\n"
        "- BOT_TOKEN must be set in environment variables\n"
        "- FFmpeg must be installed on the server"
    )


# =========================
# Video Handler
# =========================
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    ffmpeg_bin = resolve_ffmpeg()
    if not ffmpeg_bin:
        await update.message.reply_text(
            "FFmpeg is not installed or not available in PATH.\n"
            "Set FFMPEG_PATH or install FFmpeg on the server."
        )
        return

    telegram_file = None
    original_name = None

    if update.message.video:
        telegram_file = await update.message.video.get_file()
        original_name = update.message.video.file_name or f"video_{update.message.message_id}.mp4"

    elif update.message.document:
        mime_type = update.message.document.mime_type or ""
        filename = update.message.document.file_name or ""

        if not is_supported_video(filename, mime_type):
            await update.message.reply_text("Please send a real video file.")
            return

        telegram_file = await update.message.document.get_file()
        original_name = filename or f"video_{update.message.message_id}.mp4"

    else:
        await update.message.reply_text("Please send a video file.")
        return

    fallback_name = f"video_{update.message.message_id}"
    base_name = safe_stem(original_name, fallback_name)

    input_extension = Path(original_name).suffix or ".mp4"

    # Make filenames unique to avoid collisions
    input_path = DOWNLOAD_DIR / f"{base_name}_{update.message.message_id}{input_extension}"
    output_path = OUTPUT_DIR / f"{base_name}_{update.message.message_id}{AUDIO_EXTENSION}"

    status_message = await update.message.reply_text("Converting your video to MP3...")

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_AUDIO)

        await telegram_file.download_to_drive(custom_path=str(input_path))

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, convert_video_to_mp3, input_path, output_path, ffmpeg_bin)

        with output_path.open("rb") as audio_file:
            await update.message.reply_audio(
                audio=audio_file,
                filename=output_path.name,
                title=base_name,
            )

        await status_message.edit_text("Done. Your MP3 is ready.")

    except Exception as exc:
        logger.exception("Conversion failed: %s", exc)
        await status_message.edit_text(f"Conversion failed.\n\nError: {exc}")

    finally:
        await cleanup_files(input_path, output_path)


# =========================
# Main
# =========================
def main() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is missing. Set it as an environment variable.")

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
