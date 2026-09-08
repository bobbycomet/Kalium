# Kalium 1.1.1 Beta

Kalium is a Linux environment manager for running [Mod Organizer 2](https://github.com/ModOrganizer2/modorganizer) and Windows modding tools through Steam Proton.

> **NOTE:** The 1.1.1 fix currently applies to **new MO2 instances**. A migration/fix for existing instances is planned for a future update.
>
> If you know what you are doing, you can manually move your existing mods to the new instance, just as you would when migrating an MO2 instance on Windows. **Make sure you understand how your MO2 instance is configured before doing this manually.**

Kalium installs or attaches MO2 as a **non-Steam game** under Proton, prepares the Wine prefix, registers **NXM** links, detects games, supports the **Collections** plugin, and can **backpatch Skyrim SE** via Steam depots.

It's an MO2 environment builder for modding Bethesda games, handling NXM links, Skyrim backpatching, Wine prefixes, MO2 plugin installs, and per-prefix NXM reconnection, with auto-install of instances as non-Steam games. Kalium is disconnected from MO2 itself: the AppImage only manages the environment, not MO2. It's based on [NaK](https://github.com/SulfurNitride/NaK) but redesigned from the ground up.

**Kalium is not affiliated with NaK, Flourine Manager, SulfurNitride, or any of its maintainers. This is an independent project that uses NaK as a starting point for its initial structure. Kalium is independently maintained, but contributions are welcome.**

> **NOTE:** This is a Beta; fixes and upgrades are ongoing. Tools still in Beta:
> - Backpatcher
> - LOOT.exe (works as-is, but accuracy claims need further testing)
> - GOG and Heroic support
> - If you have issues with a Proton version, try GE Proton Latest, Proton 10+ is supported, but that does not mean your are locked to that choice.

**Docs:** [Wiki](https://github.com/bobbycomet/Kalium/wiki) · [First setup](https://github.com/bobbycomet/Kalium/wiki#3-first-mo2-setup) · [What setup does](https://github.com/bobbycomet/Kalium/wiki/Installation) · [Supported games](https://github.com/bobbycomet/Kalium/wiki/Supported-Games) · [Screenshots](https://github.com/bobbycomet/Kalium/tree/main/screenshots) · [CLI / Diagnostics / Troubleshooting](https://github.com/bobbycomet/Kalium/wiki/CLI-Diagnostics-Troubleshooting)

**Reporting bugs and issue:** [Discord](https://discord.gg/6VgwWJDD9A) · [Bug template](https://github.com/bobbycomet/Kalium/blob/main/bug_reports.md) · [Issues template](https://github.com/bobbycomet/Kalium/blob/main/issues_report.md)

---

## Migrating from NaK

If you used NaK before and still have MO2 and its prefix installed, use **Existing MO2 Installation**:

1. **Back up your mods and any other files you want kept safe first.** This isn't guaranteed to be a perfect port of old NaK prefixes; it follows a similar structure and should only update MO2's files, not your mods or INI files.
2. Go to **MO2 → Setup Existing MO2**.
3. Select the folder containing `ModOrganizer.exe`.
4. Choose your Proton version and start setup.

Kalium configures the Proton/Steam environment without downloading another copy of MO2.

---

## Known issue: mod installs on Skyrim 1.7.99/1.7.104

Some mods (mostly SKSE mods) aren't working correctly on these Proton versions, and a few mods have install issues that are slowing down testing. **This is an NXM/mod issue, not a Kalium issue.**

- Deleting and reinstalling the affected mod usually fixes it (LOTD and Skyland AIO are known offenders).
- LOTD is a manual download, so the problem is with MO2's "install a mod" feature, you may see an install error even though the mod installed anyway (a "dirty install"). Re-downloading from Nexus usually resolves this.
- Kalium never touches mod files; MO2 only touches a mod after it's downloaded, so this is outside Kalium's control. It's still being investigated, but Kalium won't try to "fix" MO2's behavior, since that would mean taking on MO2 management and pushing it away from Windows-like modding behavior that the community relies on.

---

## What's new in 1.1.x

- **USVFS upgraded to v0.5.7.2.** Automatic for new MO2 installs; existing installs get an update button in Settings (per prefix). Best compatibility with Wine/Proton 10.20+. Backs up automatically as needed.
- **Better multi-drive support.** Multi-drive setups already work, but `max_memory=` can cause issues with some tools across multiple drives. 1.0.0 already works fine with tools like Pandora Behaviour Engine Plus.
- **Better GOG and Heroic support**, with more compatibility work ongoing.
- **Griffin Updater integration.** [Griffin Updater](https://github.com/bobbycomet) (another of my projects) can update AppImages, so you won't need to check the releases page for every Kalium update.
- **More CLI commands**, for people who prefer them, e.g.:
  ```
  /path/to/Kalium-1.1.0-x86_64.AppImage fix-paths -p /path/to/MO2-instance/instance-folder/
  ```
- **VFS `max_memory` set to 2 GB**, helping tools like NEMESIS and larger mod lists.
- **Add MO2 plugins not in the marketplace** by pasting a link (requires an API key; a link to get one is provided in-app).
- **Marketplace additions:** NMC (#1899) and Collections (Sync was removed — the mod owner set it to manual downloads only).
- **Backpatching for Fallout 4, Starfield, Cyberpunk 2077, and The Witcher 3**, targeted by app ID. Choose your game, copy the commands, paste into the Steam console, and click "apply already-downloaded depots." No manual file moves or backups needed, copying/pasting the commands is the only manual step.
- **Diagnostics window.** If auto-detection fails, you'll be told which instance has an issue and can point it at the `MO2.exe` location to fix it. This usually happens after deleting a prefix without deleting the MO2 instance.
- **No more dual SKSE requirement** — only one SKSE copy is needed, in MO2's root folder.

### Dynamic `libraryfolders.vdf` parsing

- `parse_library_folders_detailed()` — path + AppID set per library
- `find_library_for_app(489830)` — which drive owns Skyrim SE
- `find_compatdata_for_app(489830)` → e.g. `/mnt/sdb1/SteamLibrary/steamapps/compatdata/489830`
- `find_pfx_for_app()` — used when resolving a game's Proton prefix

### LOOT support

LOOT support finally works reliably. Clicking **Install LOOT**:

1. Downloads and installs LOOT portable.
2. Edits `ModOrganizer.ini` with:
   ```ini
   6\arguments=
   6\binary=Z:/path/MO2 instance/LOOT/run_loot.bat
   6\hide=false
   6\ownicon=true
   6\steamAppID=
   6\title=LOOT
   6\toolbar=true
   6\workingDirectory=Z:/path/MO2 instance/LOOT
   ```
3. Points MO2 at a generated `run_loot.bat`:
   ```bat
   @echo off
   cd /d "%~dp0"
   LOOT.exe --game="The game you chose"
   ```

This makes LOOT launch reliably against your mod list. Even if the editor displays `Z:\...`, it always launches as `Z:/...` — no crashes, and no CEF (Chromium Embedded Framework) render failures around 130ms.

Once the `.bat` has run once, `ModOrganizer.ini` will show:

```ini
6\arguments="--game=Skyrim Special Edition"
6\binary=Z:/path/MO2 instance/LOOT/LOOT.exe
6\hide=false
6\ownicon=true
6\steamAppID=
6\title=LOOT
6\toolbar=true
6\workingDirectory=Z:/path/MO2 instance/LOOT
```

As long as you don't manually change the file location, this stays reliable (tested by relocating SKSE; the INI wasn't silently overwritten to `Z:\...`).

Two related buttons:
- **Install LOOT** — installs `LOOT.exe` on Windows and runs the setup command above.
- **Ensure vcrun2022** — a failsafe that reruns:
  ```
  WINEPREFIX="$HOME/.steam/steam/steamapps/compatdata/<app_id>/pfx" winetricks -q vcrun2022
  ```

**Why run this if vcrun2022 is already installed?** It re-registers the runtime into the exact prefix LOOT will execute in. It doesn't change how MO2 installs — this only runs after LOOT is installed, long after MO2 setup. Because `WINEPREFIX` only sets a target (it doesn't swap targets), this works across multiple instances: LOOT won't cause Kalium to change its `WINEPREFIX` target elsewhere. This lets LOOT see inside USVFS and the merged data folder, giving it closer-to-Windows accuracy, though this needs more testing before being a firm claim. If you run into issues, update USVFS to 0.5.7.2 in Kalium, which fixes bugs from the previous version. `WINEPREFIX` is what ensures LOOT launches inside Proton and can see everything properly.

> **NOTE:** You may see a minor graphical glitch — LOOT's window controls (minimize/fullscreen/exit) may clip the exit `X`. Click fullscreen, then resize the window smaller, and it corrects itself. Behavior varies by theme/distro, but is otherwise unaffected.

---

## Diagnostics

Check [CLI](https://github.com/bobbycomet/Kalium/wiki/CLI-Diagnostics-Troubleshooting) in documentation for how to correctly use CLI commands.

```
kalium check-steam
```

Shows Steam libraries, AppID ownership (Skyrim SE / FNV / FO4), and the resulting:

```
export STEAM_COMPAT_MOUNTS=...
```

MO2 still uses its own non-Steam `compatdata` (per Steam's rules for shortcuts). Game files on other drives are reached via `STEAM_COMPAT_MOUNTS`, not by sharing game prefixes — sharing prefixes would break multi-game MO2 instances.
