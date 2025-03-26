
import os

class Config:

    BOT_TOKEN = "7647294451:AAHo8YWCZTnInsr24BTQSzCZu-SGuCuVf14"
    APP_ID = 27999679
    API_HASH = "f553398ca957b9c92bcb672b05557038"

    #comma seperated user id of users who are allowed to use
    ALLOWED_USERS = [x.strip(' ') for x in os.environ.get('ALLOWED_USERS','5314733603,6022020248,5996829431,6136203777,7235663635').split(',')]

    DOWNLOAD_DIR = 'downloads'
