"""Steam game detection via appmanifest_*.acf."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from kalium.game_finder.known_games import find_by_steam_id
from kalium.game_finder.vdf_parse import AppManifest, parse_library_folders
from kalium.logging_utils import log_info
from kalium.game_finder.models import Game, Launcher
from kalium.steam.paths import find_all_steam_libraries, find_steam_path

STEAM_PATHS = [
    ".local/share/Steam",
    ".steam/debian-installation",
    ".steam/steam",
    ".var/app/com.valvesoftware.Steam/data/Steam",
    ".var/app/com.valvesoftware.Steam/.local/share/Steam",
    "snap/steam/common/.local/share/Steam",
]


def _installations(home: Path) -> list[tuple[Path, bool, bool]]:
    found = []
    seen = set()
    for rel in STEAM_PATHS:
        p = home / rel
        if not (p / "steamapps").exists() and not (p / "steam.pid").exists():
            continue
        try:
            canon = p.resolve()
        except OSError:
            canon = p
        if canon in seen:
            continue
        seen.add(canon)
        is_flatpak = ".var/app/com.valvesoftware.Steam" in str(p)
        is_snap = "snap/steam" in str(p)
        found.append((p, is_flatpak, is_snap))
    return found


def _libraries(steam_path: Path) -> list[Path]:
    """Library roots for one Steam install, including secondary drives."""
    folders: list[Path] = []
    seen: set[Path] = set()

    def _add(p: Path) -> None:
        try:
            canon = p.resolve()
        except OSError:
            canon = p
        if canon in seen:
            return
        if (canon / "steamapps").is_dir() or canon == steam_path:
            seen.add(canon)
            folders.append(canon)

    _add(steam_path)
    # Prefer the shared helper (reads the same libraryfolders.vdf thoroughly)
    try:
        for lib in find_all_steam_libraries():
            _add(lib)
    except Exception:
        pass
    for vdf in (
        steam_path / "steamapps" / "libraryfolders.vdf",
        steam_path / "config" / "libraryfolders.vdf",
    ):
        if not vdf.exists():
            continue
        try:
            content = vdf.read_text(encoding="utf-8", errors="replace")
            for path_str in parse_library_folders(content):
                _add(Path(path_str))
        except OSError:
            pass
    return folders


def _resolve_game_prefix(steamapps: Path, app_id: str, all_libs: list[Path]) -> Optional[Path]:
    """
    Locate the Proton prefix for a Steam game.

    Steam may keep compatdata next to the game (secondary library) *or*
    under the primary install. Prefer the library that owns the game
    (libraryfolders.vdf apps map / appmanifest), then fall back to every
    known library / primary Steam path.
    """
    # Prefer dynamic multi-drive resolution (libraryfolders.vdf + appmanifest)
    try:
        from kalium.steam.paths import find_pfx_for_app

        pfx = find_pfx_for_app(app_id)
        if pfx and pfx.is_dir():
            return pfx
    except Exception:
        pass

    candidates = [
        steamapps / "compatdata" / app_id / "pfx",
    ]
    for lib in all_libs:
        candidates.append(lib / "steamapps" / "compatdata" / app_id / "pfx")
    primary = find_steam_path()
    if primary:
        candidates.append(primary / "steamapps" / "compatdata" / app_id / "pfx")
    seen: set[Path] = set()
    for c in candidates:
        try:
            canon = c.resolve()
        except OSError:
            canon = c
        if canon in seen:
            continue
        seen.add(canon)
        if c.is_dir():
            return c
    return None


def detect_steam_games() -> list[Game]:
    games: list[Game] = []
    home = Path.home()
    # Shared list so secondary-drive prefixes are found even when the
    # appmanifest lives in a different library than the compatdata folder.
    all_libs = find_all_steam_libraries()
    for steam_path, is_flatpak, is_snap in _installations(home):
        libs = _libraries(steam_path)
        # Merge so we never miss a secondary library
        for extra in all_libs:
            if extra not in libs:
                libs.append(extra)
        for lib in libs:
            steamapps = lib / "steamapps"
            if not steamapps.exists():
                continue
            try:
                entries = list(steamapps.iterdir())
            except OSError:
                continue
            for entry in entries:
                name = entry.name
                if not (name.startswith("appmanifest_") and name.endswith(".acf")):
                    continue
                try:
                    content = entry.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                manifest = AppManifest.from_vdf(content)
                if not manifest or not manifest.is_installed():
                    continue
                install = steamapps / "common" / manifest.install_dir
                if not install.exists():
                    continue
                prefix = _resolve_game_prefix(steamapps, manifest.app_id, libs)
                known = find_by_steam_id(manifest.app_id)
                games.append(
                    Game(
                        name=manifest.name,
                        app_id=manifest.app_id,
                        install_path=install,
                        prefix_path=prefix,
                        launcher=Launcher("steam", is_flatpak=is_flatpak, is_snap=is_snap),
                        my_games_folder=known.my_games_folder if known else None,
                        appdata_local_folder=known.appdata_local_folder if known else None,
                        appdata_roaming_folder=known.appdata_roaming_folder if known else None,
                        registry_path=known.registry_path if known else None,
                        registry_value=known.registry_value if known else None,
                    )
                )
    log_info(f"Steam: Found {len(games)} installed games")
    return games
