"""Structured logging for Kalium."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, TextIO

_log_file: Optional[TextIO] = None
_log_path: Optional[Path] = None


def default_log_dir() -> Path:
    """Writable log directory (never inside an AppImage mount)."""
    # Prefer XDG state, then data, then home
    xdg_state = os.environ.get("XDG_STATE_HOME")
    if xdg_state:
        return Path(xdg_state) / "kalium" / "logs"
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data) / "kalium" / "logs"
    return Path.home() / ".local" / "share" / "kalium" / "logs"


def _detect_distro() -> str:
    try:
        data = Path("/etc/os-release").read_text(encoding="utf-8")
        for line in data.splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip().strip('"')
            if line.startswith("NAME="):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return platform.system()


def _detect_gpu() -> str:
    try:
        out = subprocess.check_output(["lspci"], text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            if "VGA" in line or "3D" in line or "Display" in line:
                return line.split(":", 2)[-1].strip()[:80]
    except (OSError, subprocess.SubprocessError):
        pass
    return "Unknown"


def init_logger(log_dir: Optional[Path] = None) -> Path:
    """Create a timestamped log file in a writable user directory."""
    global _log_file, _log_path
    if log_dir is None:
        log_dir = default_log_dir()
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Last resort: /tmp
        log_dir = Path("/tmp") / "kalium-logs"
        log_dir.mkdir(parents=True, exist_ok=True)

    logs = sorted(log_dir.glob("kalium_*.log"))
    while len(logs) >= 10:
        try:
            logs[0].unlink()
        except OSError:
            pass
        logs = logs[1:]

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    _log_path = log_dir / f"kalium_{ts}.log"
    try:
        _log_file = open(_log_path, "a", encoding="utf-8")
    except OSError:
        _log_path = Path("/tmp") / f"kalium_{ts}.log"
        _log_file = open(_log_path, "a", encoding="utf-8")

    try:
        version = __import__("kalium").__version__
    except Exception:
        version = "unknown"

    header = f"""================================================================================
Kalium Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
================================================================================
Application:   Kalium v{version}
Author:        Bobby Comet
System Info:
  Distro:      {_detect_distro()}
  Kernel:      {platform.release()}
  Python:      {platform.python_version()}
  Session:     {os.environ.get('XDG_SESSION_TYPE', 'Unknown')}
  Desktop:     {os.environ.get('XDG_CURRENT_DESKTOP', 'Unknown')}
  GPU:         {_detect_gpu()}
  Argv0:       {sys.argv[0] if sys.argv else ''}
================================================================================
"""
    _write_raw(header)
    print(f"Log file: {_log_path}")
    return _log_path


def _write_raw(msg: str) -> None:
    if _log_file:
        try:
            _log_file.write(msg if msg.endswith("\n") else msg + "\n")
            _log_file.flush()
        except OSError:
            pass
    print(msg.rstrip())


def _log(level: str, message: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    _write_raw(f"[{ts}] [{level}] {message}")


def log_info(msg: str) -> None:
    _log("INFO", msg)


def log_action(msg: str) -> None:
    _log("ACTION", msg)


def log_download(msg: str) -> None:
    _log("DOWNLOAD", msg)


def log_install(msg: str) -> None:
    _log("INSTALL", msg)


def log_warning(msg: str) -> None:
    _log("WARNING", msg)


def log_error(msg: str) -> None:
    _log("ERROR", msg)
