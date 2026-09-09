"""MO2 download, extract, Steam-native install."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import py7zr
import requests

from kalium.config import AppConfig, ManagedPrefixes, ManagerType
from kalium.installers.prefix_setup import install_all_dependencies
from kalium.installers.ini_paths import set_vfs_max_memory
from kalium.installers.mo2_game import set_mo2_managed_game  # moved from .theme
from kalium.installers.theme import set_mo2_style
from kalium.installers.task import TaskContext
from kalium.installers.tools_scripts import create_kalium_tools
from kalium.installers.usvfs import install_usvfs_safe
from kalium.logging_utils import log_download, log_error, log_install, log_warning
from kalium.steam import add_mod_manager_shortcut, find_steam_path, remove_steam_shortcut, is_steam_running
from kalium.steam.proton import SteamProton
from kalium.utils import download_file


@dataclass
class Mo2InstallResult:
    app_id: int
    prefix_path: Path


def fetch_latest_mo2_release() -> dict:
    url = "https://api.github.com/repos/ModOrganizer2/modorganizer/releases/latest"
    r = requests.get(url, headers={"User-Agent": "Kalium/1.0"}, timeout=60)
    r.raise_for_status()
    return r.json()


def _cleanup(app_id: int, prefix: Path) -> None:
    log_warning(f"Cleaning up failed install AppID={app_id}")
    try:
        remove_steam_shortcut(app_id)
    except Exception as e:
        log_error(str(e))
    parent = prefix.parent
    if parent.exists():
        shutil.rmtree(parent, ignore_errors=True)
    ManagedPrefixes.unregister(app_id)


def install_mo2(
    install_name: str,
    install_path: Path,
    proton: SteamProton,
    ctx: TaskContext,
    skip_disk_check: bool = False,
    update_usvfs: bool = True,
    game_name: str | None = None,
    game_path: Path | str | None = None,
) -> Mo2InstallResult:
    log_install(f"Starting MO2 install: {install_name} -> {install_path}")
    steam = find_steam_path()
    if not steam:
        raise RuntimeError("Steam not found")
    if is_steam_running():
        log_warning(
            "Steam is running — shortcut may be overwritten when Steam exits. "
            "Prefer fully exiting Steam before install."
        )
        ctx.log(
            "Warning: Steam is running. Fully exit Steam after install so the non-Steam shortcut is kept."
        )

    ctx.set_status("Creating Steam shortcut...")
    ctx.set_progress(0.05)
    exe = install_path / "ModOrganizer.exe"
    steam_result = add_mod_manager_shortcut(
        install_name, str(exe), str(install_path), proton.config_name, None, False
    )
    try:
        return _do_install(
            install_name, install_path, proton, ctx, steam_result, steam, exe,
            update_usvfs=update_usvfs,
            game_name=game_name,
            game_path=game_path,
        )
    except Exception:
        _cleanup(steam_result.app_id, steam_result.prefix_path)
        raise


def _do_install(
    install_name,
    install_path,
    proton,
    ctx,
    steam_result,
    steam,
    exe,
    update_usvfs: bool = True,
    game_name: str | None = None,
    game_path: Path | str | None = None,
):
    install_path.mkdir(parents=True, exist_ok=True)
    ctx.set_status("Checking latest MO2...")
    release = fetch_latest_mo2_release()
    invalid = ("Linux", "pdbs", "src", "uibase", "commits")
    asset = next(
        (
            a for a in release.get("assets", [])
            if a["name"].startswith("Mod.Organizer-2")
            and a["name"].endswith(".7z")
            and not any(t in a["name"] for t in invalid)
        ),
        None,
    )
    if not asset:
        raise RuntimeError("No valid MO2 archive in release")
    ctx.set_status(f"Downloading {asset['name']}...")
    ctx.set_progress(0.10)
    tmp = AppConfig.tmp_path()
    tmp.mkdir(parents=True, exist_ok=True)
    archive = tmp / asset["name"]
    download_file(asset["browser_download_url"], archive)
    log_download(f"MO2 downloaded: {archive}")

    ctx.set_status("Extracting MO2...")
    ctx.set_progress(0.15)
    with py7zr.SevenZipFile(archive, mode="r") as z:
        z.extractall(path=install_path)
    archive.unlink(missing_ok=True)
    if not exe.exists():
        raise RuntimeError("ModOrganizer.exe not found after extract")

    if update_usvfs:
        ctx.set_status("Updating USVFS to 0.5.7.2 (Wine 10.20+ fix)...")
        install_usvfs_safe(install_path, ctx)

    install_all_dependencies(steam_result.prefix_path, proton, ctx, 0.20, 0.90, steam_result.app_id)
    create_kalium_tools(install_path, steam_result.prefix_path, steam_result.app_id, proton.path, "MO2")
    set_mo2_style(install_path)

    if game_name and game_path:
        try:
            set_mo2_managed_game(install_path, game_name, game_path, create_if_missing=True)
            # === AUTOMATIC Z: GAME PATH REGISTRATION (fixes the "instance does not exist" error) ===
            _register_wine_game_path(steam_result.prefix_path, Path(game_path).resolve(), "Z:/mnt/sdb1/skyrim")
            ctx.log(f"Managed game: {game_name} @ {game_path} (Z: path registered inside prefix)")
        except Exception as e:
            log_warning(f"Could not bind managed game to MO2 ini: {e}")
            ctx.log(f"Warning: managed game not set — {e}")

    set_vfs_max_memory(install_path)
    (install_path / ".kalium_steam.json").write_text(
        json.dumps(
            {"steam_app_id": steam_result.app_id, "created": datetime.now(timezone.utc).isoformat()},
            indent=2,
        ),
        encoding="utf-8",
    )
    ManagedPrefixes.register(
        steam_result.app_id,
        install_name,
        str(steam_result.prefix_path),
        str(install_path),
        ManagerType.MO2,
        str(steam),
        proton.config_name,
    )
    ctx.set_progress(1.0)
    vdf_hint = getattr(steam_result, "shortcuts_vdf", "") or ""
    msg = (
        f"MO2 Installed! AppID {steam_result.app_id}. "
        "Fully exit Steam (Steam → Exit), then start Steam again to see the non-Steam game."
    )
    if vdf_hint:
        msg += f" shortcuts.vdf: {vdf_hint}"
    ctx.set_status(msg)
    log_install(f"MO2 complete: {install_name} appid={steam_result.app_id} vdf={vdf_hint}")
    return Mo2InstallResult(steam_result.app_id, steam_result.prefix_path)


def setup_existing_mo2(
    install_name: str,
    existing_path: Path,
    proton: SteamProton,
    ctx: TaskContext,
    update_usvfs: bool = True,
    game_name: str | None = None,
    game_path: Path | str | None = None,
) -> Mo2InstallResult:
    exe = existing_path / "ModOrganizer.exe"
    if not exe.exists():
        raise RuntimeError(f"ModOrganizer.exe not found at {existing_path}")
    steam = find_steam_path()
    if not steam:
        raise RuntimeError("Steam not found")
    if is_steam_running():
        log_warning(
            "Steam is running — shortcut may be overwritten when Steam exits. "
            "Prefer fully exiting Steam before install."
        )
        ctx.log(
            "Warning: Steam is running. Fully exit Steam after install so the non-Steam shortcut is kept."
        )
    ctx.set_status("Creating Steam shortcut...")
    ctx.set_progress(0.05)
    steam_result = add_mod_manager_shortcut(
        install_name, str(exe), str(existing_path), proton.config_name, None, False
    )
    try:
        if update_usvfs:
            ctx.set_status("Updating USVFS to 0.5.7.2 (Wine 10.20+ fix)...")
            install_usvfs_safe(existing_path, ctx)
        install_all_dependencies(steam_result.prefix_path, proton, ctx, 0.10, 0.85, steam_result.app_id)
        create_kalium_tools(existing_path, steam_result.prefix_path, steam_result.app_id, proton.path, "MO2")
        set_mo2_style(existing_path)
        if game_name and game_path:
            try:
                set_mo2_managed_game(existing_path, game_name, game_path, create_if_missing=True)
                # === AUTOMATIC Z: GAME PATH REGISTRATION ===
                _register_wine_game_path(steam_result.prefix_path, Path(game_path).resolve(), "Z:/mnt/sdb1/skyrim")
                ctx.log(f"Managed game: {game_name} @ {game_path} (Z: path registered inside prefix)")
            except Exception as e:
                log_warning(f"Could not bind managed game to MO2 ini: {e}")
                ctx.log(f"Warning: managed game not set — {e}")
        set_vfs_max_memory(existing_path)
        ManagedPrefixes.register(
            steam_result.app_id,
            install_name,
            str(steam_result.prefix_path),
            str(existing_path),
            ManagerType.MO2,
            str(steam),
            proton.config_name,
        )
        ctx.set_progress(1.0)
        vdf_hint = getattr(steam_result, "shortcuts_vdf", "") or ""
        msg = (
            f"MO2 Setup Complete! AppID {steam_result.app_id}. "
            "Fully exit Steam (Steam → Exit), then start Steam again to see the non-Steam game."
        )
        if vdf_hint:
            msg += f" shortcuts.vdf: {vdf_hint}"
        ctx.set_status(msg)
        log_install(f"Existing MO2 setup complete appid={steam_result.app_id} vdf={vdf_hint}")
        return Mo2InstallResult(steam_result.app_id, steam_result.prefix_path)
    except Exception:
        _cleanup(steam_result.app_id, steam_result.prefix_path)
        raise


def _register_wine_game_path(prefix_path: Path, linux_game_path: Path, wine_game_path: str) -> None:
    """Register the game inside the Wine prefix using the Z: drive mapping (fixes the loop)."""
    wine = proton.wine_binary()
    if not wine:
        return

    tmp = Path("/tmp/.kalium_reg")
    tmp.mkdir(exist_ok=True)
    reg_file = tmp / "wine_game_path.reg"

    reg_content = f"""Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\\Software\\Bethesda Softworks\\Skyrim Special Edition]
"Installed Path"="{wine_game_path}"
"InstallFolder"="{wine_game_path}"
"InstallDir"="{wine_game_path}"

[HKEY_LOCAL_MACHINE\\SOFTWARE\\Wow6432Node\\Software\\Bethesda Softworks\\Skyrim Special Edition]
"Installed Path"="{wine_game_path}"
"InstallFolder"="{wine_game_path}"
"InstallDir"="{wine_game_path}"
"""
    reg_file.write_text(reg_content, encoding="utf-8")

    env = os.environ.copy()
    env["WINEPREFIX"] = str(prefix_path)
    env["WINEDLLOVERRIDES"] = "mshtml=d"

    subprocess.run([str(wine), "regedit", str(reg_file)], env=env, check=False)
    reg_file.unlink(missing_ok=True)
    (tmp / "wine_game_path.reg").unlink(missing_ok=True)
