import os
import time
import threading
import logging
from handlers import Bot
from config import TELEGRAM_BOT_TOKEN
from database import init_db  # ДОБАВЛЯЕМ ИМПОРТ

# ============================================================
# СОЗДАЁМ ПАПКИ ПЕРЕД ЛОГИРОВАНИЕМ
# ============================================================
os.makedirs("data/profiles", exist_ok=True)
os.makedirs("data/logs", exist_ok=True)
os.makedirs("incoming_cookies/raw", exist_ok=True)
os.makedirs("results", exist_ok=True)

# ============================================================
# НАСТРОЙКА ЛОГОВ (ТОЛЬКО В КОНСОЛЬ)
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# ============================================================
# ЗАПУСК
# ============================================================
if __name__ == "__main__":
    # ИНИЦИАЛИЗАЦИЯ БД
    init_db()
    
    logger.info("🤖 KAI CHECKER запущен!")
    print("🤖 Бот Kai Checker готов к работе!")
    
    bot = Bot(TELEGRAM_BOT_TOKEN)
    bot.run()
