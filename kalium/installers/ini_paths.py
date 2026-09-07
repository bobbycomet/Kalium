"""Normalize customExecutables path fields + USVFS max_memory in ModOrganizer.ini."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

_WIN_PATH_TOKEN = re.compile(r'([A-Za-z]:)((?:\\[^\\\s"]+)+)')
_PATH_FIELDS = ("binary", "workingDirectory", "arguments")
DEFAULT_VFS_MAX_MEMORY = 2147483648  # 2 GB


def _to_forward_slashes(value: str) -> str:
    def repl(m: re.Match) -> str:
        drive, rest = m.group(1), m.group(2)
        return drive + rest.replace("\\", "/")
    return _WIN_PATH_TOKEN.sub(repl, value)


def sanitize_custom_executable_paths(mo2_install_path: Path) -> int:
    ini = Path(mo2_install_path) / "ModOrganizer.ini"
    if not ini.is_file():
        return 0
    text = ini.read_text(encoding="utf-8", errors="replace")
    changed = 0

    def fix_field(m: re.Match) -> str:
        nonlocal changed
        prefix, value = m.group(1), m.group(2)
        new_value = _to_forward_slashes(value)
        if new_value != value:
            changed += 1
        return prefix + new_value

    for field in _PATH_FIELDS:
        pattern = re.compile(rf"(?im)^(\d+\\{field}\s*=\s*)(.*)$")
        text = pattern.sub(fix_field, text)
    if changed:
        shutil.copy2(ini, ini.with_suffix(".ini.kalium.bak"))
        ini.write_text(text, encoding="utf-8")
    return changed


def set_vfs_max_memory(mo2_install_path: Path, max_memory: int = DEFAULT_VFS_MAX_MEMORY) -> bool:
    """Ensure [vfs] max_memory=<bytes> in ModOrganizer.ini (default 2 GB)."""
    mo2_install_path = Path(mo2_install_path)
    ini = mo2_install_path / "ModOrganizer.ini"
    if not ini.is_file():
        from kalium.logging_utils import log_warning
        log_warning(
            "ModOrganizer.ini not found — cannot set [vfs] max_memory until MO2 has been launched once."
        )
        return False
    max_memory = int(max_memory)
    if max_memory < 64 * 1024 * 1024:
        raise ValueError("max_memory must be at least 64 MiB")
    text = ini.read_text(encoding="utf-8", errors="replace")
    value_line = f"max_memory={max_memory}"
    if re.search(r"(?im)^\[vfs\]\s*$", text):
        if re.search(r"(?im)^max_memory\s*=", text):
            new_text = re.sub(r"(?im)^(max_memory\s*=).*$", rf"\g<1>{max_memory}", text, count=1)
        else:
            new_text = re.sub(r"(?im)^(\[vfs\]\s*\n)", rf"\1{value_line}\n", text, count=1)
    else:
        new_text = text.rstrip() + f"\n\n[vfs]\n{value_line}\n"
    if new_text == text:
        return True
    shutil.copy2(ini, ini.with_suffix(".ini.kalium.bak"))
    ini.write_text(new_text, encoding="utf-8")
    from kalium.logging_utils import log_install
    log_install(f"USVFS [vfs] max_memory set to {max_memory} ({max_memory // (1024 * 1024)} MiB)")
    return True
