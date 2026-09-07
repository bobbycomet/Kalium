"""Steam config.vdf CompatToolMapping helpers."""

from __future__ import annotations

import shutil
from pathlib import Path

from kalium.steam.paths import find_steam_path


def set_compat_tool(app_id: int, proton_name: str) -> None:
    if not proton_name or '"' in proton_name or "\n" in proton_name or "\r" in proton_name:
        raise ValueError(f"Invalid Proton name: {proton_name!r}")
    steam = find_steam_path()
    if not steam:
        raise RuntimeError("Steam not found")
    config_path = steam / "config" / "config.vdf"
    if not config_path.exists():
        raise RuntimeError("Steam config.vdf not found")
    content = config_path.read_text(encoding="utf-8", errors="replace")
    app_id_str = str(app_id)

    # Try simple update of existing name line for this app id
    marker = f'"{app_id_str}"'
    if '"CompatToolMapping"' in content and marker in content:
        # Replace name field near this app id block — best-effort
        lines = content.splitlines(keepends=True)
        in_block = False
        depth = 0
        for i, line in enumerate(lines):
            if marker in line and not in_block:
                in_block = True
                depth = 0
            if in_block:
                if "{" in line:
                    depth += line.count("{")
                if "}" in line:
                    depth -= line.count("}")
                if '"name"' in line:
                    indent = line[: len(line) - len(line.lstrip())]
                    lines[i] = f'{indent}"name"\t\t"{proton_name}"\n'
                    new_content = "".join(lines)
                    backup = steam / "config" / "config.vdf.kalium.bak"
                    shutil.copy2(config_path, backup)
                    config_path.write_text(new_content, encoding="utf-8")
                    return
                if depth <= 0 and "}" in line:
                    in_block = False

    # Insert new entry into CompatToolMapping
    entry = (
        f'\t\t\t\t\t"{app_id_str}"\n'
        f"\t\t\t\t\t{{\n"
        f'\t\t\t\t\t\t"name"\t\t"{proton_name}"\n'
        f'\t\t\t\t\t\t"config"\t\t""\n'
        f'\t\t\t\t\t\t"priority"\t\t"250"\n'
        f"\t\t\t\t\t}}"
    )
    needle = '"CompatToolMapping"\n\t\t\t\t{'
    if needle in content:
        new_content = content.replace(needle, needle + "\n" + entry, 1)
    elif '"CompatToolMapping"' in content:
        # Variant whitespace
        import re

        new_content, n = re.subn(
            r'("CompatToolMapping"\s*\{)',
            r"\1\n" + entry,
            content,
            count=1,
        )
        if n == 0:
            raise RuntimeError("Failed to insert CompatToolMapping entry")
    else:
        # Create section under Steam
        section = f'\t\t\t\t"CompatToolMapping"\n\t\t\t\t{{\n{entry}\n\t\t\t\t}}'
        steam_marker = '"Steam"\n\t\t\t{'
        if steam_marker in content:
            pos = content.find(steam_marker)
            insert_at = content.find("\n", pos) + 1
            new_content = content[:insert_at] + section + "\n" + content[insert_at:]
        else:
            raise RuntimeError("Could not find Steam section in config.vdf")

    if new_content == content:
        raise RuntimeError("Failed to modify config.vdf")
    backup = steam / "config" / "config.vdf.kalium.bak"
    shutil.copy2(config_path, backup)
    config_path.write_text(new_content, encoding="utf-8")
