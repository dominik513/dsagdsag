from __future__ import annotations

import os
import sqlite3
from config import DATABASE_PATH

def get_connection():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS players (
            discord_id      INTEGER PRIMARY KEY,
            username        TEXT NOT NULL,
            points          INTEGER DEFAULT 0,
            wins            INTEGER DEFAULT 0,
            losses          INTEGER DEFAULT 0,
            tournaments     INTEGER DEFAULT 0,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS player_roles (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id      INTEGER NOT NULL,
            role_id         INTEGER NOT NULL,
            role_name       TEXT,
            purchased_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (discord_id) REFERENCES players(discord_id)
        );
        CREATE TABLE IF NOT EXISTS shop_items (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            type            TEXT NOT NULL CHECK(type IN ('role', 'dota_plus', 'item')),
            name            TEXT NOT NULL,
            description     TEXT,
            role_id         INTEGER,
            price           INTEGER NOT NULL,
            is_active       BOOLEAN DEFAULT 1,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS reward_requests (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id      INTEGER NOT NULL,
            item_id         INTEGER NOT NULL,
            status          TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
            request_text    TEXT,
            admin_response  TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at     TIMESTAMP,
            FOREIGN KEY (discord_id) REFERENCES players(discord_id),
            FOREIGN KEY (item_id) REFERENCES shop_items(id)
        );
        CREATE TABLE IF NOT EXISTS tournaments (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id        TEXT UNIQUE NOT NULL,
            lobby_name      TEXT NOT NULL,
            lobby_password  TEXT NOT NULL,
            status          TEXT DEFAULT 'gathering' CHECK(status IN ('gathering', 'in_progress', 'finished', 'cancelled')),
            team_radiant    TEXT,
            team_dire       TEXT,
            winner          TEXT CHECK(winner IN ('radiant', 'dire', NULL)),
            created_by      INTEGER NOT NULL,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at     TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS tournament_players (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id   INTEGER NOT NULL,
            discord_id      INTEGER NOT NULL,
            team            TEXT CHECK(team IN ('radiant', 'dire')),
            position        INTEGER CHECK(position BETWEEN 1 AND 5),
            points_earned   INTEGER DEFAULT 0,
            FOREIGN KEY (tournament_id) REFERENCES tournaments(id),
            FOREIGN KEY (discord_id) REFERENCES players(discord_id)
        );
        CREATE TABLE IF NOT EXISTS clans (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL UNIQUE,
            tag             TEXT NOT NULL UNIQUE,
            owner_id        INTEGER NOT NULL,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            wins            INTEGER DEFAULT 0,
            losses          INTEGER DEFAULT 0,
            FOREIGN KEY (owner_id) REFERENCES players(discord_id)
        );
        CREATE TABLE IF NOT EXISTS clan_members (
            clan_id         INTEGER NOT NULL,
            discord_id      INTEGER NOT NULL UNIQUE,
            joined_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (clan_id) REFERENCES clans(id),
            FOREIGN KEY (discord_id) REFERENCES players(discord_id)
        );
    """)

    for col, col_type in [
        ("zxc_rating", "INTEGER DEFAULT 1000"),
        ("calibration_matches", "INTEGER DEFAULT 0"),
        ("total_kills", "INTEGER DEFAULT 0"),
        ("total_deaths", "INTEGER DEFAULT 0"),
        ("total_assists", "INTEGER DEFAULT 0"),
        ("elo", "INTEGER DEFAULT 1000"),
        ("zxc_5x5", "INTEGER DEFAULT 1000"),
        ("calibration_5x5", "INTEGER DEFAULT 0"),
        ("zxc_1x1", "INTEGER DEFAULT 1000"),
        ("calibration_1x1", "INTEGER DEFAULT 0"),
        ("last_daily_at", "TEXT"),
        ("last_weekly_at", "TEXT"),
        ("last_lucky_at", "TEXT"),
        ("last_activity_at", "TEXT"),
        ("activity_streak", "INTEGER DEFAULT 0"),
        ("best_activity_streak", "INTEGER DEFAULT 0"),
        ("last_gamble_at", "TEXT"),
        ("duel_wins", "INTEGER DEFAULT 0"),
        ("duel_losses", "INTEGER DEFAULT 0"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE players ADD COLUMN {col} {col_type}")
        except:
            pass

    for col, col_type in [
        ("avatar", "TEXT"),
        ("banner", "TEXT"),
        ("description", "TEXT"),
        ("chat_id", "INTEGER"),
        ("treasury", "INTEGER DEFAULT 0"),
        ("xp", "INTEGER DEFAULT 0"),
        ("level", "INTEGER DEFAULT 1"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE clans ADD COLUMN {col} {col_type}")
        except:
            pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clan_treasury_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            clan_id         INTEGER NOT NULL,
            actor_id        INTEGER,
            amount          INTEGER NOT NULL,
            reason          TEXT NOT NULL,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (clan_id) REFERENCES clans(id)
        )
    """)

    try:
        cursor.execute("ALTER TABLE clan_members ADD COLUMN role TEXT DEFAULT 'Участник'")
    except:
        pass

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id   INTEGER,
                duration        INTEGER DEFAULT 0,
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id)
            )
        """)
    except:
        pass

    for col, col_type in [
        ("dota_name", "TEXT"),
        ("steam_id", "TEXT"),
        ("win_streak", "INTEGER DEFAULT 0"),
        ("best_win_streak", "INTEGER DEFAULT 0"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE players ADD COLUMN {col} {col_type}")
        except:
            pass

    for col, col_type in [
        ("void_reason", "TEXT"),
        ("cancel_reason", "TEXT"),
        ("cheat_flags", "TEXT"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE tournaments ADD COLUMN {col} {col_type}")
        except:
            pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS match_player_logs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id   INTEGER NOT NULL,
            discord_id      INTEGER,
            dota_name       TEXT,
            team            TEXT,
            kills           INTEGER DEFAULT 0,
            deaths          INTEGER DEFAULT 0,
            assists          INTEGER DEFAULT 0,
            last_hits       INTEGER DEFAULT 0,
            denies          INTEGER DEFAULT 0,
            networth        INTEGER DEFAULT 0,
            hero            TEXT,
            flags           TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tournament_id) REFERENCES tournaments(id)
        )
    """)

    for col, col_type in [
        ("kills", "INTEGER DEFAULT 0"),
        ("deaths", "INTEGER DEFAULT 0"),
        ("assists", "INTEGER DEFAULT 0"),
        ("last_hits", "INTEGER DEFAULT 0"),
        ("denies", "INTEGER DEFAULT 0"),
        ("net_worth", "INTEGER DEFAULT 0"),
        ("hero", "TEXT"),
        ("dota_name", "TEXT"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE tournament_players ADD COLUMN {col} {col_type}")
        except:
            pass

    conn.commit()
    conn.close()
