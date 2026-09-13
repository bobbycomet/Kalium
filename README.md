# Kalium 1.2.1

**Linux modding environment manager for Steam, Proton, and Mod Organizer 2.**

Kalium prepares and maintains the environment required to run the Windows version of [Mod Organizer 2](https://github.com/ModOrganizer2/modorganizer) on Linux through Steam + Proton.

Open Kalium, install or migrate an instance, name the instance (this becomes the non-steam game name for MO2), choose where to save it, select the game and executable location, choose Proton, and install. The remaining choices are optional.

Kalium handles the Steam, Proton, Wine, NXM, USVFS, and supporting-tool configuration that normally has to be assembled manually. Just came from Windows and want to mod your games the same way as you did there? Kalium makes that happen.

[Setup Video Guide](https://youtu.be/Iy2E3C19CE4)

---

## What's New in 1.2.x

### MO2 Repair

Kalium 1.2.x introduces **MO2 Repair**.

Sometimes an MO2 plugin, application file, or supporting component can become corrupted or fail in a way that prevents MO2 from launching.

MO2 Repair targets the MO2-related files that need to be repaired without rebuilding the entire instance.

This helps preserve:

* Saves
* Mods
* Downloads
* Profiles
* Overwrite files
* Other user data

Backups are recommended, but not required. The repair process is designed to target MO2-related files rather than your mod data.

MO2 Repair has been tested on my own Skyrim SE/AE saves and is working as expected.

### Backpatching

Backpatching is restored to the UI in 1.2.1.

Kalium now creates a `.bak` backup of `ContentCatalog.txt` before applying the backpatch. This was a required step that was missing from the previous implementation.

Skyrim SE/AE backpatching has been tested and is working.

Other supported games remain experimental and may have different compatibility results.

---

## What Kalium Does

Kalium can:

* Install or attach an existing MO2 installation
* Repair an existing MO2 installation
* Backpatch supported game versions
* Configure Proton and Wine prefixes per MO2 instance
* Register MO2 as a Steam non-Steam game
* Register and reconnect Nexus Mods **NXM** links
* Detect Steam libraries and installed games
* Support games installed across multiple drives
* Configure secondary-drive access through `STEAM_COMPAT_MOUNTS`
* Install MO2 plugins
* Update and configure USVFS 0.5.7.2
* Configure VFS memory for large modlists and tools such as NEMESIS and Pandora
* Install and integrate LOOT
* Provide Winetricks and registry tools
* Provide diagnostics and repair tools
* Support Steam depot backpatching for supported games
* Support CLI-based setup and diagnostics
* Provide GOG, Heroic, Flatpak Steam, Snap Steam, and Epic support
* Install standalone Windows LOOT with WINEPREFIX registration per instance
* Install MO2 Stylesheets from Nexus Mods
* Support multiple MO2 instances for the same game
* Support the MO2 Collections plugin

Collections are supported through the MO2 plugin that can be installed after MO2 installation.

Nexus Premium is recommended for Collections. Non-Premium users may have to open a separate browser tab for each mod in a collection. This is a Nexus limitation, not a Kalium limitation.

Once Beta features have stabilized and compatibility is reliable, I will look into Wabbajack support.

Kalium is **not a replacement for MO2** and does not attempt to become another mod manager.

---

## First Setup

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

| **Kalium manages**         | **MO2 manages**               |
| -------------------------- | ----------------------------- |
| Proton environment         | Your mods                     |
| Wine prefixes              | Your load order               |
| Steam integration          | Your plugins                  |
| NXM registration           | Your profiles                 |
| MO2 installation           | Mod installation              |
| MO2 plugin installation    | Virtual file system operation |
| Supporting tools           | Modding tools                 |
| Steam library detection    | Your modded game environment  |
| Game detection and binding | Game INIs                     |
| MO2 environment settings   |                               |
| USVFS configuration        |                               |
| LOOT integration           |                               |
| Backpatching support       |                               |
| Diagnostics and repair     |                               |
| MO2 INI configuration      |                               |

Kalium may modify specific MO2 settings required for the environment, such as:

* Paths
* Managed-game information
* USVFS settings
* Theme
* Registered tools
* VFS memory settings

It does **not** manage:

* Your mods
* Your load order
* Your profiles
* Your game INIs
* MO2's mod installation behavior

### Launching Your Game

| Modded method                   | Launch option                          |
| ------------------------------- | -------------------------------------- |
| **Play with MO2 mods, no SKSE** | Launch the game `.exe` from inside MO2 |
| **Play with SKSE**              | Launch `SKSE` from inside MO2          |

> **Note:** When a Bethesda game updates versions, Kalium only sets up and maintains the environment. It does not automatically make older mods compatible with newer game versions. If a mod requires Skyrim 1.6.1170 and you are running a different version, the mod may not work. Always check the game version and the version requirements of your mods.
>
> No tool can replace the need to verify game and mod version compatibility.

---

## Proton Compatibility

If a Proton version gives you trouble, try **GE-Proton Latest**.

Kalium supports Proton 10+, but you are **not locked to Proton 10+**.

Different games, games versions, and tools may work better with different Proton versions.

[Check Launcher Compatibility](https://github.com/bobbycomet/Kalium/wiki/Launcher-Compatibility)

This includes compatibility information for:

* Native Steam
* Flatpak Steam
* Snap Steam
* GOG
* Heroic
* Epic

---

## Backpatching

Kalium provides Steam depot backpatching for supported games.

Currently supported experimental backpatching includes selected versions of:

* Skyrim Special Edition
* Fallout 4
* Starfield
* Cyberpunk 2077
* The Witcher 3

**Skyrim SE/AE backpatching is currently the most tested and confirmed working implementation.**

Other games are experimental.

Backpatching changes the game files and can cause the game to stop launching correctly depending on Steam, Proton, the selected game version, and the depot being used.

If a backpatch causes problems, you may need to validate the game files through Steam. This will restore the newest available game version.

Use backpatching only when you understand the game version and mod requirements you are trying to use.

---

## Supported Games

See the [Supported Games](https://github.com/bobbycomet/Kalium/wiki/Supported-Games) page for the current compatibility list.

Game support can depend on:

* Game version
* Proton version
* Launcher
* Installation location
* Mod configuration
* External tools
* Game-specific requirements

Kalium prepares the environment. It does not guarantee that every Windows game, mod, or tool will work through Proton.

---

## Installation

Kalium provides an AppImage for normal installation.

Download the latest AppImage from [Releases](https://github.com/bobbycomet/Kalium/releases).

```bash
chmod +x Kalium-*.AppImage
./Kalium-*.AppImage
```

The GUI is recommended for first-time setup.

### Build the AppImage Yourself

Kalium 1.2.0+ also provides `.tar` and `.zip` source/build packages.

These are useful if the provided AppImage does not work on your system because of a GLIBC version difference or another compatibility issue.

After extracting Kalium, run:

```bash
./build-appimage.sh
```

from the Kalium directory.

---

## CLI

Kalium also provides a CLI for advanced users, diagnostics, and automated workflows.

Example:

```bash
./Kalium-*.AppImage setup-mo2 -p /path/to/mo2 -n "My MO2"
```

The CLI can be used for setup and supported diagnostics without requiring the GUI.

See the [CLI / Diagnostics / Troubleshooting](https://github.com/bobbycomet/Kalium/wiki/CLI-Diagnostics-Troubleshooting) documentation for more information.

---

## Migrating from NaK

Kalium can configure an existing MO2 installation without downloading another copy of MO2.

If migrating from NaK:

1. Select **Existing MO2 Installation**
2. Select your existing MO2 installation
3. Select the game and executable
4. Select your Proton version
5. Complete the setup

Back up your mods and other important files before migration.

A complete migration guide is available in the [Wiki](https://github.com/bobbycomet/Kalium/wiki).

> Kalium is an independent project. It is not affiliated with NaK, Flourine Manager, SulfurNitride, or their maintainers.

---

## Documentation

* **[Wiki](https://github.com/bobbycomet/Kalium/wiki)**: Complete documentation
* **[Distro/kernel Compatibility](https://github.com/bobbycomet/Kalium/wiki/Kalium-Compatibility)**: Check if your setup is ready
* **[First Setup](https://github.com/bobbycomet/Kalium/wiki#3-first-mo2-setup)**: Set up your first MO2 instance
* **[Installation](https://github.com/bobbycomet/Kalium/wiki/Installation)**: Detailed environment setup
* **[Supported Games](https://github.com/bobbycomet/Kalium/wiki/Supported-Games)**: Game compatibility
* **[Launcher Compatibility](https://github.com/bobbycomet/Kalium/wiki/Launcher-Compatibility)**: Steam, GOG, Heroic, and other launcher support
* **[CLI / Diagnostics / Troubleshooting](https://github.com/bobbycomet/Kalium/wiki/CLI-Diagnostics-Troubleshooting)**: Advanced users and troubleshooting
* **[Screenshots](https://github.com/bobbycomet/Kalium/tree/main/screenshots)**: GUI and feature screenshots
* **[Standalone LOOT compatibility and accuracy](https://github.com/bobbycomet/Kalium/wiki/FAQs#how-accurate-is-the-standalone-loot-when-run-in-the-environment)**: LOOT information

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
