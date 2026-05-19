"""Разбор ссылок Steam и сопоставление SteamID64 ↔ Dota account_id."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

STEAM_ID64_BASE = 76561197960265728

_PROFILES_RE = re.compile(
    r"(?:https?://)?(?:www\.)?steamcommunity\.com/profiles/(\d{17})",
    re.I,
)
_ID_RE = re.compile(
    r"(?:https?://)?(?:www\.)?steamcommunity\.com/id/([^/?#\s]+)",
    re.I,
)
_RAW_STEAM64_RE = re.compile(r"^\d{17}$")


class SteamLinkError(Exception):
    """Ошибка привязки профиля Steam (понятное сообщение для пользователя)."""


def steam_id64_to_account_id(steam_id64: str | int) -> int:
    sid = int(str(steam_id64).strip())
    if sid < STEAM_ID64_BASE:
        raise ValueError("invalid steam id64")
    return sid - STEAM_ID64_BASE


def account_id_to_steam_id64(account_id: int | str) -> str:
    return str(int(account_id) + STEAM_ID64_BASE)


def _http_get_json(url: str, *, timeout: int = 15) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "tournament-bot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SteamLinkError(f"Steam API: HTTP {e.code}") from e
    except urllib.error.URLError as e:
        raise SteamLinkError(f"Не удалось связаться со Steam: {e.reason}") from e
    except json.JSONDecodeError as e:
        raise SteamLinkError("Некорректный ответ Steam API") from e


def _resolve_vanity(vanity: str, api_key: str) -> str:
    if not api_key:
        raise SteamLinkError(
            "Для ссылок steamcommunity.com/id/… укажите STEAM_API_KEY в .env "
            "(https://steamcommunity.com/dev/apikey)"
        )
    q = urllib.parse.urlencode({"key": api_key, "vanityurl": vanity})
    data = _http_get_json(
        f"https://api.steampowered.com/ISteamUser/ResolveVanityURL/v0001/?{q}"
    )
    resp = data.get("response", {})
    if resp.get("success") != 1:
        msg = resp.get("message", "профиль не найден")
        raise SteamLinkError(f"Не удалось найти профиль: {msg}")
    return str(resp["steamid"])


def _fetch_persona_name(steam_id64: str, api_key: str) -> str:
    if not api_key:
        return f"steam_{steam_id64[-6:]}"
    q = urllib.parse.urlencode({"key": api_key, "steamids": steam_id64})
    data = _http_get_json(
        f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?{q}"
    )
    players = data.get("response", {}).get("players", [])
    if players:
        name = (players[0].get("personaname") or "").strip()
        if name:
            return name[:32]
    return f"steam_{steam_id64[-6:]}"


def parse_steam_url(url: str, api_key: str = "") -> str:
    """Вернуть SteamID64 из ссылки или 17-значного id."""
    raw = (url or "").strip()
    if not raw:
        raise SteamLinkError("Укажите ссылку на профиль Steam.")

    m = _PROFILES_RE.search(raw)
    if m:
        return m.group(1)

    m = _ID_RE.search(raw)
    if m:
        vanity = urllib.parse.unquote(m.group(1).rstrip("/"))
        return _resolve_vanity(vanity, api_key)

    if _RAW_STEAM64_RE.match(raw):
        return raw

    raise SteamLinkError(
        "Не распознана ссылка. Примеры:\n"
        "• https://steamcommunity.com/profiles/76561198…\n"
        "• https://steamcommunity.com/id/ваш_ник"
    )


def resolve_steam_profile(url: str, api_key: str = "") -> tuple[str, str, str]:
    """(steam_id64, отображаемый ник, URL профиля)."""
    steam_id64 = parse_steam_url(url, api_key)
    if not _RAW_STEAM64_RE.match(steam_id64):
        raise SteamLinkError("Некорректный SteamID64.")
    profile_url = f"https://steamcommunity.com/profiles/{steam_id64}"
    dota_name = _fetch_persona_name(steam_id64, api_key)
    return steam_id64, dota_name, profile_url
