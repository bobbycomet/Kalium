"""Kalium system diagnostics — health checks + GitHub-ready reports."""

from __future__ import annotations

import os
import platform
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional


class CheckStatus(str, Enum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class CheckResult:
    name: str
    status: CheckStatus
    detail: str = ""
    meta: dict = field(default_factory=dict)

    def symbol(self) -> str:
        return {
            CheckStatus.OK: "✓",
            CheckStatus.WARN: "⚠",
            CheckStatus.FAIL: "✗",
            CheckStatus.SKIP: "–",
        }[self.status]

    def line(self) -> str:
        base = f"{self.symbol()} {self.name}"
        if self.detail:
            return f"{base}: {self.detail}"
        return base


@dataclass
class DiagnosticReport:
    generated: str
    checks: list[CheckResult] = field(default_factory=list)
    system: dict = field(default_factory=dict)
    summary: str = ""

    def overall_ok(self) -> bool:
        return not any(c.status == CheckStatus.FAIL for c in self.checks)

    def text(self) -> str:
        lines: list[str] = []
        lines.append("Kalium Diagnostics")
        lines.append("=" * 60)
        lines.append(f"Generated: {self.generated}")
        lines.append("")
        lines.append("System")
        lines.append("-" * 40)
        for k, v in self.system.items():
            lines.append(f"  {k}: {v}")
        lines.append("")
        lines.append("Checks")
        lines.append("-" * 40)
        for c in self.checks:
            lines.append(c.line())
            for mk, mv in (c.meta or {}).items():
                lines.append(f"    {mk}: {mv}")
        lines.append("")
        lines.append("Summary")
        lines.append("-" * 40)
        lines.append(self.summary)
        lines.append("")
        lines.append("=" * 60)
        lines.append("Paste this report into a GitHub issue if you need help.")
        return "\n".join(lines)


def _detect_distro() -> str:
    try:
        data = Path("/etc/os-release").read_text(encoding="utf-8")
        for line in data.splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return platform.system()


def _detect_gpu() -> str:
    try:
        out = subprocess.check_output(["lspci"], text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            if "VGA" in line or "3D" in line or "Display" in line:
                return line.split(":", 2)[-1].strip()[:100]
    except Exception:
        pass
    return "Unknown"


def resolve_mo2_root(path: Path | str | None) -> Optional[Path]:
    """Accept MO2 root or path to ModOrganizer.exe; return root with the exe."""
    if not path:
        return None
    p = Path(path).expanduser()
    try:
        p = p.resolve()
    except OSError:
        pass
    if p.is_file() and p.name.lower() == "modorganizer.exe":
        p = p.parent
    if (p / "ModOrganizer.exe").is_file():
        return p
    # Nested extract sometimes leaves ModOrganizer-2.x.y/
    try:
        for child in p.iterdir():
            if child.is_dir() and (child / "ModOrganizer.exe").is_file():
                return child
    except OSError:
        pass
    return None


def _usvfs_version(mo2_path: Path) -> Optional[str]:
    """Best-effort USVFS version from marker / backup folder / dll presence."""
    mo2_path = Path(mo2_path)
    dll = mo2_path / "usvfs_x64.dll"
    if not dll.is_file():
        return None
    marker = mo2_path / ".kalium_usvfs_version"
    if marker.is_file():
        try:
            return marker.read_text(encoding="utf-8").strip() or "present"
        except OSError:
            pass
    # Newest backup folder wins (name encodes version Kalium installed)
    backups = sorted(mo2_path.glob(".kalium_usvfs_backup_*"), key=lambda x: x.stat().st_mtime, reverse=True)
    for p in backups:
        ver = p.name.replace(".kalium_usvfs_backup_", "")
        if ver:
            return f"{ver} (from Kalium backup marker — current dll present)"
    # Size heuristic is unreliable; report present
    try:
        size = dll.stat().st_size
        return f"present (usvfs_x64.dll {size} bytes; version unknown — no Kalium marker)"
    except OSError:
        return "present (version unknown)"


def _loot_status(mo2_path: Path) -> CheckResult:
    mo2_path = Path(mo2_path)
    exe = mo2_path / "LOOT" / "LOOT.exe"
    bat = mo2_path / "LOOT" / "run_loot.bat"
    if exe.is_file():
        extra = " + run_loot.bat" if bat.is_file() else ""
        return CheckResult(
            "LOOT (portable)",
            CheckStatus.OK,
            f"found at {exe}{extra}",
            meta={"loot_exe": str(exe), "run_loot_bat": str(bat) if bat.is_file() else ""},
        )
    # Nested
    hits = list(mo2_path.glob("**/LOOT.exe"))
    if hits:
        return CheckResult(
            "LOOT (portable)",
            CheckStatus.OK,
            f"found at {hits[0]}",
            meta={"loot_exe": str(hits[0])},
        )
    return CheckResult(
        "LOOT (portable)",
        CheckStatus.WARN,
        f"not under {mo2_path / 'LOOT'} — Settings → Install LOOT",
    )


def _inspect_mo2_instance(
    name: str,
    install_path: Path,
    *,
    app_id: str = "",
    prefix_path: str = "",
) -> list[CheckResult]:
    """Per-instance checks: exe, USVFS, LOOT, gameName in ini."""
    checks: list[CheckResult] = []
    root = resolve_mo2_root(install_path)
    label = name or install_path.name

    if not root:
        checks.append(
            CheckResult(
                f"MO2 [{label}] ModOrganizer.exe",
                CheckStatus.FAIL,
                f"not found at {install_path} — browse to the folder that contains ModOrganizer.exe",
                meta={"install_path": str(install_path), "app_id": app_id},
            )
        )
        return checks

    checks.append(
        CheckResult(
            f"MO2 [{label}] ModOrganizer.exe",
            CheckStatus.OK,
            str(root / "ModOrganizer.exe"),
            meta={
                "install_path": str(root),
                "app_id": app_id,
                "prefix_path": prefix_path,
            },
        )
    )

    ver = _usvfs_version(root)
    dll = root / "usvfs_x64.dll"
    if dll.is_file():
        status = CheckStatus.OK
        detail = ver or "present"
        if ver and "0.5.6" in ver:
            status = CheckStatus.WARN
            detail = f"{ver} — update to 0.5.7.2 recommended"
        checks.append(CheckResult(f"MO2 [{label}] USVFS", status, detail))
    else:
        checks.append(
            CheckResult(
                f"MO2 [{label}] USVFS",
                CheckStatus.WARN,
                f"usvfs_x64.dll missing under {root}",
            )
        )

    loot = _loot_status(root)
    loot.name = f"MO2 [{label}] LOOT"
    checks.append(loot)

    # Managed game binding (portable instance)
    ini = root / "ModOrganizer.ini"
    if ini.is_file():
        try:
            text = ini.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        gn = re.search(r"(?im)^\s*gameName\s*=\s*(.+?)\s*$", text)
        gp = re.search(r"(?im)^\s*gamePath\s*=\s*(.+?)\s*$", text)
        if gn and gp:
            checks.append(
                CheckResult(
                    f"MO2 [{label}] managed game",
                    CheckStatus.OK,
                    f"{gn.group(1).strip()} @ {gp.group(1).strip()[:80]}",
                )
            )
        else:
            checks.append(
                CheckResult(
                    f"MO2 [{label}] managed game",
                    CheckStatus.WARN,
                    "gameName/gamePath missing in ModOrganizer.ini — portable instance may fail to open",
                )
            )
    else:
        checks.append(
            CheckResult(
                f"MO2 [{label}] ModOrganizer.ini",
                CheckStatus.WARN,
                "ini not created yet — launch MO2 once",
            )
        )

    return checks


def _discover_mo2_candidates(extra_paths: Optional[list[Path]] = None) -> list[tuple[str, Path, str, str]]:
    """
    Return list of (name, install_path, app_id, prefix_path).

    Sources:
      1. ManagedPrefixes registry
      2. Explicit extra_paths (GUI browse)
      3. Light heuristic under ~/Kalium, ~/MO2, ~/Games
    """
    found: list[tuple[str, Path, str, str]] = []
    seen: set[Path] = set()

    def _add(name: str, path: Path, app_id: str = "", prefix: str = "") -> None:
        root = resolve_mo2_root(path)
        if not root:
            # Still record failed managed entries so diagnostics can report FAIL
            try:
                key = path.resolve()
            except OSError:
                key = path
            if key in seen:
                return
            seen.add(key)
            found.append((name, path, app_id, prefix))
            return
        if root in seen:
            return
        seen.add(root)
        found.append((name, root, app_id, prefix))

    try:
        from kalium.config import ManagedPrefixes

        for p in ManagedPrefixes.load():
            _add(
                p.name or f"AppID {p.app_id}",
                Path(p.install_path),
                str(p.app_id),
                p.prefix_path or "",
            )
    except Exception:
        pass

    for ep in extra_paths or []:
        _add(f"manual:{Path(ep).name}", Path(ep))

    # Heuristic scan — only if nothing managed yet
    if not found:
        home = Path.home()
        for base in (
            home / "Kalium",
            home / "MO2",
            home / "Games",
            home / "games",
            home / "modding",
            home / "Modding",
        ):
            if not base.is_dir():
                continue
            try:
                if (base / "ModOrganizer.exe").is_file():
                    _add(base.name, base)
                for child in base.iterdir():
                    if child.is_dir() and (child / "ModOrganizer.exe").is_file():
                        _add(child.name, child)
            except OSError:
                pass

    return found


def run_diagnostics(
    *,
    extra_mo2_paths: Optional[list[Path | str]] = None,
) -> DiagnosticReport:
    """Run all health checks and return a structured report.

    ``extra_mo2_paths``: optional MO2 roots or ModOrganizer.exe paths from the GUI
    so diagnostics still works when managed_prefixes.json is empty/stale.
    """
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    system = {
        "Kalium": _kalium_version(),
        "Distro": _detect_distro(),
        "Kernel": platform.release(),
        "Python": platform.python_version(),
        "Session": os.environ.get("XDG_SESSION_TYPE", "Unknown"),
        "Desktop": os.environ.get("XDG_CURRENT_DESKTOP", "Unknown"),
        "GPU": _detect_gpu(),
    }

    checks: list[CheckResult] = []

    # --- Steam ---
    steam = None
    try:
        from kalium.steam.paths import find_steam_path

        steam = find_steam_path()
    except Exception as e:
        checks.append(CheckResult("Steam detected", CheckStatus.FAIL, str(e)))
    if steam:
        checks.append(CheckResult("Steam detected", CheckStatus.OK, str(steam)))
    elif not any(c.name == "Steam detected" for c in checks):
        checks.append(CheckResult("Steam detected", CheckStatus.FAIL, "not found"))

    # --- Libraries ---
    try:
        from kalium.steam.paths import find_all_steam_libraries, parse_all_library_entries

        libs = find_all_steam_libraries()
        if libs:
            checks.append(
                CheckResult(
                    "Steam libraries detected",
                    CheckStatus.OK,
                    f"{len(libs)} library root(s)",
                    meta={f"lib_{i}": str(p) for i, p in enumerate(libs)},
                )
            )
            try:
                entries = parse_all_library_entries()
                if entries:
                    checks[-1].meta["vdf_entries"] = str(len(entries))
            except Exception:
                pass
        else:
            checks.append(CheckResult("Steam libraries detected", CheckStatus.FAIL, "none found"))
    except Exception as e:
        checks.append(CheckResult("Steam libraries detected", CheckStatus.WARN, str(e)))

    # --- Skyrim SE (489830) ---
    skyrim_app = "489830"
    try:
        from kalium.steam.paths import find_library_for_app, find_compatdata_for_app, find_pfx_for_app

        owner = find_library_for_app(skyrim_app)
        if owner:
            checks.append(CheckResult("Skyrim SE detected", CheckStatus.OK, f"library {owner}"))
            checks.append(CheckResult("AppID", CheckStatus.OK, skyrim_app))
            checks.append(CheckResult("Game library", CheckStatus.OK, str(owner)))
        else:
            checks.append(
                CheckResult(
                    "Skyrim SE detected",
                    CheckStatus.WARN,
                    "AppID 489830 not found in any library (not installed or offline drive)",
                )
            )
            checks.append(CheckResult("AppID", CheckStatus.SKIP, skyrim_app))
            checks.append(CheckResult("Game library", CheckStatus.SKIP, "n/a"))

        compat = find_compatdata_for_app(skyrim_app)
        if compat:
            checks.append(CheckResult("CompatData detected", CheckStatus.OK, str(compat)))
        else:
            checks.append(
                CheckResult(
                    "CompatData detected",
                    CheckStatus.WARN if owner else CheckStatus.SKIP,
                    "no compatdata/489830 (game may not have been launched yet)",
                )
            )

        pfx = find_pfx_for_app(skyrim_app)
        if pfx:
            checks.append(CheckResult("Wine prefix detected", CheckStatus.OK, str(pfx)))
        else:
            checks.append(
                CheckResult(
                    "Wine prefix detected",
                    CheckStatus.WARN if owner else CheckStatus.SKIP,
                    "no pfx under compatdata",
                )
            )
    except Exception as e:
        checks.append(CheckResult("Skyrim SE detected", CheckStatus.WARN, str(e)))

    # --- MO2 instances (managed + optional manual path) ---
    extras = [Path(p) for p in (extra_mo2_paths or []) if p]
    instances = _discover_mo2_candidates(extras)
    if not instances:
        checks.append(
            CheckResult(
                "MO2 instance detected",
                CheckStatus.WARN,
                "no managed instances and no path provided — "
                "run MO2 setup, or set MO2 folder on the Diagnostics page",
            )
        )
    else:
        checks.append(
            CheckResult(
                "MO2 instances discovered",
                CheckStatus.OK,
                f"{len(instances)} location(s)",
                meta={f"mo2_{i}": str(p[1]) for i, p in enumerate(instances)},
            )
        )
        for name, path, app_id, prefix in instances:
            checks.extend(
                _inspect_mo2_instance(name, path, app_id=app_id, prefix_path=prefix)
            )

    # --- Proton ---
    try:
        from kalium.steam import find_steam_protons

        protons = find_steam_protons()
        if protons:
            names = ", ".join(p.name for p in protons[:5])
            more = f" (+{len(protons)-5} more)" if len(protons) > 5 else ""
            checks.append(
                CheckResult(
                    "Proton detected",
                    CheckStatus.OK,
                    f"{len(protons)} version(s): {names}{more}",
                )
            )
        else:
            checks.append(
                CheckResult(
                    "Proton detected",
                    CheckStatus.FAIL,
                    "no Proton 10+ found — install Proton Experimental or GE-Proton 10+",
                )
            )
    except Exception as e:
        checks.append(CheckResult("Proton detected", CheckStatus.FAIL, str(e)))

    # --- STEAM_COMPAT_MOUNTS ---
    try:
        from kalium.steam.paths import steam_compat_mounts

        mounts = steam_compat_mounts()
        if mounts:
            checks.append(
                CheckResult(
                    "STEAM_COMPAT_MOUNTS",
                    CheckStatus.OK,
                    f"{len(mounts)} path(s)",
                    meta={"value": ":".join(mounts)},
                )
            )
        else:
            checks.append(
                CheckResult(
                    "STEAM_COMPAT_MOUNTS",
                    CheckStatus.WARN,
                    "empty — secondary drives may be invisible inside Proton",
                )
            )
    except Exception as e:
        checks.append(CheckResult("STEAM_COMPAT_MOUNTS", CheckStatus.WARN, str(e)))

    # --- NXM ---
    try:
        from kalium.nxm import read_active, NxmHandler

        active = read_active()
        if active:
            checks.append(
                CheckResult(
                    "NXM handler registered",
                    CheckStatus.OK,
                    f"active for {active.get('name') or 'MO2'}",
                    meta={
                        "exe": str(active.get("exe") or ""),
                        "prefix": str(active.get("prefix") or ""),
                        "app_id": str(active.get("app_id") or ""),
                    },
                )
            )
        else:
            checks.append(
                CheckResult(
                    "NXM handler registered",
                    CheckStatus.WARN,
                    "no active instance — enable NXM in Settings after MO2 setup",
                )
            )
        try:
            status_txt = NxmHandler.status() if hasattr(NxmHandler, "status") else ""
            if status_txt:
                checks.append(CheckResult("NXM desktop handler", CheckStatus.OK, status_txt[:120]))
        except Exception:
            pass
    except Exception as e:
        checks.append(CheckResult("NXM handler registered", CheckStatus.WARN, str(e)))

    # --- External LOOT warning (system package) ---
    primary_mo2 = instances[0][1] if instances else None
    root0 = resolve_mo2_root(primary_mo2) if primary_mo2 else None
    if root0 and (root0 / "LOOT" / "LOOT.exe").is_file():
        pass  # already covered per-instance
    else:
        checks.append(_loot_external_warning(root0))

    # --- Steam running ---
    try:
        from kalium.steam.shortcuts import is_steam_running

        if is_steam_running():
            checks.append(
                CheckResult(
                    "Steam process",
                    CheckStatus.WARN,
                    "Steam is running — exit fully before installing/repairing shortcuts",
                )
            )
        else:
            checks.append(CheckResult("Steam process", CheckStatus.OK, "not running"))
    except Exception:
        checks.append(CheckResult("Steam process", CheckStatus.SKIP, "could not determine"))

    # Summary
    fails = sum(1 for c in checks if c.status == CheckStatus.FAIL)
    warns = sum(1 for c in checks if c.status == CheckStatus.WARN)
    if fails:
        summary = (
            f"Environment has {fails} failure(s) and {warns} warning(s). "
            "Fix failures before installing MO2."
        )
    elif warns:
        summary = f"Environment appears usable with {warns} warning(s). Review items marked ⚠."
    else:
        summary = "Environment appears healthy."

    return DiagnosticReport(
        generated=generated,
        checks=checks,
        system=system,
        summary=summary,
    )


def _loot_external_warning(mo2_path: Optional[Path]) -> CheckResult:
    if mo2_path and (mo2_path / "LOOT" / "LOOT.exe").is_file():
        return CheckResult(
            "LOOT (portable)",
            CheckStatus.OK,
            f"found at {mo2_path / 'LOOT' / 'LOOT.exe'}",
        )
    which = None
    try:
        which = subprocess.check_output(
            ["which", "LOOT", "loot"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        pass
    for candidate in (
        Path.home() / ".local/share/LOOT",
        Path("/usr/bin/LOOT"),
        Path("/usr/games/LOOT"),
    ):
        if candidate.exists():
            return CheckResult(
                "External LOOT",
                CheckStatus.WARN,
                "unsupported under Proton — prefer Kalium portable LOOT next to MO2",
                meta={"path": str(candidate)},
            )
    if which:
        return CheckResult(
            "External LOOT",
            CheckStatus.WARN,
            f"system binary at {which} — unsupported under Proton",
        )
    return CheckResult(
        "LOOT",
        CheckStatus.SKIP,
        "no portable LOOT in MO2 and no system LOOT detected",
    )


def _kalium_version() -> str:
    try:
        return __import__("kalium").__version__
    except Exception:
        return "unknown"


def default_report_path() -> Path:
    base = Path.home() / ".local" / "share" / "kalium" / "diagnostics"
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        base = Path("/tmp") / "kalium-diagnostics"
        base.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return base / f"kalium_diagnose_{ts}.txt"


def write_report(report: Optional[DiagnosticReport] = None, path: Optional[Path] = None) -> Path:
    report = report or run_diagnostics()
    path = path or default_report_path()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.text(), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# check-steam structured data, status, list-mo2
# ---------------------------------------------------------------------------


def collect_check_steam_data() -> dict:
    data: dict = {
        "steam_path": None,
        "steam_running": None,
        "protons": [],
        "libraries": [],
        "library_entries": [],
        "games": {},
        "mounts": [],
        "steam_compat_mounts": "",
        "accounts": [],
        "userdata": None,
        "shortcuts_vdf": None,
        "shortcuts": [],
    }
    try:
        from kalium.steam import (
            find_steam_path,
            find_steam_protons,
            find_userdata_path,
            get_steam_accounts,
            is_steam_running,
        )
        from kalium.steam.paths import (
            find_all_steam_libraries,
            parse_all_library_entries,
            find_library_for_app,
            find_compatdata_for_app,
            steam_compat_mounts_env,
        )
        from kalium.steam.shortcuts import ShortcutsVdf, detect_extra_mounts

        steam = find_steam_path()
        data["steam_path"] = str(steam) if steam else None
        data["steam_running"] = bool(is_steam_running())
        data["protons"] = [
            {
                "name": p.name,
                "config_name": p.config_name,
                "path": str(p.path),
                "is_steam_proton": p.is_steam_proton,
                "is_experimental": p.is_experimental,
            }
            for p in find_steam_protons()
        ]
        libs = find_all_steam_libraries()
        for lib in libs:
            try:
                is_primary = steam is not None and lib.resolve() == steam.resolve()
            except OSError:
                is_primary = False
            data["libraries"].append(
                {
                    "path": str(lib),
                    "primary": is_primary,
                    "steamapps": (lib / "steamapps").is_dir(),
                }
            )
        for entry in parse_all_library_entries():
            data["library_entries"].append(
                {
                    "path": str(entry["path"]),
                    "app_count": len(entry.get("apps") or []),
                    "apps_sample": sorted(list(entry.get("apps") or []))[:20],
                }
            )
        for app_id, label in (
            ("489830", "Skyrim SE"),
            ("22380", "Fallout NV"),
            ("377160", "Fallout 4"),
            ("1716740", "Starfield"),
        ):
            owner = find_library_for_app(app_id)
            compat = find_compatdata_for_app(app_id)
            if owner or compat:
                data["games"][app_id] = {
                    "name": label,
                    "library": str(owner) if owner else None,
                    "compatdata": str(compat) if compat else None,
                }
        mounts = detect_extra_mounts()
        data["mounts"] = mounts
        data["steam_compat_mounts"] = steam_compat_mounts_env()
        for a in get_steam_accounts():
            data["accounts"].append(
                {
                    "account_id": a.account_id,
                    "persona_name": a.persona_name,
                    "most_recent": a.most_recent,
                }
            )
        ud = find_userdata_path()
        data["userdata"] = str(ud) if ud else None
        if ud:
            sp = ShortcutsVdf.path_for_userdata(ud)
            data["shortcuts_vdf"] = str(sp)
            if sp.exists():
                v = ShortcutsVdf.load(sp)
                for s in v.shortcuts:
                    data["shortcuts"].append(
                        {
                            "app_name": s.app_name,
                            "appid": s.appid,
                            "exe": s.exe,
                            "launch_options": s.launch_options,
                        }
                    )
    except Exception as e:
        data["error"] = str(e)
    return data


def _read_ini_value(ini: Path, key: str) -> Optional[str]:
    if not ini.is_file():
        return None
    try:
        text = ini.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.search(rf"(?im)^\s*{re.escape(key)}\s*=\s*(.+?)\s*$", text)
    if m:
        return m.group(1).strip().strip('"')
    return None


def _vfs_max_memory(mo2_path: Path) -> Optional[str]:
    ini = mo2_path / "ModOrganizer.ini"
    val = _read_ini_value(ini, "max_memory")
    if not val:
        return None
    try:
        n = int(val)
        gib = n / (1024 ** 3)
        if gib >= 1:
            return f"{n} ({gib:g} GiB)"
        return f"{n} ({n // (1024 ** 2)} MiB)"
    except ValueError:
        return val


def _has_collections_plugin(mo2_path: Path) -> bool:
    plugins = mo2_path / "plugins"
    if not plugins.is_dir():
        return False
    try:
        for p in plugins.rglob("*"):
            name = p.name.lower()
            if "collection" in name:
                return True
    except OSError:
        pass
    return False


def _skyrim_runtime_guess(game_dir: Optional[Path]) -> Optional[str]:
    if not game_dir:
        return None
    exe = game_dir / "SkyrimSE.exe"
    if not exe.is_file():
        return None
    try:
        from kalium.tools.skyrim_backpatch import sniff_runtime_versions, primary_runtime_guess

        vers = sniff_runtime_versions(exe)
        return primary_runtime_guess(vers)
    except Exception:
        marker = game_dir / "kalium_backpatch.txt"
        if marker.is_file():
            try:
                for line in marker.read_text(encoding="utf-8", errors="replace").splitlines():
                    if line.startswith("target="):
                        return line.split("=", 1)[1].strip()
            except OSError:
                pass
    return None


def list_mo2_instances() -> list[dict]:
    from kalium.config import ManagedPrefixes

    out: list[dict] = []
    try:
        from kalium.nxm import read_active

        active = read_active() or {}
        active_id = int(active.get("app_id") or 0)
    except Exception:
        active_id = 0

    for p in ManagedPrefixes.load():
        install = Path(p.install_path)
        root = resolve_mo2_root(install) or install
        prefix = Path(p.prefix_path) if p.prefix_path else None
        item = {
            "name": p.name,
            "app_id": p.app_id,
            "manager_type": p.manager_type,
            "install_path": str(root),
            "prefix_path": str(prefix) if prefix else "",
            "proton": p.proton_config_name or "",
            "exe_ok": (root / "ModOrganizer.exe").is_file(),
            "prefix_ok": bool(prefix and prefix.exists()),
            "nxm_active": p.app_id == active_id,
            "usvfs": _usvfs_version(root) if root.is_dir() else None,
            "vfs_memory": _vfs_max_memory(root) if root.is_dir() else None,
            "collections": _has_collections_plugin(root) if root.is_dir() else False,
            "loot": (root / "LOOT" / "LOOT.exe").is_file() if root.is_dir() else False,
            "created": getattr(p, "created", "") or "",
        }
        out.append(item)
    return out


def format_list_mo2(instances: Optional[list[dict]] = None) -> str:
    instances = instances if instances is not None else list_mo2_instances()
    lines = ["Installed MO2 Instances", ""]
    if not instances:
        lines.append("  (none — run MO2 setup in Kalium)")
        return "\n".join(lines)
    for i, inst in enumerate(instances, 1):
        mark = "  ✓ NXM" if inst.get("nxm_active") else ""
        lines.append(f"{i}. {inst['name']}{mark}")
        lines.append(f"   {inst['install_path']}")
        proton = inst.get("proton") or "(unknown)"
        lines.append(f"   Proton: {proton}")
        lines.append(f"   AppID: {inst['app_id']}")
        lines.append(f"   ModOrganizer.exe: {'✓' if inst.get('exe_ok') else '✗'}")
        if inst.get("usvfs"):
            lines.append(f"   USVFS: {inst['usvfs']}")
        lines.append(f"   LOOT: {'✓' if inst.get('loot') else '✗'}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_status_report() -> str:
    lines: list[str] = ["Kalium Status", ""]
    instances = list_mo2_instances()
    lines.append("MO2")
    if not instances:
        lines.append("  Instance: (none managed)")
        lines.append("  Path: —")
        lines.append("  Proton: —")
        lines.append("  USVFS: —")
        lines.append("  VFS memory: —")
        lines.append("  LOOT: —")
        lines.append("  NXM: ✗")
        lines.append("  Steam shortcut: —")
        lines.append("  Collections: —")
    else:
        inst = next((i for i in instances if i.get("nxm_active")), instances[0])
        lines.append(f"  Instance: {inst['name']}")
        lines.append(f"  Path: {inst['install_path']}")
        lines.append(f"  ModOrganizer.exe: {'✓' if inst.get('exe_ok') else '✗'}")
        lines.append(f"  Proton: {inst.get('proton') or '(unknown)'}")
        lines.append(f"  USVFS: {inst.get('usvfs') or 'unknown'}")
        lines.append(f"  VFS memory: {inst.get('vfs_memory') or '(not set)'}")
        lines.append(f"  LOOT: {'✓' if inst.get('loot') else '✗'}")
        lines.append(f"  NXM: {'✓' if inst.get('nxm_active') else '✗ (not active for this instance)'}")
        lines.append(f"  Steam shortcut: {'✓' if inst.get('app_id') else '✗'}")
        lines.append(f"  Collections: {'✓' if inst.get('collections') else '✗'}")
        if len(instances) > 1:
            lines.append(f"  (+{len(instances)-1} other managed instance(s) — see kalium list-mo2)")
    lines.append("")

    lines.append("Game")
    try:
        from kalium.steam.paths import find_library_for_app, find_compatdata_for_app

        owner = find_library_for_app("489830")
        compat = find_compatdata_for_app("489830")
        if owner:
            lines.append("  Skyrim SE")
            lines.append("  AppID: 489830")
            lines.append(f"  Library: {owner}")
            game_dir = None
            common = owner / "steamapps" / "common"
            for name in ("Skyrim Special Edition", "Skyrim Special Edition GOG"):
                if (common / name / "SkyrimSE.exe").is_file():
                    game_dir = common / name
                    break
            if not game_dir and common.is_dir():
                try:
                    for child in common.iterdir():
                        if (child / "SkyrimSE.exe").is_file():
                            game_dir = child
                            break
                except OSError:
                    pass
            runtime = _skyrim_runtime_guess(game_dir)
            lines.append(f"  Runtime: {runtime or '(unknown — launch once or run backpatch diagnose)'}")
            if compat:
                lines.append(f"  CompatData: {compat}")
        else:
            lines.append("  Skyrim SE: not detected")
    except Exception as e:
        lines.append(f"  Skyrim SE: error ({e})")
    lines.append("")

    lines.append("Environment")
    try:
        from kalium.steam.paths import find_steam_path, steam_compat_mounts
        from kalium.steam import find_steam_protons

        steam = find_steam_path()
        lines.append(f"  Steam: {'✓' if steam else '✗'}")
        protons = find_steam_protons()
        lines.append(
            f"  Proton: {'✓' if protons else '✗'} ({len(protons)} found)" if protons else "  Proton: ✗"
        )
        prefix_ok = any(i.get("prefix_ok") for i in instances)
        lines.append(f"  Prefix: {'✓' if prefix_ok else '✗'}")
        mounts = steam_compat_mounts()
        lines.append(f"  Mounts: {'✓' if mounts else '✗'} ({len(mounts)} paths)")
    except Exception as e:
        lines.append(f"  error: {e}")
    lines.append("")

    warnings: list[str] = []
    try:
        from kalium.steam.shortcuts import is_steam_running

        if is_steam_running():
            warnings.append("Steam is running — exit fully before shortcut install/repair")
    except Exception:
        pass
    if instances:
        for inst in instances:
            us = (inst.get("usvfs") or "")
            if "0.5.6" in us:
                warnings.append(f"{inst['name']}: USVFS {us} — update to 0.5.7.2 recommended")
            if not inst.get("exe_ok"):
                warnings.append(f"{inst['name']}: ModOrganizer.exe missing at {inst['install_path']}")
            if not inst.get("loot"):
                warnings.append(f"{inst['name']}: portable LOOT not found — Settings → Install LOOT")
    lines.append("Warnings")
    if warnings:
        for w in warnings:
            lines.append(f"  {w}")
    else:
        lines.append("  (none)")
    lines.append("")
    return "\n".join(lines)
