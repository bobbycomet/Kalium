"""Winetricks / cabextract dependency management."""

from __future__ import annotations

import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Callable, Optional

import requests

from kalium.config import AppConfig
from kalium.logging_utils import log_error, log_info, log_install, log_warning
from kalium.steam.proton import SteamProton

STANDARD_VERBS = [
    "vcrun2022",
    "dotnet6",
    "dotnet7",
    "dotnet8",
    "dotnetdesktop6",
    "d3dcompiler_47",
    "d3dcompiler_43",
    "d3dx9",
    "d3dx11_43",
    "xact",
    "xact_x64",
]

WINETRICKS_URL = "https://raw.githubusercontent.com/Winetricks/winetricks/master/src/winetricks"
CABEXTRACT_URL = "https://github.com/SulfurNitride/NaK/releases/download/Cabextract/cabextract-linux-x86_64.zip"
MAX_DOWNLOAD = 10 * 1024 * 1024


def get_nak_bin_path() -> Path:
    return AppConfig.bin_path()


def check_command_available(cmd: str) -> bool:
    if shutil.which(cmd):
        return True
    return (get_nak_bin_path() / cmd).exists()


def get_winetricks_path() -> Path:
    return get_nak_bin_path() / "winetricks"


def ensure_winetricks() -> Path:
    bin_dir = get_nak_bin_path()
    bin_dir.mkdir(parents=True, exist_ok=True)
    path = bin_dir / "winetricks"
    log_info("Checking for winetricks updates...")
    try:
        r = requests.get(WINETRICKS_URL, timeout=60)
        r.raise_for_status()
        if len(r.content) > MAX_DOWNLOAD:
            raise RuntimeError("Winetricks download too large")
        content = r.content
        should = True
        if path.exists():
            should = path.read_bytes() != content
        if should:
            path.write_bytes(content)
            path.chmod(0o755)
            log_info("Winetricks updated")
    except Exception as e:
        if path.exists():
            log_warning(f"Failed to update winetricks: {e}")
        else:
            raise RuntimeError(f"Failed to download winetricks: {e}") from e
    return path


def ensure_cabextract() -> Path:
    if shutil.which("cabextract"):
        return Path("cabextract")
    bin_dir = get_nak_bin_path()
    dest = bin_dir / "cabextract"
    if dest.exists():
        return dest
    log_warning("System cabextract not found, downloading...")
    bin_dir.mkdir(parents=True, exist_ok=True)
    r = requests.get(CABEXTRACT_URL, timeout=120)
    r.raise_for_status()
    zip_path = bin_dir / "cabextract.zip"
    zip_path.write_bytes(r.content)
    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(bin_dir)
    finally:
        zip_path.unlink(missing_ok=True)
    if not dest.exists():
        # maybe nested
        for p in bin_dir.rglob("cabextract"):
            if p.is_file():
                shutil.move(str(p), str(dest))
                break
    if not dest.exists():
        raise RuntimeError("Failed to extract cabextract")
    dest.chmod(0o755)
    log_info(f"cabextract downloaded to {dest}")
    return dest


def run_winetricks(
    prefix_path: Path,
    proton: SteamProton,
    verbs: list[str],
    log_callback: Optional[Callable[[str], None]] = None,
    cancel_flag: Optional[Callable[[], bool]] = None,
) -> None:
    if not verbs:
        return
    cb = log_callback or (lambda m: None)
    wt = ensure_winetricks()
    ensure_cabextract()
    wine = proton.wine_binary()
    wineserver = proton.wineserver_binary()
    if not wine or not wineserver:
        raise RuntimeError("Wine/wineserver not found in Proton")
    cache = AppConfig.default_cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    nak_bin = str(get_nak_bin_path())
    path_env = nak_bin + os.pathsep + os.environ.get("PATH", "")
    env = os.environ.copy()
    env.update(
        {
            "PATH": path_env,
            "WINE": str(wine),
            "WINESERVER": str(wineserver),
            "WINEPREFIX": str(prefix_path),
            "WINETRICKS_CACHE": str(cache),
        }
    )
    msg = f"Installing dependencies via winetricks: {' '.join(verbs)}"
    cb(msg)
    log_install(msg)
    proc = subprocess.Popen([str(wt), "-q", *verbs], env=env)
    while True:
        ret = proc.poll()
        if ret is not None:
            if ret != 0:
                raise RuntimeError(f"Winetricks failed with exit code {ret}")
            log_install("Winetricks completed successfully")
            return
        if cancel_flag and cancel_flag():
            proc.kill()
            proc.wait()
            raise RuntimeError("Cancelled")
        import time

        time.sleep(0.25)


def install_standard_deps(
    prefix_path: Path,
    proton: SteamProton,
    log_callback: Optional[Callable[[str], None]] = None,
    cancel_flag: Optional[Callable[[], bool]] = None,
) -> None:
    run_winetricks(prefix_path, proton, STANDARD_VERBS, log_callback, cancel_flag)
