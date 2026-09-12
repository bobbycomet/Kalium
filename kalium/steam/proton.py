"""Detect Steam Proton versions (10+)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from kalium.logging_utils import log_info, log_warning
from kalium.steam.paths import find_steam_path


@dataclass
class SteamProton:
    name: str
    config_name: str
    path: Path
    is_steam_proton: bool = False
    is_experimental: bool = False

    def wine_binary(self) -> Optional[Path]:
        for rel in ("files/bin/wine", "dist/bin/wine"):
            p = self.path / rel
            if p.exists():
                return p
        return None

    def wineserver_binary(self) -> Optional[Path]:
        for rel in ("files/bin/wineserver", "dist/bin/wineserver"):
            p = self.path / rel
            if p.exists():
                return p
        return None

    def bin_dir(self) -> Optional[Path]:
        w = self.wine_binary()
        return w.parent if w else None


def _is_proton_10_or_newer(p: SteamProton) -> bool:
    name = p.name
    if p.is_experimental or "Experimental" in name:
        return True
    if "CachyOS" in name or "cachy" in name.lower():
        return True
    if "Runtime" in name or name == "LegacyRuntime":
        return False
    m = re.match(r"GE-Proton[^0-9]*(\d+)", name)
    if m:
        return int(m.group(1)) >= 10
    m = re.match(r"Proton\s+(\d+)", name)
    if m:
        return int(m.group(1)) >= 10
    m = re.match(r"EM-(\d+)", name)
    if m:
        return int(m.group(1)) >= 10
    return True


def _scan_dir(directory: Path, is_steam: bool) -> list[SteamProton]:
    found: list[SteamProton] = []
    if not directory.is_dir():
        return found
    try:
        entries = list(directory.iterdir())
    except OSError:
        return found
    for entry in entries:
        if not entry.is_dir():
            continue
        name = entry.name
        has_proton = (entry / "proton").exists()
        has_vdf = (entry / "compatibilitytool.vdf").exists()
        if is_steam:
            if not (name.startswith("Proton") and has_proton):
                continue
            is_exp = "Experimental" in name
            if is_exp:
                config_name = "proton_experimental"
            else:
                version = name.replace("Proton ", "")
                major = version.split(".")[0]
                config_name = f"proton_{major}"
            found.append(
                SteamProton(
                    name=name,
                    config_name=config_name,
                    path=entry,
                    is_steam_proton=True,
                    is_experimental=is_exp,
                )
            )
        else:
            if not (has_proton or has_vdf):
                continue
            found.append(
                SteamProton(
                    name=name,
                    config_name=name,
                    path=entry,
                    is_steam_proton=False,
                    is_experimental=False,
                )
            )
    return found


def find_steam_protons() -> list[SteamProton]:
    steam = find_steam_path()
    if not steam:
        return []
    is_flatpak = ".var/app/com.valvesoftware.Steam" in str(steam)
    protons: list[SteamProton] = []
    protons.extend(_scan_dir(steam / "steamapps" / "common", is_steam=True))
    protons.extend(_scan_dir(steam / "compatibilitytools.d", is_steam=False))
    if not is_flatpak:
        protons.extend(_scan_dir(Path("/usr/share/steam/compatibilitytools.d"), is_steam=False))
    else:
        log_info("Flatpak Steam detected — skipping system protons")

    protons = [p for p in protons if _is_proton_10_or_newer(p)]
    filtered = []
    for p in protons:
        if p.wine_binary():
            filtered.append(p)
        else:
            log_warning(f"Skipping Proton '{p.name}': wine binary not found")
    filtered.sort(key=lambda p: (not p.is_experimental, p.name), reverse=True)
    return filtered
