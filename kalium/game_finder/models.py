"""Game / Launcher data models (no package-level imports — breaks circular deps)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class HeroicStore(str, Enum):
    GOG = "GOG"
    EPIC = "Epic"


@dataclass
class Launcher:
    kind: str  # steam, heroic, bottles
    is_flatpak: bool = False
    is_snap: bool = False
    store: Optional[str] = None

    def display_name(self) -> str:
        if self.kind == "steam":
            if self.is_flatpak:
                return "Steam (Flatpak)"
            if self.is_snap:
                return "Steam (Snap)"
            return "Steam"
        if self.kind == "heroic":
            return f"Heroic ({self.store or '?'})"
        return "Bottles"


@dataclass
class Game:
    name: str
    app_id: str
    install_path: Path
    prefix_path: Optional[Path] = None
    launcher: Launcher = field(default_factory=lambda: Launcher("steam"))
    my_games_folder: Optional[str] = None
    appdata_local_folder: Optional[str] = None
    appdata_roaming_folder: Optional[str] = None
    registry_path: Optional[str] = None
    registry_value: Optional[str] = None


@dataclass
class GameScanResult:
    games: list[Game] = field(default_factory=list)
    steam_count: int = 0
    heroic_count: int = 0
    bottles_count: int = 0
