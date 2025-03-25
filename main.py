import os
import re
import logging
import asyncio
from pathlib import Path
from typing import Dict, Tuple

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment configuration
API_ID = 27999679
API_HASH = "f553398ca957b9c92bcb672b05557038"
BOT_TOKEN = "7647294451:AAHo8YWCZTnInsr24BTQSzCZu-SGuCuVf14"
MAX_FILE_SIZE = 2000000000  # 2GB
SUPPORTED_SUBTITLE_EXT = [".srt", ".ass", ".ssa", ".vtt"]
TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

# Store user sessions
user_sessions: Dict[int, Dict] = {}

app = Client("sub_mux_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def clean_temp(user_id: int):
    """Remove temporary files for a user"""
    user_dir = TEMP_DIR / str(user_id)
    if user_dir.exists():
        for f in user_dir.glob("*"):
            try:
                f.unlink()
            except Exception as e:
                logger.error(f"Error deleting {f}: {e}")
        try:
            user_dir.rmdir()
        except Exception as e:
            logger.error(f"Error removing directory {user_dir}: {e}")

async def run_command(command: list) -> Tuple[bool, str]:
    """Run shell command with error handling"""
    try:
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            return False, stderr.decode()
        return True, stdout.decode()
    except Exception as e:
        return False, str(e)

async def download_file(client: Client, message: Message, file_type: str) -> Path:
    """Download file with progress"""
    user_dir = TEMP_DIR / str(message.from_user.id)
    user_dir.mkdir(exist_ok=True)
    
    file_path = user_dir / f"{file_type}_{message.id}"
    
    try:
        msg = await message.reply_text(f"📥 Downloading {file_type}...")
        await client.download_media(
            message,
            file_name=str(file_path),
            progress=lambda current, total: logger.info(f"Downloaded {current} of {total}")
        )
        await msg.edit_text(f"✅ {file_type.capitalize()} downloaded successfully!")
        return file_path
    except RPCError as e:
        await msg.edit_text(f"❌ Failed to download {file_type}: {e}")
        raise
    except Exception as e:
        await msg.edit_text(f"❌ Unexpected error downloading {file_type}: {e}")
        raise

def get_output_path(user_id: int, mux_type: str) -> Path:
    """Generate output file path"""
    return TEMP_DIR / str(user_id) / f"output_{mux_type}.mkv"

async def send_results(client: Client, user_id: int, output_path: Path, mux_type: str):
    """Send processed file to user with cleanup"""
    try:
        await client.send_document(
            chat_id=user_id,
            document=str(output_path),
            caption=f"✅ {mux_type.capitalize()} muxing completed!",
            progress=lambda current, total: logger.info(f"Uploaded {current} of {total}")
        )
    finally:
        clean_temp(user_id)

@app.on_message(filters.command(["start", "help"]))
async def start(client: Client, message: Message):
    """Handle start command"""
    help_text = """
🤖 **Subtitle Muxer Bot**

🔹 **Features:**
- Soft mux (embed subtitles as separate stream)
- Hard mux (burn subtitles into video)
- Supports multiple subtitle formats (SRT, ASS, SSA, VTT)
- Progress tracking
- Error handling and validation

📌 **How to use:**
1. Send /softmux or /hardmux
2. Send video file
3. Send subtitle file

📝 **Note:**
- Maximum file size: 2GB
- Processing time depends on file size
    """
    await message.reply_text(help_text)

@app.on_message(filters.command(["softmux", "hardmux"]))
async def mux_handler(client: Client, message: Message):
    """Handle mux commands"""
    user_id = message.from_user.id
    mux_type = message.command[0]
    
    user_sessions[user_id] = {
        "mux_type": mux_type,
        "video_path": None,
        "sub_path": None,
        "processing": False
    }
    
    await message.reply_text(
        f"Please send your video file for {mux_type} muxing...",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="cancel")]])
    )

@app.on_message(filters.document | filters.video)
async def handle_files(client: Client, message: Message):
    """Handle incoming files"""
    user_id = message.from_user.id
    if user_id not in user_sessions:
        return
    
    session = user_sessions[user_id]
    
    try:
        file_name = message.document.file_name if message.document else message.video.file_name
        file_size = message.document.file_size if message.document else message.video.file_size
        
        if file_size > MAX_FILE_SIZE:
            await message.reply_text("❌ File size exceeds 2GB limit!")
            return
            
        if not session["video_path"]:
            # Handle video file
            if not re.search(r"\.(mp4|mkv|avi|mov)$", file_name, re.I):
                await message.reply_text("❌ Invalid video format! Supported formats: MP4, MKV, AVI, MOV")
                return
                
            session["video_path"] = await download_file(client, message, "video")
            await message.reply_text("Now please send your subtitle file...")
            
        elif not session["sub_path"]:
            # Handle subtitle file
            ext = Path(file_name).suffix.lower()
            if ext not in SUPPORTED_SUBTITLE_EXT:
                await message.reply_text(f"❌ Unsupported subtitle format! Supported: {', '.join(SUPPORTED_SUBTITLE_EXT)}")
                return
                
            session["sub_path"] = await download_file(client, message, "subtitle")
            await process_files(client, message, session)
            
    except Exception as e:
        logger.error(f"File handling error: {e}")
        await message.reply_text(f"❌ Error processing file: {e}")
        clean_temp(user_id)
        del user_sessions[user_id]

async def process_files(client: Client, message: Message, session: Dict):
    """Process files with FFmpeg"""
    user_id = message.from_user.id
    mux_type = session["mux_type"]
    video_path = session["video_path"]
    sub_path = session["sub_path"]
    
    try:
        output_path = get_output_path(user_id, mux_type)
        
        if mux_type == "softmux":
            cmd = [
                "ffmpeg", "-i", str(video_path), "-i", str(sub_path),
                "-map", "0", "-map", "1", "-c", "copy",
                "-metadata:s:s:0", "language=eng", str(output_path)
            ]
        else:
            cmd = [
                "ffmpeg", "-i", str(video_path), "-vf",
                f"subtitles={sub_path}", "-c:a", "copy", str(output_path)
            ]
        
        await message.reply_text("⏳ Processing... This may take a while")
        
        success, output = await run_command(cmd)
        if not success:
            raise Exception(f"FFmpeg error: {output}")
            
        if not output_path.exists():
            raise Exception("Output file not created")
            
        await send_results(client, user_id, output_path, mux_type)
        
    except Exception as e:
        logger.error(f"Processing error: {e}")
        await message.reply_text(f"❌ Processing failed: {e}")
    finally:
        clean_temp(user_id)
        del user_sessions[user_id]

@app.on_callback_query(filters.regex("^cancel$"))
async def cancel_processing(client, callback_query):
    """Handle cancellation requests"""
    user_id = callback_query.from_user.id
    if user_id in user_sessions:
        clean_temp(user_id)
        del user_sessions[user_id]
    await callback_query.answer("Operation cancelled")
    await callback_query.message.edit_text("❌ Operation cancelled by user")

@app.on_message(filters.command("clean"))
async def force_clean(client, message):
    """Force clean user's temporary files"""
    clean_temp(message.from_user.id)
    await message.reply_text("🧹 All temporary files cleaned!")


if __name__ == "__main__":
    logger.info("Starting bot...")
    app.run()
