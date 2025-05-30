from config import Config
import time
import re
import asyncio


progress_pattern = re.compile(
    r'(frame|fps|size|time|bitrate|speed)\s*\=\s*(\S+)'
)

def parse_progress(line):
    items = {
        key: value for key, value in progress_pattern.findall(line)
    }
    if not items:
        return None
    return items

async def readlines(stream):
    pattern = re.compile(br'[\r\n]+')

    data = bytearray()
    while not stream.at_eof():
        lines = pattern.split(data)
        data[:] = lines.pop(-1)

        for line in lines:
            yield line

        data.extend(await stream.read(1024))

async def read_stderr(start, msg, process):
    async for line in readlines(process.stderr):
            line = line.decode('utf-8')
            progress = parse_progress(line)
            if progress:
                #Progress bar logic
                now = time.time()
                diff = start-now
                text = 'PROGRESS\n'
                text += 'Size : {}\n'.format(progress['size'])
                text += 'Time : {}\n'.format(progress['time'])
                text += 'Speed : {}\n'.format(progress['speed'])

                if round(diff % 5)==0:
                    try:
                        await msg.edit( text )
                    except:
                        pass

async def softmux_vid(vid_filename, sub_filename, msg):

    start = time.time()
    vid = Config.DOWNLOAD_DIR+'/'+vid_filename
    sub = Config.DOWNLOAD_DIR+'/'+sub_filename

    out_file = '.'.join(vid_filename.split('.')[:-1])
    output = out_file+'1.mkv'
    out_location = Config.DOWNLOAD_DIR+'/'+output
    sub_ext = sub_filename.split('.').pop()
    command = [
            'ffmpeg','-hide_banner',
            '-i',vid,
            '-i',sub,
            '-map','1:0','-map','0',
            '-disposition:s:0','default',
            '-c:v','copy',
            '-c:a','copy',
            '-c:s','copy',
            '-y',out_location
            ]

    process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            )

    await asyncio.wait([
        asyncio.create_task(read_stderr(start, msg, process)),
        asyncio.create_task(process.wait())
    ])
    
    if process.returncode == 0:
        await msg.edit('Muxing  Completed Successfully!\n\nTime taken : {} seconds'.format(round(time.time()-start)))
    else:
        await msg.edit('An Error occurred while Muxing!')
        return False
    time.sleep(2)
    return output


async def hardmux_vid(vid_filename, sub_filename, msg):
    
    start = time.time()
    vid = Config.DOWNLOAD_DIR+'/'+vid_filename
    sub = Config.DOWNLOAD_DIR+'/'+sub_filename
    
    out_file = '.'.join(vid_filename.split('.')[:-1])
    output = out_file+'1.mp4'
    out_location = Config.DOWNLOAD_DIR+'/'+output
    
    command = [
       'ffmpeg', '-hide_banner',
       '-i', vid,
       '-vf', f"subtitles={sub}",
       '-c:v', 'libx264',         # Use libx264 encoder instead of 'h264'
       '-preset', 'faster',    # You can change this to 'medium', 'slow', etc.
       '-crf', '27',              # Adjust CRF (lower is better quality, higher is more compressed)
       '-map', '0:v:0',
       '-map', '0:a:0?',
       '-y', out_location
    ]
    process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            )
    
    await asyncio.wait([
        asyncio.create_task(read_stderr(start, msg, process)),
        asyncio.create_task(process.wait())
    ])
    
    if process.returncode == 0:
        await msg.edit('Muxing  Completed Successfully!\n\nTime taken : {} seconds'.format(round(time.time()-start)))
    else:
        await msg.edit('An Error occurred while Muxing!')
        return False
    
    time.sleep(2)
    return output
