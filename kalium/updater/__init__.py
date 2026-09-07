"""In-place updater (GitHub releases — bobbycomet/Kalium)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests
from packaging.version import Version

from kalium import __version__
from kalium.logging_utils import log_download, log_info

# Public release repository
GITHUB_REPO = "bobbycomet/Kalium"
RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases"
# Example asset (pattern used for releases):
# https://github.com/bobbycomet/Kalium/releases/download/v1.0.0/Kalium-1.0.0-x86_64.AppImage
ASSET_NAME_HINT = "Kalium-{version}-x86_64.AppImage"


@dataclass
class UpdateInfo:
    current_version: str
    latest_version: str
    download_url: Optional[str]
    release_notes: str
    is_update_available: bool
    releases_page: str = RELEASES_PAGE


def _pick_asset_url(assets: list, latest: str) -> Optional[str]:
    """Prefer Kalium-*-x86_64.AppImage from the release assets."""
    if not assets:
        return None
    scored: list[tuple[int, str]] = []
    for a in assets:
        name = (a.get("name") or "")
        url = a.get("browser_download_url") or ""
        if not url:
            continue
        lower = name.lower()
        score = 0
        if lower.endswith(".appimage"):
            score += 50
        if "kalium" in lower:
            score += 20
        if "x86_64" in lower or "x86-64" in lower or "amd64" in lower:
            score += 10
        if latest and latest in name:
            score += 5
        if lower.endswith(".zip") or lower.endswith(".tar.gz"):
            score += 5
        if score > 0:
            scored.append((score, url))
    if not scored:
        # fallback: first asset
        return assets[0].get("browser_download_url")
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def check_for_updates() -> UpdateInfo:
    """
    Query GitHub Releases API for bobbycomet/Kalium.

    Uses: GET https://api.github.com/repos/bobbycomet/Kalium/releases/latest
    Asset pattern: Kalium-<ver>-x86_64.AppImage under
      https://github.com/bobbycomet/Kalium/releases/download/v<ver>/
    """
    current = __version__
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        r = requests.get(
            url,
            headers={
                "User-Agent": f"Kalium/{current}",
                "Accept": "application/vnd.github+json",
            },
            timeout=30,
        )
        if r.status_code == 404:
            return UpdateInfo(
                current,
                current,
                None,
                "No releases published yet on GitHub.",
                False,
            )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        raise RuntimeError(f"Update check failed: {e}") from e

    tag = (data.get("tag_name") or "").strip()
    latest = tag.lstrip("vV")
    notes = data.get("body") or ""
    assets = data.get("assets") or []
    dl = _pick_asset_url(assets, latest)
    if not dl and latest:
        # Construct conventional AppImage URL if assets missing from API
        dl = (
            f"https://github.com/{GITHUB_REPO}/releases/download/"
            f"v{latest}/Kalium-{latest}-x86_64.AppImage"
        )

    newer = False
    try:
        newer = Version(latest) > Version(current)
    except Exception:
        newer = bool(latest) and latest != current

    return UpdateInfo(current, latest or current, dl, notes, newer)


def can_self_update() -> bool:
    try:
        exe = Path(sys.executable).resolve()
        parent = exe.parent
        test = parent / ".kalium_write_test"
        test.write_text("test")
        test.unlink()
        return True
    except Exception:
        return False


def install_update(download_url: str) -> Path:
    log_info(f"Downloading update: {download_url}")
    dest_dir = Path.home() / ".cache" / "kalium"
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = download_url.rstrip("/").rsplit("/", 1)[-1] or "Kalium-update.AppImage"
    dest = dest_dir / name
    r = requests.get(
        download_url,
        stream=True,
        timeout=300,
        headers={"User-Agent": f"Kalium/{__version__}"},
    )
    r.raise_for_status()
    with dest.open("wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 256):
            if chunk:
                f.write(chunk)
    dest.chmod(dest.stat().st_mode | 0o111)
    log_download(f"Update saved to {dest}")
    return dest
