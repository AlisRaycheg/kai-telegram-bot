import sqlite3
import os

DB_FILE = "bot.db"

def get_db_connection():
    """Создаёт подключение к БД и создаёт таблицы при первом запуске"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Таблица для лимита проверок
    c.execute('''CREATE TABLE IF NOT EXISTS check_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        timestamp TEXT,
        cookie_count INTEGER
    )''')
    
    # Глобальная статистика
    c.execute('''CREATE TABLE IF NOT EXISTS global_stats (
        id INTEGER PRIMARY KEY,
        total_cookies_checked INTEGER DEFAULT 0
    )''')
    c.execute('INSERT OR IGNORE INTO global_stats (id) VALUES (1)')
    
    conn.commit()
    return conn

# Инициализация при импорте
conn = get_db_connection()
cursor = conn.cursor()

def init_db():
    """Функция для явного вызова (если нужно)"""
    pass  # Уже инициализировано при импорте

def log_user_check(user_id, count):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM check_logs WHERE timestamp < datetime('now', '-2 hours')")
    c.execute("INSERT INTO check_logs (user_id, timestamp, cookie_count) VALUES (?, datetime('now'), ?)", (user_id, count))
    conn.commit()
    conn.close()

def get_hourly_check_count(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(cookie_count), 0) FROM check_logs WHERE user_id = ? AND timestamp > datetime('now', '-1 hour')", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def update_global_cookies_checked(amount):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE global_stats SET total_cookies_checked = total_cookies_checked + ? WHERE id = 1", (amount,))
    conn.commit()
    conn.close()
