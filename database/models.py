from __future__ import annotations

import json
from datetime import datetime, timedelta
from database.connection import get_connection

def get_tournament(tournament_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM tournaments WHERE id = ?", (tournament_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_or_create_player(discord_id: int, username: str) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO players (discord_id, username) VALUES (?, ?) ON CONFLICT(discord_id) DO UPDATE SET username=excluded.username", (discord_id, username))
    conn.commit()
    player = cursor.execute("SELECT * FROM players WHERE discord_id = ?", (discord_id,)).fetchone()
    conn.close()
    return dict(player) if player else None

def get_player(discord_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM players WHERE discord_id = ?", (discord_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def add_points(discord_id: int, points: int, is_win: bool = False, count_match: bool = True):
    """
    Начислить/списать очки.

    ВАЖНО:
    - Если это очки за матч (победа/поражение) — count_match=True (по умолчанию),
      тогда также увеличиваются wins/losses и tournaments.
    - Если это покупка в магазине, ставка, штраф, админ-выдача и т.п. — используйте count_match=False,
      чтобы НЕ портить статистику.
    """
    conn = get_connection()
    if count_match:
        if is_win:
            conn.execute(
                "UPDATE players SET points = points + ?, wins = wins + 1, tournaments = tournaments + 1 WHERE discord_id = ?",
                (points, discord_id),
            )
        else:
            conn.execute(
                "UPDATE players SET points = points + ?, losses = losses + 1, tournaments = tournaments + 1 WHERE discord_id = ?",
                (points, discord_id),
            )
    else:
        conn.execute("UPDATE players SET points = points + ? WHERE discord_id = ?", (points, discord_id))
    conn.commit()
    conn.close()


def set_points(discord_id: int, points: int):
    """Задать точное количество очков (админ-команда)."""
    conn = get_connection()
    conn.execute("UPDATE players SET points = ? WHERE discord_id = ?", (points, discord_id))
    conn.commit()
    conn.close()


def _parse_iso(dt_raw: str) -> datetime | None:
    if not dt_raw:
        return None
    try:
        # ожидаем формат datetime.isoformat()
        return datetime.fromisoformat(dt_raw)
    except Exception:
        return None


def get_last_daily_at(discord_id: int) -> datetime | None:
    conn = get_connection()
    row = conn.execute("SELECT last_daily_at FROM players WHERE discord_id = ?", (discord_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return _parse_iso(row["last_daily_at"])


def set_last_daily_at(discord_id: int, when: datetime):
    conn = get_connection()
    conn.execute("UPDATE players SET last_daily_at = ? WHERE discord_id = ?", (when.isoformat(), discord_id))
    conn.commit()
    conn.close()


def can_claim_daily(discord_id: int, cooldown_seconds: int = 24 * 60 * 60) -> tuple[bool, int]:
    """
    Возвращает (можно_ли, секунд_осталось).
    """
    last = get_last_daily_at(discord_id)
    if not last:
        return True, 0
    now = datetime.utcnow()
    passed = int((now - last).total_seconds())
    left = max(0, cooldown_seconds - passed)
    return left == 0, left


def claim_daily(discord_id: int, amount: int, cooldown_seconds: int = 24 * 60 * 60) -> tuple[bool, int]:
    """
    Пытается выдать daily.
    Возвращает (успех, секунд_осталось_до_следующего).
    """
    ok, left = can_claim_daily(discord_id, cooldown_seconds)
    if not ok:
        return False, left
    # daily — не матч, статистику не трогаем
    add_points(discord_id, amount, count_match=False)
    set_last_daily_at(discord_id, datetime.utcnow())
    return True, cooldown_seconds

def get_player_stats(discord_id: int) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT position, COUNT(*) as count FROM tournament_players WHERE discord_id = ? GROUP BY position ORDER BY count DESC LIMIT 1", (discord_id,))
    fav_pos = cursor.fetchone()
    # ВАЖНО: статистика W/L хранится в таблице players.
    # COUNT(*) по tournament_players может расходиться (например, если админ вручную правит wins/losses),
    # из‑за чего винрейт может стать > 100%. Поэтому "матчей" считаем как wins+losses.
    player = get_player(discord_id)
    total_matches = ((player or {}).get("wins") or 0) + ((player or {}).get("losses") or 0)
    conn.close()
    return {"fav_position": fav_pos["position"] if fav_pos else None, "total_matches": total_matches, "wins": player["wins"] if player else 0, "losses": player["losses"] if player else 0, "points": player["points"] if player else 0}

def _get_zxc_column(mode: str) -> str:
    if mode == "5x5":
        return "zxc_5x5"
    return "zxc_1x1"  # 1x1 и 2x2

def _get_calib_column(mode: str) -> str:
    if mode == "5x5":
        return "calibration_5x5"
    return "calibration_1x1"

RANKS_1X1 = [
    ("static", 400),
    ("null", 650),
    ("pulse", 900),
    ("vein", 1075),
    ("echo", 1225),
    ("haze", 1400),
    ("vanta", 1650),
    ("abyss", 1950),
    ("phantom", 2300),
    ("eclipse", 2700),
]

RANKS_5X5 = [
    ("мусор", 400),
    ("бронза", 650),
    ("серебро", 900),
    ("золото", 1075),
    ("платина", 1225),
    ("алмаз", 1400),
    ("мастер", 1650),
    ("элита", 1950),
    ("легенда", 2300),
    ("титан", 2700),
]


def rating_for_rank(rank_name: str, mode: str = "5x5") -> int | None:
    """Средний рейтинг внутри тира по названию ранга."""
    key = (rank_name or "").strip().lower()
    table = RANKS_1X1 if mode == "1x1" else RANKS_5X5
    for name, rating in table:
        if name == key or key in name or name in key:
            return rating
    return None


def list_rank_names(mode: str = "5x5") -> list[str]:
    table = RANKS_1X1 if mode == "1x1" else RANKS_5X5
    return [name.title() if mode == "1x1" else name.capitalize() for name, _ in table]


def get_rank_name(rating: int, mode: str = "5x5") -> str:
    if mode == "1x1":
        if rating < 500: return "Static"
        elif rating < 800: return "Null"
        elif rating < 1000: return "Pulse"
        elif rating < 1150: return "Vein"
        elif rating < 1300: return "Echo"
        elif rating < 1500: return "Haze"
        elif rating < 1800: return "Vanta"
        elif rating < 2100: return "Abyss"
        elif rating < 2500: return "Phantom"
        else: return "Eclipse"
    else:
        if rating < 500: return "Мусор"
        elif rating < 800: return "Бронза"
        elif rating < 1000: return "Серебро"
        elif rating < 1150: return "Золото"
        elif rating < 1300: return "Платина"
        elif rating < 1500: return "Алмаз"
        elif rating < 1800: return "Мастер"
        elif rating < 2100: return "Элита"
        elif rating < 2500: return "Легенда"
        else: return "Титан"

def get_rank_emoji(rating: int, calib: int = 5, mode: str = "5x5") -> str:
    from config import EMOJI_CALIBRATION, EMOJI_STATIC, EMOJI_NULL, EMOJI_PULSE, EMOJI_VEIN, EMOJI_ECHO, EMOJI_HAZE, EMOJI_VANTA, EMOJI_ABYSS, EMOJI_PHANTOM, EMOJI_ECLIPSE
    if calib < 5:
        return EMOJI_CALIBRATION
    if mode == "1x1":
        if rating < 500: return EMOJI_STATIC
        elif rating < 800: return EMOJI_NULL
        elif rating < 1000: return EMOJI_PULSE
        elif rating < 1150: return EMOJI_VEIN
        elif rating < 1300: return EMOJI_ECHO
        elif rating < 1500: return EMOJI_HAZE
        elif rating < 1800: return EMOJI_VANTA
        elif rating < 2100: return EMOJI_ABYSS
        elif rating < 2500: return EMOJI_PHANTOM
        else: return EMOJI_ECLIPSE
    else:
        if rating < 500: return "<:no:1503121885674868938>"
        elif rating < 800: return "🥉"
        elif rating < 1000: return "🥈"
        elif rating < 1150: return "🥇"
        elif rating < 1300: return "💎"
        elif rating < 1500: return "👑"
        elif rating < 1800: return "🔥"
        elif rating < 2100: return "⚡"
        elif rating < 2500: return "🌟"
        else: return "👑"

def get_zxc_rating(discord_id: int, mode: str = "5x5") -> tuple:
    conn = get_connection()
    zxc_col = _get_zxc_column(mode)
    calib_col = _get_calib_column(mode)
    row = conn.execute(f"SELECT {zxc_col}, {calib_col} FROM players WHERE discord_id = ?", (discord_id,)).fetchone()
    conn.close()
    if not row:
        return 0, "Новичок", "🔰"
    rating = row[zxc_col] or 1000
    calib = row[calib_col] or 0
    if calib < 5:
        return rating, f"Калибровка ({calib}/5)", get_rank_emoji(rating, calib, mode)
    return rating, get_rank_name(rating, mode), get_rank_emoji(rating, calib, mode)

def get_player_kda(discord_id: int) -> tuple:
    conn = get_connection()
    row = conn.execute("SELECT total_kills, total_deaths, total_assists FROM players WHERE discord_id = ?", (discord_id,)).fetchone()
    conn.close()
    if row:
        return row["total_kills"] or 0, row["total_deaths"] or 0, row["total_assists"] or 0
    return 0, 0, 0

def is_calibrated(discord_id: int, mode: str = "5x5") -> bool:
    conn = get_connection()
    calib_col = _get_calib_column(mode)
    row = conn.execute(f"SELECT {calib_col} FROM players WHERE discord_id = ?", (discord_id,)).fetchone()
    conn.close()
    return row and (row[calib_col] or 0) >= 5

def get_team_avg_zxc(team: list, mode: str = "5x5") -> int:
    if not team:
        return 1000
    col = _get_zxc_column(mode)
    conn = get_connection()
    total = 0
    for uid in team:
        row = conn.execute(f"SELECT {col} FROM players WHERE discord_id = ?", (uid,)).fetchone()
        total += row[col] if row and row[col] else 1000
    conn.close()
    return total // len(team)

def update_zxc_calibration(discord_id: int, kills: int, deaths: int, assists: int, won: bool, mode: str = "5x5", last_hits: int = 0, denies: int = 0):
    conn = get_connection()
    zxc_col = _get_zxc_column(mode)
    calib_col = _get_calib_column(mode)
    player = conn.execute(f"SELECT {zxc_col}, {calib_col}, total_kills, total_deaths, total_assists FROM players WHERE discord_id = ?", (discord_id,)).fetchone()
    if not player:
        conn.close()
        return 1000
    calib = (player[calib_col] or 0) + 1
    total_k = (player["total_kills"] or 0) + kills
    total_d = (player["total_deaths"] or 0) + deaths
    total_a = (player["total_assists"] or 0) + assists
    if mode == "1x1":
        cs_score = (last_hits * 15) + (denies * 10)
        kda_score = (kills * 25) - (deaths * 20)
        performance = cs_score + kda_score
        win_bonus = 150 if won else -100
        match_rating = 1000 + performance + win_bonus
    else:
        kda_score = (kills * 30) + (assists * 15) - (deaths * 20)
        win_bonus = 150 if won else -100
        match_rating = 1000 + kda_score + win_bonus
    match_rating = max(0, min(3000, match_rating))
    if calib == 1:
        new_rating = match_rating
    else:
        old_rating = player[zxc_col] or 1000
        new_rating = int(old_rating + (match_rating - old_rating) / calib)
    conn.execute(f"UPDATE players SET {zxc_col} = ?, {calib_col} = ?, total_kills = ?, total_deaths = ?, total_assists = ? WHERE discord_id = ?", (new_rating, calib, total_k, total_d, total_a, discord_id))
    conn.commit()
    conn.close()
    return new_rating

def update_zxc_after_calibration(
    discord_id: int,
    kills: int,
    deaths: int,
    assists: int,
    won: bool,
    avg_team_zxc: int,
    avg_enemy_zxc: int,
    mode: str = "5x5",
) -> int:
    """
    Обновление рейтинга после калибровки.
    Модель упрощённая (Elo-подобная) + небольшой бонус за KDA.
    """
    conn = get_connection()
    zxc_col = _get_zxc_column(mode)

    row = conn.execute(
        f"SELECT {zxc_col}, total_kills, total_deaths, total_assists FROM players WHERE discord_id = ?",
        (discord_id,),
    ).fetchone()
    if not row:
        conn.close()
        return 1000

    old_rating = row[zxc_col] or 1000

    # КДА-оценка (грубая) — влияет умеренно
    kda_score = (kills * 30) + (assists * 15) - (deaths * 20)

    # Elo-ожидание относительно средних рейтингов команд
    try:
        expected = 1 / (1 + 10 ** ((avg_enemy_zxc - avg_team_zxc) / 400))
    except Exception:
        expected = 0.5

    result = 1.0 if won else 0.0
    base_k = 30  # базовая скорость изменения рейтинга
    delta = int(base_k * (result - expected) + (kda_score / 120))
    delta = max(-60, min(60, delta))

    new_rating = max(0, min(3000, int(old_rating + delta)))

    # Обновляем суммарный K/D/A, чтобы /profile мог показывать статистику после калибровки тоже
    total_k = (row["total_kills"] or 0) + kills
    total_d = (row["total_deaths"] or 0) + deaths
    total_a = (row["total_assists"] or 0) + assists

    conn.execute(
        f"UPDATE players SET {zxc_col} = ?, total_kills = ?, total_deaths = ?, total_assists = ? WHERE discord_id = ?",
        (new_rating, total_k, total_d, total_a, discord_id),
    )
    conn.commit()
    conn.close()
    return new_rating

def save_match_duration(tournament_id: int, duration: int):
    conn = get_connection()
    conn.execute("INSERT INTO matches (tournament_id, duration) VALUES (?, ?)", (tournament_id, duration))
    conn.commit()
    conn.close()

def add_shop_item(item_type: str, name: str, price: int, description: str = None, role_id: int = None) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO shop_items (type, name, description, role_id, price) VALUES (?, ?, ?, ?, ?)", (item_type, name, description, role_id, price))
    conn.commit()
    item_id = cursor.lastrowid
    conn.close()
    return item_id

def get_shop_items(item_type: str = None) -> list[dict]:
    conn = get_connection()
    if item_type:
        rows = conn.execute("SELECT * FROM shop_items WHERE type = ? AND is_active = 1", (item_type,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM shop_items WHERE is_active = 1").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_shop_item(item_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM shop_items WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def delete_shop_item(item_id: int):
    conn = get_connection()
    conn.execute("UPDATE shop_items SET is_active = 0 WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

def add_player_role(discord_id: int, role_id: int, role_name: str):
    conn = get_connection()
    conn.execute("INSERT INTO player_roles (discord_id, role_id, role_name) VALUES (?, ?, ?)", (discord_id, role_id, role_name))
    conn.commit()
    conn.close()

def get_player_roles(discord_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM player_roles WHERE discord_id = ?", (discord_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def has_player_role(discord_id: int, role_id: int) -> bool:
    conn = get_connection()
    row = conn.execute("SELECT 1 FROM player_roles WHERE discord_id = ? AND role_id = ?", (discord_id, role_id)).fetchone()
    conn.close()
    return row is not None

def create_request(discord_id: int, item_id: int, request_text: str = None) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO reward_requests (discord_id, item_id, request_text) VALUES (?, ?, ?)", (discord_id, item_id, request_text))
    conn.commit()
    req_id = cursor.lastrowid
    conn.close()
    return req_id

def get_pending_requests() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT rr.*, si.name as item_name, si.type as item_type, p.username FROM reward_requests rr JOIN shop_items si ON rr.item_id = si.id JOIN players p ON rr.discord_id = p.discord_id WHERE rr.status = 'pending' ORDER BY rr.created_at ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def resolve_request(request_id: int, status: str, admin_response: str = None):
    conn = get_connection()
    conn.execute("UPDATE reward_requests SET status = ?, admin_response = ?, resolved_at = ? WHERE id = ?", (status, admin_response, datetime.utcnow(), request_id))
    conn.commit()
    conn.close()

def create_tournament(match_id: str, lobby_name: str, lobby_password: str, created_by: int) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tournaments (match_id, lobby_name, lobby_password, created_by) VALUES (?, ?, ?, ?)", (match_id, lobby_name, lobby_password, created_by))
    conn.commit()
    tour_id = cursor.lastrowid
    conn.close()
    return tour_id

def get_active_tournament() -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM tournaments WHERE status IN ('gathering', 'in_progress') ORDER BY created_at DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None

def set_tournament_teams(tournament_id: int, team_radiant: list, team_dire: list):
    conn = get_connection()
    conn.execute("UPDATE tournaments SET team_radiant = ?, team_dire = ?, status = 'in_progress' WHERE id = ?", (json.dumps(team_radiant), json.dumps(team_dire), tournament_id))
    conn.commit()
    conn.close()

def add_tournament_player(tournament_id: int, discord_id: int, team: str, position: int):
    conn = get_connection()
    conn.execute("INSERT INTO tournament_players (tournament_id, discord_id, team, position) VALUES (?, ?, ?, ?)", (tournament_id, discord_id, team, position))
    conn.commit()
    conn.close()

def set_tournament_winner(tournament_id: int, winner: str):
    conn = get_connection()
    conn.execute("UPDATE tournaments SET winner = ?, status = 'finished', finished_at = ? WHERE id = ?", (winner, datetime.utcnow(), tournament_id))
    conn.commit()
    conn.close()

def cancel_tournament(tournament_id: int, reason: str | None = None):
    conn = get_connection()
    if reason:
        conn.execute(
            "UPDATE tournaments SET status = 'cancelled', cancel_reason = ? WHERE id = ?",
            (reason, tournament_id),
        )
    else:
        conn.execute("UPDATE tournaments SET status = 'cancelled' WHERE id = ?", (tournament_id,))
    conn.commit()
    conn.close()


def annul_tournament(tournament_id: int, reason: str, cheat_flags: str | None = None):
    """Аннулировать матч без победителя (очки не начислялись)."""
    conn = get_connection()
    conn.execute(
        "UPDATE tournaments SET status = 'cancelled', winner = NULL, cancel_reason = ?, cheat_flags = ?, finished_at = ? WHERE id = ?",
        (reason, cheat_flags, datetime.utcnow(), tournament_id),
    )
    conn.commit()
    conn.close()


def set_dota_name(discord_id: int, dota_name: str):
    conn = get_connection()
    conn.execute("UPDATE players SET dota_name = ? WHERE discord_id = ?", (dota_name.strip(), discord_id))
    conn.commit()
    conn.close()


def get_dota_name(discord_id: int) -> str | None:
    conn = get_connection()
    row = conn.execute("SELECT dota_name FROM players WHERE discord_id = ?", (discord_id,)).fetchone()
    conn.close()
    if row and row["dota_name"]:
        return row["dota_name"]
    return None


def build_name_map(discord_ids: list[int], username_fallback: dict[int, str]) -> dict[int, str]:
    """discord_id -> имя для сопоставления с GSI."""
    result = {}
    for uid in discord_ids:
        dn = get_dota_name(uid)
        result[uid] = dn or username_fallback.get(uid) or str(uid)
    return result


def save_match_player_logs(tournament_id: int, rows: list[dict]):
    conn = get_connection()
    for r in rows:
        conn.execute(
            """INSERT INTO match_player_logs
               (tournament_id, discord_id, dota_name, team, kills, deaths, assists, last_hits, denies, networth, hero, flags)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                tournament_id,
                r.get("discord_id"),
                r.get("dota_name"),
                r.get("team"),
                r.get("kills", 0),
                r.get("deaths", 0),
                r.get("assists", 0),
                r.get("last_hits", 0),
                r.get("denies", 0),
                r.get("networth", 0),
                r.get("hero"),
                r.get("flags"),
            ),
        )
    conn.commit()
    conn.close()


def update_win_streak(discord_id: int, won: bool) -> int:
    conn = get_connection()
    row = conn.execute(
        "SELECT win_streak, best_win_streak FROM players WHERE discord_id = ?", (discord_id,)
    ).fetchone()
    if not row:
        conn.close()
        return 0
    streak = row["win_streak"] or 0
    best = row["best_win_streak"] or 0
    if won:
        streak += 1
        best = max(best, streak)
    else:
        streak = 0
    conn.execute(
        "UPDATE players SET win_streak = ?, best_win_streak = ? WHERE discord_id = ?",
        (streak, best, discord_id),
    )
    conn.commit()
    conn.close()
    return streak


def get_win_streak_info(discord_id: int) -> tuple[int, int]:
    conn = get_connection()
    row = conn.execute(
        "SELECT win_streak, best_win_streak FROM players WHERE discord_id = ?", (discord_id,)
    ).fetchone()
    conn.close()
    if not row:
        return 0, 0
    return row["win_streak"] or 0, row["best_win_streak"] or 0


def get_last_match_log_for_player(discord_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        """SELECT mpl.*, t.id as tid FROM match_player_logs mpl
           JOIN tournaments t ON t.id = mpl.tournament_id
           WHERE mpl.discord_id = ? ORDER BY mpl.id DESC LIMIT 1""",
        (discord_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def refund_bets_for_tournament(tournament_id: int, bets: dict) -> None:
    """Вернуть ставки при аннулировании (bets: {uid: {team, amount}})."""
    for uid, bet in bets.items():
        add_points(uid, bet["amount"], count_match=False)


def void_tournament(tournament_id: int, reason: str):
    """Аннулировать матч (status=cancelled + void_reason, совместимо со схемой БД)."""
    conn = get_connection()
    conn.execute(
        "UPDATE tournaments SET status = 'cancelled', winner = NULL, void_reason = ?, cancel_reason = ?, finished_at = ? WHERE id = ?",
        (reason, reason, datetime.utcnow(), tournament_id),
    )
    conn.commit()
    conn.close()


def set_player_dota_name(discord_id: int, dota_name: str):
    conn = get_connection()
    conn.execute(
        "UPDATE players SET dota_name = ? WHERE discord_id = ?",
        (dota_name.strip(), discord_id),
    )
    conn.commit()
    conn.close()


def set_player_steam_link(discord_id: int, steam_id64: str, dota_name: str):
    conn = get_connection()
    conn.execute(
        "UPDATE players SET steam_id = ?, dota_name = ? WHERE discord_id = ?",
        (str(steam_id64).strip(), dota_name.strip(), discord_id),
    )
    conn.commit()
    conn.close()


def get_player_steam_id(discord_id: int) -> str | None:
    conn = get_connection()
    row = conn.execute("SELECT steam_id FROM players WHERE discord_id = ?", (discord_id,)).fetchone()
    conn.close()
    if row and row["steam_id"]:
        return str(row["steam_id"])
    return None


def get_discord_id_by_steam_id(steam_id64: str) -> int | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT discord_id FROM players WHERE steam_id = ?",
        (str(steam_id64).strip(),),
    ).fetchone()
    conn.close()
    return int(row["discord_id"]) if row else None


def get_player_dota_name(discord_id: int) -> str | None:
    conn = get_connection()
    row = conn.execute("SELECT dota_name FROM players WHERE discord_id = ?", (discord_id,)).fetchone()
    conn.close()
    if row and row["dota_name"]:
        return row["dota_name"]
    return None


def learn_dota_name(discord_id: int, dota_name: str):
    if not dota_name or not dota_name.strip():
        return
    conn = get_connection()
    row = conn.execute("SELECT dota_name FROM players WHERE discord_id = ?", (discord_id,)).fetchone()
    if row and not row["dota_name"]:
        conn.execute("UPDATE players SET dota_name = ? WHERE discord_id = ?", (dota_name.strip(), discord_id))
        conn.commit()
    conn.close()


def get_registered_name_set(team: list[int]) -> set[str]:
    names = set()
    conn = get_connection()
    for uid in team:
        row = conn.execute("SELECT dota_name, username FROM players WHERE discord_id = ?", (uid,)).fetchone()
        if row:
            if row["dota_name"]:
                names.add(row["dota_name"].lower())
            if row["username"]:
                names.add(row["username"].lower())
    conn.close()
    return names


def resolve_stats_to_discord(player_stats: dict, team: list[int]) -> dict[int, dict]:
    """Сопоставить GSI-ник / account_id → discord_id."""
    from utils.steam import steam_id64_to_account_id

    result: dict[int, dict] = {}
    conn = get_connection()
    for uid in team:
        row = conn.execute(
            "SELECT dota_name, username, steam_id FROM players WHERE discord_id = ?",
            (uid,),
        ).fetchone()
        if not row:
            continue
        keys = {str(uid)}
        if row["dota_name"]:
            keys.add(row["dota_name"].lower())
        if row["username"]:
            keys.add(row["username"].lower())
        account_keys: set[str] = set()
        if row["steam_id"]:
            try:
                account_keys.add(str(steam_id64_to_account_id(row["steam_id"])))
            except (TypeError, ValueError):
                pass
        for gsi_name, stats in player_stats.items():
            gsi_account = stats.get("account_id") if isinstance(stats, dict) else None
            if gsi_account is not None and account_keys and str(gsi_account) in account_keys:
                result[uid] = stats
                break
            if gsi_name.lower() in keys or gsi_name == str(uid):
                result[uid] = stats
                break
    conn.close()
    return result


def save_tournament_player_stats(
    tournament_id: int,
    discord_id: int,
    stats: dict,
    *,
    hero: str | None = None,
    dota_name: str | None = None,
):
    conn = get_connection()
    conn.execute(
        """UPDATE tournament_players SET
            kills = ?, deaths = ?, assists = ?, last_hits = ?, denies = ?,
            net_worth = ?, hero = ?, dota_name = ?
        WHERE tournament_id = ? AND discord_id = ?""",
        (
            stats.get("kills", 0),
            stats.get("deaths", 0),
            stats.get("assists", 0),
            stats.get("last_hits", 0),
            stats.get("denies", 0),
            stats.get("net_worth", 0),
            hero,
            dota_name,
            tournament_id,
            discord_id,
        ),
    )
    conn.commit()
    conn.close()


def get_win_streak(discord_id: int) -> int:
    conn = get_connection()
    row = conn.execute("SELECT win_streak FROM players WHERE discord_id = ?", (discord_id,)).fetchone()
    conn.close()
    return row["win_streak"] if row and row["win_streak"] else 0


def set_win_streak(discord_id: int, streak: int):
    conn = get_connection()
    conn.execute("UPDATE players SET win_streak = ? WHERE discord_id = ?", (max(0, streak), discord_id))
    conn.commit()
    conn.close()


def refund_bet(discord_id: int, amount: int):
    add_points(discord_id, amount, count_match=False)


# --- Админ: ручное управление данными ---

_PLAYER_ADMIN_FIELDS = {
    "points", "wins", "losses", "tournaments",
    "zxc_5x5", "zxc_1x1", "calibration_5x5", "calibration_1x1",
    "total_kills", "total_deaths", "total_assists",
    "win_streak", "best_win_streak", "dota_name", "steam_id", "username",
}


def get_player_full(discord_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM players WHERE discord_id = ?", (discord_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def admin_update_player(discord_id: int, **fields) -> bool:
    clean = {k: v for k, v in fields.items() if k in _PLAYER_ADMIN_FIELDS and v is not None}
    if not clean:
        return False
    conn = get_connection()
    sets = ", ".join(f"{k} = ?" for k in clean)
    conn.execute(f"UPDATE players SET {sets} WHERE discord_id = ?", (*clean.values(), discord_id))
    conn.commit()
    conn.close()
    return True


def admin_set_calibration(discord_id: int, mode: str, value: int):
    col = _get_calib_column(mode)
    value = max(0, min(5, int(value)))
    conn = get_connection()
    conn.execute(f"UPDATE players SET {col} = ? WHERE discord_id = ?", (value, discord_id))
    conn.commit()
    conn.close()


def admin_reset_calibration(discord_id: int, mode: str | None = None):
    conn = get_connection()
    if mode in (None, "both", "all"):
        conn.execute(
            "UPDATE players SET calibration_5x5 = 0, calibration_1x1 = 0 WHERE discord_id = ?",
            (discord_id,),
        )
    elif mode == "5x5":
        conn.execute("UPDATE players SET calibration_5x5 = 0 WHERE discord_id = ?", (discord_id,))
    elif mode == "1x1":
        conn.execute("UPDATE players SET calibration_1x1 = 0 WHERE discord_id = ?", (discord_id,))
    conn.commit()
    conn.close()


def admin_finish_calibration(discord_id: int, mode: str):
    admin_set_calibration(discord_id, mode, 5)


def admin_add_win_loss(discord_id: int, wins: int = 0, losses: int = 0, tournaments: int = 0):
    conn = get_connection()
    conn.execute(
        """UPDATE players SET
           wins = MAX(0, wins + ?),
           losses = MAX(0, losses + ?),
           tournaments = MAX(0, tournaments + ?)
           WHERE discord_id = ?""",
        (wins, losses, tournaments, discord_id),
    )
    conn.commit()
    conn.close()


def admin_reset_player_stats(discord_id: int, *, keep_points: bool = True):
    conn = get_connection()
    if keep_points:
        conn.execute(
            """UPDATE players SET
               wins=0, losses=0, tournaments=0,
               zxc_5x5=1000, zxc_1x1=1000,
               calibration_5x5=0, calibration_1x1=0,
               total_kills=0, total_deaths=0, total_assists=0,
               win_streak=0, best_win_streak=0, last_daily_at=NULL
               WHERE discord_id = ?""",
            (discord_id,),
        )
    else:
        conn.execute(
            """UPDATE players SET
               points=0, wins=0, losses=0, tournaments=0,
               zxc_5x5=1000, zxc_1x1=1000,
               calibration_5x5=0, calibration_1x1=0,
               total_kills=0, total_deaths=0, total_assists=0,
               win_streak=0, best_win_streak=0, last_daily_at=NULL
               WHERE discord_id = ?""",
            (discord_id,),
        )
    conn.commit()
    conn.close()


def admin_delete_player(discord_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM match_player_logs WHERE discord_id = ?", (discord_id,))
    conn.execute("DELETE FROM tournament_players WHERE discord_id = ?", (discord_id,))
    conn.execute("DELETE FROM player_roles WHERE discord_id = ?", (discord_id,))
    conn.execute("DELETE FROM reward_requests WHERE discord_id = ?", (discord_id,))
    conn.execute("DELETE FROM clan_members WHERE discord_id = ?", (discord_id,))
    conn.execute("DELETE FROM players WHERE discord_id = ?", (discord_id,))
    conn.commit()
    conn.close()


def admin_delete_tournament(tournament_id: int) -> bool:
    conn = get_connection()
    cur = conn.execute("SELECT id FROM tournaments WHERE id = ?", (tournament_id,)).fetchone()
    if not cur:
        conn.close()
        return False
    conn.execute("DELETE FROM match_player_logs WHERE tournament_id = ?", (tournament_id,))
    conn.execute("DELETE FROM tournament_players WHERE tournament_id = ?", (tournament_id,))
    conn.execute("DELETE FROM matches WHERE tournament_id = ?", (tournament_id,))
    conn.execute("DELETE FROM tournaments WHERE id = ?", (tournament_id,))
    conn.commit()
    conn.close()
    return True


def admin_clear_match_logs(limit: int | None = None) -> int:
    conn = get_connection()
    if limit:
        rows = conn.execute(
            "SELECT id FROM match_player_logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        if rows:
            ids = [r[0] for r in rows]
            placeholders = ",".join("?" * len(ids))
            cur = conn.execute(f"DELETE FROM match_player_logs WHERE id IN ({placeholders})", ids)
        else:
            cur = conn.execute("DELETE FROM match_player_logs WHERE 0")
    else:
        cur = conn.execute("DELETE FROM match_player_logs")
    n = cur.rowcount
    conn.commit()
    conn.close()
    return n


def admin_clear_all_tournaments() -> int:
    conn = get_connection()
    conn.execute("DELETE FROM match_player_logs")
    conn.execute("DELETE FROM matches")
    conn.execute("DELETE FROM tournament_players")
    cur = conn.execute("DELETE FROM tournaments")
    n = cur.rowcount
    conn.commit()
    conn.close()
    return n


def admin_list_tournaments(limit: int = 10) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, status, winner, created_at, finished_at, void_reason, cancel_reason FROM tournaments ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def export_player_snapshot(discord_id: int) -> dict | None:
    p = get_player_full(discord_id)
    if not p:
        return None
    keys = [
        "discord_id", "username", "points", "wins", "losses", "tournaments",
        "zxc_5x5", "zxc_1x1", "calibration_5x5", "calibration_1x1",
        "total_kills", "total_deaths", "total_assists",
        "win_streak", "best_win_streak", "dota_name", "steam_id",
    ]
    return {k: p.get(k) for k in keys if k in p}


def import_player_snapshot(data: dict) -> bool:
    discord_id = int(data["discord_id"])
    username = str(data.get("username") or "unknown")
    get_or_create_player(discord_id, username)
    fields = {k: data[k] for k in _PLAYER_ADMIN_FIELDS if k in data and k != "username"}
    if "username" in data:
        fields["username"] = username
    admin_update_player(discord_id, **fields)
    return True


# --- Кланы: казна, уровни, матчи ---

class ClanError(Exception):
    pass


_CLAN_TREASURY_ROLES = frozenset({"офицер", "казначей", "officer", "treasurer"})


def clan_level_from_xp(xp: int, base: int = 500) -> int:
    return max(1, 1 + int(xp) // max(base, 1))


def _clan_recalc_level(conn, clan_id: int, xp: int, base: int):
    lvl = clan_level_from_xp(xp, base)
    conn.execute("UPDATE clans SET level = ? WHERE id = ?", (lvl, clan_id))


def get_clan_membership(discord_id: int) -> dict | None:
    """Клан игрока + роль в клане."""
    conn = get_connection()
    row = conn.execute(
        """
        SELECT c.*, cm.role AS member_role
        FROM clans c
        JOIN clan_members cm ON c.id = cm.clan_id
        WHERE cm.discord_id = ?
        """,
        (discord_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def clan_can_manage_treasury(clan: dict, discord_id: int, member_role: str | None) -> bool:
    if clan.get("owner_id") == discord_id:
        return True
    role = (member_role or "").strip().lower()
    return role in _CLAN_TREASURY_ROLES


def _clan_log(conn, clan_id: int, actor_id: int | None, amount: int, reason: str):
    conn.execute(
        "INSERT INTO clan_treasury_log (clan_id, actor_id, amount, reason) VALUES (?, ?, ?, ?)",
        (clan_id, actor_id, amount, reason),
    )


def get_clan_treasury_log(clan_id: int, limit: int = 8) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT actor_id, amount, reason, created_at
        FROM clan_treasury_log
        WHERE clan_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (clan_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def clan_deposit(discord_id: int, amount: int, *, xp_base: int = 500, xp_per_100: int = 15) -> dict:
    if amount <= 0:
        raise ClanError("Сумма должна быть больше 0.")
    clan = get_clan_membership(discord_id)
    if not clan:
        raise ClanError("Вы не в клане.")
    conn = get_connection()
    row = conn.execute("SELECT points FROM players WHERE discord_id = ?", (discord_id,)).fetchone()
    if not row or row["points"] < amount:
        conn.close()
        raise ClanError("Недостаточно личных очков.")
    conn.execute("UPDATE players SET points = points - ? WHERE discord_id = ?", (amount, discord_id))
    conn.execute("UPDATE clans SET treasury = treasury + ? WHERE id = ?", (amount, clan["id"]))
    xp_gain = (amount // 100) * xp_per_100
    if xp_gain:
        conn.execute("UPDATE clans SET xp = xp + ? WHERE id = ?", (xp_gain, clan["id"]))
        new_xp = conn.execute("SELECT xp FROM clans WHERE id = ?", (clan["id"],)).fetchone()["xp"]
        _clan_recalc_level(conn, clan["id"], new_xp, xp_base)
    _clan_log(conn, clan["id"], discord_id, amount, "deposit")
    conn.commit()
    treasury = conn.execute("SELECT treasury, xp, level FROM clans WHERE id = ?", (clan["id"],)).fetchone()
    conn.close()
    return {"treasury": treasury["treasury"], "xp": treasury["xp"], "level": treasury["level"]}


def clan_withdraw(discord_id: int, amount: int) -> dict:
    if amount <= 0:
        raise ClanError("Сумма должна быть больше 0.")
    clan = get_clan_membership(discord_id)
    if not clan:
        raise ClanError("Вы не в клане.")
    if not clan_can_manage_treasury(clan, discord_id, clan.get("member_role")):
        raise ClanError("Снимать из казны могут владелец, Офицер или Казначей.")
    conn = get_connection()
    row = conn.execute("SELECT treasury FROM clans WHERE id = ?", (clan["id"],)).fetchone()
    if not row or row["treasury"] < amount:
        conn.close()
        raise ClanError("В казне недостаточно очков.")
    conn.execute("UPDATE clans SET treasury = treasury - ? WHERE id = ?", (amount, clan["id"]))
    conn.execute("UPDATE players SET points = points + ? WHERE discord_id = ?", (amount, discord_id))
    _clan_log(conn, clan["id"], discord_id, -amount, "withdraw")
    conn.commit()
    treasury = conn.execute("SELECT treasury FROM clans WHERE id = ?", (clan["id"],)).fetchone()["treasury"]
    conn.close()
    return {"treasury": treasury}


def clan_pay_member(actor_id: int, target_id: int, amount: int) -> dict:
    if amount <= 0:
        raise ClanError("Сумма должна быть больше 0.")
    if actor_id == target_id:
        raise ClanError("Нельзя выплатить самому себе — используйте /clan_withdraw.")
    clan = get_clan_membership(actor_id)
    if not clan:
        raise ClanError("Вы не в клане.")
    if clan["owner_id"] != actor_id:
        raise ClanError("Выплаты из казны — только владелец клана.")
    conn = get_connection()
    in_clan = conn.execute(
        "SELECT 1 FROM clan_members WHERE clan_id = ? AND discord_id = ?",
        (clan["id"], target_id),
    ).fetchone()
    if not in_clan:
        conn.close()
        raise ClanError("Игрок не в вашем клане.")
    row = conn.execute("SELECT treasury FROM clans WHERE id = ?", (clan["id"],)).fetchone()
    if not row or row["treasury"] < amount:
        conn.close()
        raise ClanError("В казне недостаточно очков.")
    conn.execute("UPDATE clans SET treasury = treasury - ? WHERE id = ?", (amount, clan["id"]))
    get_or_create_player(target_id, str(target_id))
    conn.execute("UPDATE players SET points = points + ? WHERE discord_id = ?", (amount, target_id))
    _clan_log(conn, clan["id"], actor_id, -amount, f"pay:{target_id}")
    conn.commit()
    treasury = conn.execute("SELECT treasury FROM clans WHERE id = ?", (clan["id"],)).fetchone()["treasury"]
    conn.close()
    return {"treasury": treasury}


def clan_transfer_ownership(owner_id: int, new_owner_id: int) -> None:
    clan = get_clan_membership(owner_id)
    if not clan:
        raise ClanError("Вы не в клане.")
    if clan["owner_id"] != owner_id:
        raise ClanError("Только владелец может передать клан.")
    conn = get_connection()
    check = conn.execute(
        "SELECT 1 FROM clan_members WHERE clan_id = ? AND discord_id = ?",
        (clan["id"], new_owner_id),
    ).fetchone()
    if not check:
        conn.close()
        raise ClanError("Новый владелец должен быть в клане.")
    conn.execute("UPDATE clans SET owner_id = ? WHERE id = ?", (new_owner_id, clan["id"]))
    conn.execute(
        "UPDATE clan_members SET role = 'Участник' WHERE clan_id = ? AND discord_id = ?",
        (clan["id"], owner_id),
    )
    conn.execute(
        "UPDATE clan_members SET role = 'Владелец' WHERE clan_id = ? AND discord_id = ?",
        (clan["id"], new_owner_id),
    )
    conn.commit()
    conn.close()


def clan_set_member_role(actor_id: int, target_id: int, role: str) -> None:
    clan = get_clan_membership(actor_id)
    if not clan or clan["owner_id"] != actor_id:
        raise ClanError("Только владелец может менять роли.")
    conn = get_connection()
    ok = conn.execute(
        "SELECT 1 FROM clan_members WHERE clan_id = ? AND discord_id = ?",
        (clan["id"], target_id),
    ).fetchone()
    if not ok:
        conn.close()
        raise ClanError("Игрок не в клане.")
    conn.execute(
        "UPDATE clan_members SET role = ? WHERE clan_id = ? AND discord_id = ?",
        (role.strip()[:30], clan["id"], target_id),
    )
    conn.commit()
    conn.close()


def process_clan_match_result(
    winner_ids: list[int],
    loser_ids: list[int],
    *,
    treasury_bonus: int = 25,
    min_members: int = 2,
    xp_gain: int = 40,
) -> list[dict]:
    """Бонус казне и W/L кланам, если на команде 2+ игроков одного клана."""
    from collections import defaultdict

    def _group(ids: list[int]) -> dict[int, list[int]]:
        out: dict[int, list[int]] = defaultdict(list)
        conn = get_connection()
        for uid in ids:
            row = conn.execute(
                "SELECT clan_id FROM clan_members WHERE discord_id = ?",
                (uid,),
            ).fetchone()
            if row:
                out[int(row["clan_id"])].append(uid)
        conn.close()
        return out

    results: list[dict] = []
    conn = get_connection()

    for clan_id, members in _group(winner_ids).items():
        if len(members) < min_members:
            continue
        conn.execute(
            "UPDATE clans SET wins = wins + 1, treasury = treasury + ?, xp = xp + ? WHERE id = ?",
            (treasury_bonus, xp_gain, clan_id),
        )
        _clan_log(conn, clan_id, None, treasury_bonus, "match_win")
        row = conn.execute("SELECT xp, tag, name FROM clans WHERE id = ?", (clan_id,)).fetchone()
        if row:
            _clan_recalc_level(conn, clan_id, row["xp"], 500)
            results.append(
                {
                    "clan_id": clan_id,
                    "tag": row["tag"],
                    "name": row["name"],
                    "members": len(members),
                    "treasury_bonus": treasury_bonus,
                    "win": True,
                }
            )

    for clan_id, members in _group(loser_ids).items():
        if len(members) < min_members:
            continue
        conn.execute("UPDATE clans SET losses = losses + 1 WHERE id = ?", (clan_id,))
        lrow = conn.execute("SELECT tag, name FROM clans WHERE id = ?", (clan_id,)).fetchone()
        results.append(
            {
                "clan_id": clan_id,
                "tag": lrow["tag"] if lrow else "?",
                "name": lrow["name"] if lrow else "?",
                "win": False,
                "members": len(members),
            }
        )

    conn.commit()
    conn.close()
    return results


def _seconds_until_claim(last_at: datetime | None, cooldown_seconds: int) -> tuple[bool, int]:
    if not last_at:
        return True, 0
    passed = int((datetime.utcnow() - last_at).total_seconds())
    left = max(0, cooldown_seconds - passed)
    return left == 0, left


def can_claim_weekly(discord_id: int, cooldown_seconds: int = 7 * 24 * 3600) -> tuple[bool, int]:
    conn = get_connection()
    row = conn.execute("SELECT last_weekly_at FROM players WHERE discord_id = ?", (discord_id,)).fetchone()
    conn.close()
    return _seconds_until_claim(_parse_iso(row["last_weekly_at"]) if row else None, cooldown_seconds)


def claim_weekly(discord_id: int, amount: int, cooldown_seconds: int = 7 * 24 * 3600) -> tuple[bool, int]:
    ok, left = can_claim_weekly(discord_id, cooldown_seconds)
    if not ok:
        return False, left
    add_points(discord_id, amount, count_match=False)
    conn = get_connection()
    conn.execute(
        "UPDATE players SET last_weekly_at = ? WHERE discord_id = ?",
        (datetime.utcnow().isoformat(), discord_id),
    )
    conn.commit()
    conn.close()
    return True, cooldown_seconds


def can_claim_lucky(discord_id: int, cooldown_seconds: int) -> tuple[bool, int]:
    conn = get_connection()
    row = conn.execute("SELECT last_lucky_at FROM players WHERE discord_id = ?", (discord_id,)).fetchone()
    conn.close()
    return _seconds_until_claim(_parse_iso(row["last_lucky_at"]) if row else None, cooldown_seconds)


def claim_lucky(
    discord_id: int,
    *,
    cooldown_seconds: int,
    min_reward: int,
    max_reward: int,
    jackpot: int,
    jackpot_chance_percent: int,
) -> tuple[bool, int, int, bool]:
    """(ok, seconds_left, amount, is_jackpot)."""
    import random

    ok, left = can_claim_lucky(discord_id, cooldown_seconds)
    if not ok:
        return False, left, 0, False
    is_jackpot = random.randint(1, 100) <= max(1, min(jackpot_chance_percent, 100))
    amount = jackpot if is_jackpot else random.randint(min_reward, max_reward)
    add_points(discord_id, amount, count_match=False)
    conn = get_connection()
    conn.execute(
        "UPDATE players SET last_lucky_at = ? WHERE discord_id = ?",
        (datetime.utcnow().isoformat(), discord_id),
    )
    conn.commit()
    conn.close()
    return True, 0, amount, is_jackpot


def can_gamble(discord_id: int, cooldown_seconds: int) -> tuple[bool, int]:
    conn = get_connection()
    row = conn.execute("SELECT last_gamble_at FROM players WHERE discord_id = ?", (discord_id,)).fetchone()
    conn.close()
    return _seconds_until_claim(_parse_iso(row["last_gamble_at"]) if row else None, cooldown_seconds)


def play_gamble(discord_id: int, bet: int, *, cooldown_seconds: int, payout_mult: float) -> tuple[bool, str, int]:
    """
    Возвращает (ok, message, balance_delta).
    balance_delta > 0 выигрыш, < 0 проигрыш.
    """
    import random

    ok, left = can_gamble(discord_id, cooldown_seconds)
    if not ok:
        return False, f"Подождите {left} сек.", 0
    player = get_player(discord_id)
    if not player or player["points"] < bet:
        return False, "Недостаточно очков.", 0
    won = random.random() < 0.5
    if won:
        profit = int(bet * payout_mult) - bet
        add_points(discord_id, profit, count_match=False)
        delta = profit
        msg = f"Победа! +**{profit}** (ставка {bet})"
    else:
        add_points(discord_id, -bet, count_match=False)
        delta = -bet
        msg = f"Проигрыш **-{bet}**"
    conn = get_connection()
    conn.execute(
        "UPDATE players SET last_gamble_at = ? WHERE discord_id = ?",
        (datetime.utcnow().isoformat(), discord_id),
    )
    conn.commit()
    conn.close()
    return True, msg, delta


def claim_activity_streak(
    discord_id: int,
    *,
    base_reward: int,
    streak_bonus_per_day: int = 3,
    streak_cap: int = 50,
) -> tuple[bool, int, int, int]:
    """
    Ежедневная серия активности (отдельно от daily).
    Возвращает (ok, seconds_left, streak, reward).
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT activity_streak, best_activity_streak, last_activity_at FROM players WHERE discord_id = ?",
        (discord_id,),
    ).fetchone()
    if not row:
        conn.close()
        return False, 0, 0, 0

    now = datetime.utcnow()
    last = _parse_iso(row["last_activity_at"])
    if last and last.date() == now.date():
        conn.close()
        left = int((datetime.combine(now.date() + timedelta(days=1), datetime.min.time()) - now).total_seconds())
        return False, max(left, 60), int(row["activity_streak"] or 0), 0

    streak = int(row["activity_streak"] or 0)
    if last and (now.date() - last.date()).days == 1:
        streak += 1
    else:
        streak = 1
    best = max(int(row["best_activity_streak"] or 0), streak)
    bonus = min((streak - 1) * streak_bonus_per_day, streak_cap)
    reward = base_reward + bonus
    add_points(discord_id, reward, count_match=False)
    conn.execute(
        """
        UPDATE players SET activity_streak = ?, best_activity_streak = ?, last_activity_at = ?
        WHERE discord_id = ?
        """,
        (streak, best, now.isoformat(), discord_id),
    )
    conn.commit()
    conn.close()
    return True, 0, streak, reward


def get_activity_streak_info(discord_id: int) -> tuple[int, int, bool]:
    """(current, best, claimed_today)."""
    conn = get_connection()
    row = conn.execute(
        "SELECT activity_streak, best_activity_streak, last_activity_at FROM players WHERE discord_id = ?",
        (discord_id,),
    ).fetchone()
    conn.close()
    if not row:
        return 0, 0, False
    last = _parse_iso(row["last_activity_at"])
    claimed = bool(last and last.date() == datetime.utcnow().date())
    return int(row["activity_streak"] or 0), int(row["best_activity_streak"] or 0), claimed


def get_leaderboard(kind: str = "points", limit: int = 10) -> list[dict]:
    queries = {
        "points": "SELECT discord_id, username, points FROM players ORDER BY points DESC LIMIT ?",
        "wins": "SELECT discord_id, username, wins FROM players ORDER BY wins DESC LIMIT ?",
        "streak": "SELECT discord_id, username, win_streak, best_win_streak FROM players ORDER BY win_streak DESC LIMIT ?",
        "zxc": "SELECT discord_id, username, zxc_5x5 FROM players ORDER BY zxc_5x5 DESC LIMIT ?",
    }
    sql = queries.get(kind, queries["points"])
    conn = get_connection()
    rows = conn.execute(sql, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def record_duel_result(winner_id: int, loser_id: int) -> None:
    conn = get_connection()
    conn.execute("UPDATE players SET duel_wins = duel_wins + 1 WHERE discord_id = ?", (winner_id,))
    conn.execute("UPDATE players SET duel_losses = duel_losses + 1 WHERE discord_id = ?", (loser_id,))
    conn.commit()
    conn.close()


def get_player_achievements(discord_id: int) -> list[str]:
    p = get_player(discord_id)
    if not p:
        return []
    badges = []
    wins = p.get("wins", 0) or 0
    tournaments = p.get("tournaments", 0) or 0
    points = p.get("points", 0) or 0
    streak, best_streak = get_win_streak_info(discord_id)
    act, best_act, _ = get_activity_streak_info(discord_id)
    if wins >= 1:
        badges.append("🎮 Первая победа")
    if wins >= 10:
        badges.append("🏅 10 побед")
    if wins >= 50:
        badges.append("👑 50 побед")
    if tournaments >= 25:
        badges.append("📊 Ветеран (25+ матчей)")
    if points >= 1000:
        badges.append("💰 Богач (1000+ очков)")
    if best_streak >= 5:
        badges.append(f"🔥 Серия {best_streak} побед")
    if best_act >= 7:
        badges.append(f"📅 Активность {best_act} дней")
    dw = p.get("duel_wins", 0) or 0
    if dw >= 5:
        badges.append(f"⚔️ Дуэлянт ({dw} побед)")
    if not badges:
        badges.append("🌱 Новичок — сыграйте первый матч!")
    return badges


def tip_player(from_id: int, to_id: int, amount: int) -> None:
    if amount <= 0:
        raise ClanError("Сумма должна быть больше 0.")
    if from_id == to_id:
        raise ClanError("Нельзя перевести себе.")
    conn = get_connection()
    row = conn.execute("SELECT points FROM players WHERE discord_id = ?", (from_id,)).fetchone()
    if not row or row["points"] < amount:
        conn.close()
        raise ClanError("Недостаточно очков.")
    get_or_create_player(to_id, str(to_id))
    conn.execute("UPDATE players SET points = points - ? WHERE discord_id = ?", (amount, from_id))
    conn.execute("UPDATE players SET points = points + ? WHERE discord_id = ?", (amount, to_id))
    conn.commit()
    conn.close()
