"""Bind a managed game to a portable MO2 instance via ModOrganizer.ini.

MO2 portable instances store the managed game in ModOrganizer.ini under
[General]:

  gameName=<display name MO2 plugins understand>
  gamePath=<Windows path, usually Z:/... under Proton>

Without these, first launch often fails with “game / instance not found”
style errors because the portable instance has no game binding.

Kalium seeds these during install from either a detected install or a
user-picked folder + known game name.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from kalium.logging_utils import log_install, log_warning

# Names MO2 game plugins expect (match LOOT / basic_games identifiers where possible)
_MO2_GAME_NAMES: dict[str, str] = {
    "skyrim special edition": "Skyrim Special Edition",
    "skyrim se": "Skyrim Special Edition",
    "skyrimse": "Skyrim Special Edition",
    "skyrim": "Skyrim",
    "skyrim vr": "Skyrim VR",
    "enderal": "Enderal",
    "enderal special edition": "Enderal Special Edition",
    "fallout 4": "Fallout 4",
    "fallout4": "Fallout 4",
    "fallout 4 vr": "Fallout 4 VR",
    "fallout4vr": "Fallout 4 VR",
    "fallout new vegas": "New Vegas",
    "fallout nv": "New Vegas",
    "falloutnv": "New Vegas",
    "fallout 3": "Fallout 3",
    "fallout3": "Fallout 3",
    "oblivion": "Oblivion",
    "oblivion remastered": "Oblivion Remastered",
    "morrowind": "Morrowind",
    "starfield": "Starfield",
    "the witcher 3": "The Witcher 3",
    "witcher 3": "The Witcher 3",
    "cyberpunk 2077": "Cyberpunk 2077",
    "baldur's gate 3": "Baldur's Gate 3",
    "baldurs gate 3": "Baldur's Gate 3",
}


@dataclass(frozen=True)
class ManagedGameChoice:
    """One selectable game for the install wizard."""

    display_name: str  # UI label
    mo2_game_name: str  # value written to gameName=
    install_path: Optional[Path]  # None → user must browse
    source: str = ""  # steam / heroic / bottles / manual


def normalize_mo2_game_name(name: str) -> str:
    key = " ".join((name or "").strip().lower().split())
    return _MO2_GAME_NAMES.get(key, (name or "").strip() or "Skyrim Special Edition")


def linux_path_to_wine_z(path: Path | str) -> str:
    """Z:/abs/path with forward slashes for Proton/Wine."""
    p = Path(path).expanduser().resolve()
    return "Z:" + str(p).replace("\\", "/")


def _qt_bytearray_path(wine_path: str) -> str:
    """Qt QSettings often stores paths as @ByteArray(...)."""
    return f"@ByteArray({wine_path})"


def list_known_game_templates() -> list[ManagedGameChoice]:
    """Games Kalium knows about (path optional — user may browse later)."""
    try:
        from kalium.game_finder.known_games import KNOWN_GAMES

        out: list[ManagedGameChoice] = []
        for g in KNOWN_GAMES:
            out.append(
                ManagedGameChoice(
                    display_name=g.name,
                    mo2_game_name=normalize_mo2_game_name(g.name),
                    install_path=None,
                    source="known",
                )
            )
        return out
    except Exception:
        # Minimal fallback if known_games is unavailable
        names = [
            "Skyrim Special Edition",
            "Skyrim",
            "Skyrim VR",
            "Fallout 4",
            "Fallout New Vegas",
            "Fallout 3",
            "Enderal Special Edition",
            "Starfield",
            "Oblivion",
            "Morrowind",
            "Cyberpunk 2077",
            "The Witcher 3",
            "Baldur's Gate 3",
        ]
        return [
            ManagedGameChoice(n, normalize_mo2_game_name(n), None, "known") for n in names
        ]


def detect_managed_game_choices() -> list[ManagedGameChoice]:
    """Detected installs first, then known templates without a path."""
    choices: list[ManagedGameChoice] = []
    seen_names: set[str] = set()

    try:
        from kalium.game_finder import detect_all_games

        result = detect_all_games()
        for g in getattr(result, "games", []) or []:
            path = getattr(g, "install_path", None)
            name = getattr(g, "name", "") or "Unknown"
            if not path or not Path(path).exists():
                continue
            mo2_name = normalize_mo2_game_name(name)
            key = mo2_name.lower()
            if key in seen_names:
                continue
            seen_names.add(key)
            launcher = getattr(g, "launcher", None)
            source = getattr(launcher, "kind", "") if launcher else "detected"
            choices.append(
                ManagedGameChoice(
                    display_name=f"{name}  ({path})",
                    mo2_game_name=mo2_name,
                    install_path=Path(path),
                    source=str(source),
                )
            )
    except Exception as e:
        log_warning(f"Game auto-detect failed: {e}")

    for t in list_known_game_templates():
        if t.mo2_game_name.lower() not in seen_names:
            choices.append(
                ManagedGameChoice(
                    display_name=f"{t.display_name}  (pick folder…)",
                    mo2_game_name=t.mo2_game_name,
                    install_path=None,
                    source="known",
                )
            )
    return choices


def set_mo2_managed_game(
    mo2_install_path: Path,
    game_name: str,
    game_path: Path | str,
    *,
    create_if_missing: bool = True,
) -> bool:
    """
    Write [General] gameName= and gamePath= into ModOrganizer.ini.

    Returns True if the ini was written/updated.
    """
    mo2_install_path = Path(mo2_install_path)
    ini = mo2_install_path / "ModOrganizer.ini"
    game_path = Path(game_path).expanduser()
    if not game_path.is_dir():
        raise ValueError(f"Game folder does not exist: {game_path}")

    mo2_name = normalize_mo2_game_name(game_name)
    wine_path = linux_path_to_wine_z(game_path)
    # Prefer plain path; MO2/Qt accept both. ByteArray form is more common on Windows saves.
    path_value = _qt_bytearray_path(wine_path)

    if not ini.is_file():
        if not create_if_missing:
            log_warning("ModOrganizer.ini not found — cannot set managed game yet.")
            return False
        content = (
            "[General]\n"
            f"gameName={mo2_name}\n"
            f"gamePath={path_value}\n"
            "first_start=false\n"
            "\n"
            "[Settings]\n"
            "style=dracula.qss\n"
        )
        ini.write_text(content, encoding="utf-8")
        log_install(f"Created ModOrganizer.ini — gameName={mo2_name} gamePath={wine_path}")
        return True

    text = ini.read_text(encoding="utf-8", errors="replace")
    if ini.is_file():
        shutil.copy2(ini, ini.with_suffix(".ini.kalium.bak"))

    def _set_general_key(content: str, key: str, value: str) -> str:
        # Inside [General] section preferably
        pat = rf"(?im)^({key}\s*=).*$"
        if re.search(pat, content):
            return re.sub(pat, rf"\g<1>{value}", content, count=1)
        if re.search(r"(?im)^\[General\]\s*$", content):
            return re.sub(
                r"(?im)^(\[General\]\s*\n)",
                rf"\1{key}={value}\n",
                content,
                count=1,
            )
        return content.rstrip() + f"\n\n[General]\n{key}={value}\n"

    new_text = text
    new_text = _set_general_key(new_text, "gameName", mo2_name)
    new_text = _set_general_key(new_text, "gamePath", path_value)
    # Avoid forced first-run wizard when we already bound a game
    if re.search(r"(?im)^first_start\s*=", new_text):
        new_text = re.sub(r"(?im)^(first_start\s*=).*$", r"\g<1>false", new_text, count=1)
    else:
        new_text = _set_general_key(new_text, "first_start", "false")

    if new_text != text:
        ini.write_text(new_text, encoding="utf-8")
    log_install(f"MO2 managed game set: gameName={mo2_name} gamePath={wine_path}")
    return True


def read_mo2_managed_game(mo2_install_path: Path) -> tuple[Optional[str], Optional[str]]:
    """Return (gameName, gamePath raw) from ini if present."""
    ini = Path(mo2_install_path) / "ModOrganizer.ini"
    if not ini.is_file():
        return None, None
    text = ini.read_text(encoding="utf-8", errors="replace")
    name = None
    path = None
    m = re.search(r"(?im)^\s*gameName\s*=\s*(.+?)\s*$", text)
    if m:
        name = m.group(1).strip().strip('"')
    m = re.search(r"(?im)^\s*gamePath\s*=\s*(.+?)\s*$", text)
    if m:
        raw = m.group(1).strip()
        # Strip @ByteArray(...)
        bm = re.match(r"@ByteArray\((.*)\)\s*$", raw)
        path = bm.group(1) if bm else raw.strip('"')
    return name, path
