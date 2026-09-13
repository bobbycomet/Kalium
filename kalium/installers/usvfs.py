"""Portable USVFS update for Kalium MO2 instances.

MO2 2.5.2 ships usvfs 0.5.6.x. On Wine/Proton 10.20+ that version can
duplicate virtual folders (visible in Explore Virtual Folder), which slows
game launches dramatically. Upstream usvfs 0.5.7.2 fixes it.

The release archive has a ``bin/`` directory with:
  usvfs_x64.dll, usvfs_x86.dll, usvfs_proxy_x64.exe, usvfs_proxy_x86.exe
These are copied into the MO2 install root (next to ModOrganizer.exe).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

import py7zr
import requests

from kalium.config import AppConfig
from kalium.installers.task import TaskContext
from kalium.logging_utils import log_install, log_warning
from kalium.utils import download_file

# Pinned release known to fix the Wine 10.20+ duplication / slow-boot issue.
USVFS_VERSION = "0.5.7.2"
USVFS_RELEASE_URL = (
    f"https://github.com/ModOrganizer2/usvfs/releases/download/"
    f"v{USVFS_VERSION}/usvfs_v{USVFS_VERSION}.7z"
)
USVFS_ASSET_NAME = f"usvfs_v{USVFS_VERSION}.7z"

# Files that live next to ModOrganizer.exe after a normal MO2 install.
USVFS_BIN_FILES = (
    "usvfs_x64.dll",
    "usvfs_x86.dll",
    "usvfs_proxy_x64.exe",
    "usvfs_proxy_x86.exe",
)


def fetch_usvfs_asset() -> dict:
    """Return asset metadata for the pinned USVFS release (download URL + name)."""
    # Prefer the fixed URL so we don't depend on "latest" changing meaning.
    return {
        "name": USVFS_ASSET_NAME,
        "browser_download_url": USVFS_RELEASE_URL,
        "tag": USVFS_VERSION,
    }


def install_usvfs(
    mo2_install_path: Path,
    ctx: Optional[TaskContext] = None,
    *,
    backup: bool = True,
) -> Path:
    """
    Download usvfs 0.5.7.2 and overwrite the binaries in the MO2 root.

    Returns the MO2 install path (for convenience).
    Raises on hard failures (network, missing extract, etc.).
    """

    def status(msg: str) -> None:
        log_install(msg)
        if ctx:
            ctx.set_status(msg)
            ctx.log(msg)

    mo2_install_path = Path(mo2_install_path)
    if not (mo2_install_path / "ModOrganizer.exe").is_file():
        raise RuntimeError(
            f"ModOrganizer.exe not found in {mo2_install_path} — "
            "point at the MO2 instance root."
        )

    status(f"Downloading USVFS {USVFS_VERSION}...")
    asset = fetch_usvfs_asset()
    tmp = AppConfig.tmp_path()
    tmp.mkdir(parents=True, exist_ok=True)
    archive = tmp / asset["name"]
    download_file(asset["browser_download_url"], archive)

    extract_root = tmp / f"usvfs_extract_{USVFS_VERSION}"
    if extract_root.exists():
        shutil.rmtree(extract_root, ignore_errors=True)
    extract_root.mkdir(parents=True, exist_ok=True)

    status("Extracting USVFS...")
    with py7zr.SevenZipFile(archive, mode="r") as z:
        z.extractall(path=extract_root)
    archive.unlink(missing_ok=True)

    # Prefer bin/ next to archive root; fall back to any nested bin/.
    bin_dir = extract_root / "bin"
    if not bin_dir.is_dir():
        candidates = list(extract_root.rglob("usvfs_x64.dll"))
        if not candidates:
            raise RuntimeError("usvfs_x64.dll not found in USVFS archive")
        bin_dir = candidates[0].parent

    missing = [f for f in USVFS_BIN_FILES if not (bin_dir / f).is_file()]
    if missing:
        raise RuntimeError(f"USVFS archive missing expected files: {missing}")

    if backup:
        bak_dir = mo2_install_path / f".kalium_usvfs_backup_{USVFS_VERSION}"
        bak_dir.mkdir(parents=True, exist_ok=True)
        for name in USVFS_BIN_FILES:
            src = mo2_install_path / name
            if src.is_file():
                shutil.copy2(src, bak_dir / name)
        status(f"Backed up previous USVFS binaries → {bak_dir}")

    for name in USVFS_BIN_FILES:
        src = bin_dir / name
        dest = mo2_install_path / name
        shutil.copy2(src, dest)
        # Ensure the DLLs/exes are readable/executable by Wine
        try:
            dest.chmod(dest.stat().st_mode | 0o755)
        except OSError:
            pass

    # Clean extract tree
    shutil.rmtree(extract_root, ignore_errors=True)

    status(f"USVFS {USVFS_VERSION} installed into {mo2_install_path}")
    return mo2_install_path


def install_usvfs_safe(
    mo2_install_path: Path,
    ctx: Optional[TaskContext] = None,
    *,
    backup: bool = True,
) -> bool:
    """
    Same as install_usvfs but never raises into the caller.
    Returns True on success, False on failure (logged).
    """
    try:
        install_usvfs(mo2_install_path, ctx, backup=backup)
        return True
    except Exception as e:
        log_warning(f"USVFS update failed: {e}")
        if ctx:
            ctx.log(f"USVFS update failed: {e}")
        return False
