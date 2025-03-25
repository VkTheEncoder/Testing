import os
import re
import time
import math
import logging
import asyncio
from pathlib import Path
from typing import Dict, Tuple

from pyrogram import Client, filters
from pyrogram.errors import RPCError
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
BOT_TOKEN = "7747531722:AAFgE11HA4SbfjOFWTVT3_Sp-xR8tBDJdeo"
MAX_FILE_SIZE = 4000000000  # 4GB
SUPPORTED_SUBTITLE_EXT = [".srt", ".ass", ".ssa", ".vtt"]

# Temporary directory for storing downloads and processed files
TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

# Store user sessions in memory
user_sessions: Dict[int, Dict] = {}

app = Client("sub_mux_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ----------------------------------------------------------------------------- #
#                               HELPER FUNCTIONS                                #
# ----------------------------------------------------------------------------- #

def clean_temp(user_id: int):
    """
    Remove temporary files for a user by deleting the user's subdirectory in temp/.
    """
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

def human_readable_size(size: float) -> str:
    """
    Convert a file size (in bytes) into a human-readable format, e.g. 1.23 MB.
    """
    if size == 0:
        return "0B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    return f"{size:.2f}{units[i]}"

def time_formatter(seconds: float) -> str:
    """
    Convert seconds into HH:MM:SS format for ETA display.
    """
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = (seconds % 3600) % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

async def get_video_duration(file_path: Path) -> float:
    """
    Use ffprobe to get the duration (in seconds) of a video file.
    Returns 0.0 if there's an error.
    """
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            return float(stdout.decode().strip())
    except Exception as e:
        logger.error(f"Error getting duration: {e}")
    return 0.0

def get_output_path(user_id: int, original_name: str) -> Path:
    """
    Generate the output file path using the exact same file name as the original video.
    """
    user_dir = TEMP_DIR / str(user_id)
    return user_dir / original_name

# ----------------------------------------------------------------------------- #
#                     PROGRESS-AWARE DOWNLOAD / UPLOAD                          #
# ----------------------------------------------------------------------------- #

async def download_file_with_progress(
    client: Client, message: Message, file_type: str
) -> Path:
    """
    Download a file (video or subtitle) from the message to a user-specific directory,
    with a progress callback that updates every ~1 second.
    """
    user_dir = TEMP_DIR / str(message.from_user.id)
    user_dir.mkdir(exist_ok=True)
    
    file_path = user_dir / f"{file_type}_{message.id}"
    start_time = time.time()
    status_msg = await message.reply_text(f"📥 Downloading {file_type}...")
    
    last_update_time = time.time()
    previous_bytes = [0]  # store previous "current" to measure speed

    def progress_callback(current, total):
        nonlocal last_update_time
        
        now = time.time()
        if (now - last_update_time) >= 1:  # update every 1 second
            diff = now - last_update_time
            speed = (current - previous_bytes[0]) / diff if diff > 0 else 0
            previous_bytes[0] = current
            last_update_time = now

            if speed != 0:
                eta = (total - current) / speed
            else:
                eta = 0

            percentage = current * 100 / total
            progress_text = (
                f"**{file_type.capitalize()} Downloading**\n"
                f"**Progress:** {percentage:.2f}%\n"
                f"**Done:** {human_readable_size(current)}/{human_readable_size(total)}\n"
                f"**Speed:** {human_readable_size(speed)}/s\n"
                f"**ETA:** {time_formatter(eta)}\n"
            )
            try:
                asyncio.create_task(status_msg.edit_text(progress_text))
            except:
                pass  # ignore edit failures

    # Perform the actual download
    try:
        await client.download_media(
            message,
            file_name=str(file_path),
            progress=progress_callback
        )
        await status_msg.edit_text(f"✅ {file_type.capitalize()} downloaded successfully!")
        return file_path
    except RPCError as e:
        await status_msg.edit_text(f"❌ Failed to download {file_type}: {e}")
        raise
    except Exception as e:
        await status_msg.edit_text(f"❌ Unexpected error downloading {file_type}: {e}")
        raise

async def upload_file_with_progress(
    client: Client, chat_id: int, file_path: Path, caption: str
):
    """
    Send (upload) the processed file back to the user with progress updates.
    """
    start_time = time.time()
    status_msg = await client.send_message(chat_id, "📤 Uploading file...")
    
    last_update_time = time.time()
    previous_bytes = [0]

    def progress_callback(current, total):
        nonlocal last_update_time
        
        now = time.time()
        if (now - last_update_time) >= 1:  # update every 1 second
            diff = now - last_update_time
            speed = (current - previous_bytes[0]) / diff if diff > 0 else 0
            previous_bytes[0] = current
            last_update_time = now

            if speed != 0:
                eta = (total - current) / speed
            else:
                eta = 0

            percentage = current * 100 / total
            progress_text = (
                f"**Uploading**\n"
                f"**Progress:** {percentage:.2f}%\n"
                f"**Done:** {human_readable_size(current)}/{human_readable_size(total)}\n"
                f"**Speed:** {human_readable_size(speed)}/s\n"
                f"**ETA:** {time_formatter(eta)}\n"
            )
            try:
                asyncio.create_task(status_msg.edit_text(progress_text))
            except:
                pass

    # Perform the actual upload
    await client.send_document(
        chat_id=chat_id,
        document=str(file_path),
        caption=caption,
        progress=progress_callback
    )
    await status_msg.delete()

# ----------------------------------------------------------------------------- #
#                    PROGRESS-AWARE FFmpeg ENCODING (MUX)                       #
# ----------------------------------------------------------------------------- #

async def ffmpeg_mux_with_progress(
    input_video: Path,
    input_sub: Path,
    output_path: Path,
    mux_type: str,
    message: Message
):
    """
    Run FFmpeg in real-time to either soft-mux or hard-mux subtitles, showing progress.
    For encoding, we parse -progress pipe:1 output to estimate time done and speed.
    """
    # 1) Get total duration of the input video for progress
    total_duration = await get_video_duration(input_video)
    
    # 2) Build FFmpeg command with -progress pipe:1
    #    * Softmux: embed subtitles (copy video/audio)
    #    * Hardmux: burn subtitles (re-encode video, copy audio)
    if mux_type == "softmux":
        cmd = [
            "ffmpeg",
            "-i", str(input_video),
            "-i", str(input_sub),
            "-map", "0", "-map", "1",
            "-c", "copy",
            "-metadata:s:s:0", "language=eng",
            "-progress", "pipe:1",
            "-nostats",
            str(output_path)
        ]
    else:
        cmd = [
            "ffmpeg",
            "-i", str(input_video),
            "-vf", f"subtitles={input_sub}",
            "-c:a", "copy",
            "-progress", "pipe:1",
            "-nostats",
            str(output_path)
        ]
    
    status_msg = await message.reply_text("⏳ Starting FFmpeg process...")
    
    # 3) Start FFmpeg process
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    last_update_time = time.time()
    current_time_in_seconds = 0.0
    speed_str = "0.0x"

    # 4) Read progress lines in real-time
    while True:
        line = await proc.stdout.readline()
        if not line:
            break  # no more output, process ended
        line = line.decode().strip()
        
        # Example lines we might get from -progress pipe:1:
        # out_time_ms=1234567
        # speed=1.23x
        if line.startswith("out_time_ms="):
            val = line.split("=")[1]
            out_time_ms = int(val)
            current_time_in_seconds = out_time_ms / 1_000_000.0
        elif line.startswith("speed="):
            speed_str = line.split("=")[1]  # e.g. "2.53x"
        
        now = time.time()
        if (now - last_update_time) >= 1:  # update every 1 second
            last_update_time = now

            # Calculate percentage
            if total_duration > 0:
                progress_pct = (current_time_in_seconds / total_duration) * 100
                if progress_pct > 100:
                    progress_pct = 100.0
            else:
                # If we can't determine total duration, just show current_time
                progress_pct = 0

            # Estimate time left
            # speed_str might look like "2.53x"
            try:
                speed_val = float(speed_str.replace('x', ''))
            except:
                speed_val = 0.0

            # If speed_val > 0, we can compute an ETA
            if speed_val > 0 and total_duration > 0:
                real_time_done = current_time_in_seconds / speed_val
                real_time_total = total_duration / speed_val
                eta = real_time_total - real_time_done
            else:
                eta = 0
            
            # Build progress text
            done_time_fmt = time_formatter(current_time_in_seconds)
            total_time_fmt = time_formatter(total_duration)
            eta_fmt = time_formatter(eta)
            progress_text = (
                f"**FFmpeg {mux_type.capitalize()} in Progress**\n"
                f"**Progress:** {progress_pct:.2f}%\n"
                f"**Time:** {done_time_fmt}/{total_time_fmt}\n"
                f"**Speed:** {speed_str}\n"
                f"**ETA:** {eta_fmt}"
            )
            try:
                await status_msg.edit_text(progress_text)
            except:
                pass

    # Wait for process to exit fully
    await proc.wait()

    # Check return code
    if proc.returncode != 0:
        # If there's an error, read stderr
        err = (await proc.stderr.read()).decode()
        raise RuntimeError(f"FFmpeg failed:\n{err}")

    # If everything is okay, update message
    await status_msg.edit_text("✅ FFmpeg process completed successfully!")

# ----------------------------------------------------------------------------- #
#                               BOT HANDLERS                                    #
# ----------------------------------------------------------------------------- #

@app.on_message(filters.command(["start", "help"]))
async def start(client: Client, message: Message):
    """
    Handle /start or /help commands.
    """
    help_text = """
🤖 **Subtitle Muxer Bot**

🔹 **Features:**
- Soft mux (embed subtitles as a separate stream)
- Hard mux (burn subtitles into video)
- Multiple subtitle formats (SRT, ASS, SSA, VTT)
- Progress tracking (download, encode, upload)
- Error handling and validation

📌 **How to use:**
1. Send /softmux or /hardmux
2. Send video file
3. Send subtitle file

📝 **Notes:**
- Maximum file size: 2GB
- Processing time depends on file size and encode complexity
"""
    await message.reply_text(help_text)

@app.on_message(filters.command(["softmux", "hardmux"]))
async def mux_handler(client: Client, message: Message):
    """
    Handle /softmux or /hardmux commands.
    """
    user_id = message.from_user.id
    mux_type = message.command[0]
    
    # Initialize user session
    user_sessions[user_id] = {
        "mux_type": mux_type,
        "video_path": None,
        "video_name": None,  # We'll store the original video file name here
        "sub_path": None,
        "processing": False
    }
    
    await message.reply_text(
        f"Please send your video file for {mux_type} muxing...",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
        )
    )

@app.on_message(filters.document | filters.video)
async def handle_files(client: Client, message: Message):
    """
    Handle incoming video/subtitle files, track user session state, and download them.
    """
    user_id = message.from_user.id
    if user_id not in user_sessions:
        # The user hasn't started a muxing session yet
        return
    
    session = user_sessions[user_id]
    
    try:
        # Extract filename and size from either document or video
        file_name = (
            message.document.file_name if message.document else message.video.file_name
        )
        file_size = (
            message.document.file_size if message.document else message.video.file_size
        )
        
        if file_size > MAX_FILE_SIZE:
            await message.reply_text("❌ File size exceeds 2GB limit!")
            return
            
        # If we haven't stored a video yet, this file is assumed to be the video
        if not session["video_path"]:
            # Validate video extension
            if not re.search(r"\.(mp4|mkv|avi|mov)$", file_name, re.I):
                await message.reply_text(
                    "❌ Invalid video format! Supported formats: MP4, MKV, AVI, MOV"
                )
                return
            
            # Download video with progress
            session["video_path"] = await download_file_with_progress(
                client, message, "video"
            )
            session["video_name"] = file_name  # Store original video name
            await message.reply_text("Now please send your subtitle file...")
        
        # If we already have the video but no subtitle yet, this file is assumed to be the subtitle
        elif not session["sub_path"]:
            # Validate subtitle extension
            ext = Path(file_name).suffix.lower()
            if ext not in SUPPORTED_SUBTITLE_EXT:
                await message.reply_text(
                    f"❌ Unsupported subtitle format! Supported: {', '.join(SUPPORTED_SUBTITLE_EXT)}"
                )
                return
            
            # Download subtitle with progress
            session["sub_path"] = await download_file_with_progress(
                client, message, "subtitle"
            )
            
            # Now we have both video and subtitle, process them
            await process_files_with_progress(client, message, session)
            
    except Exception as e:
        logger.error(f"File handling error: {e}")
        await message.reply_text(f"❌ Error processing file: {e}")
        clean_temp(user_id)
        del user_sessions[user_id]

async def process_files_with_progress(client: Client, message: Message, session: Dict):
    """
    Use FFmpeg to softmux or hardmux subtitles into the video, showing progress,
    then upload the result with progress.
    """
    user_id = message.from_user.id
    mux_type = session["mux_type"]
    video_path = session["video_path"]
    sub_path = session["sub_path"]
    original_name = session["video_name"]  # The original video file name
    
    try:
        # The output path uses the same original file name
        output_path = get_output_path(user_id, original_name)
        
        # 1) Run FFmpeg with real-time progress
        await ffmpeg_mux_with_progress(video_path, sub_path, output_path, mux_type, message)
        
        # 2) Ensure output file exists
        if not output_path.exists():
            raise Exception("Output file not created by FFmpeg.")
        
        # 3) Upload the resulting file with progress
        await upload_file_with_progress(
            client, user_id, output_path, f"✅ {mux_type.capitalize()} muxing completed!"
        )
        
    except Exception as e:
        logger.error(f"Processing error: {e}")
        await message.reply_text(f"❌ Processing failed: {e}")
    finally:
        # Clean up session and temporary files
        clean_temp(user_id)
        del user_sessions[user_id]

@app.on_callback_query(filters.regex("^cancel$"))
async def cancel_processing(client, callback_query):
    """
    Handle the user pressing 'Cancel' during a muxing session.
    """
    user_id = callback_query.from_user.id
    if user_id in user_sessions:
        clean_temp(user_id)
        del user_sessions[user_id]
    await callback_query.answer("Operation cancelled")
    await callback_query.message.edit_text("❌ Operation cancelled by user")

@app.on_message(filters.command("clean"))
async def force_clean(client: Client, message: Message):
    """
    Force a cleanup of the user's temporary files if something goes wrong.
    """
    clean_temp(message.from_user.id)
    await message.reply_text("🧹 All temporary files cleaned!")

if __name__ == "__main__":
    logger.info("Starting bot...")
    app.run()
