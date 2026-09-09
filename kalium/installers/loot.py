"""Portable LOOT install for Kalium MO2 instances.

Design:
  - Always write run_loot.bat with --game= embedded (one-shot / recovery launcher).
  - Register the *permanent* MO2 custom executable as LOOT.exe (Z: path) with
    --game= in the arguments field — not the .bat.
  - The old ``start "" /wait`` bat hung under Proton (LOOT never appeared);
    the bat now invokes LOOT.exe directly.

  Qt can rewrite binary paths with backslashes; ``kalium fix-paths`` (and the
  Launch script) normalize those. Arguments with --game= are kept on the
  LOOT.exe entry so subsequent runs stay on the correct game.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Optional

import py7zr
import requests

from kalium.config import AppConfig
from kalium.installers.task import TaskContext
from kalium.logging_utils import log_install, log_warning
from kalium.utils import download_file

LOOT_PINNED_VERSION = "0.29.2"
LOOT_PINNED_URL = (
    f"https://github.com/loot/loot/releases/download/{LOOT_PINNED_VERSION}/"
    f"loot_{LOOT_PINNED_VERSION}-win64.7z"
)
LOOT_PINNED_NAME = f"loot_{LOOT_PINNED_VERSION}-win64.7z"
RUN_LOOT_BAT_NAME = "run_loot.bat"

_GAME_ALIASES: dict[str, str] = {
    "skyrim special edition": "Skyrim Special Edition",
    "skyrim se": "Skyrim Special Edition",
    "skyrimse": "Skyrim Special Edition",
    "skyrim": "Skyrim",
    "skyrim vr": "Skyrim VR",
    "enderal": "Enderal",
    "enderal special edition": "Enderal Special Edition",
    "fallout 4": "Fallout4",
    "fallout4": "Fallout4",
    "fallout 4 vr": "Fallout4VR",
    "fallout4vr": "Fallout4VR",
    "fallout new vegas": "FalloutNV",
    "fallout nv": "FalloutNV",
    "falloutnv": "FalloutNV",
    "new vegas": "FalloutNV",
    "fallout 3": "Fallout3",
    "fallout3": "Fallout3",
    "oblivion": "Oblivion",
    "oblivion remastered": "Oblivion Remastered",
    "morrowind": "Morrowind",
    "starfield": "Starfield",
    "nehrim": "Nehrim",
    "openmw": "OpenMW",
}


def normalize_loot_game_name(name: Optional[str]) -> str:
    if not name:
        return "Skyrim Special Edition"
    raw = name.strip().strip('"')
    key = " ".join(raw.lower().split())
    return _GAME_ALIASES.get(key, raw)


def fetch_latest_loot_asset() -> dict:
    url = "https://api.github.com/repos/loot/loot/releases/latest"
    try:
        r = requests.get(url, headers={"User-Agent": "Kalium/1.0"}, timeout=60)
        r.raise_for_status()
        data = r.json()
        for a in data.get("assets", []):
            aname = a.get("name", "")
            if aname.endswith("-win64.7z") and aname.startswith("loot_"):
                return a
    except Exception as e:
        log_warning(f"LOOT latest release lookup failed ({e}); using pinned {LOOT_PINNED_VERSION}")
    return {"name": LOOT_PINNED_NAME, "browser_download_url": LOOT_PINNED_URL}


def _write_run_loot_bat(loot_dir: Path, game_name: str) -> Path:
    """One-shot / recovery launcher. Invokes LOOT.exe directly (no start /wait).

    ``start "" /wait`` under Proton often never returns control and LOOT never
    shows a window. A plain call lets Wine/Proton track the process correctly.
    """
    loot_game = normalize_loot_game_name(game_name)
    safe_game = loot_game.replace('"', '""')
    content = (
        "@echo off\r\n"
        "setlocal\r\n"
        'cd /d "%~dp0"\r\n'
        f'"%~dp0LOOT.exe" --game="{safe_game}" %*\r\n'
        "exit /b %ERRORLEVEL%\r\n"
    )
    bat = loot_dir / RUN_LOOT_BAT_NAME
    bat.write_text(content, encoding="utf-8", newline="")
    try:
        bat.chmod(bat.stat().st_mode | 0o755)
    except OSError:
        pass
    log_install(f'Wrote {bat} (--game="{loot_game}") — optional one-shot / recovery launcher')
    return bat


def install_loot(
    mo2_install_path: Path,
    ctx: Optional[TaskContext] = None,
    game_name: Optional[str] = None,
) -> Path:
    def status(msg: str) -> None:
        log_install(msg)
        if ctx:
            ctx.set_status(msg)
            ctx.log(msg)

    status("Checking LOOT release...")
    asset = fetch_latest_loot_asset()
    status(f"Downloading {asset['name']}...")

    tmp = AppConfig.tmp_path()
    tmp.mkdir(parents=True, exist_ok=True)
    archive = tmp / asset["name"]
    download_file(asset["browser_download_url"], archive)

    loot_dir = Path(mo2_install_path) / "LOOT"
    if loot_dir.exists():
        shutil.rmtree(loot_dir, ignore_errors=True)
    loot_dir.mkdir(parents=True, exist_ok=True)

    status("Extracting LOOT...")
    with py7zr.SevenZipFile(archive, mode="r") as z:
        z.extractall(path=loot_dir)
    archive.unlink(missing_ok=True)

    candidates = list(loot_dir.rglob("LOOT.exe"))
    if not candidates:
        raise RuntimeError("LOOT.exe not found after extract")
    exe = candidates[0]

    if exe.parent.resolve() != loot_dir.resolve():
        for item in list(exe.parent.iterdir()):
            target = loot_dir / item.name
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            item.rename(target)
        try:
            exe.parent.rmdir()
        except OSError:
            pass
        exe = loot_dir / "LOOT.exe"

    if not exe.is_file():
        raise RuntimeError(f"LOOT.exe missing after flatten: {exe}")

    gname = game_name
    if not gname:
        ini = Path(mo2_install_path) / "ModOrganizer.ini"
        if ini.is_file():
            try:
                gname = _detect_mo2_game_name(ini.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass
    if not gname:
        gname = "Skyrim Special Edition"
        log_warning(f'No game name resolved — defaulting run_loot.bat to --game="{gname}"')

    _write_run_loot_bat(loot_dir, gname)
    status(f"LOOT installed → {exe} (game: {normalize_loot_game_name(gname)})")
    # Permanent target for MO2 registration is LOOT.exe, not the bat.
    return exe


def _wine_z_path(linux_path: Path) -> str:
    return "Z:" + str(linux_path.resolve())


def _detect_mo2_game_name(ini_text: str) -> Optional[str]:
    for pattern in (
        r"(?im)^\s*gameName\s*=\s*(.+?)\s*$",
        r"(?im)^\s*game_name\s*=\s*(.+?)\s*$",
        r"(?im)^\s*SelectedGame\s*=\s*(.+?)\s*$",
    ):
        m = re.search(pattern, ini_text)
        if m:
            name = m.group(1).strip().strip('"')
            if name:
                return name
    return None


def register_loot_in_mo2(
    mo2_install_path: Path,
    loot_launcher: Path,
    game_name: Optional[str] = None,
) -> bool:
    """Register LOOT.exe (not the bat) as the permanent custom executable.

    --game= is stored in the arguments field. run_loot.bat remains on disk as a
    recovery one-shot if arguments ever get stripped.
    """
    mo2_install_path = Path(mo2_install_path)
    loot_launcher = Path(loot_launcher)
    ini = mo2_install_path / "ModOrganizer.ini"
    if not ini.is_file():
        log_warning(
            "ModOrganizer.ini not found — MO2 hasn't been launched yet, "
            "so LOOT can't be registered until it has."
        )
        return False

    text = ini.read_text(encoding="utf-8", errors="replace")

    if not game_name:
        game_name = _detect_mo2_game_name(text)
    if not game_name:
        game_name = "Skyrim Special Edition"
        log_warning(f'No game name found — defaulting to "{game_name}".')

    loot_game = normalize_loot_game_name(game_name)

    loot_dir = loot_launcher.parent if loot_launcher.is_file() else loot_launcher
    if loot_launcher.name.lower() == RUN_LOOT_BAT_NAME.lower():
        loot_dir = loot_launcher.parent
    if not (loot_dir / "LOOT.exe").is_file():
        cand = Path(mo2_install_path) / "LOOT"
        if (cand / "LOOT.exe").is_file():
            loot_dir = cand
    exe = loot_dir / "LOOT.exe"
    if not exe.is_file():
        log_warning(f"LOOT.exe not found under {loot_dir} — cannot register")
        return False

    # Keep recovery bat in sync
    _write_run_loot_bat(loot_dir, loot_game)

    binary = _wine_z_path(exe)
    workdir = _wine_z_path(loot_dir)
    arguments = f'--game="{loot_game}"'

    loot_title = re.search(r"(?im)^(\d+)\\title\s*=\s*LOOT\s*$", text)
    if loot_title:
        idx = loot_title.group(1)

        def _set_field(content: str, field: str, value: str) -> str:
            pat = rf"(?im)^({idx}\\{field}\s*=).*$"
            if re.search(pat, content):
                return re.sub(pat, rf"\g<1>{value}", content, count=1)
            return re.sub(
                rf"(?im)^({idx}\\title\s*=\s*LOOT\s*)$",
                rf"\1\n{idx}\\{field}={value}",
                content,
                count=1,
            )

        text = _set_field(text, "arguments", arguments)
        text = _set_field(text, "binary", binary)
        text = _set_field(text, "workingDirectory", workdir)
        text = _set_field(text, "hide", "false")
        text = _set_field(text, "ownicon", "true")
        text = _set_field(text, "toolbar", "true")
        ini.write_text(text, encoding="utf-8")
        log_install(
            f'Updated LOOT entry (index {idx}) binary={binary} arguments={arguments}'
        )
        return True

    m = re.search(r"\[customExecutables\]\s*\nsize\s*=\s*(\d+)", text)
    if m:
        size = int(m.group(1))
        new_idx = size + 1
        entry = (
            f"{new_idx}\\arguments={arguments}\n"
            f"{new_idx}\\binary={binary}\n"
            f"{new_idx}\\hide=false\n"
            f"{new_idx}\\ownicon=true\n"
            f"{new_idx}\\steamAppID=\n"
            f"{new_idx}\\title=LOOT\n"
            f"{new_idx}\\toolbar=true\n"
            f"{new_idx}\\workingDirectory={workdir}\n"
        )
        text = re.sub(
            r"(\[customExecutables\]\s*\nsize\s*=\s*)\d+",
            rf"\g<1>{new_idx}",
            text,
            count=1,
        )
        text = re.sub(
            r"(\[customExecutables\]\s*\nsize\s*=\s*\d+\n)",
            lambda mm: mm.group(1) + entry,
            text,
            count=1,
        )
    else:
        text += (
            "\n[customExecutables]\n"
            "size=1\n"
            f"1\\arguments={arguments}\n"
            f"1\\binary={binary}\n"
            "1\\hide=false\n"
            "1\\ownicon=true\n"
            "1\\steamAppID=\n"
            "1\\title=LOOT\n"
            "1\\toolbar=true\n"
            f"1\\workingDirectory={workdir}\n"
        )

    ini.write_text(text, encoding="utf-8")
    log_install(f'Registered LOOT binary={binary} arguments={arguments}')
    return True


def _vcrun_after_loot(mo2_install_path: Path, ctx: Optional[TaskContext] = None) -> None:
    """Best-effort: winetricks vcrun2022 in the managed MO2 prefix so LOOT can start."""
    try:
        from kalium.config import ManagedPrefixes
        from kalium.installers.loot_vcrun import run_vcrun2022_for_prefix

        mo2_install_path = Path(mo2_install_path).resolve()
        match = None
        for p in ManagedPrefixes.load():
            try:
                if Path(p.install_path).resolve() == mo2_install_path:
                    match = p
                    break
            except OSError:
                if str(p.install_path) == str(mo2_install_path):
                    match = p
                    break
        if not match or not match.prefix_path:
            log_warning(
                "No managed prefix found for this MO2 path — skip vcrun2022. "
                "Use Settings → Ensure vcrun2022 after the instance is registered."
            )
            return

        def st(msg: str) -> None:
            log_install(msg)
            if ctx:
                ctx.set_status(msg)
                ctx.log(msg)

        run_vcrun2022_for_prefix(
            match.prefix_path,
            proton_config_name=match.proton_config_name,
            status=st,
        )
    except Exception as e:
        log_warning(f"vcrun2022 for LOOT prefix failed (LOOT is still installed): {e}")
        if ctx:
            ctx.log(f"vcrun2022 warning: {e}")


def install_and_register_loot(
    mo2_install_path: Path,
    ctx: Optional[TaskContext] = None,
    game_name: Optional[str] = None,
    *,
    ensure_vcrun: bool = True,
) -> Optional[Path]:
    try:
        launcher = install_loot(mo2_install_path, ctx, game_name=game_name)
        registered = register_loot_in_mo2(mo2_install_path, launcher, game_name=game_name)
        if not registered:
            msg = (
                "LOOT was downloaded (LOOT.exe + run_loot.bat) but not yet added to MO2's "
                "executable list (ModOrganizer.ini missing until first launch). "
                "Launch MO2 once, then Settings → Install LOOT or "
                "kalium install-loot -p <mo2 path>"
            )
            log_warning(msg)
            if ctx:
                ctx.log(msg)
                ctx.set_status(msg)
        if ensure_vcrun:
            _vcrun_after_loot(mo2_install_path, ctx)
        return launcher
    except Exception as e:
        log_warning(f"LOOT auto-install failed: {e}")
        if ctx:
            ctx.log(f"LOOT auto-install failed: {e}")
        return None
