"""Ensure vcrun2022 is present in an MO2 instance Wine prefix (for LOOT).

The invocation that works in a normal terminal is simply::

    WINEPREFIX="$HOME/.steam/steam/steamapps/compatdata/<appid>/pfx" \\
      winetricks -q vcrun2022

Earlier Kalium code forced Proton's ``WINE``/``WINESERVER`` and a private
winetricks binary; that combination often fails while the plain shell
command succeeds. This module mirrors the terminal approach first, then
falls back to Proton wine only if needed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

from kalium.logging_utils import log_install, log_warning


StatusCb = Optional[Callable[[str], None]]


def _status(cb: StatusCb, msg: str) -> None:
    log_install(msg)
    if cb:
        try:
            cb(msg)
        except Exception:
            pass


def _find_winetricks() -> str:
    """Prefer the same winetricks the user gets in a login shell (PATH)."""
    # 1) PATH (matches terminal)
    found = shutil.which("winetricks")
    if found:
        return found
    # 2) Kalium-managed copy
    try:
        from kalium.deps import ensure_winetricks

        wt = ensure_winetricks()
        if wt and Path(wt).is_file():
            return str(wt)
    except Exception as e:
        log_warning(f"ensure_winetricks failed: {e}")
    # 3) Common locations
    for p in (
        Path.home() / ".config/kalium/bin/winetricks",
        Path("/usr/bin/winetricks"),
        Path("/usr/local/bin/winetricks"),
    ):
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    raise RuntimeError(
        "winetricks not found on PATH. Install it (e.g. your distro package) "
        "or ensure `which winetricks` works in a terminal."
    )


def _normalize_pfx(prefix_path: Path) -> Path:
    """Accept either …/compatdata/<id>/pfx or …/compatdata/<id>."""
    p = Path(prefix_path).expanduser()
    try:
        p = p.resolve()
    except OSError:
        pass
    if p.name != "pfx" and (p / "pfx").is_dir():
        p = p / "pfx"
    if not p.is_dir():
        raise RuntimeError(f"Wine prefix not found: {prefix_path}")
    # Sanity: drive_c is a real prefix
    if not (p / "drive_c").is_dir() and not (p / "system.reg").is_file():
        log_warning(
            f"Prefix looks incomplete (no drive_c/system.reg yet): {p} — "
            "launch MO2 once via Steam if winetricks fails."
        )
    return p


def resolve_proton_for_prefix(proton_config_name: Optional[str] = None):
    from kalium.steam import find_steam_protons

    protons = find_steam_protons()
    if not protons:
        return None
    if proton_config_name:
        want = proton_config_name.lower()
        for p in protons:
            if p.config_name == proton_config_name or p.name == proton_config_name:
                return p
            if p.name.lower() == want or p.config_name.lower() == want:
                return p
    return protons[0]


def _run_winetricks(
    wt: str,
    prefix: Path,
    env: dict,
    status: StatusCb,
) -> subprocess.CompletedProcess:
    cmd = [wt, "-q", "vcrun2022"]
    shown = f'WINEPREFIX="{prefix}" {" ".join(cmd)}'
    _status(status, f"Running:\n{shown}")
    log_install(f"exec: {shown}")
    # Do NOT capture in a way that blocks GUI wine dialogs forever — still
    # capture so we can show errors, but inherit stdin and leave a long timeout.
    return subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60 * 45,
        cwd=str(Path.home()),
    )


def _ok_output(out: str, code: int) -> bool:
    if code == 0:
        return True
    low = (out or "").lower()
    markers = (
        "already installed",
        "is already installed",
        "already been installed",
        "vcrun2022 already",
    )
    return any(m in low for m in markers)


def run_vcrun2022_for_prefix(
    prefix_path: Path | str,
    *,
    proton_config_name: Optional[str] = None,
    status: StatusCb = None,
) -> None:
    """
    Match the working terminal command first::

        WINEPREFIX=<pfx> winetricks -q vcrun2022

    Only if that fails, retry with Proton's wine on WINE/WINESERVER.
    """
    prefix = _normalize_pfx(Path(prefix_path))
    wt = _find_winetricks()
    _status(status, f"winetricks={wt}\nprefix={prefix}")

    # --- Attempt 1: same as terminal (WINEPREFIX only) ---
    env1 = os.environ.copy()
    env1["WINEPREFIX"] = str(prefix)
    # Keep user's DISPLAY / WAYLAND so any silent UI bits can run
    # Do not force WINE= here — let winetricks find wine like the shell does.
    env1.pop("WINE", None)
    env1.pop("WINESERVER", None)
    env1.setdefault("WINEDLLOVERRIDES", "mshtml=d")

    proc = _run_winetricks(wt, prefix, env1, status)
    out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    if out:
        log_install(out[-2000:])
    if _ok_output(out, proc.returncode):
        _status(
            status,
            f"✓ vcrun2022 OK (terminal-style)\nWINEPREFIX={prefix}\n"
            + (out[-400:] if out else ""),
        )
        return

    log_warning(
        f"Terminal-style winetricks failed (exit {proc.returncode}); "
        "retrying with Proton wine…"
    )
    _status(
        status,
        f"First try failed (exit {proc.returncode}). Retrying with Proton wine…\n"
        + (out[-500:] if out else ""),
    )

    # --- Attempt 2: Proton wine (some installs only have that) ---
    proton = resolve_proton_for_prefix(proton_config_name)
    if not proton or not proton.wine_binary():
        raise RuntimeError(
            f"winetricks vcrun2022 failed with system wine, and no Proton wine "
            f"was available to retry.\nPrefix: {prefix}\nOutput:\n{out[-1500:]}"
        )

    env2 = os.environ.copy()
    env2["WINEPREFIX"] = str(prefix)
    env2["WINE"] = str(proton.wine_binary())
    ws = proton.wineserver_binary()
    if ws:
        env2["WINESERVER"] = str(ws)
    env2.setdefault("WINEDLLOVERRIDES", "mshtml=d")

    proc2 = _run_winetricks(wt, prefix, env2, status)
    out2 = ((proc2.stdout or "") + "\n" + (proc2.stderr or "")).strip()
    if out2:
        log_install(out2[-2000:])
    if _ok_output(out2, proc2.returncode):
        _status(
            status,
            f"✓ vcrun2022 OK (Proton wine)\nWINEPREFIX={prefix}\nWINE={env2['WINE']}\n"
            + (out2[-400:] if out2 else ""),
        )
        return

    raise RuntimeError(
        f"winetricks vcrun2022 failed (exit {proc2.returncode}).\n"
        f"Command: WINEPREFIX=\"{prefix}\" {wt} -q vcrun2022\n"
        f"Output:\n{(out2 or out)[-1800:]}"
    )


def run_vcrun2022_for_managed(
    app_id: int,
    prefix_path: Path | str,
    proton_config_name: Optional[str] = None,
    status: StatusCb = None,
) -> None:
    run_vcrun2022_for_prefix(
        prefix_path,
        proton_config_name=proton_config_name,
        status=status,
    )
