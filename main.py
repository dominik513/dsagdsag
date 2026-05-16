import discord
from discord.ext import commands
from config import BOT_TOKEN, GUILD_ID
from database.connection import init_db
from gsi_server import app
import threading
import os
import inspect

print("""
╔══════════════════════════════════════════╗
║          TOURNAMENT | ZXC                ║
║        Dota 2 Tournament Bot             ║
║                                          ║
║   Спасибо за покупку в Mindy Studios!    ║
╚══════════════════════════════════════════╝
""")

init_db()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

EXTENSIONS = (
    "cogs.tournament",
    "cogs.shop",
    "cogs.inventory",
    "cogs.clans",
    "cogs.roles",
    "cogs.fun",
)


class TournamentBot(commands.Bot):
    async def setup_hook(self):
        # Важно: в discord.py 2.x load_extension стал coroutine.
        # В py-cord может быть sync — поэтому поддерживаем оба варианта.
        for ext in EXTENSIONS:
            try:
                res = self.load_extension(ext)
                if inspect.isawaitable(res):
                    await res
                print(f"[OK] extension loaded: {ext}")
            except Exception as e:
                print(f"[ERROR] failed to load extension {ext}: {e}")

        # Синхронизация slash-команд:
        # - py-cord: bot.sync_commands(...)
        # - discord.py: bot.tree.sync(...)
        try:
            if hasattr(self, "sync_commands"):
                await self.sync_commands(guild_ids=[GUILD_ID])
                print("[OK] slash commands synced (py-cord)")
            elif hasattr(self, "tree"):
                await self.tree.sync(guild=discord.Object(id=GUILD_ID))
                print("[OK] slash commands synced (discord.py)")
        except Exception as e:
            print(f"[ERROR] slash commands sync failed: {e}")


bot = TournamentBot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"[READY] Logged in as {bot.user} (guild_id={GUILD_ID})")

if __name__ == "__main__":
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is empty. Set BOT_TOKEN env var in Render.")

    # Render ожидает HTTP сервер на $PORT, поэтому Flask оставляем,
    # но переносим его в отдельный поток, а Discord bot запускаем в main thread.
    def run_flask():
        port = int(os.getenv("PORT", "8080"))
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(BOT_TOKEN)
