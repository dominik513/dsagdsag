"""Режимы турнира: лимиты игроков и отображение."""

MODES = ("5x5", "1x1", "2x2")


def max_players(mode: str) -> int:
    return {"5x5": 10, "1x1": 2, "2x2": 4}[mode]


def mode_title(mode: str) -> str:
    return {
        "5x5": "Сбор 5x5",
        "1x1": "Мид-дуэль 1x1",
        "2x2": "Мид 2x2",
    }[mode]


def mode_label(mode: str) -> str:
    return {"5x5": "5x5", "1x1": "1x1", "2x2": "2x2"}[mode]


def is_small_lobby(mode: str) -> bool:
    return mode in ("1x1", "2x2")


def rating_mode(mode: str) -> str:
    """2x2 использует рейтинг и калибровку 1x1."""
    return "5x5" if mode == "5x5" else "1x1"
