"""Set the MO2 UI stylesheet for Kalium-created instances.

Dracula ships bundled with MO2 2.x itself, in <mo2 install>/stylesheets/
dracula.qss — there's nothing to download. This writes [Settings] style=
into ModOrganizer.ini. If the ini does not exist yet (MO2 never launched),
a minimal ini is created so the theme is applied on first launch.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Optional

from kalium.logging_utils import log_install, log_warning

DEFAULT_STYLE = "dracula.qss"


def _style_available(mo2_install_path: Path, style: str) -> bool:
    return (Path(mo2_install_path) / "stylesheets" / style).is_file()


def set_mo2_style(
    mo2_install_path: Path,
    style: str = DEFAULT_STYLE,
) -> bool:
    """
    Set ModOrganizer.ini's [Settings] style= to the given bundled .qss theme.

    Returns True if the ini was updated (or already correct). Returns False
    when the requested .qss is not present under <mo2>/stylesheets/.

    If ModOrganizer.ini is missing (MO2 not launched yet), creates a minimal
    ini with [Settings] style=<theme> so the first launch picks it up.
    Backs up an existing ini before writing.
    """
    mo2_install_path = Path(mo2_install_path)
    ini = mo2_install_path / "ModOrganizer.ini"

    if not _style_available(mo2_install_path, style):
        log_warning(
            f"{style} not found in {mo2_install_path / 'stylesheets'} — "
            "skipping theme set. This ships with stock MO2 2.x; a heavily "
            "customized install may not have it."
        )
        return False

    if not ini.is_file():
        # First install: seed a minimal ini so style is present before MO2 runs.
        # MO2 merges/extends this on first launch rather than always wiping it.
        ini.write_text(
            f"[General]\n"
            f"\n"
            f"[Settings]\n"
            f"style={style}\n",
            encoding="utf-8",
        )
        log_install(
            f"Created ModOrganizer.ini with style={style} "
            f"(MO2 had not been launched yet)"
        )
        return True

    text = ini.read_text(encoding="utf-8", errors="replace")

    if re.search(r"(?im)^\[Settings\]\s*$", text):
        if re.search(r"(?im)^style\s*=.*$", text):
            new_text = re.sub(r"(?im)^(style\s*=).*$", rf"\g<1>{style}", text, count=1)
        else:
            new_text = re.sub(
                r"(?im)^(\[Settings\]\s*\n)",
                rf"\1style={style}\n",
                text,
                count=1,
            )
    else:
        new_text = text.rstrip() + f"\n\n[Settings]\nstyle={style}\n"

    if new_text == text:
        return True  # already set

    shutil.copy2(ini, ini.with_suffix(".ini.kalium.bak"))
    ini.write_text(new_text, encoding="utf-8")
    log_install(f"MO2 theme set to {style}")
    return True
