"""
Проверка честности матча: фид, подозрительные статы, абуз лобби.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class IntegrityIssue:
    code: str
    player_key: str
    detail: str


@dataclass
class IntegrityResult:
    valid: bool
    void_reason: str | None = None
    issues: list[IntegrityIssue] = field(default_factory=list)
    feeders: list[str] = field(default_factory=list)
    mvp_key: str | None = None


def _kda_score(stats: dict) -> float:
    k = stats.get("kills", 0)
    d = max(stats.get("deaths", 0), 1)
    a = stats.get("assists", 0)
    return (k + a * 0.7) / d


def detect_feed(
    player_key: str,
    stats: dict,
    *,
    mode: str,
    clock_time: int,
    min_deaths_5x5: int,
    min_deaths_1x1: int,
    max_kda_feed: float,
) -> IntegrityIssue | None:
    kills = stats.get("kills", 0)
    deaths = stats.get("deaths", 0)
    assists = stats.get("assists", 0)
    last_hits = stats.get("last_hits", 0)
    min_deaths = min_deaths_1x1 if mode == "1x1" else min_deaths_5x5
    minutes = max(clock_time / 60, 1)

    if deaths < min_deaths:
        return None

    ka = kills + assists
    if ka <= 1 and deaths >= min_deaths:
        return IntegrityIssue("feed", player_key, f"K+A={ka}, смертей={deaths}")

    if deaths >= min_deaths + 5 and ka <= 3:
        return IntegrityIssue("feed", player_key, f"экстремальный фид: {deaths}/{kills}/{assists}")

    if _kda_score(stats) < max_kda_feed and deaths >= min_deaths:
        return IntegrityIssue("feed", player_key, f"KDA={kills}/{deaths}/{assists}")

    if mode == "1x1" and minutes >= 8 and last_hits < 30 and deaths >= 8:
        return IntegrityIssue("feed", player_key, f"мало LH ({last_hits}) при {deaths} смертях")

    if mode == "5x5" and minutes >= 12 and last_hits < 15 and deaths >= 12:
        return IntegrityIssue("feed", player_key, f"мало фарма ({last_hits} LH) при {deaths} смертях")

    return None


def detect_cheat_stats(player_key: str, stats: dict, clock_time: int) -> IntegrityIssue | None:
    kills = stats.get("kills", 0)
    deaths = stats.get("deaths", 0)
    assists = stats.get("assists", 0)
    last_hits = stats.get("last_hits", 0)
    minutes = max(clock_time / 60, 1)

    if kills > 80 or deaths > 80 or assists > 80:
        return IntegrityIssue("cheat_stats", player_key, "невозможные K/D/A")

    if minutes < 3 and (kills > 40 or deaths > 40):
        return IntegrityIssue("cheat_stats", player_key, "подозрительные статы за короткую игру")

    if minutes >= 5 and last_hits > minutes * 25:
        return IntegrityIssue("cheat_stats", player_key, f"подозрительный фарм: {last_hits} LH")

    return None


def pick_mvp(player_stats: dict, winner_team: str) -> str | None:
    best_key, best_score = None, -1.0
    for key, stats in player_stats.items():
        if stats.get("team") not in ("radiant", "dire"):
            continue
        if stats.get("team") != winner_team:
            continue
        score = stats.get("kills", 0) * 3 + stats.get("assists", 0) * 2 - stats.get("deaths", 0)
        if score > best_score:
            best_score = score
            best_key = key
    return best_key


def analyze_match(
    *,
    mode: str,
    clock_time: int,
    player_stats: dict,
    registered_names: set[str],
    mapped_count: int,
    score: tuple[int, int],
    min_mapped_players: int,
    min_deaths_5x5: int,
    min_deaths_1x1: int,
    max_kda_feed: float,
    blowout_score_diff: int,
    blowout_max_minutes: int,
) -> IntegrityResult:
    issues: list[IntegrityIssue] = []
    feeders: list[str] = []

    for key, stats in player_stats.items():
        feed = detect_feed(
            key,
            stats,
            mode=mode,
            clock_time=clock_time,
            min_deaths_5x5=min_deaths_5x5,
            min_deaths_1x1=min_deaths_1x1,
            max_kda_feed=max_kda_feed,
        )
        if feed:
            issues.append(feed)
            feeders.append(key)

        cheat = detect_cheat_stats(key, stats, clock_time)
        if cheat:
            issues.append(cheat)

    minutes = clock_time / 60
    score_diff = abs(score[0] - score[1])
    if minutes <= blowout_max_minutes and score_diff >= blowout_score_diff:
        issues.append(
            IntegrityIssue(
                "lobby_abuse",
                "match",
                f"разгром {score[0]}:{score[1]} за {minutes:.0f} мин — возможный абуз лобби",
            )
        )

    if player_stats and mapped_count < min_mapped_players:
        issues.append(
            IntegrityIssue(
                "lobby_abuse",
                "match",
                f"привязано игроков: {mapped_count}/{len(player_stats)} — используйте /link_dota",
            )
        )

    if registered_names and player_stats:
        unknown = [k for k in player_stats if k.lower() not in registered_names]
        if len(unknown) == len(player_stats) and len(player_stats) >= 1:
            issues.append(
                IntegrityIssue(
                    "lobby_abuse",
                    "match",
                    "ни один игрок GSI не совпал с участниками матча",
                )
            )

    void_codes = {"feed", "cheat_stats", "lobby_abuse"}
    critical = [i for i in issues if i.code in void_codes]

    if feeders:
        void_reason = "намеренный фид: " + ", ".join(feeders[:3])
        valid = False
    elif any(i.code == "cheat_stats" for i in critical):
        void_reason = "подозрение на чит/накрутку статов"
        valid = False
    elif any(i.code == "lobby_abuse" for i in critical) and mapped_count < min_mapped_players:
        void_reason = critical[0].detail
        valid = False
    elif any(i.code == "lobby_abuse" for i in critical) and score_diff >= blowout_score_diff:
        void_reason = critical[0].detail
        valid = False
    else:
        void_reason = None
        valid = True

    winner_team = "radiant" if score[0] >= score[1] else "dire"
    mvp = pick_mvp(player_stats, winner_team) if valid else None

    return IntegrityResult(
        valid=valid,
        void_reason=void_reason,
        issues=issues,
        feeders=feeders,
        mvp_key=mvp,
    )
