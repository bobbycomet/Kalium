"""NXM URL handler: register scheme, activate MO2 instance, dispatch downloads."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from kalium.config import AppConfig, ManagedPrefixes
from kalium.logging_utils import log_error, log_info, log_install, log_warning
from kalium.steam.paths import find_steam_path
from kalium.steam.proton import find_steam_protons

# Files under ~/.config/kalium that the shell handler + Python share
ACTIVE_EXE = "active_nxm_exe"
ACTIVE_PREFIX = "active_nxm_prefix"
ACTIVE_PROTON = "active_nxm_proton"
ACTIVE_APPID = "active_nxm_appid"
ACTIVE_NAME = "active_nxm_name"


def _cfg_dir() -> Path:
    d = AppConfig.config_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_active(
    *,
    exe: Path,
    prefix: Path,
    proton: Path,
    app_id: int,
    name: str = "MO2",
) -> None:
    cfg = _cfg_dir()
    (cfg / ACTIVE_EXE).write_text(str(exe.resolve()), encoding="utf-8")
    (cfg / ACTIVE_PREFIX).write_text(str(prefix.resolve()), encoding="utf-8")
    (cfg / ACTIVE_PROTON).write_text(str(proton.resolve()), encoding="utf-8")
    (cfg / ACTIVE_APPID).write_text(str(app_id), encoding="utf-8")
    (cfg / ACTIVE_NAME).write_text(name, encoding="utf-8")
    log_install(f"NXM active → {name} | {exe} | prefix={prefix}")


def resolve_proton_path(proton_config_name: Optional[str] = None) -> Optional[Path]:
    protons = find_steam_protons()
    if not protons:
        return None
    if proton_config_name:
        for p in protons:
            if p.config_name == proton_config_name or p.name == proton_config_name:
                return p.path
            if proton_config_name.lower() in p.name.lower():
                return p.path
    return protons[0].path


def activate_for_install(
    install_path: Path | str,
    prefix_path: Path | str,
    proton_path: Path | str,
    app_id: int,
    name: str = "MO2",
) -> None:
    """Point the system NXM handler at this MO2 instance (call after install)."""
    install_path = Path(install_path)
    prefix_path = Path(prefix_path)
    proton_path = Path(proton_path)
    exe = install_path / "ModOrganizer.exe"
    if not exe.exists():
        # some layouts nest one folder
        candidates = list(install_path.rglob("ModOrganizer.exe"))
        if not candidates:
            raise RuntimeError(f"ModOrganizer.exe not found under {install_path}")
        exe = candidates[0]
    # prefix should be the wine pfx (…/compatdata/<id>/pfx)
    if prefix_path.name != "pfx" and (prefix_path / "pfx").is_dir():
        prefix_path = prefix_path / "pfx"
    _write_active(exe=exe, prefix=prefix_path, proton=proton_path, app_id=app_id, name=name)
    NxmHandler.setup()  # ensure desktop/mime still registered


def activate_from_managed(app_id: Optional[int] = None) -> bool:
    """Activate NXM using ManagedPrefixes (latest MO2 or matching app_id)."""
    prefixes = ManagedPrefixes.load()
    if not prefixes:
        return False
    if app_id is not None:
        match = next((p for p in prefixes if p.app_id == app_id), None)
    else:
        # Prefer MO2 entries, most recently created last in list
        mo2 = [p for p in prefixes if p.manager_type.upper() == "MO2"]
        match = (mo2 or prefixes)[-1]
    if not match:
        return False
    proton = resolve_proton_path(match.proton_config_name)
    if not proton:
        log_warning("No Proton found while activating NXM from managed prefixes")
        return False
    try:
        activate_for_install(
            match.install_path,
            match.prefix_path,
            proton,
            match.app_id,
            match.name or "MO2",
        )
        return True
    except Exception as e:
        log_error(f"NXM activate_from_managed failed: {e}")
        return False


def read_active() -> Optional[dict]:
    cfg = _cfg_dir()
    exe = cfg / ACTIVE_EXE
    prefix = cfg / ACTIVE_PREFIX
    proton = cfg / ACTIVE_PROTON
    appid = cfg / ACTIVE_APPID
    if not exe.exists() or not prefix.exists():
        return None
    return {
        "exe": Path(exe.read_text(encoding="utf-8").strip()),
        "prefix": Path(prefix.read_text(encoding="utf-8").strip()),
        "proton": Path(proton.read_text(encoding="utf-8").strip()) if proton.exists() else None,
        "app_id": int(appid.read_text(encoding="utf-8").strip()) if appid.exists() else 0,
        "name": (cfg / ACTIVE_NAME).read_text(encoding="utf-8").strip()
        if (cfg / ACTIVE_NAME).exists()
        else "MO2",
    }


def _find_proton_bin(proton_path: Optional[Path]) -> Optional[Path]:
    candidates: list[Path] = []
    if proton_path:
        candidates.append(proton_path / "proton")
    for base in (
        Path.home() / ".steam/steam/compatibilitytools.d",
        Path.home() / ".local/share/Steam/compatibilitytools.d",
        Path.home() / ".var/app/com.valvesoftware.Steam/data/Steam/compatibilitytools.d",
    ):
        if base.is_dir():
            for d in sorted(base.iterdir(), reverse=True):
                candidates.append(d / "proton")
    steam = find_steam_path()
    if steam:
        for d in (steam / "steamapps" / "common").glob("Proton*"):
            candidates.append(d / "proton")
    for c in candidates:
        if c.is_file():
            return c
    return None


def handle_nxm_url(url: str) -> int:
    """Dispatch an nxm:// URL into the active MO2 via Proton. Return process exit code."""
    url = (url or "").strip()
    if not url.lower().startswith("nxm:"):
        log_error(f"Not an NXM URL: {url}")
        return 1

    active = read_active()
    if not active:
        log_info("No active NXM config — trying managed prefixes…")
        if activate_from_managed():
            active = read_active()
    if not active:
        _notify(
            "No active mod manager for NXM.\n"
            "Install/setup MO2 in Kalium first, or open Settings and enable NXM for your instance."
        )
        return 1

    exe: Path = active["exe"]
    prefix: Path = active["prefix"]
    proton_path: Optional[Path] = active.get("proton")
    app_id = int(active.get("app_id") or 0)

    if not exe.exists():
        _notify(f"ModOrganizer.exe missing:\n{exe}")
        return 1

    proton_bin = _find_proton_bin(proton_path)
    if not proton_bin:
        _notify("Proton not found for NXM handler.")
        return 1

    steam = find_steam_path() or (Path.home() / ".steam/steam")
    compat_data = prefix.parent if prefix.name == "pfx" else prefix

    # If MO2 isn't running, launch it through Steam so the same prefix is used
    if not _mo2_running():
        if app_id:
            # Non-Steam shortcut game id: (appid << 32) | 0x02000000
            game_id = (app_id << 32) | 0x02000000
            log_info(f"Starting MO2 via steam://rungameid/{game_id}")
            try:
                subprocess.Popen(
                    ["xdg-open", f"steam://rungameid/{game_id}"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except OSError:
                pass
            for _ in range(45):
                if _mo2_running():
                    break
                import time
                time.sleep(1)
            import time
            time.sleep(3)

    env = os.environ.copy()
    env["WINEPREFIX"] = str(prefix)
    env["STEAM_COMPAT_DATA_PATH"] = str(compat_data)
    env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = str(steam)
    env["WINEDLLOVERRIDES"] = "winemenubuilder.exe="
    # Quiet proton logging a bit
    env.setdefault("PROTON_LOG", "0")

    log_info(f"NXM → {exe}  url={url}")
    try:
        # Prefer: pass URL to already-running MO2; still works if just started
        proc = subprocess.run(
            [str(proton_bin), "run", str(exe), url],
            env=env,
            timeout=120,
        )
        return int(proc.returncode or 0)
    except subprocess.TimeoutExpired:
        # MO2 may keep running; URL was still delivered
        return 0
    except Exception as e:
        log_error(f"NXM launch failed: {e}")
        _notify(f"NXM launch failed:\n{e}")
        return 1


def _mo2_running() -> bool:
    try:
        out = subprocess.check_output(["ps", "-eo", "args="], text=True, stderr=subprocess.DEVNULL)
        return "ModOrganizer.exe" in out
    except Exception:
        return False


def _notify(text: str) -> None:
    log_error(text.replace("\n", " | "))
    for cmd in (
        ["zenity", "--error", f"--text={text}", "--title=Kalium NXM"],
        ["notify-send", "Kalium NXM", text],
    ):
        try:
            subprocess.run(cmd, check=False, timeout=5)
            return
        except Exception:
            continue
    print(text, file=sys.stderr)


HANDLER_SCRIPT = r'''#!/bin/bash
# Kalium NXM scheme handler — dispatches to Python so logic stays in one place
set -euo pipefail
URL="${1:-}"
export PATH="${PATH:-/usr/bin}"

# Prefer installed kalium module / venv next to config
CFG="${XDG_CONFIG_HOME:-$HOME/.config}/kalium"
PYTHON_BIN="${KALIUM_PYTHON:-}"
if [ -z "$PYTHON_BIN" ]; then
  for c in \
    "$CFG/venv/bin/python" \
    "$HOME/.local/share/kalium/venv/bin/python" \
    "$(command -v python3 || true)"
  do
    if [ -n "$c" ] && [ -x "$c" ]; then PYTHON_BIN="$c"; break; fi
  done
fi
if [ -z "${PYTHON_BIN:-}" ]; then
  PYTHON_BIN=python3
fi

# If Kalium AppImage set this, use it
if [ -n "${APPDIR:-}" ] && [ -x "${APPDIR}/usr/venv/bin/python" ]; then
  PYTHON_BIN="${APPDIR}/usr/venv/bin/python"
  export PYTHONPATH="${APPDIR}/usr/share/kalium:${PYTHONPATH:-}"
fi

exec "$PYTHON_BIN" -c '
import sys
from kalium.nxm import handle_nxm_url
from kalium.logging_utils import init_logger
init_logger()
sys.exit(handle_nxm_url(sys.argv[1] if len(sys.argv) > 1 else ""))
' "$URL"
'''


class NxmHandler:
    """Register x-scheme-handler/nxm with a dedicated desktop entry."""

    DESKTOP_ID = "kalium-nxm-handler.desktop"

    @staticmethod
    def setup() -> None:
        cfg = _cfg_dir()
        script = cfg / "nxm_handler.sh"
        # Keep a pure-bash fallback that also tries Python; write robust script
        script.write_text(_bash_handler_script(script), encoding="utf-8")
        script.chmod(0o755)

        apps = Path.home() / ".local" / "share" / "applications"
        apps.mkdir(parents=True, exist_ok=True)
        desktop = apps / NxmHandler.DESKTOP_ID

        # Icon: prefer bundled kalium.png if present
        icon = "applications-games"
        for cand in (
            Path(__file__).resolve().parent.parent / "resources" / "icons" / "kalium.png",
            Path.home() / ".local" / "share" / "icons" / "kalium.png",
        ):
            if cand.is_file():
                icon = str(cand)
                break

        desktop.write_text(
            f"""[Desktop Entry]
Type=Application
Version=1.5
Name=Kalium NXM Handler
GenericName=Nexus Mods Link Handler
Comment=Send nxm:// download links to your Kalium-managed Mod Organizer 2
Exec={script} %u
TryExec={script}
Icon={icon}
Terminal=false
Categories=Game;Network;
MimeType=x-scheme-handler/nxm;
NoDisplay=true
StartupNotify=false
""",
            encoding="utf-8",
        )

        # mimeapps.list — set as default, remove competing guesses if we own the handler
        mime = Path.home() / ".config" / "mimeapps.list"
        mime.parent.mkdir(parents=True, exist_ok=True)
        content = mime.read_text(encoding="utf-8") if mime.exists() else ""
        lines = content.splitlines()
        out: list[str] = []
        in_default = False
        seen_default_section = False
        wrote = False
        for line in lines:
            if line.strip() == "[Default Applications]":
                in_default = True
                seen_default_section = True
                out.append(line)
                continue
            if line.startswith("[") and line.strip() != "[Default Applications]":
                if in_default and not wrote:
                    out.append(f"x-scheme-handler/nxm={NxmHandler.DESKTOP_ID}")
                    wrote = True
                in_default = False
            if in_default and line.strip().startswith("x-scheme-handler/nxm="):
                out.append(f"x-scheme-handler/nxm={NxmHandler.DESKTOP_ID}")
                wrote = True
                continue
            out.append(line)
        if not seen_default_section:
            out.append("")
            out.append("[Default Applications]")
            out.append(f"x-scheme-handler/nxm={NxmHandler.DESKTOP_ID}")
            wrote = True
        elif in_default and not wrote:
            out.append(f"x-scheme-handler/nxm={NxmHandler.DESKTOP_ID}")
        mime.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")

        try:
            subprocess.run(
                ["xdg-mime", "default", NxmHandler.DESKTOP_ID, "x-scheme-handler/nxm"],
                check=False,
                capture_output=True,
            )
        except OSError:
            pass
        try:
            subprocess.run(["update-desktop-database", str(apps)], check=False, capture_output=True)
        except OSError:
            pass
        log_install(f"NXM handler registered ({NxmHandler.DESKTOP_ID})")

    @staticmethod
    def status() -> str:
        active = read_active()
        if not active:
            return "NXM: not configured (install MO2 in Kalium or enable NXM in Settings)"
        return (
            f"NXM: active → {active.get('name')} | {active['exe']} | "
            f"prefix={active['prefix']} | appid={active.get('app_id')}"
        )


def _bash_handler_script(script_path: Path) -> str:
    """Shell entry that calls Python handle_nxm_url, with a pure-bash fallback."""
    return f'''#!/bin/bash
set -euo pipefail
URL="${{1:-}}"
CFG="${{XDG_CONFIG_HOME:-$HOME/.config}}/kalium"
mkdir -p "$CFG"
LOG="$CFG/nxm_handler.log"
echo "$(date -Iseconds) NXM invoke: $URL" >> "$LOG"

# --- Python path (AppImage / venv / system) ---
PYTHON_BIN=""
if [ -n "${{APPDIR:-}}" ] && [ -x "${{APPDIR}}/usr/venv/bin/python" ]; then
  PYTHON_BIN="${{APPDIR}}/usr/venv/bin/python"
  export PYTHONPATH="${{APPDIR}}/usr/share/kalium:${{PYTHONPATH:-}}"
elif [ -x "$CFG/../kalium-venv/bin/python" ]; then
  PYTHON_BIN="$CFG/../kalium-venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
fi

if [ -n "$PYTHON_BIN" ] && "$PYTHON_BIN" -c "import kalium.nxm" 2>/dev/null; then
  exec "$PYTHON_BIN" -c "from kalium.logging_utils import init_logger; from kalium.nxm import handle_nxm_url; init_logger(); import sys; sys.exit(handle_nxm_url(sys.argv[1]))" "$URL"
fi

# --- Pure bash fallback (active_* files required) ---
EXE_FILE="$CFG/active_nxm_exe"
PREFIX_FILE="$CFG/active_nxm_prefix"
PROTON_FILE="$CFG/active_nxm_proton"
APPID_FILE="$CFG/active_nxm_appid"

if [ ! -f "$EXE_FILE" ] || [ ! -f "$PREFIX_FILE" ]; then
  MSG="No active mod manager for NXM. Open Kalium → finish MO2 setup (NXM is enabled automatically), or run NXM Toggle in Kalium Tools."
  zenity --error --text="$MSG" --title="Kalium NXM" 2>/dev/null || notify-send "Kalium NXM" "$MSG" 2>/dev/null || echo "$MSG" >&2
  exit 1
fi

NXM_EXE=$(cat "$EXE_FILE")
WINEPREFIX=$(cat "$PREFIX_FILE")
PROTON_PATH=$(cat "$PROTON_FILE" 2>/dev/null || true)
PROTON_BIN=""
if [ -n "$PROTON_PATH" ] && [ -f "$PROTON_PATH/proton" ]; then
  PROTON_BIN="$PROTON_PATH/proton"
else
  for d in "$HOME/.steam/steam/compatibilitytools.d"/* \\
           "$HOME/.local/share/Steam/compatibilitytools.d"/*; do
    [ -f "$d/proton" ] && PROTON_BIN="$d/proton" && break
  done
fi
if [ -z "$PROTON_BIN" ] || [ ! -f "$PROTON_BIN" ]; then
  zenity --error --text="Proton not found for NXM handler" --title="Kalium NXM" 2>/dev/null || true
  exit 1
fi

STEAM_PATH="${{HOME}}/.steam/steam"
[ -d "$HOME/.local/share/Steam" ] && STEAM_PATH="$HOME/.local/share/Steam"
export WINEPREFIX
export STEAM_COMPAT_DATA_PATH="${{WINEPREFIX%/pfx}}"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_PATH"
export WINEDLLOVERRIDES="winemenubuilder.exe="

if ! pgrep -f "ModOrganizer.exe" >/dev/null 2>&1; then
  if [ -f "$APPID_FILE" ]; then
    APPID=$(cat "$APPID_FILE")
    GAME_ID=$(python3 -c "print(($APPID << 32) | 0x02000000)" 2>/dev/null || echo "")
    if [ -n "$GAME_ID" ]; then
      xdg-open "steam://rungameid/$GAME_ID" >/dev/null 2>&1 || true
      for _ in $(seq 1 40); do
        sleep 1
        pgrep -f "ModOrganizer.exe" >/dev/null 2>&1 && break
      done
      sleep 3
    fi
  fi
fi

echo "$(date -Iseconds) running: $PROTON_BIN run $NXM_EXE $URL" >> "$LOG"
exec "$PROTON_BIN" run "$NXM_EXE" "$URL"
'''
