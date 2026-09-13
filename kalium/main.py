#!/usr/bin/env python3
"""Kalium entry point — GUI by default, CLI subcommands for automation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kalium",
        description="Kalium — Linux Modding Helper (MO2 via Steam/Proton). Author: Bobby Comet.",
    )
    parser.add_argument("--version", action="version", version="kalium 1.2.1")
    sub = parser.add_subparsers(dest="cmd")

    p_setup = sub.add_parser("setup-mo2", help="Set up existing MO2 with Steam integration")
    p_setup.add_argument("-p", "--path", type=Path, required=True)
    p_setup.add_argument("-n", "--name", default="Mod Organizer 2")
    p_setup.add_argument("--proton", default=None, help="Proton name or index")
    p_setup.add_argument(
        "--no-usvfs",
        action="store_true",
        help="Keep stock USVFS from the MO2 package (skip 0.5.7.2 update)",
    )

    sub.add_parser("list-protons", help="List available Proton 10+ versions")
    p_list_mo2 = sub.add_parser("list-mo2", help="List managed MO2 instances")
    p_list_mo2.add_argument("--json", action="store_true", help="Emit JSON")
    sub.add_parser("status", help="Kalium/MO2 environment status (support-friendly overview)")
    sub.add_parser("enable-nxm", help="Register NXM handler and activate last MO2 instance")
    p_check = sub.add_parser("check-steam", help="Diagnose Steam install, libraries, mounts, shortcuts")
    p_check.add_argument("--json", action="store_true", help="Emit machine-readable JSON (for GitHub issues)")
    sub.add_parser("diagnose", help="Full environment health report (also writes a file for GitHub issues)")
    p_bp = sub.add_parser(
        "backpatch-skyrim",
        help="Backpatch a supported game via Steam depots (Skyrim SE, Fallout 4, Starfield, Cyberpunk, Witcher 3)",
    )
    p_bp.add_argument("-p", "--path", type=Path, required=True, help="Game install folder")
    p_bp.add_argument(
        "--game",
        default="skyrim-se",
        choices=["skyrim-se", "fallout4", "starfield", "cyberpunk2077", "witcher3"],
        help="Game id (default skyrim-se)",
    )
    p_bp.add_argument(
        "--target",
        default="",
        help="Target version id (e.g. 1.6.1170, 1.10.163, 2.12). Empty = game default",
    )
    p_bp.add_argument(
        "--list-targets",
        action="store_true",
        help="List version targets for --game and exit",
    )
    p_bp.add_argument(
        "--method",
        default="auto",
        choices=["auto", "steamcmd", "console", "apply-only", "diagnose"],
    )
    p_bp.add_argument("--steam-user", default="", help="Steam username for steamcmd")
    p_bp.add_argument("--no-backup", action="store_true")
    p_bp.add_argument("--content", type=Path, default=None, help="steamapps/content or app_489830 dir")

    p_fix = sub.add_parser(
        "repair-shortcut",
        help="Re-add an MO2 folder as a non-Steam game (writes shortcuts.vdf)",
    )
    p_fix.add_argument("-p", "--path", type=Path, required=True, help="MO2 folder with ModOrganizer.exe")
    p_fix.add_argument("-n", "--name", default="Mod Organizer 2")
    p_fix.add_argument("--proton", default=None, help="Proton name or index")

    p_plugin = sub.add_parser("install-collections", help="Install MO2 Collections plugin (Nexus #1541)")
    p_plugin.add_argument("-p", "--path", type=Path, required=True, help="MO2 install directory")
    p_plugin.add_argument("--api-key", default="", help="Nexus API key")

    p_usvfs = sub.add_parser(
        "install-usvfs",
        help="Update USVFS binaries in an MO2 folder to 0.5.7.2 "
        "(fixes virtual-folder duplication / slow boots on Wine 10.20+)",
    )
    p_usvfs.add_argument(
        "-p",
        "--path",
        type=Path,
        required=True,
        help="MO2 folder (contains ModOrganizer.exe)",
    )
    p_usvfs.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not back up the previous usvfs DLLs/exes",
    )

    p_fixpaths = sub.add_parser(
        "fix-paths",
        help="Normalize backslash paths in MO2's customExecutables "
        "(SKSE, LOOT, xEdit, etc.) to forward slashes",
    )
    p_fixpaths.add_argument(
        "-p",
        "--path",
        type=Path,
        required=True,
        help="MO2 folder (contains ModOrganizer.exe)",
    )

    p_loot = sub.add_parser(
        "install-loot",
        help="Download portable LOOT, write run_loot.bat (--game= for this instance), "
        "and register it in ModOrganizer.ini",
    )
    p_loot.add_argument(
        "-p",
        "--path",
        type=Path,
        required=True,
        help="MO2 folder (contains ModOrganizer.exe)",
    )
    p_loot.add_argument(
        "-g",
        "--game",
        default="",
        help='LOOT --game= id (default: from ModOrganizer.ini or "Skyrim Special Edition")',
    )

    p_theme = sub.add_parser(
        "set-theme",
        help="Set MO2's UI style to a bundled .qss theme (default: dracula.qss)",
    )
    p_theme.add_argument(
        "-p",
        "--path",
        type=Path,
        required=True,
        help="MO2 folder (contains ModOrganizer.exe)",
    )
    p_theme.add_argument(
        "--style",
        default="dracula.qss",
        help="Filename of a .qss already present in <mo2>/stylesheets/",
    )


    p_vfs = sub.add_parser(
        "set-vfs-memory",
        help="Set [vfs] max_memory in ModOrganizer.ini (default: 2147483648 = 2 GB)",
    )
    p_vfs.add_argument(
        "-p",
        "--path",
        type=Path,
        required=True,
        help="MO2 folder (contains ModOrganizer.exe / ModOrganizer.ini)",
    )
    p_vfs.add_argument(
        "--bytes",
        type=int,
        default=2147483648,
        dest="max_memory",
        help="max_memory in bytes (default 2147483648 = 2 GiB)",
    )

    p_fixmo2 = sub.add_parser(
        "fix-mo2",
        help="Staged MO2 repair (same path / same prefix): backup | repair | restore. "
        "Restore is never automatic after repair.",
    )
    p_fixmo2.add_argument("-p", "--path", type=Path, required=True, help="MO2 install folder")
    p_fixmo2.add_argument(
        "action",
        choices=["backup", "repair", "restore", "checklist"],
        help="backup | repair | restore | checklist",
    )
    p_fixmo2.add_argument(
        "--backup-dir",
        type=Path,
        default=None,
        help="Backup folder (output for backup; input for restore). "
        "Default for backup: <parent>/MO2_backups/<name>_<timestamp>",
    )
    p_fixmo2.add_argument("--no-mods", action="store_true", help="Exclude mods/")
    p_fixmo2.add_argument("--no-downloads", action="store_true", help="Exclude downloads/ (default: exclude)")
    p_fixmo2.add_argument("--with-downloads", action="store_true", help="Include downloads/")
    p_fixmo2.add_argument("--no-profiles", action="store_true")
    p_fixmo2.add_argument("--no-stylesheets", action="store_true")
    p_fixmo2.add_argument("--no-overwrite", action="store_true", help="Exclude overwrite/ (default: exclude)")
    p_fixmo2.add_argument("--with-overwrite", action="store_true", help="Include overwrite/")
    p_fixmo2.add_argument("--fresh-ini", action="store_true", help="Exclude ModOrganizer.ini")
    p_fixmo2.add_argument(
        "--remove-instance-after-backup",
        action="store_true",
        help="With repair: delete backed-up instance folders so you can test a clean MO2 "
        "(only use after a confirmed backup)",
    )

    p_nexus = sub.add_parser(
        "install-nexus-plugin",
        help="Install an MO2 plugin from a Nexus Mods page URL into <mo2>/plugins/",
    )
    p_nexus.add_argument("-p", "--path", type=Path, required=True, help="MO2 folder")
    p_nexus.add_argument("-u", "--url", required=True, help="Nexus mod page URL")
    p_nexus.add_argument("--api-key", default="", help="Nexus API key")

    # Allow bare: kalium "nxm://..."  (desktop / AppImage may pass the URL as argv)
    raw = list(argv) if argv is not None else sys.argv[1:]
    for a in raw:
        if isinstance(a, str) and a.lower().startswith("nxm:"):
            from kalium.logging_utils import init_logger
            from kalium.nxm import handle_nxm_url, NxmHandler
            init_logger()
            try:
                NxmHandler.setup()
            except Exception:
                pass
            return handle_nxm_url(a)

    args = parser.parse_args(argv)

    if args.cmd is None:
        from kalium.ui import run_app
        run_app()
        return 0

    from kalium.logging_utils import init_logger, log_info
    init_logger()

    if args.cmd == "backpatch-skyrim":
        from kalium.tools.game_depots import get_game, steam_console_commands
        game_id = getattr(args, "game", None) or "skyrim-se"
        game = get_game(game_id)
        if getattr(args, "list_targets", False):
            print(f"{game.name} (AppID {game.app_id}) targets:")
            for t in game.targets:
                print(f"  {t.id:12}  {t.label}")
            return 0
        target = (getattr(args, "target", None) or "").strip() or game.default_target
        if args.method == "diagnose":
            if game_id != "skyrim-se":
                print(steam_console_commands(game_id, target, include_optional=True))
                print("\n(diagnose compare is Skyrim-SE specific; showing depot commands above)")
                return 0
            from kalium.tools.skyrim_backpatch import diagnose
            print(diagnose(args.path, args.content))
            return 0
        if game_id != "skyrim-se" and args.method in ("auto", "console", "steamcmd"):
            print(steam_console_commands(game_id, target, include_optional=True))
            print("\nNon-Skyrim auto-apply is limited. Paste the commands into Steam Console,")
            print("wait for depots, then re-run with --method apply-only once content is ready.")
            print(f"Content root tip: steamapps/content/app_{game.app_id}")
            return 0
        from kalium.tools.skyrim_backpatch import run_backpatch
        result = run_backpatch(
            args.path,
            version=args.target,
            method=args.method,
            steam_user=args.steam_user,
            backup=not args.no_backup,
            content_dir=args.content,
            status=print,
        )
        print(f"OK {result.game_dir} via {result.method}")
        return 0

    if args.cmd == "enable-nxm":
        from kalium.nxm import NxmHandler, activate_from_managed, read_active
        NxmHandler.setup()
        ok = activate_from_managed()
        active = read_active()
        if ok and active:
            print(f"NXM enabled for {active.get('name')} → {active['exe']}")
            print(NxmHandler.status())
            return 0
        print("No managed MO2 install found. Run MO2 setup in Kalium first.")
        return 1

    if args.cmd == "list-protons":
        from kalium.steam import find_steam_protons
        protons = find_steam_protons()
        if not protons:
            print("No Proton 10+ found.")
            return 1
        for i, p in enumerate(protons):
            print(f"  {i}. {p.name} ({'Steam' if p.is_steam_proton else 'Custom'})")
        return 0

    if args.cmd == "check-steam":
        from kalium.diagnostics import collect_check_steam_data
        data = collect_check_steam_data()
        if getattr(args, "json", False):
            import json
            print(json.dumps(data, indent=2, default=str))
            return 0 if data.get("steam_path") else 1
        # Human-readable (support + interactive)
        if not data.get("steam_path"):
            print("Steam not found.")
            if data.get("error"):
                print(f"Error: {data['error']}")
            return 1
        print(f"Steam: {data['steam_path']}")
        print(f"Steam running: {data.get('steam_running')}")
        print(f"Protons: {len(data.get('protons') or [])}")
        for p in data.get("protons") or []:
            kind = "Steam" if p.get("is_steam_proton") else "Custom"
            print(f"  - {p.get('name')} ({kind})  config={p.get('config_name')}")
        libs = data.get("libraries") or []
        print(f"Steam libraries ({len(libs)}):")
        for lib in libs:
            marker = " [primary]" if lib.get("primary") else " [secondary]"
            sa = "yes" if lib.get("steamapps") else "NO"
            print(f"  {lib.get('path')}{marker}  steamapps={sa}")
        print("libraryfolders.vdf entries (path → app count):")
        for entry in data.get("library_entries") or []:
            print(f"  {entry.get('path')}  apps={entry.get('app_count')}")
        for app_id, g in (data.get("games") or {}).items():
            print(f"AppID {app_id} ({g.get('name')}):")
            print(f"  library:    {g.get('library') or '(not found)'}")
            print(f"  compatdata: {g.get('compatdata') or '(not found)'}")
        mounts = data.get("mounts") or []
        print(f"STEAM_COMPAT_MOUNTS candidates ({len(mounts)}): {':'.join(mounts)}")
        print(f"export STEAM_COMPAT_MOUNTS={data.get('steam_compat_mounts') or ''}")
        for a in data.get("accounts") or []:
            flag = " [most recent]" if a.get("most_recent") else ""
            print(f"  Account {a.get('account_id')} ({a.get('persona_name')}){flag}")
        print(f"Active userdata: {data.get('userdata')}")
        print(f"shortcuts.vdf: {data.get('shortcuts_vdf')}  exists={bool(data.get('shortcuts'))}")
        for s in data.get("shortcuts") or []:
            print(f"  - {s.get('app_name')}  appid={s.get('appid')}  exe={s.get('exe')}")
        return 0


    if args.cmd == "status":
        from kalium.diagnostics import build_status_report
        print(build_status_report())
        return 0

    if args.cmd == "list-mo2":
        from kalium.diagnostics import list_mo2_instances, format_list_mo2
        if getattr(args, "json", False):
            import json
            print(json.dumps(list_mo2_instances(), indent=2, default=str))
        else:
            print(format_list_mo2())
        return 0

    if args.cmd == "diagnose":
        from kalium.diagnostics import run_diagnostics, write_report
        report = run_diagnostics()
        print(report.text())
        path = write_report(report)
        print(f"\nReport saved to: {path}")
        return 0 if report.overall_ok() else 1

    if args.cmd == "repair-shortcut":
        from kalium.steam import find_steam_protons, is_steam_running
        from kalium.steam.shortcuts import add_mod_manager_shortcut
        exe = args.path / "ModOrganizer.exe"
        if not exe.exists():
            print(f"ModOrganizer.exe not found in {args.path}")
            return 1
        if is_steam_running():
            print("WARNING: Steam is running. Fully exit Steam first for a reliable write.")
        protons = find_steam_protons()
        if not protons:
            print("No Proton found.")
            return 1
        proton = protons[0]
        if args.proton:
            if str(args.proton).isdigit():
                proton = protons[int(args.proton)]
            else:
                proton = next(p for p in protons if p.name.lower() == str(args.proton).lower())
        result = add_mod_manager_shortcut(
            args.name, str(exe), str(args.path), proton.config_name
        )
        print(f"Wrote shortcut AppID={result.app_id}")
        print(f"shortcuts.vdf: {result.shortcuts_vdf}")
        print(f"userdata: {result.userdata}")
        print("Fully exit Steam, then start it again to see the non-Steam game.")
        return 0

    if args.cmd == "setup-mo2":
        from kalium.steam import find_steam_protons
        from kalium.installers.mo2 import setup_existing_mo2
        from kalium.installers.task import TaskContext

        protons = find_steam_protons()
        if not protons:
            print("No Proton found.")
            return 1
        proton = protons[0]
        if args.proton:
            if args.proton.isdigit():
                proton = protons[int(args.proton)]
            else:
                proton = next(p for p in protons if p.name.lower() == args.proton.lower())
        cancel = {"v": False}
        ctx = TaskContext(
            status_callback=lambda m: print(f"[STATUS] {m}"),
            log_callback=lambda m: print(f"[LOG] {m}"),
            progress_callback=lambda p: print(f"\r[PROGRESS] {int(p*100)}%", end="", flush=True),
            cancel_flag=lambda: cancel["v"],
        )
        result = setup_existing_mo2(
            args.name, args.path, proton, ctx, update_usvfs=not args.no_usvfs
        )
        print(f"\nDone. AppID={result.app_id} prefix={result.prefix_path}")
        return 0

    if args.cmd == "install-collections":
        from kalium.marketplace import BUILTIN_PLUGINS, install_plugin_into_mo2
        from kalium.config import AppConfig
        plugin = next(p for p in BUILTIN_PLUGINS if p.id == "mo2-collections")
        key = args.api_key or AppConfig.load().nexus_api_key
        path = install_plugin_into_mo2(plugin, args.path, api_key=key)
        print(f"Installed Collections plugin into {path}")
        return 0

    if args.cmd == "install-usvfs":
        from kalium.installers.usvfs import install_usvfs
        mo2 = args.path
        if not (mo2 / "ModOrganizer.exe").exists():
            print(f"ModOrganizer.exe not found in {mo2}")
            return 1
        try:
            install_usvfs(mo2, backup=not args.no_backup)
            print(f"USVFS 0.5.7.2 installed into {mo2}")
            if not args.no_backup:
                print(f"Previous binaries backed up under {mo2}/.kalium_usvfs_backup_0.5.7.2")
            return 0
        except Exception as e:
            print(f"USVFS install failed: {e}")
            return 1


    if args.cmd == "install-loot":
        from kalium.installers.loot import install_and_register_loot
        mo2 = args.path
        if not (mo2 / "ModOrganizer.exe").exists():
            print(f"ModOrganizer.exe not found in {mo2}")
            return 1
        game = (getattr(args, "game", None) or "").strip() or None
        launcher = install_and_register_loot(mo2, game_name=game)
        if launcher:
            print(f"LOOT ready → {launcher}")
            print("Custom executable uses run_loot.bat (--game= is inside the bat).")
            print(f"If paths get rewritten: kalium fix-paths -p {mo2}")
            return 0
        print("LOOT install failed or could not register (see log).")
        return 1

    if args.cmd == "fix-paths":
        from kalium.installers.ini_paths import sanitize_custom_executable_paths
        mo2 = args.path
        if not (mo2 / "ModOrganizer.exe").exists():
            print(f"ModOrganizer.exe not found in {mo2}")
            return 1
        n = sanitize_custom_executable_paths(mo2)
        if n:
            print(f"Fixed {n} path field(s) in ModOrganizer.ini "
                  f"(backup saved as ModOrganizer.ini.kalium.bak)")
        else:
            print("No backslash paths found — nothing to fix.")
        return 0

    if args.cmd == "set-theme":
        from kalium.installers.theme import set_mo2_style
        mo2 = args.path
        if not (mo2 / "ModOrganizer.exe").exists():
            print(f"ModOrganizer.exe not found in {mo2}")
            return 1
        ok = set_mo2_style(mo2, style=args.style)
        if ok:
            print(f"MO2 theme set to {args.style} (backup saved as ModOrganizer.ini.kalium.bak)")
            return 0
        print(f"Could not set theme — check the Kalium log for details.")
        return 1


    if args.cmd == "set-vfs-memory":
        from kalium.installers.ini_paths import set_vfs_max_memory
        mo2 = args.path
        if not (mo2 / "ModOrganizer.exe").exists() and not (mo2 / "ModOrganizer.ini").exists():
            print(f"Neither ModOrganizer.exe nor ModOrganizer.ini found in {mo2}")
            return 1
        try:
            ok = set_vfs_max_memory(mo2, max_memory=args.max_memory)
        except ValueError as e:
            print(f"Invalid value: {e}")
            return 1
        if ok:
            mb = args.max_memory // (1024 * 1024)
            print(f"[vfs] max_memory={args.max_memory} ({mb} MiB) → {mo2 / 'ModOrganizer.ini'}")
            return 0
        print("ModOrganizer.ini not found yet — launch MO2 once, then re-run.")
        return 1

    if args.cmd == "install-nexus-plugin":
        from kalium.marketplace import install_nexus_url_into_mo2
        from kalium.config import AppConfig
        mo2 = args.path
        if not (mo2 / "ModOrganizer.exe").exists():
            print(f"ModOrganizer.exe not found in {mo2}")
            return 1
        key = args.api_key or AppConfig.load().nexus_api_key
        try:
            dest = install_nexus_url_into_mo2(args.url, mo2, api_key=key)
            print(f"Installed Nexus plugin into {dest}")
            return 0
        except Exception as e:
            print(f"Install failed: {e}")
            return 1


    if args.cmd == "fix-mo2":
        from kalium.installers.fix_mo2 import (
            backup_instance_data,
            repair_mo2_application,
            restore_instance_data,
            InstanceSelection,
            default_backup_root,
            suggest_backup_parent,
            manual_backup_checklist,
        )
        from kalium.installers.task import TaskContext

        if args.action == "checklist":
            print(manual_backup_checklist())
            return 0

        dirs = set()
        if not args.no_mods:
            dirs.add("mods")
        if args.with_downloads and not args.no_downloads:
            dirs.add("downloads")
        if not args.no_profiles:
            dirs.add("profiles")
        if not args.no_stylesheets:
            dirs.add("stylesheets")
        if args.with_overwrite and not args.no_overwrite:
            dirs.add("overwrite")
        selection = InstanceSelection(dirs=dirs, keep_ini=not args.fresh_ini)

        ctx = TaskContext(
            status_callback=lambda m: print(f"[STATUS] {m}"),
            log_callback=lambda m: print(f"[LOG] {m}"),
            progress_callback=lambda p: None,
            cancel_flag=lambda: False,
        )
        try:
            if args.action == "backup":
                dest = args.backup_dir or default_backup_root(args.path)
                result = backup_instance_data(args.path, dest, selection, ctx=ctx)
                print(f"Backup OK → {result.backup_root}")
                print("Confirm the backup, then run: kalium fix-mo2 -p ... repair")
                return 0
            if args.action == "repair":
                repair_mo2_application(
                    args.path,
                    remove_backed_up_instance_data=args.remove_instance_after_backup,
                    selection=selection if args.remove_instance_after_backup else None,
                    ctx=ctx,
                )
                print("Repair OK. Launch MO2 from Steam to test before restoring.")
                return 0
            if args.action == "restore":
                if not args.backup_dir:
                    print("restore requires --backup-dir")
                    return 1
                result = restore_instance_data(
                    args.path, args.backup_dir, selection, ctx=ctx
                )
                print(f"Restore OK → {result.mo2_path}")
                return 0
        except Exception as e:
            print(f"fix-mo2 {args.action} failed: {e}")
            return 1


    return 0


if __name__ == "__main__":
    raise SystemExit(main())
