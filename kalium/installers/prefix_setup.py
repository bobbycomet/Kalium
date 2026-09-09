"""Prefix initialization, winetricks, .NET, registry, DPI."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Callable

import requests

from kalium.config import AppConfig
from kalium.deps import install_standard_deps, ensure_winetricks
from kalium.game_finder import detect_all_games
from kalium.logging_utils import log_install, log_warning
from kalium.steam.paths import find_steam_path
from kalium.steam.proton import SteamProton
from kalium.installers.task import TaskContext

DOTNET9_SDK_URL = "https://builds.dotnet.microsoft.com/dotnet/Sdk/9.0.310/dotnet-sdk-9.0.310-win-x64.exe"
DOTNET_DESKTOP10_URL = "https://builds.dotnet.microsoft.com/dotnet/WindowsDesktop/10.0.2/windowsdesktop-runtime-10.0.2-win-x64.exe"

WINE_SETTINGS_REG = """Windows Registry Editor Version 5.00

[HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides]
"dwrite.dll"="native,builtin"
"winmm.dll"="native,builtin"
"version.dll"="native,builtin"
"dxgi.dll"="native,builtin"
"d3d12.dll"="native,builtin"
"wininet.dll"="native,builtin"
"winhttp.dll"="native,builtin"
"dinput8.dll"="native,builtin"

[HKEY_CURRENT_USER\\Software\\Wine]
"ShowDotFiles"="Y"

[HKEY_CURRENT_USER\\Control Panel\\Desktop]
"FontSmoothing"="2"
"FontSmoothingType"=dword:00000002

[HKEY_CURRENT_USER\\Software\\Microsoft\\Windows NT\\CurrentVersion\\AppCompatFlags\\Layers]
@="~ HIGHDPIAWARE"
"""


def initialize_prefix(prefix_root: Path, proton: SteamProton, app_id: int, ctx: TaskContext) -> None:
    proton_script = proton.path / "proton"
    if not proton_script.exists():
        raise RuntimeError(f"Proton wrapper missing: {proton_script}")
    steam = find_steam_path()
    if not steam:
        raise RuntimeError("Steam not found")
    compat = prefix_root.parent
    env = os.environ.copy()
    env.update({
        "STEAM_COMPAT_CLIENT_INSTALL_PATH": str(steam),
        "STEAM_COMPAT_DATA_PATH": str(compat),
        "SteamAppId": str(app_id),
        "SteamGameId": str(app_id),
        "DISPLAY": "",
        "WAYLAND_DISPLAY": "",
        "WINEDEBUG": "-all",
        "WINEDLLOVERRIDES": "msdia80.dll=n;conhost.exe=d;cmd.exe=d",
    })
    log_install(f"Initializing prefix with proton: {proton_script}")
    ret = ctx.run_cancellable([str(proton_script), "run", "wineboot", "-u"], env=env)
    if ret != 0:
        raise RuntimeError(f"proton wineboot failed: {ret}")
    time.sleep(2)
    if not prefix_root.exists():
        raise RuntimeError("Prefix not created after wineboot")


def apply_wine_registry(prefix: Path, proton: SteamProton, log_cb: Callable[[str], None]) -> None:
    wine = proton.wine_binary()
    if not wine:
        raise RuntimeError("Wine binary not found")
    tmp = AppConfig.tmp_path()
    tmp.mkdir(parents=True, exist_ok=True)
    reg = tmp / "wine_settings.reg"
    reg.write_text(WINE_SETTINGS_REG, encoding="utf-8")
    env = os.environ.copy()
    env["WINEPREFIX"] = str(prefix)
    env["WINEDLLOVERRIDES"] = "mshtml=d"
    env["PROTON_USE_XALIA"] = "0"
    log_cb("Applying Wine registry settings...")
    subprocess.run([str(wine), "regedit", str(reg)], env=env, check=False)
    reg.unlink(missing_ok=True)
    log_install("Wine registry settings applied")


def apply_game_registries(prefix: Path, proton: SteamProton, log_cb: Callable[[str], None]) -> None:
    wine = proton.wine_binary()
    if not wine:
        return
    result = detect_all_games()
    count = 0
    tmp = AppConfig.tmp_path()
    tmp.mkdir(parents=True, exist_ok=True)
    for game in result.games:
        if not game.registry_path or not game.registry_value:
            continue
        linux = str(game.install_path)
        wine_path = "Z:" + linux.replace("/", "\\\\")
        reg_path = game.registry_path
        wow = reg_path[9:] if reg_path.startswith("Software\\") else reg_path
        reg_content = (
            "Windows Registry Editor Version 5.00\n\n"
            f"[HKEY_LOCAL_MACHINE\\{reg_path}]\n"
            f'"{game.registry_value}"="{wine_path}"\n\n'
            f"[HKEY_LOCAL_MACHINE\\SOFTWARE\\Wow6432Node\\{wow}]\n"
            f'"{game.registry_value}"="{wine_path}"\n'
        )
        reg_file = tmp / f"game_reg_{game.app_id}.reg"
        reg_file.write_text(reg_content, encoding="utf-8")
        env = os.environ.copy()
        env["WINEPREFIX"] = str(prefix)
        env["WINEDLLOVERRIDES"] = "mshtml=d"
        env["PROTON_USE_XALIA"] = "0"
        ret = subprocess.run([str(wine), "regedit", str(reg_file)], env=env)
        reg_file.unlink(missing_ok=True)
        if ret.returncode == 0:
            count += 1
            log_cb(f"Registered {game.name}")
    if count:
        log_install(f"Auto-applied registry for {count} game(s)")


def install_dotnet(prefix: Path, proton: SteamProton, url: str, name: str, ctx: TaskContext) -> None:
    cache = AppConfig.default_cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    filename = url.rsplit("/", 1)[-1]
    installer = cache / filename
    if not installer.exists():
        log_install(f"Downloading {name}...")
        r = requests.get(url, timeout=300, headers={"User-Agent": "Kalium/1.0"})
        r.raise_for_status()
        installer.write_bytes(r.content)
    wine = proton.wine_binary()
    if not wine:
        raise RuntimeError("Wine binary not found")
    env = os.environ.copy()
    env["WINEPREFIX"] = str(prefix)
    env["WINEDLLOVERRIDES"] = "mshtml=d"
    log_install(f"Running {name} installer...")
    ret = ctx.run_cancellable(
        [str(wine), str(installer), "/install", "/quiet", "/norestart"],
        env=env,
    )
    if ret != 0:
        raise RuntimeError(f"{name} installer exit {ret}")


def set_win11(prefix: Path, proton: SteamProton, ctx: TaskContext) -> None:
    wt = ensure_winetricks()
    wine = proton.wine_binary()
    wineserver = proton.wineserver_binary()
    if not wine or not wineserver:
        raise RuntimeError("Wine not found")
    env = os.environ.copy()
    env.update({"WINE": str(wine), "WINESERVER": str(wineserver), "WINEPREFIX": str(prefix)})
    ret = ctx.run_cancellable([str(wt), "-q", "win11"], env=env)
    if ret != 0:
        raise RuntimeError(f"winetricks win11 failed: {ret}")


def install_all_dependencies(
    prefix_root: Path,
    proton: SteamProton,
    ctx: TaskContext,
    start_progress: float = 0.2,
    end_progress: float = 0.9,
    app_id: int = 0,
) -> None:
    AppConfig.tmp_path().mkdir(parents=True, exist_ok=True)
    span = end_progress - start_progress
    ctx.set_status("Setting up Windows compatibility layer...")
    try:
        initialize_prefix(prefix_root, proton, app_id, ctx)
    except Exception as e:
        log_warning(f"Prefix init warning: {e}")
        ctx.log(f"Warning: {e}")
    ctx.set_progress(start_progress + span * 0.1)
    if ctx.is_cancelled():
        raise RuntimeError("Cancelled")

    ctx.set_status("Installing required Windows components (several minutes)...")

    def log_cb(m: str) -> None:
        ctx.log(m)
        ctx.set_status(m)

    try:
        install_standard_deps(prefix_root, proton, log_cb, ctx.is_cancelled)
    except Exception as e:
        log_warning(f"Winetricks issues: {e}")
        ctx.log(f"Warning: {e}")
    ctx.set_progress(start_progress + span * 0.5)
    if ctx.is_cancelled():
        raise RuntimeError("Cancelled")

    ctx.set_status("Installing .NET 9 SDK...")
    try:
        install_dotnet(prefix_root, proton, DOTNET9_SDK_URL, "dotnet-sdk-9", ctx)
    except Exception as e:
        log_warning(f".NET 9 SDK failed: {e}")
    ctx.set_status("Installing .NET Desktop 10...")
    try:
        install_dotnet(prefix_root, proton, DOTNET_DESKTOP10_URL, "dotnet-desktop-10", ctx)
    except Exception as e:
        log_warning(f".NET Desktop 10 failed: {e}")
    ctx.set_progress(start_progress + span * 0.65)

    ctx.set_status("Detecting installed games...")
    apply_game_registries(prefix_root, proton, ctx.log)
    ctx.set_progress(start_progress + span * 0.75)

    ctx.set_status("Configuring Windows registry...")
    apply_wine_registry(prefix_root, proton, ctx.log)
    try:
        set_win11(prefix_root, proton, ctx)
    except Exception as e:
        log_warning(f"win11 mode: {e}")
    ctx.set_progress(end_progress)
    ctx.set_status("Dependencies installed")


def apply_dpi(prefix: Path, proton: SteamProton, dpi: int) -> None:
    wine = proton.wine_binary()
    if not wine:
        raise RuntimeError("Wine not found")
    env = os.environ.copy()
    env["WINEPREFIX"] = str(prefix)
    env["PROTON_USE_XALIA"] = "0"
    subprocess.run(
        [str(wine), "reg", "add", r"HKCU\Control Panel\Desktop",
         "/v", "LogPixels", "/t", "REG_DWORD", "/d", str(dpi), "/f"],
        env=env,
        check=False,
    )
    log_install(f"DPI {dpi} applied")


def kill_wineserver(prefix: Path, proton: SteamProton) -> None:
    ws = proton.wineserver_binary()
    if not ws:
        return
    env = os.environ.copy()
    env["WINEPREFIX"] = str(prefix)
    subprocess.run([str(ws), "-k"], env=env, check=False)
