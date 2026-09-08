# Kalium 1.1.1 Beta

**Linux modding environment manager for Steam, Proton, and Mod Organizer 2.**

Kalium prepares and maintains the environment required to run the Windows version of [Mod Organizer 2](https://github.com/ModOrganizer2/modorganizer) on Linux through Steam + Proton.

It handles the Steam, Proton, Wine, NXM, USVFS, and supporting-tool configuration that normally has to be assembled manually.

> **The 1.1.1 fix is for newer instances. Existing instances will be fixed in 1.1.1.1 [Check Versioning Philosophy](https://github.com/bobbycomet/Kalium/wiki/Versioning-Philosophy) to understand why versions are numbered how they are.**

---

## What Kalium Does

Kalium can:

* Install or attach an existing MO2 installation
* Configure Proton and Wine prefixes per MO2 instance
* Register MO2 as a Steam non-Steam game
* Register and reconnect Nexus Mods **NXM** links
* Detect Steam libraries and installed games
* Support games installed across multiple drives
* Configure secondary-drive access through `STEAM_COMPAT_MOUNTS`
* Install MO2 plugins
* Update and configure USVFS to 0.5.7.2
* Configure VFS memory for large modlists and tools like NEMESIS and Pandora
* Install and integrate LOOT
* Provide Winetricks and registry tools
* Provide diagnostics and repair tools
* Provide Steam depot backpatching for supported games
* Support CLI-based setup and diagnostics
* Provide ongoing GOG and Heroic compatibility work
* Install standalone Windows LOOT with the WINEPREFIX registration per instance

Kalium is **not a replacement for MO2** and does not attempt to become another mod manager.

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

---

## Beta Status

Kalium is currently **Beta software**. Compatibility work is ongoing.

Areas still receiving testing include:

* Backpatching
* LOOT compatibility and accuracy
* GOG support
* Heroic support
* Proton-version compatibility
* Existing MO2 instance migration

If a Proton version gives you trouble, try **GE-Proton Latest**. Kalium supports Proton 10+, but you are **not locked to Proton 10+**. Different games and tools may work better with different Proton versions.

---

## Supported Games

See the [Supported Games](https://github.com/bobbycomet/Kalium/wiki/Supported-Games) page for the current compatibility list.

Backpatching is currently available for selected versions of:

* Skyrim Special Edition
* Fallout 4
* Starfield
* Cyberpunk 2077
* The Witcher 3

Support and compatibility vary by game and Proton version.

---

## Installation

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

## Known Mod Installation Issues

Some mods can currently have installation or runtime issues on Skyrim 1.7.99/1.7.104 environments.

Known examples include:

* **Legacy of the Dragonborn (LOTD)**
* **Skyland AIO**

These appear to involve MO2/NXM behavior rather than Kalium itself. Re-downloading an affected mod from Nexus can resolve some installation problems.

Kalium does not modify downloaded mod files or attempt to replace MO2's mod installation behavior.

---

## Migrating from NaK

Kalium can configure an existing MO2 installation without downloading another copy of MO2.

If migrating from NaK, use **Existing MO2 Installation** and back up your mods and other important files first.

A complete migration guide is available in the [Wiki](https://github.com/bobbycomet/Kalium/wiki).

> Kalium is an independent project. It is not affiliated with NaK, Flourine Manager, SulfurNitride, or their maintainers.

---

## Documentation

* **[Wiki](https://github.com/bobbycomet/Kalium/wiki)** — Complete documentation
* **[First Setup](https://github.com/bobbycomet/Kalium/wiki#3-first-mo2-setup)** — Set up your first MO2 instance
* **[Installation](https://github.com/bobbycomet/Kalium/wiki/Installation)** — Detailed environment setup
* **[Supported Games](https://github.com/bobbycomet/Kalium/wiki/Supported-Games)** — Game compatibility
* **[CLI / Diagnostics / Troubleshooting](https://github.com/bobbycomet/Kalium/wiki/CLI-Diagnostics-Troubleshooting)** — Advanced users and troubleshooting
* **[Screenshots](https://github.com/bobbycomet/Kalium/tree/main/screenshots)** — GUI and feature screenshots

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
