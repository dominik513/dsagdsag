from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
import traceback
import logging
import urllib.error
import urllib.request

import discord
from discord.ext import commands

from config import BOT_TOKEN, GUILD_ID
from database.connection import init_db


def log(msg: str):
    print(msg, flush=True)


log("""
╔══════════════════════════════════════════╗
║          TOURNAMENT | ZXC                ║
║        Dota 2 Tournament Bot             ║
║                                          ║
║   Спасибо за покупку в Mindy Studios!    ║
╚══════════════════════════════════════════╝
""")

if not BOT_TOKEN:
    log("[FATAL] BOT_TOKEN пустой")
    sys.exit(1)
if not GUILD_ID:
    log("[FATAL] GUILD_ID пустой")
    sys.exit(1)

log(f"[CONFIG] GUILD_ID={GUILD_ID}")

init_db()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# fun/shop раньше — при обрыве sync хотя бы daily/profile успеют зарегистрироваться
EXTENSIONS = (
    "cogs.fun",
    "cogs.engagement",
    "cogs.shop",
    "cogs.inventory",
    "cogs.clans",
    "cogs.roles",
    "cogs.tournament",
    "cogs.admin",
)

DISCORD_API = "https://discord.com/api/v10"
# важные команды регистрируем первыми (individual sync)
_CMD_PRIORITY = (
    "ping", "bot_resync", "daily", "weekly", "lucky", "profile", "shop", "buy", "leaderboard",
    "sync", "link_dota", "link_steam", "gsi_status", "points_add",
)

_flask_started = False
_extension_load_ok = 0
_extension_errors: list[str] = []
MIN_COMMANDS_TO_SYNC = int(os.getenv("MIN_COMMANDS_TO_SYNC", "10"))


class TournamentBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("auto_sync_commands", False)
        super().__init__(*args, **kwargs)

    async def setup_hook(self):
        """Коги до подключения. Ошибка кога не должна ронять весь бот."""
        global _extension_load_ok, _extension_errors
        try:
            _extension_load_ok, _extension_errors = _load_extensions()
        except Exception as e:
            _extension_load_ok, _extension_errors = 0, [f"setup_hook: {e}"]
            log(f"[FATAL setup_hook] {e}")
            traceback.print_exc()


bot = TournamentBot(command_prefix="!", intents=intents)


@bot.slash_command(name="ping", guild_ids=[GUILD_ID])
async def ping(ctx: discord.ApplicationContext):
    await ctx.respond("pong", ephemeral=True)


@bot.slash_command(
    name="bot_resync",
    description="Пересинхронизировать команды (админ)",
    guild_ids=[GUILD_ID],
)
@commands.has_permissions(administrator=True)
async def bot_resync(ctx: discord.ApplicationContext):
    global _extension_load_ok, _extension_errors
    await ctx.defer(ephemeral=True)
    if _extension_load_ok < len(EXTENSIONS):
        try:
            _extension_load_ok, _extension_errors = _load_extensions()
        except Exception:
            pass
    ok, err = await _sync_slash_commands(force=True)
    n = len(_guild_commands())
    total = len(bot.pending_application_commands or [])
    if ok:
        await ctx.followup.send(
            f"<:yes:1503121926128664766> Зарегистрировано **{n}** команд (всего в боте: {total}).",
            ephemeral=True,
        )
    else:
        hint = "\n".join(_extension_errors[:6]) if _extension_errors else "—"
        await ctx.followup.send(
            f"<:no:1503121885674868938> Sync отменён: `{err}`\n"
            f"Коги: **{_extension_load_ok}/{len(EXTENSIONS)}**\n"
            f"```\n{hint[:900]}\n```",
            ephemeral=True,
        )


@bot.slash_command(
    name="bot_check",
    description="Диагностика: загружены ли коги и команды",
    guild_ids=[GUILD_ID],
)
async def bot_check(ctx: discord.ApplicationContext):
    await ctx.defer(ephemeral=True)
    guild_n = len(_guild_commands())
    total = len(bot.pending_application_commands or [])
    lines = [f"Коги: **{_extension_load_ok}/{len(EXTENSIONS)}**", f"Команд (guild): **{guild_n}**", f"Команд (всего): **{total}**"]
    if _extension_errors:
        lines.append("**Ошибки:**\n" + "\n".join(f"• `{e}`" for e in _extension_errors[:8]))
    else:
        lines.append("Все коги загружены.")
    if guild_n < MIN_COMMANDS_TO_SYNC:
        lines.append(
            f"\n⚠️ Мало команд (нужно ≥{MIN_COMMANDS_TO_SYNC}). "
            "Залейте папки `cogs/` и `utils/` на сервер."
        )
    await ctx.followup.send("\n".join(lines), ephemeral=True)


def _load_extensions():
    loaded = 0
    errors: list[str] = []
    for ext in EXTENSIONS:
        try:
            if ext in bot.extensions:
                loaded += 1
                continue
            bot.load_extension(ext)
            log(f"[OK] extension loaded: {ext}")
            loaded += 1
        except Exception as e:
            err_line = f"{ext}: {e}"
            errors.append(err_line)
            log(f"[ERROR] extension {err_line}")
            traceback.print_exc()
    guild_n = len(_guild_commands())
    total = len(bot.pending_application_commands or [])
    log(f"[SETUP] extensions {loaded}/{len(EXTENSIONS)} | slash guild={guild_n} total={total}")
    if errors:
        log("[SETUP] Исправьте ошибки когов — иначе в Discord останутся только ping/bot_resync")
    return loaded, errors


def _cmd_guild_ids(cmd) -> set[int]:
    gids = getattr(cmd, "guild_ids", None) or []
    out = set()
    for g in gids:
        try:
            out.add(int(g))
        except (TypeError, ValueError):
            pass
    return out


def _collect_guild_commands():
    """Все slash-команды бота для этого сервера (включая коги)."""
    out = []
    seen = set()
    walker = getattr(bot, "walk_application_commands", None)
    if walker:
        for cmd in walker():
            if cmd.name in seen:
                continue
            gids = _cmd_guild_ids(cmd)
            if not gids or GUILD_ID in gids:
                out.append(cmd)
                seen.add(cmd.name)
    else:
        for cmd in bot.pending_application_commands or []:
            if cmd.name in seen:
                continue
            if GUILD_ID in _cmd_guild_ids(cmd):
                out.append(cmd)
                seen.add(cmd.name)
    return out


def _guild_commands():
    return _collect_guild_commands()


def _start_flask_once():
    global _flask_started
    if _flask_started:
        return
    _flask_started = True
    from gsi_server import app

    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    def run_flask():
        port = int(os.getenv("PORT", "9576"))
        log(f"[FLASK] GSI порт {port}")
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

    threading.Thread(target=run_flask, daemon=True).start()


def _sort_payload(payload: list) -> list:
    prio = {n: i for i, n in enumerate(_CMD_PRIORITY)}
    return sorted(payload, key=lambda d: prio.get(d.get("name"), 500))


def _discord_http(method: str, path: str, body=None, timeout: float = 60.0):
    """Синхронный запрос к Discord API (stdlib urllib)."""
    url = DISCORD_API + path
    headers = {
        "Authorization": f"Bot {BOT_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "DiscordBot (tournament-zxc, 1.0)",
    }
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else []
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {err[:400]}") from e


def _parse_discord_error(msg: str):
    """Код 30034 = дневной лимит 200 созданий slash-команд."""
    try:
        start = msg.index("{")
        data = json.loads(msg[start:])
        return data.get("code"), float(data.get("retry_after") or 0)
    except (ValueError, json.JSONDecodeError, TypeError):
        return None, 0.0


def _guild_commands_path(app_id: int) -> str:
    return f"/applications/{app_id}/guilds/{GUILD_ID}/commands"


def _get_guild_commands(app_id: int):
    return _discord_http("GET", _guild_commands_path(app_id), None, timeout=30.0)


def _sync_bulk_put(app_id: int, payload: list):
    return _discord_http("PUT", _guild_commands_path(app_id), payload, timeout=90.0)


def _commands_already_registered(existing: list, payload: list) -> bool:
    """Пропускаем PUT только если набор команд совпадает (не «частично есть»)."""
    want = {p.get("name") for p in payload}
    have = {c.get("name") for c in existing if c.get("name")}
    return want == have and len(have) == len(want)


def _apply_command_ids(cmds, by_name: dict):
    for cmd in cmds:
        cid = by_name.get(cmd.name)
        if cid:
            cmd.id = cid


async def _bulk_put_retry(app_id: int, payload: list, cmds, label: str = ""):
    loop = asyncio.get_running_loop()
    prefix = f"[SYNC]{label}"
    for attempt in range(2):
        try:
            result = await loop.run_in_executor(None, _sync_bulk_put, app_id, payload)
            by_name = {item.get("name"): item.get("id") for item in result}
            _apply_command_ids(cmds, by_name)
            log(f"{prefix} OK — {len(result)} команд (один bulk PUT)")
            return True
        except Exception as e:
            err = str(e)
            code, retry = _parse_discord_error(err)
            if code == 30034:
                wait = max(retry, 300)
                log(f"{prefix} ЛИМИТ DISCORD 200 команд/сутки (код 30034).")
                log(f"{prefix} Слишком много перезапусков бота сегодня — лимит сбросится ~00:00 UTC.")
                log(f"{prefix} НЕ перезапускайте сервис. Автоповтор bulk через {wait:.0f} сек.")
                asyncio.create_task(_delayed_bulk_sync(app_id, payload, cmds, wait))
                return False
            if "429" in err and retry > 0 and attempt == 0:
                log(f"{prefix} rate limit, жду {retry + 2:.0f} сек…")
                await asyncio.sleep(retry + 2)
                continue
            log(f"{prefix} bulk ошибка: {err[:300]}")
            return False
    return False


async def _delayed_bulk_sync(app_id: int, payload: list, cmds, delay: float):
    await asyncio.sleep(delay + 5)
    log("[SYNC] автоповтор bulk после ожидания лимита…")
    await _bulk_put_retry(app_id, payload, cmds, label=" retry")


async def _sync_slash_commands(*, force: bool = False):
    if os.getenv("SKIP_COMMAND_SYNC", "").strip().lower() in ("1", "true", "yes"):
        log("[SYNC] пропуск (SKIP_COMMAND_SYNC=1)")
        return True, None

    force = force or os.getenv("FORCE_COMMAND_SYNC", "").strip().lower() in ("1", "true", "yes")

    cmds = _collect_guild_commands()
    n = len(cmds)
    pending = len(bot.pending_application_commands or [])
    log(f"[SYNC] команд={n} pending={pending} коги={_extension_load_ok}/{len(EXTENSIONS)} force={force}")

    if _extension_load_ok < len(EXTENSIONS):
        for line in _extension_errors[:8]:
            log(f"[SYNC]   {line}")
        if not force:
            return False, f"коги {_extension_load_ok}/{len(EXTENSIONS)} — см. journalctl"

    if n < MIN_COMMANDS_TO_SYNC and not force:
        return (
            False,
            f"в боте только {n} команд (нужно ≥{MIN_COMMANDS_TO_SYNC}). Залейте cogs/ и utils/",
        )

    # Основной способ — py-cord (не затирает список до 2 команд)
    try:
        log("[SYNC] bot.sync_commands()…")
        await bot.sync_commands(guild_ids=[GUILD_ID])
        log(f"[SYNC] OK — зарегистрировано ~{n} команд для guild {GUILD_ID}")
        return True, None
    except Exception as e:
        err = str(e)
        log(f"[SYNC] sync_commands ошибка: {err[:400]}")
        code, retry = _parse_discord_error(err)
        if code == 30034:
            return False, "лимит Discord 200 команд/сутки — не перезапускайте, ждите UTC 00:00"

    # Запасной bulk PUT (старый путь)
    app_id = bot.application_id or (bot.user.id if bot.user else None)
    if not app_id or n < 3:
        return False, "sync_commands не сработал — проверьте логи"

    try:
        payload = _sort_payload([c.to_dict() for c in cmds])
    except Exception as e:
        return False, str(e)

    if await _bulk_put_retry(app_id, payload, cmds):
        return True, None
    return False, "не удалось синхронизировать команды"


@bot.event
async def on_ready():
    log(f"[READY] {bot.user} | guild={GUILD_ID}")

    if getattr(bot, "_startup_done", False):
        return
    bot._startup_done = True

    global _extension_load_ok, _extension_errors
    if _extension_load_ok < len(EXTENSIONS):
        log("[STARTUP] повторная загрузка когов…")
        try:
            _extension_load_ok, _extension_errors = _load_extensions()
        except Exception as e:
            log(f"[STARTUP] коги: {e}")
            traceback.print_exc()

    try:
        _start_flask_once()
    except Exception as e:
        log(f"[WARN] Flask/GSI не запустился: {e}")

    log(f"[STARTUP] коги {_extension_load_ok}/{len(EXTENSIONS)}, sync в фоне (~1–2 мин)")

    async def _bg_sync():
        await asyncio.sleep(2)
        ok, err = await _sync_slash_commands()
        if ok:
            log(f"[STARTUP] sync завершён — {len(_guild_commands())} команд для guild {GUILD_ID}")
        else:
            log(f"[STARTUP] sync не удался: {err}")
            log("[STARTUP] Поставьте FORCE_COMMAND_SYNC=1 в .env и перезапустите сервис")

    asyncio.create_task(_bg_sync())


@bot.event
async def on_application_command_error(ctx: discord.ApplicationContext, error: Exception):
    log(f"[CMD ERROR] /{getattr(ctx.command, 'name', '?')}: {error}")
    traceback.print_exc()
    try:
        if ctx.interaction.response.is_done():
            await ctx.followup.send(f"Ошибка: `{error}`", ephemeral=True)
        else:
            await ctx.respond(f"Ошибка: `{error}`", ephemeral=True)
    except Exception:
        pass


if __name__ == "__main__":
    log(f"[START] bot.run()… token_len={len(BOT_TOKEN)}")
    try:
        bot.run(BOT_TOKEN)
    except discord.LoginFailure as e:
        log(f"[FATAL] Неверный BOT_TOKEN — сгенерируйте новый в Developer Portal: {e}")
        sys.exit(1)
    except Exception as e:
        log(f"[FATAL] bot.run: {e}")
        traceback.print_exc()
        sys.exit(1)
