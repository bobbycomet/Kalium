"""Game detection entry point."""

from __future__ import annotations

from kalium.game_finder.models import GameScanResult


def detect_all_games() -> GameScanResult:
    games = []
    steam_count = heroic_count = bottles_count = 0
    try:
        from kalium.game_finder.steam_games import detect_steam_games
        sg = detect_steam_games()
        games.extend(sg)
        steam_count = len(sg)
    except Exception:
        pass
    try:
        from kalium.game_finder.heroic import detect_heroic_games
        hg = detect_heroic_games()
        games.extend(hg)
        heroic_count = len(hg)
    except Exception:
        pass
    try:
        from kalium.game_finder.bottles import detect_bottles_games
        bg = detect_bottles_games()
        games.extend(bg)
        bottles_count = len(bg)
    except Exception:
        pass
    return GameScanResult(
        games=games,
        steam_count=steam_count,
        heroic_count=heroic_count,
        bottles_count=bottles_count,
    )
