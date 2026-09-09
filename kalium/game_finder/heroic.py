"""Heroic (GOG/Epic) game detection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from kalium.game_finder.known_games import find_by_epic_id, find_by_gog_id, find_by_title
from kalium.game_finder.models import Game, Launcher
from kalium.logging_utils import log_info, log_warning

HEROIC_PATHS = [
    ".config/heroic",
    ".var/app/com.heroicgameslauncher.hgl/config/heroic",
]


def _prefix(heroic: Path, app_name: str) -> Optional[Path]:
    cfg = heroic / "GamesConfig" / f"{app_name}.json"
    if not cfg.exists():
        return None
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
    except Exception:
        return None
    wp = data.get("winePrefix")
    if not wp and app_name in data:
        wp = data[app_name].get("winePrefix")
    if not wp:
        return None
    p = Path(wp)
    return p if p.exists() else None


def detect_heroic_games() -> list[Game]:
    games: list[Game] = []
    home = Path.home()
    for rel in HEROIC_PATHS:
        heroic = home / rel
        if not heroic.exists():
            continue
        log_info(f"Found Heroic: {heroic}")
        # GOG
        inst = heroic / "gog_store" / "installed.json"
        if inst.exists():
            try:
                raw = json.loads(inst.read_text(encoding="utf-8"))
                items = raw.get("installed", raw) if isinstance(raw, dict) else raw
                for g in items:
                    if g.get("platform") != "windows":
                        continue
                    path_str = g.get("install_path")
                    if not path_str:
                        continue
                    install = Path(path_str)
                    if not install.exists():
                        continue
                    app_name = g.get("appName", "")
                    known = find_by_gog_id(app_name)
                    games.append(
                        Game(
                            name=g.get("title") or app_name,
                            app_id=app_name,
                            install_path=install,
                            prefix_path=_prefix(heroic, app_name),
                            launcher=Launcher("heroic", store="GOG"),
                            my_games_folder=known.my_games_folder if known else None,
                            appdata_local_folder=known.appdata_local_folder if known else None,
                            appdata_roaming_folder=known.appdata_roaming_folder if known else None,
                            registry_path=known.registry_path if known else None,
                            registry_value=known.registry_value if known else None,
                        )
                    )
            except Exception as e:
                log_warning(f"Heroic GOG parse failed: {e}")
        # Epic
        for epic_json in (
            heroic / "store_cache" / "legendary_library.json",
            heroic / "legendaryConfig" / "legendary" / "installed.json",
        ):
            if not epic_json.exists():
                continue
            try:
                lib = json.loads(epic_json.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(lib, dict):
                continue
            for app_name, game_data in lib.items():
                if not isinstance(game_data, dict):
                    continue
                if not game_data.get("is_installed"):
                    continue
                plat = (game_data.get("platform") or "").lower()
                if plat not in ("windows",):
                    continue
                path_str = game_data.get("install_path")
                if not path_str:
                    continue
                install = Path(path_str)
                if not install.exists():
                    continue
                title = game_data.get("title") or app_name
                known = find_by_epic_id(app_name) or find_by_title(title)
                games.append(
                    Game(
                        name=title,
                        app_id=app_name,
                        install_path=install,
                        prefix_path=_prefix(heroic, app_name),
                        launcher=Launcher("heroic", store="Epic"),
                        my_games_folder=known.my_games_folder if known else None,
                        appdata_local_folder=known.appdata_local_folder if known else None,
                        appdata_roaming_folder=known.appdata_roaming_folder if known else None,
                        registry_path=known.registry_path if known else None,
                        registry_value=known.registry_value if known else None,
                    )
                )
            break
    log_info(f"Heroic: Found {len(games)} installed games")
    return games
