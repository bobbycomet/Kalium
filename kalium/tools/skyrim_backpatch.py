"""
Skyrim Special Edition backpatch via Steam depots.

Targets: 1.6.1170, 1.6.640, 1.7.104.0

Critical rules:
  - Resolve depot folders that actually contain game data
  - Read version-like strings from SOURCE and DEST SkyrimSE.exe before copy
  - Backup only after source is validated
  - Atomic replace of SkyrimSE.exe + full tree merge
  - Verify destination hash matches source after copy
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from kalium.logging_utils import log_info, log_warning
from kalium.steam.paths import find_steam_path

SKYRIM_APP_ID = 489830
StatusCb = Optional[Callable[[str], None]]

# Depot 489833 holds SkyrimSE.exe for modern builds; 1.5.97 needs all three depots.
BACKPATCH_TARGETS: dict[str, list[tuple[int, int]]] = {
    "1.5.97": [
        (489831, 7848722008564294070),
        (489832, 8702665189575304780),
        (489833, 2289561010626853674),
    ],
    "1.6.640": [
        (489833, 5291801952219815735),
    ],
    "1.6.1130": [
        (489833, 2442187225363891157),
    ],
    "1.6.1170": [
        (489833, 1914580699073641964),
    ],
}

DEFAULT_TARGET = "1.6.1170"

# Version tokens we care about when scanning the PE
_VERSION_RE = re.compile(rb"(?:^|\x00)(1\.(?:6|7)\.\d+(?:\.\d+)?)", re.MULTILINE)


def list_targets() -> list[str]:
    return list(BACKPATCH_TARGETS.keys())


def normalize_target(version: str) -> str:
    v = (version or "").strip()
    if v in BACKPATCH_TARGETS:
        return v
    aliases = {
        "1170": "1.6.1170",
        "1.6.1170.0": "1.6.1170",
        "1130": "1.6.1130",
        "1.6.1130.0": "1.6.1130",
        "640": "1.6.640",
        "1.6.640.0": "1.6.640",
        "1.5.97.0": "1.5.97",
        "97": "1.5.97",
    }
    if v in aliases:
        return aliases[v]
    raise ValueError(f"Unknown target {version!r}. Choose: {', '.join(list_targets())}")


def depots_for(version: str) -> list[tuple[int, int]]:
    return list(BACKPATCH_TARGETS[normalize_target(version)])


def _status(cb: StatusCb, msg: str) -> None:
    log_info(msg)
    if cb:
        cb(msg)


def steam_console_commands(version: str = DEFAULT_TARGET, game_id: str = "skyrim-se") -> str:
    """Steam console download_depot lines for a game/version.

    Defaults to Skyrim SE for backward compatibility. Pass game_id for
    Fallout 4, Starfield, Cyberpunk, Witcher 3, etc.
    """
    try:
        from kalium.tools.game_depots import steam_console_commands as _multi

        return _multi(game_id, version, include_optional=True)
    except Exception:
        return "\n".join(
            f"download_depot {SKYRIM_APP_ID} {d} {m}" for d, m in depots_for(version)
        )


def sha256_file(path: Path, limit: int | None = None) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        if limit is None:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        else:
            h.update(f.read(limit))
    return h.hexdigest()


def sniff_runtime_versions(exe: Path) -> list[str]:
    """Pull 1.6.x / 1.7.x version-like strings from the binary (same idea as strings|grep)."""
    data = exe.read_bytes()
    found: list[str] = []
    seen: set[str] = set()
    # Scan ASCII runs
    for m in re.finditer(rb"1\.[567]\.[0-9]+(?:\.[0-9]+)?", data):
        s = m.group().decode("ascii", errors="ignore")
        if s not in seen:
            seen.add(s)
            found.append(s)
    return found


def primary_runtime_guess(versions: list[str]) -> str | None:
    """Prefer a full 1.6.x / 1.7.x.x token if present."""
    if not versions:
        return None
    # Prefer longer / more specific
    ranked = sorted(versions, key=lambda v: (v.count("."), len(v)), reverse=True)
    for v in ranked:
        if v.startswith("1.5.") or v.startswith("1.6.") or v.startswith("1.7."):
            return v
    return ranked[0]


def find_skyrim_exe(game_dir: Path) -> Path:
    for name in ("SkyrimSE.exe", "SkyrimSELauncher.exe"):
        p = game_dir / name
        if p.is_file():
            return p
    raise FileNotFoundError(f"No SkyrimSE.exe in {game_dir}")


def content_search_roots() -> list[Path]:
    home = Path.home()
    candidates = [
        home / ".steam/steam/steamapps/content",
        home / ".local/share/Steam/steamapps/content",
        home / ".steam/debian-installation/steamapps/content",
        home / ".steam/debian-installation/ubuntu12_32/steamapps/content",
        home / ".steam/debian-installation/ubuntu12_64/steamapps/content",
        home / ".var/app/com.valvesoftware.Steam/data/Steam/steamapps/content",
        home / ".var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/content",
    ]
    steam = find_steam_path()
    if steam:
        candidates += [
            steam / "steamapps" / "content",
            steam / "ubuntu12_32" / "steamapps" / "content",
            steam / "ubuntu12_64" / "steamapps" / "content",
        ]
    out: list[Path] = []
    for c in candidates:
        try:
            c = c.resolve()
        except OSError:
            pass
        if c not in out:
            out.append(c)
    return out


def _dir_stats(path: Path) -> tuple[int, int]:
    total = 0
    n = 0
    try:
        for root, _d, files in os.walk(path):
            for f in files:
                n += 1
                try:
                    total += (Path(root) / f).stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total, n


def _find_named(root: Path, name: str) -> Path | None:
    want = name.lower()
    try:
        for dirpath, _dn, filenames in os.walk(root):
            for f in filenames:
                if f.lower() == want:
                    return Path(dirpath) / f
    except OSError:
        pass
    return None


def resolve_depot_path(depot_id: int, content_hint: Path | None = None) -> Path | None:
    candidates: list[Path] = []

    def consider(p: Path) -> None:
        if not p.is_dir():
            return
        try:
            p = p.resolve()
        except OSError:
            return
        # Never treat the live game install as a "depot"
        if (p / "SkyrimSE.exe").is_file() and (p / "Data").is_dir() and "depot_" not in p.name:
            if "steamapps/common" in str(p).replace("\\", "/"):
                return
        if p not in candidates:
            candidates.append(p)

    if content_hint:
        h = Path(content_hint).expanduser().resolve()
        if h.name in (f"depot_{depot_id}", str(depot_id)):
            consider(h)
        consider(h / f"depot_{depot_id}")
        consider(h / str(depot_id))
        consider(h / f"app_{SKYRIM_APP_ID}" / f"depot_{depot_id}")
        # If hint is content root
        if h.name == "content" or (h / f"app_{SKYRIM_APP_ID}").is_dir():
            consider(h / f"app_{SKYRIM_APP_ID}" / f"depot_{depot_id}")

    for root in content_search_roots():
        consider(root / f"app_{SKYRIM_APP_ID}" / f"depot_{depot_id}")
        consider(root / f"depot_{depot_id}")
        if root.is_dir():
            try:
                for child in root.rglob(f"depot_{depot_id}"):
                    consider(child)
            except OSError:
                pass

    best: Path | None = None
    best_score = -1
    for c in candidates:
        total, nfiles = _dir_stats(c)
        if total < 500_000 and nfiles < 5:
            continue
        score = total
        if _find_named(c, "SkyrimSE.exe"):
            score += 50_000_000_000
        if score > best_score:
            best_score = score
            best = c
    return best


def resolve_all_depots(
    version: str, content_hint: Path | None = None, status: StatusCb = None
) -> dict[int, Path]:
    ver = normalize_target(version)
    out: dict[int, Path] = {}
    for depot_id, _manifest in depots_for(ver):
        path = resolve_depot_path(depot_id, content_hint)
        if not path:
            raise RuntimeError(
                f"Could not find non-empty depot_{depot_id}.\n"
                f"Content hint: {content_hint}\n"
                "Set Content folder to the app_489830 path from Steam Console."
            )
        total, nfiles = _dir_stats(path)
        exe = _find_named(path, "SkyrimSE.exe")
        _status(
            status,
            f"depot_{depot_id}: {path}\n"
            f"  {nfiles} files, {total // (1024 * 1024)} MiB"
            + (f", exe={exe}" if exe else ""),
        )
        out[depot_id] = path

    if not any(_find_named(p, "SkyrimSE.exe") for p in out.values()):
        raise RuntimeError(
            "No SkyrimSE.exe inside resolved depots. Download is incomplete or wrong folder."
        )
    return out


def find_steamcmd() -> Optional[Path]:
    for name in ("steamcmd", "steamcmd.sh"):
        w = shutil.which(name)
        if w:
            return Path(w)
    for p in (
        Path.home() / ".local/share/Steam/steamcmd/steamcmd.sh",
        Path("/usr/games/steamcmd"),
        Path("/usr/bin/steamcmd"),
    ):
        if p.is_file():
            return p
    return None


def download_depots_steamcmd(
    version: str, username: str, password: str = "", status: StatusCb = None
) -> None:
    cmd_path = find_steamcmd()
    if not cmd_path:
        raise RuntimeError("steamcmd not found")
    for depot_id, manifest in depots_for(version):
        _status(status, f"steamcmd: depot {depot_id} manifest {manifest}")
        login = f"+login {username} {password}" if password else f"+login {username}"
        proc = subprocess.run(
            [
                str(cmd_path),
                login,
                f"+download_depot {SKYRIM_APP_ID} {depot_id} {manifest}",
                "+quit",
            ],
            capture_output=True,
            text=True,
            timeout=3600 * 3,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        if "Depot download complete" not in out and proc.returncode != 0:
            raise RuntimeError(f"steamcmd failed:\n{out[-1500:]}")


def open_steam_console() -> None:
    for cmd in (
        ["xdg-open", "steam://open/console"],
        ["steam", "steam://open/console"],
    ):
        try:
            subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True
            )
            return
        except OSError:
            continue


def copy_to_clipboard(text: str) -> bool:
    for cmd in (
        ["wl-copy"],
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
    ):
        try:
            if subprocess.run(cmd, input=text.encode(), capture_output=True).returncode == 0:
                return True
        except OSError:
            continue
    return False


def wait_for_depots(
    version: str,
    content_hint: Path | None = None,
    timeout_sec: int = 7200,
    poll_sec: int = 15,
    status: StatusCb = None,
) -> dict[int, Path]:
    deadline = time.time() + timeout_sec
    last_err = ""
    while time.time() < deadline:
        try:
            return resolve_all_depots(version, content_hint, status=status)
        except RuntimeError as e:
            last_err = str(e)
            _status(status, f"Waiting for depots… {e}")
            time.sleep(poll_sec)
    raise TimeoutError(last_err or "Timed out waiting for depots")


def _atomic_replace(src: Path, dest: Path) -> None:
    """Copy src to dest via temp file + os.replace (overwrites)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".kalium_tmp")
    if tmp.exists():
        try:
            tmp.unlink()
        except OSError:
            pass
    shutil.copy2(src, tmp)
    # Ensure writable dest
    if dest.exists():
        try:
            dest.chmod(dest.stat().st_mode | 0o200)
        except OSError:
            pass
    os.replace(tmp, dest)


def _merge_tree(src: Path, dst: Path, status: StatusCb = None) -> int:
    """Overwrite-merge src into dst file by file (explicit, cross-filesystem safe)."""
    count = 0
    for root, _dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        target_dir = dst / rel
        target_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            s = Path(root) / f
            d = target_dir / f
            try:
                _atomic_replace(s, d)
            except OSError as e:
                raise RuntimeError(f"Failed to write {d}: {e}") from e
            count += 1
    _status(status, f"  merged {count} files from {src.name}")
    return count


def apply_depots_to_game(
    game_dir: Path,
    depot_paths: dict[int, Path],
    version: str,
    *,
    backup: bool = True,
    status: StatusCb = None,
) -> Path | None:
    game_dir = Path(game_dir).resolve()
    if not os.access(game_dir, os.W_OK):
        raise RuntimeError(f"Game folder not writable: {game_dir}")

    dest_exe = find_skyrim_exe(game_dir)
    if dest_exe.name != "SkyrimSE.exe":
        dest_exe = game_dir / "SkyrimSE.exe"
        if not dest_exe.is_file():
            raise RuntimeError("SkyrimSE.exe missing in game folder")

    ver = normalize_target(version)
    before_hash = sha256_file(dest_exe)
    before_size = dest_exe.stat().st_size
    before_vers = sniff_runtime_versions(dest_exe)
    before_primary = primary_runtime_guess(before_vers)

    # Source exe from depots
    exe_src: Path | None = None
    for did, src in depot_paths.items():
        hit = _find_named(src, "SkyrimSE.exe")
        if hit:
            exe_src = hit
            _status(status, f"SOURCE SkyrimSE.exe from depot_{did}:\n  {hit}")
            break
    if exe_src is None:
        raise RuntimeError("No SkyrimSE.exe in depots — aborting before backup.")

    # Refuse to use source that is clearly the same file as destination (same inode/path)
    try:
        if dest_exe.resolve() == exe_src.resolve():
            raise RuntimeError(
                "Depot path resolved to the live game SkyrimSE.exe. "
                "Choose the Steam content/app_489830 folder, not the game install."
            )
    except RuntimeError:
        raise
    except OSError:
        pass

    src_hash = sha256_file(exe_src)
    src_size = exe_src.stat().st_size
    src_vers = sniff_runtime_versions(exe_src)
    src_primary = primary_runtime_guess(src_vers)

    _status(
        status,
        f"DEST  version strings: {before_vers[:8]} (guess {before_primary})\n"
        f"DEST  size={before_size} sha256={before_hash[:16]}…\n"
        f"SOURCE version strings: {src_vers[:8]} (guess {src_primary})\n"
        f"SOURCE size={src_size} sha256={src_hash[:16]}…",
    )

    if src_hash == before_hash:
        raise RuntimeError(
            "SOURCE SkyrimSE.exe is byte-identical to the one already in the game folder.\n"
            "The depot you downloaded is the same build you already have (or the wrong folder).\n"
            "Re-run download_depot with the correct manifests, wait for completion, and\n"
            "point Content at …/steamapps/content/app_489830 — then check:\n"
            f"  strings \"{exe_src}\" | grep -E '^1\\.[67]\\.'\n"
            "If that still shows 1.7.99.0, Steam did not give you the historical depot."
        )

    # Backup OLD only after we know source differs
    backup_dir = None
    if backup:
        safe = ver.replace(".", "_")
        backup_dir = game_dir.parent / f"SkyrimSE_backup_before_{safe}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        for name in ("SkyrimSE.exe", "SkyrimSELauncher.exe", "bink2w64.dll", "steam_api64.dll"):
            p = game_dir / name
            if p.is_file():
                shutil.copy2(p, backup_dir / name)
        _status(status, f"OLD binaries backed up to:\n  {backup_dir}")

    # Merge all depot files
    total = 0
    for depot_id, _m in depots_for(ver):
        src = depot_paths[depot_id]
        _status(status, f"Merging depot_{depot_id} → game folder")
        total += _merge_tree(src, game_dir, status=status)

    # Atomic force-replace exe from known source
    _status(status, f"Atomic replace SkyrimSE.exe from\n  {exe_src}")
    _atomic_replace(exe_src, dest_exe)

    after_hash = sha256_file(dest_exe)
    after_size = dest_exe.stat().st_size
    after_vers = sniff_runtime_versions(dest_exe)

    if after_hash != src_hash:
        raise RuntimeError(
            f"Copy verification failed.\n"
            f"Expected sha256 {src_hash}\n"
            f"Got      sha256 {after_hash}\n"
            f"Is the game folder writable? Any other process locking SkyrimSE.exe?"
        )

    marker = game_dir / "kalium_backpatch.txt"
    marker.write_text(
        f"target={ver}\n"
        f"files_merged={total}\n"
        f"before_size={before_size}\n"
        f"after_size={after_size}\n"
        f"before_hash={before_hash}\n"
        f"after_hash={after_hash}\n"
        f"source={exe_src}\n"
        f"before_versions={before_vers}\n"
        f"after_versions={after_vers}\n"
        f"depots={depot_paths}\n",
        encoding="utf-8",
    )

    _status(
        status,
        f"SUCCESS — SkyrimSE.exe replaced.\n"
        f"size {before_size} → {after_size}\n"
        f"versions now: {after_vers[:8]}\n"
        f"marker: {marker}",
    )
    return backup_dir


@dataclass
class BackpatchResult:
    game_dir: Path
    version: str
    backup_dir: Optional[Path]
    depot_paths: dict[int, Path]
    method: str


def diagnose(game_dir: Path | str, content_dir: Path | str | None = None) -> str:
    """Print human diagnosis without modifying files."""
    game_dir = Path(game_dir).expanduser().resolve()
    lines: list[str] = []
    exe = find_skyrim_exe(game_dir)
    lines.append(f"Game exe: {exe}")
    lines.append(f"  size={exe.stat().st_size} hash={sha256_file(exe)[:16]}…")
    lines.append(f"  versions={sniff_runtime_versions(exe)}")
    hint = Path(content_dir).expanduser() if content_dir else None
    for ver in list_targets():
        lines.append(f"\n--- resolve for {ver} ---")
        try:
            depots = resolve_all_depots(ver, hint, status=None)
            for did, path in depots.items():
                hit = _find_named(path, "SkyrimSE.exe")
                lines.append(f"  depot_{did}: {path}")
                if hit:
                    lines.append(
                        f"    SOURCE exe {hit} size={hit.stat().st_size} "
                        f"hash={sha256_file(hit)[:16]}… vers={sniff_runtime_versions(hit)}"
                    )
                    if sha256_file(hit) == sha256_file(exe):
                        lines.append("    *** IDENTICAL to game exe — cannot change version ***")
        except Exception as e:
            lines.append(f"  error: {e}")
    return "\n".join(lines)


def run_backpatch(
    game_dir: Path | str,
    *,
    version: str = DEFAULT_TARGET,
    method: str = "auto",
    steam_user: str = "",
    steam_password: str = "",
    content_dir: Path | str | None = None,
    wait_timeout: int = 7200,
    backup: bool = True,
    status: StatusCb = None,
) -> BackpatchResult:
    ver = normalize_target(version)
    game_dir = Path(game_dir).expanduser().resolve()
    find_skyrim_exe(game_dir)
    hint = Path(content_dir).expanduser().resolve() if content_dir else None
    if hint and not hint.exists():
        raise RuntimeError(f"Content folder missing: {hint}")

    _status(status, f"Game: {game_dir}\nTarget: {ver}\nContent: {hint or 'auto'}")

    if method == "auto":
        method = "steamcmd" if find_steamcmd() and steam_user else "apply-only"

    if method == "steamcmd":
        if not steam_user:
            raise RuntimeError("steamcmd requires username")
        download_depots_steamcmd(ver, steam_user, steam_password, status=status)
        depot_paths = wait_for_depots(ver, hint, timeout_sec=600, poll_sec=5, status=status)
    elif method == "console":
        cmds = steam_console_commands(ver)
        copy_to_clipboard(cmds)
        open_steam_console()
        _status(status, f"Paste into Steam Console:\n{cmds}")
        depot_paths = wait_for_depots(ver, hint, timeout_sec=wait_timeout, poll_sec=15, status=status)
    elif method == "apply-only":
        depot_paths = resolve_all_depots(ver, hint, status=status)
    else:
        raise ValueError(method)

    backup_dir = apply_depots_to_game(
        game_dir, depot_paths, ver, backup=backup, status=status
    )
    return BackpatchResult(
        game_dir=game_dir,
        version=ver,
        backup_dir=backup_dir,
        depot_paths=depot_paths,
        method=method,
    )
