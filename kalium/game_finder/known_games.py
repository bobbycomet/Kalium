"""Known moddable games metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class KnownGame:
    name: str
    steam_app_id: str
    gog_app_id: Optional[str]
    epic_app_id: Optional[str]
    my_games_folder: Optional[str]
    appdata_local_folder: Optional[str]
    appdata_roaming_folder: Optional[str]
    registry_path: str
    registry_value: str
    steam_folder: str


KNOWN_GAMES: list[KnownGame] = [
    KnownGame("Enderal", "933480", "1708684988", None, "Enderal", None, None, r"Software\SureAI\Enderal", "Install_Path", "Enderal"),
    KnownGame("Enderal Special Edition", "976620", None, None, "Enderal Special Edition", None, None, r"Software\SureAI\Enderal SE", "installed path", "Enderal Special Edition"),
    KnownGame("Fallout 3", "22300", "1454315831", "adeae8bbfc94427db57c7dfecce3f1d4", "Fallout3", "Fallout3", None, r"Software\Bethesda Softworks\Fallout3", "Installed Path", "Fallout 3"),
    KnownGame("Fallout 4", "377160", "1998527297", "61d52ce4d09d41e48800c22784d13ae8", "Fallout4", "Fallout4", None, r"Software\Bethesda Softworks\Fallout4", "Installed Path", "Fallout 4"),
    KnownGame("Fallout 4 VR", "611660", None, None, "Fallout4VR", None, None, r"Software\Bethesda Softworks\Fallout 4 VR", "Installed Path", "Fallout 4 VR"),
    KnownGame("Fallout New Vegas", "22380", "1454587428", "5daeb974a22a435988892319b3a4f476", "FalloutNV", "FalloutNV", None, r"Software\Bethesda Softworks\FalloutNV", "Installed Path", "Fallout New Vegas"),
    KnownGame("Morrowind", "22320", "1440163901", None, "Morrowind", None, None, r"Software\Bethesda Softworks\Morrowind", "Installed Path", "Morrowind"),
    KnownGame("Oblivion", "22330", "1458058109", None, "Oblivion", "Oblivion", None, r"Software\Bethesda Softworks\Oblivion", "Installed Path", "Oblivion"),
    KnownGame("Skyrim", "72850", None, None, "Skyrim", "Skyrim", None, r"Software\Bethesda Softworks\Skyrim", "Installed Path", "Skyrim"),
    KnownGame("Skyrim Special Edition", "489830", "1711230643", "ac82db5035584c7f8a2c548d98c86b2c", "Skyrim Special Edition", "Skyrim Special Edition", None, r"Software\Bethesda Softworks\Skyrim Special Edition", "Installed Path", "Skyrim Special Edition"),
    KnownGame("Skyrim VR", "611670", None, None, "Skyrim VR", None, None, r"Software\Bethesda Softworks\Skyrim VR", "Installed Path", "Skyrim VR"),
    KnownGame("Starfield", "1716740", None, None, "Starfield", None, None, r"Software\Bethesda Softworks\Starfield", "Installed Path", "Starfield"),
    KnownGame("The Witcher 3", "292030", "1495134320", None, "The Witcher 3", None, None, r"Software\CD Projekt Red\The Witcher 3", "InstallFolder", "The Witcher 3 Wild Hunt"),
    KnownGame("Cyberpunk 2077", "1091500", "1423049311", None, None, "CD Projekt Red/Cyberpunk 2077", None, r"Software\CD Projekt Red\Cyberpunk 2077", "InstallFolder", "Cyberpunk 2077"),
    KnownGame("Baldur's Gate 3", "1086940", "1456460669", None, None, "Larian Studios/Baldur's Gate 3", None, r"Software\Larian Studios\Baldur's Gate 3", "InstallDir", "Baldurs Gate 3"),
]

GOG_ID_ALIASES = {
    "1435828767": "1440163901",
    "1801825368": "1711230643",
}


def normalize_steam_id(app_id: str) -> str:
    return "22300" if app_id == "22370" else app_id


def find_by_steam_id(app_id: str) -> Optional[KnownGame]:
    nid = normalize_steam_id(app_id)
    for g in KNOWN_GAMES:
        if g.steam_app_id == nid:
            return g
    return None


def find_by_gog_id(app_id: str) -> Optional[KnownGame]:
    for g in KNOWN_GAMES:
        if g.gog_app_id == app_id:
            return g
    primary = GOG_ID_ALIASES.get(app_id)
    if primary:
        for g in KNOWN_GAMES:
            if g.gog_app_id == primary:
                return g
    return None


def find_by_epic_id(app_id: str) -> Optional[KnownGame]:
    for g in KNOWN_GAMES:
        if g.epic_app_id == app_id:
            return g
    return None


def find_by_name(name: str) -> Optional[KnownGame]:
    nl = name.lower()
    for g in KNOWN_GAMES:
        if g.name.lower() == nl:
            return g
    return None


def _norm(s: str) -> str:
    return " ".join("".join(c if c.isalnum() or c == " " else " " for c in s.lower()).split())


def find_by_title(title: str) -> Optional[KnownGame]:
    tl = title.lower()
    g = find_by_name(title)
    if g:
        return g
    ordered = sorted(KNOWN_GAMES, key=lambda x: len(x.name), reverse=True)
    tn = _norm(title)
    for game in ordered:
        gl = game.name.lower()
        gn = _norm(game.name)
        if gl in tl or gn in tn:
            return game
        if ":" in tl:
            after = tl.split(":", 1)[1].strip()
            if after.startswith(gl):
                return game
    return None
