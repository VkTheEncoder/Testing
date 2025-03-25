# Use an official Python slim image as base
FROM python:3.10-slim

# Install system dependencies (including ffmpeg for video processing)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy the requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Set environment variables (replace these with your actual credentials or pass them during runtime)
ENV API_ID=your_api_id
ENV API_HASH=your_api_hash
ENV BOT_TOKEN=your_bot_token

# Run the bot (assuming your main script is named bot.py)
CMD ["python", "bot.py"]
