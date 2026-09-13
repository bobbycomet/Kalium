"""Bottles prefix game detection via registry files."""

from __future__ import annotations

from pathlib import Path

from kalium.game_finder.known_games import KNOWN_GAMES
from kalium.game_finder.registry import read_registry_value, wine_path_to_linux
from kalium.game_finder.models import Game, Launcher
from kalium.logging_utils import log_info

BOTTLES_PATHS = [
    ".local/share/bottles/bottles",
    ".var/app/com.usebottles.bottles/data/bottles/bottles",
]


def detect_bottles_games() -> list[Game]:
    games: list[Game] = []
    home = Path.home()
    for rel in BOTTLES_PATHS:
        base = home / rel
        if not base.exists():
            continue
        log_info(f"Found Bottles: {base}")
        try:
            bottles = [p for p in base.iterdir() if p.is_dir()]
        except OSError:
            continue
        for bottle in bottles:
            drive_c = bottle / "drive_c"
            if not drive_c.exists():
                continue
            for kg in KNOWN_GAMES:
                wine_path = read_registry_value(bottle, kg.registry_path, kg.registry_value)
                if not wine_path:
                    continue
                install = wine_path_to_linux(wine_path)
                if install is None and wine_path.lower().startswith("c:"):
                    relative = wine_path[2:].replace("\\", "/").lstrip("/")
                    candidate = (drive_c / relative).resolve()
                    try:
                        candidate.relative_to(drive_c.resolve())
                        install = candidate
                    except ValueError:
                        continue
                if not install or not install.exists():
                    continue
                games.append(
                    Game(
                        name=kg.name,
                        app_id=f"bottles-{kg.steam_app_id}",
                        install_path=install,
                        prefix_path=bottle,
                        launcher=Launcher("bottles"),
                        my_games_folder=kg.my_games_folder,
                        appdata_local_folder=kg.appdata_local_folder,
                        appdata_roaming_folder=kg.appdata_roaming_folder,
                        registry_path=kg.registry_path,
                        registry_value=kg.registry_value,
                    )
                )
    log_info(f"Bottles: Found {len(games)} installed games")
    return games
