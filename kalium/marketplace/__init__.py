"""Marketplace plugins + MO2 Collections (Nexus site mod 1541) support.

Drop-in replacement for kalium/marketplace/__init__.py (or merge these changes).

Improvements vs previous:
  - Clearer install result (paths written, file count)
  - Smarter zip/7z layout handling (nested single folder, lone .py → folder)
  - Explicit errors when nothing useful lands in plugins/
  - Sync Plugins (#47325) and similar Python plugins install more reliably
"""

from __future__ import annotations

import json
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import py7zr
import requests

from kalium.config import AppConfig
from kalium.logging_utils import log_download, log_info, log_install, log_warning
from kalium.utils import download_file

COLLECTIONS_MOD_ID = 1541
COLLECTIONS_GAME_DOMAIN = "site"
NEXUS_API = "https://api.nexusmods.com/v1"

_NEXUS_MOD_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?nexusmods\.com/"
    r"(?:games/)?(?P<domain>[a-z0-9_]+)/mods/(?P<mod_id>\d+)",
    re.IGNORECASE,
)


@dataclass
class PluginInfo:
    id: str
    name: str
    description: str
    author: str = ""
    version: str = ""
    download_url: str = ""
    install_type: str = "archive-7z"
    exe_name: str = ""
    compatible: bool = True
    source: str = "builtin"
    nexus_domain: str = ""
    nexus_mod_id: int = 0


@dataclass
class PluginInstallResult:
    plugins_dir: Path
    installed_paths: list[Path]
    plugin_name: str
    version: str
    message: str


BUILTIN_PLUGINS = [
    PluginInfo(
        id="mo2-collections",
        name="MO2 Collections Support",
        description="Adds Collections downloading/installing to Mod Organizer 2. Nexus site mod #1541.",
        author="Nexus Mods community",
        version="latest",
        install_type="archive-zip",
        source="nexus",
        nexus_domain="site",
        nexus_mod_id=1541,
    ),
    PluginInfo(
        id="nmc-nexus-mod-checker",
        name="NMC Nexus Mod Checker for MO2",
        description="Online status, multi-endorsement, auto version fixer, download list generator. Site mod #1899.",
        author="Kronprinz77",
        version="latest",
        install_type="archive-zip",
        source="nexus",
        nexus_domain="site",
        nexus_mod_id=1899,
    ),
]


def list_plugins() -> list[PluginInfo]:
    plugins = list(BUILTIN_PLUGINS)
    try:
        r = requests.get(
            "https://raw.githubusercontent.com/SulfurNitride/NaK/main/marketplace/registry.json",
            timeout=15,
            headers={"User-Agent": "Kalium/1.0"},
        )
        if r.status_code == 200:
            data = r.json()
            for item in data if isinstance(data, list) else data.get("plugins", []):
                plugins.append(
                    PluginInfo(
                        id=str(item.get("id", item.get("name", "plugin"))),
                        name=item.get("name", "Plugin"),
                        description=item.get("description", ""),
                        author=item.get("author", ""),
                        version=item.get("version", ""),
                        download_url=item.get("download_url", ""),
                        install_type=item.get("install_type", "archive-7z"),
                        exe_name=item.get("exe_name", ""),
                        source="registry",
                        nexus_domain=str(item.get("nexus_domain", "") or ""),
                        nexus_mod_id=int(item.get("nexus_mod_id", 0) or 0),
                    )
                )
    except Exception:
        pass
    return plugins


def nexus_headers(api_key: str) -> dict:
    return {
        "User-Agent": "Kalium/1.0 (Linux; by Bobby Comet)",
        "apikey": api_key,
        "Accept": "application/json",
    }


def parse_nexus_mod_url(url_or_text: str) -> Optional[tuple[str, int]]:
    s = (url_or_text or "").strip()
    if not s:
        return None
    m = _NEXUS_MOD_URL_RE.search(s)
    if m:
        return m.group("domain").lower(), int(m.group("mod_id"))
    m2 = re.search(r"(?i)([a-z0-9_]+)/mods/(\d+)", s)
    if m2:
        return m2.group(1).lower(), int(m2.group(2))
    return None


def resolve_nexus_download(api_key: str, game_domain: str, mod_id: int) -> tuple[str, str, str]:
    if not api_key:
        raise RuntimeError("Nexus API key required (https://www.nexusmods.com/settings/api-keys).")
    if not game_domain or not mod_id:
        raise RuntimeError("Nexus game domain and mod id are required")
    headers = nexus_headers(api_key)
    mod_name = f"mod_{mod_id}"
    try:
        rm = requests.get(
            f"{NEXUS_API}/games/{game_domain}/mods/{mod_id}.json",
            headers=headers,
            timeout=30,
        )
        if rm.status_code == 401:
            raise RuntimeError("Invalid Nexus API key")
        if rm.status_code == 200:
            mod_name = str(rm.json().get("name") or mod_name)
    except RuntimeError:
        raise
    except Exception:
        pass
    r = requests.get(
        f"{NEXUS_API}/games/{game_domain}/mods/{mod_id}/files.json",
        headers=headers,
        timeout=30,
    )
    if r.status_code == 401:
        raise RuntimeError("Invalid Nexus API key")
    if r.status_code == 404:
        raise RuntimeError(f"Nexus mod not found: {game_domain}/mods/{mod_id}")
    r.raise_for_status()
    files = r.json()
    file_list = files if isinstance(files, list) else files.get("files", [])
    if not file_list:
        raise RuntimeError(f"No files found for {game_domain}/mods/{mod_id}")

    def _sort_key(f: dict) -> tuple:
        cat = str(f.get("category_name") or f.get("category") or "").upper()
        is_main = 0 if cat in ("MAIN", "1", "PRIMARY") else 1
        return (is_main, -int(f.get("uploaded_timestamp") or 0))

    file_info = sorted(file_list, key=_sort_key)[0]
    file_id = file_info["file_id"]
    version = str(file_info.get("version") or file_info.get("mod_version") or "latest")
    r2 = requests.get(
        f"{NEXUS_API}/games/{game_domain}/mods/{mod_id}/files/{file_id}/download_link.json",
        headers=headers,
        timeout=30,
    )
    r2.raise_for_status()
    links = r2.json()
    if isinstance(links, list) and links:
        url = links[0].get("URI") or links[0].get("uri")
    elif isinstance(links, dict):
        url = links.get("URI") or links.get("uri")
    else:
        url = None
    if not url:
        raise RuntimeError("Could not resolve Nexus download link")
    return url, version, mod_name


def resolve_collections_download(api_key: str) -> tuple[str, str]:
    url, version, _ = resolve_nexus_download(api_key, COLLECTIONS_GAME_DOMAIN, COLLECTIONS_MOD_ID)
    return url, version


def plugin_from_nexus_url(url: str, api_key: str = "") -> PluginInfo:
    parsed = parse_nexus_mod_url(url)
    if not parsed:
        raise RuntimeError("Not a recognized Nexus Mods URL.")
    domain, mod_id = parsed
    name = f"Nexus {domain} #{mod_id}"
    description = f"Installed from https://www.nexusmods.com/{domain}/mods/{mod_id}"
    if api_key:
        try:
            rm = requests.get(
                f"{NEXUS_API}/games/{domain}/mods/{mod_id}.json",
                headers=nexus_headers(api_key),
                timeout=20,
            )
            if rm.status_code == 200:
                data = rm.json()
                name = str(data.get("name") or name)
                description = str(data.get("summary") or data.get("description") or description)[:400]
        except Exception:
            pass
    return PluginInfo(
        id=f"nexus-{domain}-{mod_id}",
        name=name,
        description=description,
        version="latest",
        install_type="archive-zip",
        source="nexus",
        nexus_domain=domain,
        nexus_mod_id=mod_id,
    )


def _looks_like_plugin_payload(path: Path) -> bool:
    """Heuristic: MO2 plugins are folders with __init__.py / .py, or loose .dll/.py."""
    if path.is_file():
        return path.suffix.lower() in (".py", ".dll", ".so", ".json", ".ini", ".txt", ".md")
    if not path.is_dir():
        return False
    names = {p.name.lower() for p in path.iterdir()}
    if "__init__.py" in names or any(n.endswith(".py") for n in names):
        return True
    if any(n.endswith(".dll") for n in names):
        return True
    # Nested one level
    try:
        for child in path.iterdir():
            if child.is_dir() and (child / "__init__.py").is_file():
                return True
    except OSError:
        pass
    return False


def _safe_write_member(plugins_dir: Path, relative: str, data: bytes) -> Optional[Path]:
    name = relative.replace("\\", "/").lstrip("/")
    if not name or name.startswith("__MACOSX") or name.endswith("/"):
        if name.endswith("/"):
            target = (plugins_dir / name).resolve()
            if str(target).startswith(str(plugins_dir.resolve())):
                target.mkdir(parents=True, exist_ok=True)
        return None
    target = (plugins_dir / name).resolve()
    if not str(target).startswith(str(plugins_dir.resolve())):
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


def _extract_archive_to_plugins(archive: Path, plugins_dir: Path) -> list[Path]:
    """Extract archive into plugins_dir; return top-level paths that were created/updated."""
    plugins_dir = plugins_dir.resolve()
    plugins_dir.mkdir(parents=True, exist_ok=True)
    staging = AppConfig.tmp_path() / f"plugin_stage_{archive.stem}"
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)

    if archive.suffix.lower() == ".7z":
        with py7zr.SevenZipFile(archive, mode="r") as z:
            z.extractall(path=staging)
    elif archive.suffix.lower() == ".zip":
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                name = (info.filename or "").replace("\\", "/").lstrip("/")
                if not name or name.startswith("__MACOSX"):
                    continue
                target = (staging / name).resolve()
                if not str(target).startswith(str(staging.resolve())):
                    continue
                if name.endswith("/") or info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src:
                    target.write_bytes(src.read())
    else:
        raise RuntimeError(f"Unsupported archive type: {archive.suffix}")

    entries = [p for p in staging.iterdir() if p.name not in (".DS_Store", "__MACOSX")]
    installed: list[Path] = []

    def _copy_into(src: Path, dest: Path) -> None:
        if dest.exists():
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()
        if src.is_dir():
            shutil.copytree(src, dest)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        installed.append(dest)

    if not entries:
        shutil.rmtree(staging, ignore_errors=True)
        raise RuntimeError(f"Archive extracted empty: {archive.name}")

    # Single nested folder → install as that plugin folder name
    if len(entries) == 1 and entries[0].is_dir():
        src = entries[0]
        dest = plugins_dir / src.name
        _copy_into(src, dest)
    # Single .py file → wrap in a folder named after the plugin stem
    elif len(entries) == 1 and entries[0].is_file() and entries[0].suffix.lower() == ".py":
        folder_name = re.sub(r"[^\w\-]+", "_", entries[0].stem) or "plugin"
        dest = plugins_dir / folder_name
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(entries[0], dest / entries[0].name)
        installed.append(dest)
    # Multiple root files (common for simple plugins) → one folder from archive stem
    elif all(e.is_file() for e in entries):
        folder_name = re.sub(r"\.[0-9]+(\.[0-9]+)*$", "", archive.stem) or archive.stem
        folder_name = re.sub(r"[^\w\-]+", "_", folder_name) or "plugin"
        dest = plugins_dir / folder_name
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)
        for e in entries:
            shutil.copy2(e, dest / e.name)
        installed.append(dest)
    else:
        for e in entries:
            dest = plugins_dir / e.name
            _copy_into(e, dest)

    shutil.rmtree(staging, ignore_errors=True)

    if not installed:
        raise RuntimeError("Nothing was installed into the plugins folder")

    # Sanity: at least one path should look like a plugin payload
    if not any(_looks_like_plugin_payload(p) for p in installed):
        log_warning(
            "Installed paths may not look like MO2 plugins "
            f"({', '.join(str(p.name) for p in installed)}). "
            "Check the archive layout on the Nexus page."
        )

    return installed


def install_plugin_into_mo2(
    plugin: PluginInfo,
    mo2_path: Path,
    api_key: str = "",
    progress: Optional[callable] = None,
) -> PluginInstallResult:
    if not mo2_path.exists():
        raise RuntimeError(f"MO2 path does not exist: {mo2_path}")
    if not (mo2_path / "ModOrganizer.exe").is_file():
        raise RuntimeError(f"ModOrganizer.exe not found in {mo2_path}")
    plugins_dir = mo2_path / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)
    url = plugin.download_url
    version = plugin.version
    is_nexus = plugin.source == "nexus" or bool(plugin.nexus_mod_id) or plugin.id == "mo2-collections"
    if is_nexus:
        domain = plugin.nexus_domain or (
            COLLECTIONS_GAME_DOMAIN if plugin.id == "mo2-collections" else ""
        )
        mod_id = plugin.nexus_mod_id or (COLLECTIONS_MOD_ID if plugin.id == "mo2-collections" else 0)
        if not domain or not mod_id:
            raise RuntimeError(f"Plugin '{plugin.name}' missing Nexus domain/mod_id")
        url, version, resolved_name = resolve_nexus_download(api_key, domain, mod_id)
        if not plugin.name or plugin.name.startswith("Nexus "):
            plugin.name = resolved_name
        log_info(f"Resolved Nexus download {domain}/{mod_id} v{version}: {plugin.name}")
    if not url:
        raise RuntimeError("No download URL for plugin")
    tmp = AppConfig.tmp_path()
    tmp.mkdir(parents=True, exist_ok=True)
    path_part = urlparse(url).path.lower()
    ext = ".zip"
    if ".7z" in path_part:
        ext = ".7z"
    archive = tmp / f"plugin_{plugin.id}{ext}"
    if progress:
        progress(0.2)
    log_download(f"Downloading plugin {plugin.name}...")
    download_file(url, archive)
    if progress:
        progress(0.6)
    if archive.suffix.lower() not in (".zip", ".7z"):
        head = archive.read_bytes()[:6]
        if head[:2] == b"PK":
            archive = archive.rename(archive.with_suffix(".zip"))
        elif head[:2] == b"7z" or head[:6] == b"7z\xbc\xaf'\x1c"[:6]:
            archive = archive.rename(archive.with_suffix(".7z"))
    installed_paths = _extract_archive_to_plugins(archive, plugins_dir)
    archive.unlink(missing_ok=True)
    if progress:
        progress(1.0)
    names = ", ".join(p.name for p in installed_paths)
    msg = f"Installed {plugin.name} v{version} → {plugins_dir} ({names})"
    log_install(msg)
    state = AppConfig.config_dir() / "installed_plugins.json"
    installed = []
    if state.exists():
        try:
            installed = json.loads(state.read_text(encoding="utf-8"))
        except Exception:
            installed = []
    installed = [p for p in installed if p.get("id") != plugin.id]
    installed.append(
        {
            "id": plugin.id,
            "name": plugin.name,
            "version": version,
            "path": str(plugins_dir),
            "items": [str(p) for p in installed_paths],
            "nexus_domain": plugin.nexus_domain,
            "nexus_mod_id": plugin.nexus_mod_id,
        }
    )
    state.write_text(json.dumps(installed, indent=2), encoding="utf-8")
    return PluginInstallResult(
        plugins_dir=plugins_dir,
        installed_paths=installed_paths,
        plugin_name=plugin.name,
        version=version,
        message=msg,
    )


def install_nexus_url_into_mo2(
    nexus_url: str,
    mo2_path: Path,
    api_key: str = "",
    progress: Optional[callable] = None,
) -> PluginInstallResult:
    plugin = plugin_from_nexus_url(nexus_url, api_key=api_key)
    return install_plugin_into_mo2(plugin, mo2_path, api_key=api_key, progress=progress)


def _safe_extract_zip(archive: Path, dest: Path) -> list[Path]:
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            if not info.filename or info.filename.startswith("__MACOSX"):
                continue
            name = info.filename.replace("\\", "/").lstrip("/")
            if not name or name.endswith("/"):
                target = (dest / name).resolve()
                if str(target).startswith(str(dest)):
                    target.mkdir(parents=True, exist_ok=True)
                continue
            target = (dest / name).resolve()
            if not str(target).startswith(str(dest)):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(target, "wb") as out:
                out.write(src.read())
            top = dest / name.split("/")[0]
            if top not in created:
                created.append(top)
    return created


def install_github_zip_into_mo2(
    zip_url: str,
    mo2_path: Path,
    progress: Optional[callable] = None,
) -> PluginInstallResult:
    zip_url = (zip_url or "").strip()
    if not zip_url.startswith(("http://", "https://")):
        raise RuntimeError("URL must start with http:// or https://")
    if not (mo2_path / "ModOrganizer.exe").exists():
        raise RuntimeError(f"ModOrganizer.exe not found in {mo2_path}")
    plugins_dir = mo2_path / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)
    tmp = AppConfig.tmp_path()
    tmp.mkdir(parents=True, exist_ok=True)
    fname = zip_url.rstrip("/").rsplit("/", 1)[-1].split("?", 1)[0] or "plugin.zip"
    if not fname.lower().endswith(".zip"):
        fname += ".zip"
    archive = tmp / fname
    if progress:
        progress(0.15)
    log_download(f"Downloading plugin zip: {zip_url}")
    r = requests.get(
        zip_url,
        headers={"User-Agent": "Kalium/1.0", "Accept": "application/octet-stream,*/*"},
        timeout=180,
        stream=True,
        allow_redirects=True,
    )
    r.raise_for_status()
    with open(archive, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 256):
            if chunk:
                f.write(chunk)
    if progress:
        progress(0.55)
    if not zipfile.is_zipfile(archive):
        archive.unlink(missing_ok=True)
        raise RuntimeError("Downloaded file is not a valid .zip")
    installed_paths = _extract_archive_to_plugins(archive, plugins_dir)
    archive.unlink(missing_ok=True)
    if progress:
        progress(1.0)
    names = ", ".join(p.name for p in installed_paths)
    msg = f"Installed GitHub plugin → {plugins_dir} ({names})"
    log_install(msg)
    return PluginInstallResult(
        plugins_dir=plugins_dir,
        installed_paths=installed_paths,
        plugin_name=names,
        version="",
        message=msg,
    )
