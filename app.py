from flask import Flask
import threading
import os

# ТВОЙ БОТ (импортируй как у тебя)
from bot import bot

app = Flask(__name__)

@app.route('/')
def home():
    return "Бот работает!"

def run_bot():
    bot.polling(none_stop=True)

if __name__ == "__main__":
    thread = threading.Thread(target=run_bot)
    thread.start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)