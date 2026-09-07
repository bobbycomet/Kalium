"""Wine registry file parsing."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from kalium.logging_utils import log_warning


def read_registry_value(prefix: Path, key_path: str, value_name: str) -> Optional[str]:
    for reg_name in ("system.reg", "user.reg"):
        path = prefix / reg_name
        val = _read_from_file(path, key_path, value_name)
        if val is not None:
            return val
    return None


def _read_from_file(reg_file: Path, key_path: str, value_name: str) -> Optional[str]:
    if not reg_file.exists():
        return None
    try:
        content = reg_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    wine_key = "[" + key_path.lower().replace("\\", "\\\\") + "]"
    stripped = key_path
    if stripped.lower().startswith("software\\"):
        stripped = stripped[len("Software\\") :]
    wine_key_wow = "[software\\\\wow6432node\\\\" + stripped.lower().replace("\\", "\\\\") + "]"
    for key in (wine_key, wine_key_wow):
        val = _find_value(content, key, value_name)
        if val is not None:
            return val
    return None


def _find_value(content: str, key: str, value_name: str) -> Optional[str]:
    in_key = False
    vn = value_name.lower()
    for line in content.splitlines():
        t = line.strip()
        if t.startswith("[") and t.endswith("]"):
            in_key = t.lower() == key.lower()
            continue
        if not in_key:
            continue
        if t.startswith("["):
            break
        if "=" not in t:
            continue
        name_part, val_part = t.split("=", 1)
        name = name_part.strip().strip('"')
        if name.lower() != vn:
            continue
        if val_part.startswith('"'):
            return _unquote(val_part)
        if val_part.startswith("dword:"):
            try:
                return str(int(val_part[6:], 16))
            except ValueError:
                return val_part
        return val_part
    return None


def _unquote(s: str) -> str:
    s = s.strip()
    if not s.startswith('"'):
        return s
    out = []
    i = 1
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            mapping = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"'}
            out.append(mapping.get(nxt, "\\" + nxt))
            i += 2
            continue
        if c == '"':
            break
        out.append(c)
        i += 1
    return "".join(out)


def wine_path_to_linux(wine_path: str) -> Optional[Path]:
    path = wine_path.strip()
    if path.lower().startswith("z:"):
        return Path(path[2:].replace("\\", "/"))
    if path.lower().startswith("c:"):
        log_warning(f"Cannot convert C: path without prefix context: {path}")
        return None
    return None
