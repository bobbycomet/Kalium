# Kalium 1.2.1

Kalium 1.2.x+ Skyrim SE/AE introduces the MO2 repair. Sometimes a plugin hangs or gets corrupted causing MO2 not to launch, this preserves saves, mods, downloads, and more. Tested on my own Skyrim SE/AE saves, and it does work. Backups are recommended, but not required, as this just targets the MO2 related files to be repaired. I had no issues without adding the backups back in, but backup for safety.

Backpatch is restored on 1.2.1+ to the UI. It now will create a .bak for ContentCatalog.txt, which was a missing step to the backpatch before. Tested and working on Skyrim SE/AE.

**Linux modding environment manager for Steam, Proton, and Mod Organizer 2. Open the app, install new/migrate instance, name the instance (non-Steam game name), choose where to save the folder, choose game and exe location, choose proton, and install. The rest are just optional choices.**

Kalium prepares and maintains the environment required to run the Windows version of [Mod Organizer 2](https://github.com/ModOrganizer2/modorganizer) on Linux through Steam + Proton.

[Setup Video Guide](https://youtu.be/Iy2E3C19CE4)

It handles the Steam, Proton, Wine, NXM, USVFS, and supporting-tool configuration that normally has to be assembled manually. 

> Removed Backpatch from the UI. The issue is the Backpatch worked, but Steam, does not like when Linux tries to down grade a game. This is a Steam, Proton issue, nothing I do will fix that, so it will stay experimental in CLI.
>
> **Existing instances migration are fixed in 1.1.1.1, back up files for safety before migration. [Check Versioning Philosophy](https://github.com/bobbycomet/Kalium/wiki/Versioning-Philosophy) to understand why versions are numbered how they are.**
>
> Confirmed that multiple instances for a game can be made and ran in the latest update. Previous 1.1.1. versions were locked to one instance. 1.1.1.2+ allows this, but mods and game versions are important to double check.

---

## What Kalium Does

Kalium can:

* Install or attach an existing MO2 installation
* MO2 Repair
* Backpatch game versions, Skyrim SE/AE confirmed working, the other games are in Beta for backpatching
* Configure Proton and Wine prefixes per MO2 instance
* Register MO2 as a Steam non-Steam game
* Register and reconnect Nexus Mods **NXM** links
* Detect Steam libraries and installed games
* Support games installed across multiple drives
* Configure secondary-drive access through `STEAM_COMPAT_MOUNTS`
* Install MO2 plugins
* Update and configure USVFS to 0.5.7.2 [Check Beta Status](#Beta-Status)
* Configure VFS memory for large modlists and tools like NEMESIS and Pandora
* Install and integrate LOOT
* Provide Winetricks and registry tools
* Provide diagnostics and repair tools
* Provide Steam depot backpatching for supported games
* Support CLI-based setup and diagnostics
* Provide GOG, Flatpak Steam, Snap Steam, and Epic support
* Install standalone Windows LOOT with the WINEPREFIX registration per instance
* Install [Stylesheets](https://github.com/bobbycomet/Kalium/blob/main/Screenshots/Fluency_dark.png) from nexus just like Windows, drag and drop files in the stylesheets folder, and they just work
* **Collections** are supported via the MO2 plugin you can choose to install after MO2 install (Nexus premium is best for this feature, as non-premium members will open as many tabs as there are mods in the collection. This is a Nexus limitation, not Kalium's).

Once Beta status has leveled out, and everything works as it should, I will look into Wabbajack support.

Kalium is **not a replacement for MO2** and does not attempt to become another mod manager.

---

### First setup

The setup wizard handles:

1. MO2 selection
2. Game selection
3. Proton selection
4. Steam shortcut creation
5. Proton/Wine environment configuration
6. MO2 environment configuration
7. Kalium Tools creation
8. Instance registration

**[Read the First Setup Guide →](https://github.com/bobbycomet/Kalium/wiki#3-first-mo2-setup)**

---

## Kalium vs. MO2

| **Kalium manages**       | **MO2 manages**               |
| ------------------------ | ----------------------------- |
| Proton environment       | Your mods                     |
| Wine prefixes            | Your load order               |
| Steam integration        | Your plugins                  |
| NXM registration         | Your profiles                 |
| MO2 installation         | Mod installation              |
| MO2 plugin installation  | Virtual file system operation |
| Supporting tools         | Modding tools                 |
| Steam library detection  | Your modded game environment  |
| Game detection/binding   | Game INIs                     |
| MO2 environment settings |                               |
| USVFS configuration      |                               |
| LOOT integration         |                               |
| Backpatching support     |                               |
| Diagnostics and repair   |                               |
| MO2 INI *(paths, default theme, VFS max memory, etc)* |                      |

Kalium may modify specific MO2 settings required for the environment, such as paths, managed-game information, USVFS settings, theme, and registered tools.

It does **not** manage your mods, load order, profiles, or game INIs.

| Modded method | Launch Option |
| ------------- | ------------- |
| **Play with MO2 mods (no SKSE)** | Launch the game `.exe` from inside MO2 | 
| **Play with SKSE** | Launch `SKSE` from inside MO2 |

> **Note:** When a Bethesda game updates versions, Kalium only sets up the environment. So, if the mod is for an older game version, Kalium will not magically make it work because MO2's job is to handle the mods. If the mod and game version are not compatible (e.g., mod is for 1.6.1170 Skyrim SE, but current version you play is 1.7.99+), then the mod will simply not work. It is up to you to check versions of your game and mod needs. No tool can will replace that.

---

[Check Launcher Compatibility for GOG, Heroic, Flatpak Steam, and Snap Steam support](https://github.com/bobbycomet/Kalium/wiki/Launcher-Compatibility)

If a Proton version gives you trouble, try **GE-Proton Latest**. Kalium supports Proton 10+, but you are **not locked to Proton 10+**. Different games and tools may work better with different Proton versions.

---

## Supported Games

See the [Supported Games](https://github.com/bobbycomet/Kalium/wiki/Supported-Games) page for the current compatibility list.

Experimental Backpatching is currently available for selected versions of:

* Skyrim Special Edition
* Fallout 4
* Starfield
* Cyberpunk 2077
* The Witcher 3

Support and compatibility vary by game and Proton version. This may cause the game to crash, and you will have to validate files to get it working again, which means back to the newest release. I tried the manual way as well, same result.

---

## Installation

1.2.0 now has tar and zip files for you to build the AppImage yourself, if the AppImage built does not work on your machine (GLIBC version is different for you, or similar issues). Just run `./build-appimage.sh` in tour terminal in the same location as the Kalium folder.

Download the latest AppImage from [Releases](https://github.com/bobbycomet/Kalium/releases).

```bash
chmod +x Kalium-*.AppImage
./Kalium-*.AppImage
```

The GUI is recommended for first-time setup.

For advanced users, Kalium also provides a CLI:

```bash
./Kalium-*.AppImage setup-mo2 -p /path/to/mo2 -n "My MO2"
```

### First setup

The setup wizard handles:

1. MO2 selection
2. Game selection
3. Proton selection
4. Steam shortcut creation
5. Proton/Wine environment configuration
6. MO2 environment configuration
7. Kalium Tools creation
8. Instance registration

**[Read the First Setup Guide →](https://github.com/bobbycomet/Kalium/wiki#3-first-mo2-setup)**

---

## Migrating from NaK

Kalium can configure an existing MO2 installation without downloading another copy of MO2.

If migrating from NaK, use **Existing MO2 Installation** and back up your mods and other important files first.

A complete migration guide is available in the [Wiki](https://github.com/bobbycomet/Kalium/wiki).

> Kalium is an independent project. It is not affiliated with NaK, Flourine Manager, SulfurNitride, or their maintainers.

---

## Documentation

* **[Wiki](https://github.com/bobbycomet/Kalium/wiki)** — Complete documentation
* **[Distro/kernel Compatibility](https://github.com/bobbycomet/Kalium/wiki/Kalium-Compatibility)** — See if your set up is ready to go
* **[First Setup](https://github.com/bobbycomet/Kalium/wiki#3-first-mo2-setup)** — Set up your first MO2 instance
* **[Installation](https://github.com/bobbycomet/Kalium/wiki/Installation)** — Detailed environment setup
* **[Supported Games](https://github.com/bobbycomet/Kalium/wiki/Supported-Games)** — Game compatibility
* **[CLI / Diagnostics / Troubleshooting](https://github.com/bobbycomet/Kalium/wiki/CLI-Diagnostics-Troubleshooting)** — Advanced users and troubleshooting
* **[Screenshots](https://github.com/bobbycomet/Kalium/tree/main/screenshots)** — GUI and feature screenshots
* **[Standalone LOOT compatibility and accuracy](https://github.com/bobbycomet/Kalium/wiki/FAQs#how-accurate-is-the-standalone-loot-when-run-in-the-environment)

---

## Support & Bug Reports

* **[Discord](https://discord.gg/6VgwWJDD9A)**
* **[Bug Report Template](https://github.com/bobbycomet/Kalium/blob/main/bug_reports.md)**
* **[Issue Report Template](https://github.com/bobbycomet/Kalium/blob/main/issues_report.md)**
* **[GitHub Issues](https://github.com/bobbycomet/Kalium/issues)**

---

## The Boundary

Kalium is intentionally not a Linux rewrite of MO2.

It manages the environment around MO2:

**Steam → Proton → Wine → MO2 → supporting tools**

MO2 remains responsible for the actual modding workflow.

**Kalium prepares the environment. MO2 manages the mods.**
