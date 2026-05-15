import discord
from discord.ext import commands
from config import BOT_TOKEN, GUILD_ID
from database.connection import init_db
from gsi_server import app
import threading
import os

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

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    try:
        guild = bot.get_guild(GUILD_ID)
        if guild:
            await bot.sync_commands(guild_ids=[GUILD_ID])
    except:
        pass

bot.load_extension("cogs.tournament")
bot.load_extension("cogs.shop")
bot.load_extension("cogs.inventory")
bot.load_extension("cogs.clans")
bot.load_extension("cogs.roles")
bot.load_extension("cogs.fun")

if __name__ == "__main__":
    threading.Thread(target=lambda: bot.run(BOT_TOKEN), daemon=True).start()
    port = int(os.getenv("PORT", "8080"))
    app.run(host='0.0.0.0', port=port, debug=False)
