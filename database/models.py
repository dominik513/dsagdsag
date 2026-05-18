from __future__ import annotations

import json
from datetime import datetime
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
    cursor.execute("SELECT COUNT(*) FROM tournament_players WHERE discord_id = ?", (discord_id,))
    total_matches = cursor.fetchone()[0]
    player = get_player(discord_id)
    conn.close()
    return {"fav_position": fav_pos["position"] if fav_pos else None, "total_matches": total_matches, "wins": player["wins"] if player else 0, "losses": player["losses"] if player else 0, "points": player["points"] if player else 0}

def _get_zxc_column(mode: str) -> str:
    return "zxc_5x5" if mode == "5x5" else "zxc_1x1"

def _get_calib_column(mode: str) -> str:
    return "calibration_5x5" if mode == "5x5" else "calibration_1x1"

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

def get_team_avg_zxc(team: list) -> int:
    if not team: return 1000
    conn = get_connection()
    total = 0
    for uid in team:
        row = conn.execute("SELECT zxc_5x5 FROM players WHERE discord_id = ?", (uid,)).fetchone()
        total += row["zxc_5x5"] if row and row["zxc_5x5"] else 1000
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
    """Сопоставить GSI-ник → discord_id."""
    result: dict[int, dict] = {}
    conn = get_connection()
    for uid in team:
        row = conn.execute(
            "SELECT dota_name, username FROM players WHERE discord_id = ?",
            (uid,),
        ).fetchone()
        if not row:
            continue
        keys = {str(uid)}
        if row["dota_name"]:
            keys.add(row["dota_name"].lower())
        if row["username"]:
            keys.add(row["username"].lower())
        for gsi_name, stats in player_stats.items():
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
