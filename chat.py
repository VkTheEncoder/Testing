class Chat:

    START_TEXT = """👋 <b>Hey there!</b>  
📌 <b>This is a Telegram Bot to Mux Subtitles into a Video.</b>  

🎬 <b>How to Use:</b>  
➡️ Send me a Telegram file to begin!  
ℹ️ Type <code>/help</code> for more details.  

💡 <b>Credits:</b> @Cybrion  
    """

    HELP_USER = "🤖 How can I assist you?"

    HELP_TEXT = """🆘 <b>Welcome to the Help Menu!</b>  

✅ <b>How to Use:</b>  
1️⃣ Send a video file or provide a URL.  
2️⃣ Send a subtitle file (<code>.ass</code> or <code>.srt</code>).  
3️⃣ Choose your desired type of muxing!  

📌 <b>Custom File Name:</b>  
To set a custom name, send it along with the URL separated by <code>|</code>.  
Example: <i>url|custom_name.mp4</i>  

⚠️ <b>Note:</b>  
<i>Hardmux only supports English fonts. Other scripts may appear as empty blocks in the video!</i>  

🤖 <b>For AI-based Subtitle Generation, Visit:</b> <a href="https://aisubbing.xyz">aisubbing.xyz</a>  

💡 <b>Credits:</b> @Cybrion  
    """

    NO_AUTH_USER = """🚫 <b>Access Denied!</b>  
You are not authorized to use this bot.  

📩 Contact Cybrion II via @Cybrion for access!  

💡 <b>Credits:</b> @Cybrion  
    """

    DOWNLOAD_SUCCESS = """✅ <b>File Downloaded Successfully!</b>  

⏳ Time Taken: <b>{} seconds</b>.  

💡 <b>Credits:</b> @Cybrion  
    """

    FILE_SIZE_ERROR = "❌ <b>ERROR:</b> Unable to extract file size from the URL!\n\n💡 <b>Credits:</b> @Cybrion"
    MAX_FILE_SIZE = "⚠️ <b>File too Large!</b> The maximum file size allowed by Telegram is <b>2GB</b>.\n\n💡 <b>Credits:</b> @Cybrion"
    
    LONG_CUS_FILENAME = """⚠️ <b>Filename Too Long!</b>  
The filename you provided exceeds 60 characters.  
Please use a shorter name.  

💡 <b>Credits:</b> @Cybrion  
    """

    UNSUPPORTED_FORMAT = "❌ <b>ERROR:</b> File format <b>{}</b> is not supported!\n\n💡 <b>Credits:</b> @Cybrion"