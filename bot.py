# bot.py
import logging
import os
from handlers import Bot
from config import TELEGRAM_BOT_TOKEN
from database import init_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/logs/bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

if __name__ == "__main__":
    os.makedirs("data/profiles", exist_ok=True)
    os.makedirs("data/logs", exist_ok=True)
    os.makedirs("incoming_cookies/raw", exist_ok=True)
    os.makedirs("results", exist_ok=True)
    init_db()
    
    bot = Bot(TELEGRAM_BOT_TOKEN)
    bot.run()