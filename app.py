from gsi_server import app  # Flask app для gunicorn

# ВАЖНО: Discord-бот запускаем только если не выключено через ENV
import os
if os.getenv("DISABLE_DISCORD_BOT") != "1":
    import threading
    from main import bot  # bot уже создан в main.py
    from config import BOT_TOKEN
    threading.Thread(target=lambda: bot.run(BOT_TOKEN), daemon=True).start()
