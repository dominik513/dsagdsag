from __future__ import annotations

import os


def _env_int(name: str, default: int = 0) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"[WARN] {name}={raw!r} — не число, используем {default}")
        return default


# Поддержка .env (удобно для хостингов, где нет нормального UI для ENV).
# Если python-dotenv не установлен — просто игнорируем.
try:
    from dotenv import load_dotenv
    # 1) Явный путь (если задан ENV_FILE)
    env_file = os.getenv("ENV_FILE", "").strip()
    if env_file:
        load_dotenv(env_file, override=False)
    # 2) Дефолтный путь для VPS-деплоя
    elif os.path.exists("/opt/tournament-bot/.env"):
        load_dotenv("/opt/tournament-bot/.env", override=False)
    # 3) Фолбэк: .env рядом с запуском (локально/Render)
    load_dotenv(override=False)
except Exception:
    pass

# ВАЖНО: токен не должен храниться в коде/репозитории. Задавай BOT_TOKEN в переменных окружения.
BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip().strip('"').strip("'")
ADMIN_CHANNEL_ID = int(os.getenv("ADMIN_CHANNEL_ID", "1194213813470363711"))
REGISTRATION_CHANNEL_ID = int(os.getenv("REGISTRATION_CHANNEL_ID", "1204457612121215028"))
REQUESTS_CHANNEL_ID = int(os.getenv("REQUESTS_CHANNEL_ID", "1202232778771402772"))
# Канал подробных логов матчей (K/D/A, добив, LH/DN, аннулирования). 0 = отключено
MATCH_LOG_CHANNEL_ID = _env_int("MATCH_LOG_CHANNEL_ID", 0)

# Антиабуз / аннулирование матчей
INTEGRITY_MIN_MAPPED_PLAYERS = int(os.getenv("INTEGRITY_MIN_MAPPED_PLAYERS", "1"))
INTEGRITY_MIN_DEATHS_5X5 = int(os.getenv("INTEGRITY_MIN_DEATHS_5X5", "12"))
INTEGRITY_MIN_DEATHS_1X1 = int(os.getenv("INTEGRITY_MIN_DEATHS_1X1", "8"))
INTEGRITY_MAX_KDA_FEED = float(os.getenv("INTEGRITY_MAX_KDA_FEED", "0.15"))
INTEGRITY_BLOWOUT_SCORE_DIFF = int(os.getenv("INTEGRITY_BLOWOUT_SCORE_DIFF", "25"))
INTEGRITY_BLOWOUT_MAX_MINUTES = int(os.getenv("INTEGRITY_BLOWOUT_MAX_MINUTES", "8"))
MVP_BONUS_POINTS = int(os.getenv("MVP_BONUS_POINTS", "15"))
STREAK_BONUS_PER_WIN = int(os.getenv("STREAK_BONUS_PER_WIN", "5"))
STREAK_BONUS_MAX = int(os.getenv("STREAK_BONUS_MAX", "25"))
FEED_PENALTY_POINTS = int(os.getenv("FEED_PENALTY_POINTS", "75"))
GUILD_ID = _env_int("GUILD_ID", 1194213813428441108)
DEFAULT_GATHER_TIMEOUT = int(os.getenv("DEFAULT_GATHER_TIMEOUT", "300"))
WINNER_POINTS = int(os.getenv("WINNER_POINTS", "125"))
LOSER_POINTS = int(os.getenv("LOSER_POINTS", "35"))
GSI_HOST = os.getenv("GSI_HOST", "0.0.0.0")
GSI_PUBLIC_URL = os.getenv("GSI_PUBLIC_URL", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/tournament_bot.db")
# Опционально: для ссылок steamcommunity.com/id/… (ResolveVanityURL)
STEAM_API_KEY = os.getenv("STEAM_API_KEY", "").strip()

# Кланы: казна и бонусы
CLAN_MATCH_TREASURY_BONUS = _env_int("CLAN_MATCH_TREASURY_BONUS", 25)
CLAN_MATCH_MIN_MEMBERS = _env_int("CLAN_MATCH_MIN_MEMBERS", 2)
CLAN_XP_PER_100_DEPOSIT = _env_int("CLAN_XP_PER_100_DEPOSIT", 15)
CLAN_LEVEL_XP_BASE = _env_int("CLAN_LEVEL_XP_BASE", 500)
CLAN_TIP_MIN = _env_int("CLAN_TIP_MIN", 5)

# Развлечения / удержание
WEEKLY_REWARD = _env_int("WEEKLY_REWARD", 75)
LUCKY_COOLDOWN_HOURS = _env_int("LUCKY_COOLDOWN_HOURS", 12)
LUCKY_MIN = _env_int("LUCKY_MIN", 5)
LUCKY_MAX = _env_int("LUCKY_MAX", 45)
LUCKY_JACKPOT = _env_int("LUCKY_JACKPOT", 150)
LUCKY_JACKPOT_CHANCE = _env_int("LUCKY_JACKPOT_CHANCE", 3)
ACTIVITY_BASE_REWARD = _env_int("ACTIVITY_BASE_REWARD", 10)
ACTIVITY_STREAK_CAP = _env_int("ACTIVITY_STREAK_CAP", 50)
GAMBLE_MIN = _env_int("GAMBLE_MIN", 10)
GAMBLE_MAX = _env_int("GAMBLE_MAX", 500)
GAMBLE_COOLDOWN_SEC = _env_int("GAMBLE_COOLDOWN_SEC", 30)
GAMBLE_PAYOUT_MULT = float(os.getenv("GAMBLE_PAYOUT_MULT", "1.85"))
DUEL_MIN = _env_int("DUEL_MIN", 15)
DUEL_MAX = _env_int("DUEL_MAX", 1000)
DUEL_TIMEOUT_SEC = _env_int("DUEL_TIMEOUT_SEC", 120)
EMOJI_CALIBRATION = os.getenv("EMOJI_CALIBRATION", "<:Calibration:1502664167532793856>")
EMOJI_STATIC = os.getenv("EMOJI_STATIC", "<:Static:1502385956450336818>")
EMOJI_NULL = os.getenv("EMOJI_NULL", "<:Null:1502385996455612537>")
EMOJI_PULSE = os.getenv("EMOJI_PULSE", "<:Pulse:1502386027904503888>")
EMOJI_VEIN = os.getenv("EMOJI_VEIN", "<:Vein:1502386065451909293>")
EMOJI_ECHO = os.getenv("EMOJI_ECHO", "<:Echo:1502386121903050934>")
EMOJI_HAZE = os.getenv("EMOJI_HAZE", "<:Haze:1502386156099338241>")
EMOJI_VANTA = os.getenv("EMOJI_VANTA", "<:Vanta:1502386195550961806>")
EMOJI_ABYSS = os.getenv("EMOJI_ABYSS", "<:Abyss:1502386230543777902>")
EMOJI_PHANTOM = os.getenv("EMOJI_PHANTOM", "<:Phantom:1502386265050316810>")
EMOJI_ECLIPSE = os.getenv("EMOJI_ECLIPSE", "<:Eclipse:1502386298764263474>")
EMOJI_CARRY = os.getenv("EMOJI_CARRY", "<:pos1:1502596075045781714>")
EMOJI_MID = os.getenv("EMOJI_MID", "<:pos2:1502596096478810112>")
EMOJI_OFFLANE = os.getenv("EMOJI_OFFLANE", "<:pos3:1502596113537044491>")
EMOJI_SUP4 = os.getenv("EMOJI_SUP4", "<:pos4:1502596130838548541>")
EMOJI_SUP5 = os.getenv("EMOJI_SUP5", "<:pos5:1502596151688433746>")
EMOJI_RADIANT = os.getenv("EMOJI_RADIANT", "<:radiant:1502663664644128900>")
EMOJI_DIRE = os.getenv("EMOJI_DIRE", "<:dire:1502663694079758486>")
EMOJI_BET = os.getenv("EMOJI_BET", "<:bet:1502708077663621191>")
EMOJI_POINTS = os.getenv("EMOJI_POINTS", "<:points:1502708175114338504>")
EMOJI_CLOCK = os.getenv("EMOJI_CLOCK", "<:clocker:1502708207359885433>")
EMOJI_KILLS = os.getenv("EMOJI_KILLS", "<:kills:1502708368354050191>")
EMOJI_DEATHS = os.getenv("EMOJI_DEATHS", "<:deaths:1502708407730176010>")
EMOJI_ASSISTS = os.getenv("EMOJI_ASSISTS", "<:assists:1502708546603712643>")
EMOJI_PROFILE_POINTS = os.getenv("EMOJI_PROFILE_POINTS", "<:points:1502708175114338504>")
EMOJI_PROFILE_WINS = os.getenv("EMOJI_PROFILE_WINS", "<:kubok:1502711350689005740>")
EMOJI_PROFILE_LOSSES = os.getenv("EMOJI_PROFILE_LOSSES", "<:deaths:1502708407730176010>")
EMOJI_PROFILE_WINRATE = os.getenv("EMOJI_PROFILE_WINRATE", "<:winrate:1502718521275187200>")
EMOJI_PROFILE_MATCHES = os.getenv("EMOJI_PROFILE_MATCHES", "<:games:1502718569165885481>")
