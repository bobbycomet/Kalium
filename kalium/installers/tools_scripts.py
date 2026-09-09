"""Generate Kalium Tools shell scripts inside install dirs."""

from __future__ import annotations

from pathlib import Path

from kalium.config import normalize_path_for_steam
from kalium.logging_utils import log_install, log_warning

FIX_REGISTRY = r"""#!/bin/bash
set -e -o pipefail
PREFIX="{{PREFIX_PATH}}"
PROTON_PATH="{{PROTON_PATH}}"
if [ -x "$PROTON_PATH/files/bin/wine" ]; then WINE_BIN="$PROTON_PATH/files/bin/wine"
elif [ -x "$PROTON_PATH/dist/bin/wine" ]; then WINE_BIN="$PROTON_PATH/dist/bin/wine"
else echo "ERROR: Proton wine not found"; exit 1; fi
echo "Kalium Game Registry Fixer"
declare -a GAMES=(
  "Enderal|Software\\SureAI\\Enderal|Install_Path"
  "Enderal Special Edition|Software\\SureAI\\Enderal SE|installed path"
  "Fallout 3|Software\\Bethesda Softworks\\Fallout3|Installed Path"
  "Fallout 4|Software\\Bethesda Softworks\\Fallout4|Installed Path"
  "Fallout New Vegas|Software\\Bethesda Softworks\\FalloutNV|Installed Path"
  "Skyrim|Software\\Bethesda Softworks\\Skyrim|Installed Path"
  "Skyrim Special Edition|Software\\Bethesda Softworks\\Skyrim Special Edition|Installed Path"
  "Starfield|Software\\Bethesda Softworks\\Starfield|Installed Path"
  "Cyberpunk 2077|Software\\CD Projekt Red\\Cyberpunk 2077|InstallFolder"
  "Baldur's Gate 3|Software\\Larian Studios\\Baldur's Gate 3|InstallDir"
)
for i in "${!GAMES[@]}"; do echo "  $((i+1)). ${GAMES[$i]%%|*}"; done
read -r -p "Enter number: " choice
selected="${GAMES[$((choice-1))]}"
GAME_NAME="${selected%%|*}"; rest="${selected#*|}"; REG_PATH="${rest%%|*}"; VALUE_NAME="${rest##*|}"
read -r -p "Linux game path: " GAME_PATH
WINE_PATH_REG="Z:${GAME_PATH//\//\\\\}"
REG_FILE=$(mktemp --suffix=.reg)
cat > "$REG_FILE" << EOFREG
Windows Registry Editor Version 5.00
[HKEY_LOCAL_MACHINE\\$REG_PATH]
"$VALUE_NAME"="$WINE_PATH_REG"
[HKEY_LOCAL_MACHINE\\SOFTWARE\\Wow6432Node\\${REG_PATH#Software\\}]
"$VALUE_NAME"="$WINE_PATH_REG"
EOFREG
WINEPREFIX="$PREFIX" "$WINE_BIN" regedit "$REG_FILE"
rm -f "$REG_FILE"
echo "Done."
"""

NXM_TOGGLE = r"""#!/bin/bash
set -e -o pipefail
APP_ID={{APP_ID}}
MANAGER_NAME="{{MANAGER_NAME}}"
NXM_EXE="{{NXM_EXE}}"
PREFIX_PATH="{{PREFIX_PATH}}"
PROTON_PATH="{{PROTON_PATH}}"
CFG="${XDG_CONFIG_HOME:-$HOME/.config}/kalium"
mkdir -p "$CFG"
echo "$APP_ID" > "$CFG/active_nxm_appid"
echo "$NXM_EXE" > "$CFG/active_nxm_exe"
echo "$PREFIX_PATH" > "$CFG/active_nxm_prefix"
echo "$PROTON_PATH" > "$CFG/active_nxm_proton"
echo "NXM handling enabled for $MANAGER_NAME (AppID $APP_ID)"
"""

LAUNCH = r"""#!/bin/bash
set -e -o pipefail
GAME_ID={{GAME_ID}}
MO2_PATH="{{MO2_PATH}}"
# Normalize any backslash paths added by hand in MO2's Add Executable
# dialog (SKSE, xEdit, LOOT, etc.) since the last launch — see
# kalium/installers/ini_paths.py for why this is needed.
if command -v kalium >/dev/null 2>&1; then
    kalium fix-paths -p "$MO2_PATH" || true
fi
# Multi-drive: ensure secondary Steam libraries (/mnt/sdb1, SD cards, …)
# are visible inside Proton. Steam launch options also set this; exporting
# here covers direct/script launches.
if [ -z "${STEAM_COMPAT_MOUNTS:-}" ]; then
    _MOUNTS=""
    for d in /mnt /media /run/media; do
        [ -d "$d" ] || continue
        _MOUNTS="${_MOUNTS:+$_MOUNTS:}$d"
        for child in "$d"/*; do
            [ -d "$child" ] || continue
            case "$(basename "$child")" in .* ) continue ;; esac
            _MOUNTS="$_MOUNTS:$child"
        done
    done
    # libraryfolders.vdf secondary roots if kalium is available
    if command -v kalium >/dev/null 2>&1; then
        _EXTRA=$(kalium check-steam 2>/dev/null | sed -n 's/^STEAM_COMPAT_MOUNTS candidates ([0-9]*): //p' | head -1 || true)
        if [ -n "$_EXTRA" ]; then
            _MOUNTS="$_EXTRA"
        fi
    fi
    if [ -n "$_MOUNTS" ]; then
        export STEAM_COMPAT_MOUNTS="$_MOUNTS"
        echo "STEAM_COMPAT_MOUNTS=$STEAM_COMPAT_MOUNTS"
    fi
fi
echo "Launching {{MANAGER_NAME}} via Steam..."
xdg-open "steam://rungameid/$GAME_ID"
"""

WINETRICKS = r"""#!/bin/bash
set -e -o pipefail
PREFIX="{{PREFIX_PATH}}"
NAK_WT="${XDG_CONFIG_HOME:-$HOME/.config}/kalium/bin/winetricks"
if [ -x "$NAK_WT" ]; then WT="$NAK_WT"
elif command -v winetricks >/dev/null; then WT=winetricks
else echo "winetricks not found"; exit 1; fi
WINEPREFIX="$PREFIX" "$WT" --gui
"""


def _write_script(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o700)


def create_kalium_tools(
    install_dir: Path,
    prefix_path: Path,
    app_id: int,
    proton_path: Path,
    manager_name: str = "MO2",
) -> None:
    tools = install_dir / "Kalium Tools"
    tools.mkdir(parents=True, exist_ok=True)
    link = tools / "Wine Prefix"
    if link.exists() or link.is_symlink():
        link.unlink()
    try:
        link.symlink_to(prefix_path)
    except OSError as e:
        log_warning(f"Prefix symlink failed: {e}")

    prefix_s = normalize_path_for_steam(str(prefix_path))
    proton_s = normalize_path_for_steam(str(proton_path))
    install_s = normalize_path_for_steam(str(install_dir))
    game_id = (app_id << 32) | 0x02000000

    _write_script(
        tools / "Fix Game Registry.sh",
        FIX_REGISTRY.replace("{{PREFIX_PATH}}", prefix_s).replace("{{PROTON_PATH}}", proton_s),
    )
    _write_script(
        tools / "NXM Toggle.sh",
        NXM_TOGGLE.replace("{{APP_ID}}", str(app_id))
        .replace("{{MANAGER_NAME}}", manager_name)
        .replace("{{NXM_EXE}}", f"{install_s}/ModOrganizer.exe")
        .replace("{{PREFIX_PATH}}", prefix_s)
        .replace("{{PROTON_PATH}}", proton_s),
    )
    _write_script(
        tools / f"Launch {manager_name}.sh",
        LAUNCH.replace("{{GAME_ID}}", str(game_id))
        .replace("{{MANAGER_NAME}}", manager_name)
        .replace("{{MO2_PATH}}", install_s),
    )
    _write_script(
        tools / "Winetricks.sh",
        WINETRICKS.replace("{{PREFIX_PATH}}", prefix_s),
    )
    dxvk = tools / "dxvk.conf"
    if not dxvk.exists():
        dxvk.write_text(
            "# Kalium DXVK settings\ndxvk.enableGraphicsPipelineLibrary = False\n",
            encoding="utf-8",
        )
    log_install(f"Kalium Tools created in {install_dir}")
    # Auto-enable NXM for this instance so browser links work immediately
    try:
        from kalium.nxm import activate_for_install
        activate_for_install(install_dir, prefix_path, proton_path, app_id, manager_name)
        log_install("NXM handler activated for this MO2 instance")
    except Exception as e:
        log_warning(f"NXM auto-activate failed: {e}")
