"""Repair MO2 application files; optional staged backup / restore of instance data.

Safety model (human-driven, never silent):

  Backup  →  Confirm  →  Repair application  →  Test  →  Restore

Kalium does **not** automatically chain reinstall into restore. After a successful
repair the user is expected to launch MO2 from Steam, verify the original problem
is gone, then optionally run Restore as a separate action.

State classes
-------------
Application state (always replaced by Repair)
  MO2 binaries, shipped plugins, runtime, USVFS, helpers, …

Instance / user state (optional Backup / Restore)
  mods/, downloads/, profiles/, stylesheets/, overwrite/, ModOrganizer.ini

The Steam non-Steam shortcut, AppID, and Wine/Proton prefix under
compatdata/<id>/pfx are never modified — repair always targets the same path.

Backup location
---------------
Backups must live **outside** the MO2 install folder (no cross-contamination).
Default suggestion: same drive, sibling folder e.g.

  MO2 at     /mnt/sda1/MO2
  Backup at  /mnt/sda1/MO2_backups/<timestamp>/

The user may browse to any other path.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import py7zr

from kalium.config import AppConfig
from kalium.installers.task import TaskContext
from kalium.logging_utils import log_install, log_warning
from kalium.utils import download_file

INSTANCE_DIR_OPTIONS: tuple[tuple[str, str], ...] = (
    ("mods", "mods/ — installed mods (large; some mods may not copy cleanly)"),
    ("downloads", "downloads/ — Nexus / manual archives (large; optional)"),
    ("profiles", "profiles/ — load orders, ini tweaks, separator layout"),
    ("stylesheets", "stylesheets/ — custom / bundled UI themes"),
    ("overwrite", "overwrite/ — VFS writes (SKSE, shaders, generated files)"),
)
INSTANCE_INI = "ModOrganizer.ini"
ALL_INSTANCE_DIR_NAMES = frozenset(name for name, _ in INSTANCE_DIR_OPTIONS)
BACKUP_MARKER = "kalium_repair_backup.txt"


@dataclass
class InstanceSelection:
    """Which instance items participate in backup or restore."""

    dirs: set[str] = field(
        default_factory=lambda: {"mods", "profiles", "stylesheets"}
    )
    keep_ini: bool = True

    def selected_dirs(self) -> list[str]:
        ordered = [n for n, _ in INSTANCE_DIR_OPTIONS]
        return [n for n in ordered if n in self.dirs]

    def validate(self) -> None:
        unknown = self.dirs - ALL_INSTANCE_DIR_NAMES
        if unknown:
            raise RuntimeError(f"Unknown instance dir(s): {sorted(unknown)}")


@dataclass
class BackupRecord:
    relative: str
    source: Path
    backup_path: Path
    is_dir: bool
    source_size: int = 0
    backup_size: int = 0
    fingerprint: str = ""


@dataclass
class BackupResult:
    mo2_path: Path
    backup_root: Path
    records: list[BackupRecord]
    selection: InstanceSelection


@dataclass
class RestoreResult:
    mo2_path: Path
    backup_root: Path
    restored: list[str]
    warnings: list[str] = field(default_factory=list)


def _status(ctx: Optional[TaskContext], msg: str) -> None:
    log_install(msg)
    if ctx:
        ctx.set_status(msg)
        ctx.log(msg)


def _dir_size_and_count(path: Path) -> tuple[int, int]:
    total = 0
    n = 0
    try:
        for root, _dirs, files in os.walk(path):
            for f in files:
                n += 1
                try:
                    total += (Path(root) / f).stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total, n


def _file_fingerprint(path: Path, limit: int = 1024 * 1024) -> str:
    try:
        st = path.stat()
        h = hashlib.sha256()
        with path.open("rb") as f:
            h.update(f.read(limit))
        return f"{st.st_size}:{h.hexdigest()[:16]}"
    except OSError:
        return ""


def _item_fingerprint(path: Path, is_dir: bool) -> str:
    if is_dir:
        total, n = _dir_size_and_count(path)
        return f"dir:{n}:{total}"
    return _file_fingerprint(path)


def _copy_item(src: Path, dest: Path, is_dir: bool) -> None:
    if dest.exists():
        if dest.is_dir():
            shutil.rmtree(dest, ignore_errors=True)
        else:
            dest.unlink(missing_ok=True)
    if is_dir:
        shutil.copytree(src, dest, symlinks=True)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def suggest_backup_parent(mo2_install_path: Path | str) -> Path:
    """
    Default parent for backups: same drive / parent as MO2, never inside MO2.

    Example: /mnt/sda1/Games/MO2  →  /mnt/sda1/Games/MO2_backups
    """
    mo2 = Path(mo2_install_path).expanduser().resolve()
    parent = mo2.parent
    candidate = parent / "MO2_backups"
    # Never nest inside the install tree
    try:
        candidate.resolve().relative_to(mo2)
        # If somehow under mo2, fall back to parent of parent
        candidate = parent.parent / "MO2_backups"
    except ValueError:
        pass
    return candidate


def default_backup_root(mo2_install_path: Path | str, parent: Optional[Path] = None) -> Path:
    """Timestamped folder under the suggested (or user-chosen) parent."""
    mo2 = Path(mo2_install_path).expanduser().resolve()
    base = Path(parent).expanduser().resolve() if parent else suggest_backup_parent(mo2)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return base / f"{mo2.name}_{ts}"


def assert_backup_outside_mo2(mo2: Path, backup_root: Path) -> None:
    mo2 = mo2.resolve()
    backup_root = backup_root.resolve()
    try:
        backup_root.relative_to(mo2)
        raise RuntimeError(
            f"Backup path must not be inside the MO2 folder:\n"
            f"  MO2:    {mo2}\n"
            f"  Backup: {backup_root}\n"
            "Choose a location outside the install (e.g. sibling MO2_backups/)."
        )
    except ValueError:
        return


def manual_backup_checklist() -> str:
    lines = [
        "Manual instance-data backup checklist",
        "=====================================",
        "",
        "Copy these OUT of your MO2 folder to a safe location on the same drive",
        "(or any other drive). Do not store the backup inside the MO2 folder.",
        "",
    ]
    for name, label in INSTANCE_DIR_OPTIONS:
        lines.append(f"  • {label}")
    lines += [
        f"  • {INSTANCE_INI}",
        "",
        "Staged recovery workflow:",
        "  1. Backup (Kalium or manual) and confirm it looks complete.",
        "  2. Repair application files (same path / same Proton prefix).",
        "  3. Launch MO2 from Steam once — verify the original problem is gone.",
        "  4. Fully exit Steam + MO2.",
        "  5. Restore from backup (Kalium button or manual copy).",
        "",
        "Notes:",
        "  • Some mods may not survive a filesystem copy; re-download if needed.",
        "  • Large overhaul lists on HDD can take an hour or longer to copy.",
        "  • overwrite/ may include generated SKSE/shader data.",
    ]
    return "\n".join(lines)


def _validate_mo2(mo2: Path) -> None:
    if not mo2.is_dir():
        raise RuntimeError(f"MO2 path is not a directory: {mo2}")
    if not (mo2 / "ModOrganizer.exe").is_file():
        log_warning(
            f"ModOrganizer.exe not found in {mo2} — treating as install root."
        )


# ---------------------------------------------------------------------------
# Stage 1: Backup (explicit, verified — does not touch application files)
# ---------------------------------------------------------------------------

def backup_instance_data(
    mo2_install_path: Path | str,
    backup_root: Path | str,
    selection: Optional[InstanceSelection] = None,
    ctx: Optional[TaskContext] = None,
) -> BackupResult:
    """
    Copy selected instance data to backup_root (must be outside MO2).

    Does not modify the live MO2 tree. Caller must confirm success before Repair.
    """
    mo2 = Path(mo2_install_path).expanduser().resolve()
    backup_root = Path(backup_root).expanduser().resolve()
    selection = selection or InstanceSelection()
    selection.validate()
    _validate_mo2(mo2)
    assert_backup_outside_mo2(mo2, backup_root)

    if not selection.selected_dirs() and not selection.keep_ini:
        raise RuntimeError("Nothing selected to back up.")

    backup_root.mkdir(parents=True, exist_ok=True)
    records: list[BackupRecord] = []

    for name in selection.selected_dirs():
        src = mo2 / name
        if not src.exists():
            _status(ctx, f"Skip missing {name}/")
            continue
        if not src.is_dir():
            raise RuntimeError(f"Expected directory: {src}")
        dest = backup_root / name
        _status(ctx, f"Backing up {name}/ → {dest}\n(this can take a long time on large lists)")
        _copy_item(src, dest, is_dir=True)
        total, n = _dir_size_and_count(src)
        rec = BackupRecord(
            relative=name,
            source=src,
            backup_path=dest,
            is_dir=True,
            source_size=total,
            backup_size=_dir_size_and_count(dest)[0],
            fingerprint=_item_fingerprint(src, True),
        )
        records.append(rec)
        _status(ctx, f"  {n} files, {total // (1024 * 1024)} MiB")

    if selection.keep_ini:
        src = mo2 / INSTANCE_INI
        if src.is_file():
            dest = backup_root / INSTANCE_INI
            _status(ctx, f"Backing up {INSTANCE_INI}")
            _copy_item(src, dest, is_dir=False)
            records.append(
                BackupRecord(
                    relative=INSTANCE_INI,
                    source=src,
                    backup_path=dest,
                    is_dir=False,
                    source_size=src.stat().st_size,
                    backup_size=dest.stat().st_size,
                    fingerprint=_item_fingerprint(src, False),
                )
            )

    if not records:
        raise RuntimeError(
            "No instance data was found to back up under the current selection."
        )

    # Verify before returning success
    failures: list[str] = []
    for r in records:
        if not r.backup_path.exists():
            failures.append(f"{r.relative}: missing at {r.backup_path}")
            continue
        fp = _item_fingerprint(r.backup_path, r.is_dir)
        if r.fingerprint and fp != r.fingerprint:
            failures.append(
                f"{r.relative}: fingerprint mismatch source={r.fingerprint} backup={fp}"
            )
        if not r.is_dir and r.backup_size != r.source_size:
            failures.append(f"{r.relative}: size mismatch")
    if failures:
        raise RuntimeError(
            "Backup verification failed — live MO2 was not modified:\n  "
            + "\n  ".join(failures)
        )

    marker = backup_root / BACKUP_MARKER
    marker.write_text(
        f"kind=mo2-instance-backup\n"
        f"source={mo2}\n"
        f"created={datetime.now(timezone.utc).isoformat()}\n"
        f"dirs={','.join(selection.selected_dirs())}\n"
        f"keep_ini={selection.keep_ini}\n"
        f"items={','.join(r.relative for r in records)}\n",
        encoding="utf-8",
    )

    _status(
        ctx,
        f"Backup complete and verified → {backup_root}\n"
        f"Items: {', '.join(r.relative for r in records)}\n"
        "Confirm this backup looks correct before running Repair.",
    )
    return BackupResult(
        mo2_path=mo2, backup_root=backup_root, records=records, selection=selection
    )


# ---------------------------------------------------------------------------
# Stage 2: Repair application only (no automatic restore)
# ---------------------------------------------------------------------------

def _clear_application_files(
    mo2: Path,
    *,
    also_remove_instance: bool,
    selection: Optional[InstanceSelection],
    ctx: Optional[TaskContext],
) -> None:
    """
    Remove application files. Optionally also remove selected instance folders
    (only after a confirmed backup — so the user can test a clean MO2).
    """
    remove_instance = set()
    if also_remove_instance and selection:
        remove_instance = set(selection.selected_dirs())
        if selection.keep_ini:
            remove_instance.add(INSTANCE_INI)

    for child in list(mo2.iterdir()):
        name = child.name
        is_instance = name in ALL_INSTANCE_DIR_NAMES or name == INSTANCE_INI
        if is_instance and name not in remove_instance:
            continue
        if is_instance and name not in remove_instance:
            continue
        # Keep unselected instance data on disk
        if is_instance and name not in remove_instance:
            continue
        try:
            if child.is_dir() and not child.is_symlink():
                # Only delete instance dir if explicitly in remove_instance
                if is_instance and name not in remove_instance:
                    continue
                shutil.rmtree(child, ignore_errors=True)
            else:
                if is_instance and name not in remove_instance:
                    continue
                child.unlink(missing_ok=True)
        except OSError as e:
            log_warning(f"Could not remove {child}: {e}")

    # Simpler second pass for clarity
    for child in list(mo2.iterdir()):
        name = child.name
        is_instance = name in ALL_INSTANCE_DIR_NAMES or name == INSTANCE_INI
        if is_instance:
            if name in remove_instance or (
                name == INSTANCE_INI and selection and selection.keep_ini and also_remove_instance
            ):
                try:
                    if child.is_dir():
                        shutil.rmtree(child, ignore_errors=True)
                    else:
                        child.unlink(missing_ok=True)
                except OSError as e:
                    log_warning(f"Could not remove instance item {child}: {e}")
            continue
        # Application file/dir
        try:
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
        except OSError as e:
            log_warning(f"Could not remove {child}: {e}")

    _status(ctx, f"Cleared application files under {mo2}")


def _fetch_latest_mo2_asset() -> dict:
    import requests

    url = "https://api.github.com/repos/ModOrganizer2/modorganizer/releases/latest"
    r = requests.get(url, headers={"User-Agent": "Kalium/1.0"}, timeout=60)
    r.raise_for_status()
    release = r.json()
    invalid = ("Linux", "pdbs", "src", "uibase", "commits")
    asset = next(
        (
            a
            for a in release.get("assets", [])
            if a["name"].startswith("Mod.Organizer-2")
            and a["name"].endswith(".7z")
            and not any(t in a["name"] for t in invalid)
        ),
        None,
    )
    if not asset:
        raise RuntimeError("No valid MO2 archive in latest GitHub release")
    return asset


def _extract_mo2_archive(archive: Path, dest: Path, ctx: Optional[TaskContext]) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    _status(ctx, f"Extracting {archive.name}")
    with py7zr.SevenZipFile(archive, mode="r") as z:
        z.extractall(path=dest)
    if (dest / "ModOrganizer.exe").is_file():
        return
    candidates = list(dest.rglob("ModOrganizer.exe"))
    if not candidates:
        raise RuntimeError("ModOrganizer.exe not found after extract")
    nested = candidates[0].parent
    if nested.resolve() == dest.resolve():
        return
    for item in list(nested.iterdir()):
        target = dest / item.name
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
            else:
                target.unlink(missing_ok=True)
        item.rename(target)
    try:
        nested.rmdir()
    except OSError:
        pass


def _merge_app_from_extract(
    extract_root: Path,
    mo2: Path,
    ctx: Optional[TaskContext],
) -> None:
    """Copy application files from extract into mo2 without deleting leftover instance dirs."""
    _status(ctx, "Installing application files into MO2 path…")
    for item in extract_root.iterdir():
        name = item.name
        if name in ALL_INSTANCE_DIR_NAMES or name == INSTANCE_INI:
            continue
        dest = mo2 / name
        if dest.exists():
            if dest.is_dir():
                shutil.rmtree(dest, ignore_errors=True)
            else:
                dest.unlink(missing_ok=True)
        if item.is_dir():
            shutil.copytree(item, dest, symlinks=True)
        else:
            shutil.copy2(item, dest)


def _reapply_kalium_config(mo2: Path, ctx: Optional[TaskContext]) -> None:
    try:
        from kalium.installers.usvfs import install_usvfs_safe
        _status(ctx, "Re-applying USVFS 0.5.7.2…")
        install_usvfs_safe(mo2, ctx)
    except Exception as e:
        log_warning(f"USVFS: {e}")
    try:
        from kalium.installers.theme import set_mo2_style
        set_mo2_style(mo2)
    except Exception as e:
        log_warning(f"Theme: {e}")
    try:
        from kalium.installers.ini_paths import set_vfs_max_memory
        set_vfs_max_memory(mo2)
    except Exception as e:
        log_warning(f"vfs memory: {e}")
    try:
        from kalium.installers.ini_paths import sanitize_custom_executable_paths
        n = sanitize_custom_executable_paths(mo2)
        if n:
            _status(ctx, f"Normalized {n} custom-executable path(s)")
    except Exception as e:
        log_warning(f"fix-paths: {e}")


def repair_mo2_application(
    mo2_install_path: Path | str,
    *,
    remove_backed_up_instance_data: bool = False,
    selection: Optional[InstanceSelection] = None,
    ctx: Optional[TaskContext] = None,
) -> Path:
    """
    Replace MO2 application files on the same path (same Steam prefix).

    Does **not** restore instance data. That is a separate step.

    If remove_backed_up_instance_data is True, selected instance folders are
    removed after a confirmed backup so the user can test a clean MO2 first.
    Unselected instance folders are always left in place.
    """
    mo2 = Path(mo2_install_path).expanduser().resolve()
    _validate_mo2(mo2)
    selection = selection or InstanceSelection(dirs=set(), keep_ini=False)

    _status(
        ctx,
        f"Repair application files (same path / same prefix)\n"
        f"  {mo2}\n"
        f"  remove_backed_up_instance_data={remove_backed_up_instance_data}",
    )

    # Clear app files; optionally clear instance items that were backed up
    for child in list(mo2.iterdir()):
        name = child.name
        is_instance = name in ALL_INSTANCE_DIR_NAMES or name == INSTANCE_INI
        if is_instance:
            should_remove = False
            if remove_backed_up_instance_data and selection:
                if name in selection.dirs:
                    should_remove = True
                if name == INSTANCE_INI and selection.keep_ini:
                    should_remove = True
            if not should_remove:
                continue
        try:
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
        except OSError as e:
            log_warning(f"Could not remove {child}: {e}")

    _status(ctx, "Fetching latest MO2 release…")
    asset = _fetch_latest_mo2_asset()
    _status(ctx, f"Downloading {asset['name']}…")
    tmp = AppConfig.tmp_path()
    tmp.mkdir(parents=True, exist_ok=True)
    archive = tmp / asset["name"]
    extract = tmp / f"mo2_extract_{os.getpid()}"
    if extract.exists():
        shutil.rmtree(extract, ignore_errors=True)
    try:
        download_file(asset["browser_download_url"], archive)
        _extract_mo2_archive(archive, extract, ctx)
        _merge_app_from_extract(extract, mo2, ctx)
    finally:
        archive.unlink(missing_ok=True)
        shutil.rmtree(extract, ignore_errors=True)

    if not (mo2 / "ModOrganizer.exe").is_file():
        raise RuntimeError(f"ModOrganizer.exe missing after repair under {mo2}")

    _reapply_kalium_config(mo2, ctx)
    _status(
        ctx,
        f"Application repair complete → {mo2}\n"
        "Launch MO2 from Steam and confirm the original problem is fixed "
        "before restoring any backup.",
    )
    return mo2


# ---------------------------------------------------------------------------
# Stage 3: Restore (independent, cancellable)
# ---------------------------------------------------------------------------

def restore_instance_data(
    mo2_install_path: Path | str,
    backup_root: Path | str,
    selection: Optional[InstanceSelection] = None,
    ctx: Optional[TaskContext] = None,
) -> RestoreResult:
    """
    Copy instance data from a backup folder into the MO2 install.

    Independent of repair — user should test the repaired app first.
    """
    mo2 = Path(mo2_install_path).expanduser().resolve()
    backup_root = Path(backup_root).expanduser().resolve()
    if not backup_root.is_dir():
        raise RuntimeError(f"Backup folder not found: {backup_root}")
    _validate_mo2(mo2)

    # Infer selection from backup contents if not provided
    if selection is None:
        dirs = {n for n, _ in INSTANCE_DIR_OPTIONS if (backup_root / n).is_dir()}
        keep_ini = (backup_root / INSTANCE_INI).is_file()
        selection = InstanceSelection(dirs=dirs, keep_ini=keep_ini)
    selection.validate()

    restored: list[str] = []
    warnings: list[str] = []

    for name in selection.selected_dirs():
        src = backup_root / name
        if not src.is_dir():
            warnings.append(f"{name}/ not in backup — skip")
            continue
        dest = mo2 / name
        _status(ctx, f"Restoring {name}/ from backup…")
        try:
            _copy_item(src, dest, is_dir=True)
            restored.append(name)
        except OSError as e:
            warnings.append(f"{name}/: {e}")
            log_warning(f"Restore {name}: {e}")

    if selection.keep_ini:
        src = backup_root / INSTANCE_INI
        if src.is_file():
            try:
                _copy_item(src, mo2 / INSTANCE_INI, is_dir=False)
                restored.append(INSTANCE_INI)
            except OSError as e:
                warnings.append(f"{INSTANCE_INI}: {e}")
        else:
            warnings.append(f"{INSTANCE_INI} not in backup — skip")

    for w in warnings:
        log_warning(w)
        if ctx:
            ctx.log(f"WARNING: {w}")

    _status(
        ctx,
        f"Restore finished → {mo2}\n"
        f"Restored: {', '.join(restored) if restored else '(none)'}\n"
        + (f"Warnings: {len(warnings)}\n" if warnings else "")
        + "Relaunch MO2 from Steam.",
    )
    return RestoreResult(
        mo2_path=mo2,
        backup_root=backup_root,
        restored=restored,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Convenience: legacy single-shot still available but not used by new UI
# ---------------------------------------------------------------------------

def repair_mo2(mo2_install_path: Path | str, **kwargs) -> Path:
    """Application-only repair (no automatic backup/restore)."""
    return repair_mo2_application(mo2_install_path, ctx=kwargs.get("ctx"))


def fix_mo2(mo2_install_path: Path | str, **kwargs) -> Path:
    return repair_mo2_application(mo2_install_path, ctx=kwargs.get("ctx"))
