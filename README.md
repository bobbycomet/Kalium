# Kalium 1.0.0 Beta

**Linux modding helper** for Steam and [Mod Organizer 2](https://github.com/ModOrganizer2/modorganizer).

Kalium installs or attaches MO2 as a **non-Steam game** under Proton, prepares the Wine prefix, registers **NXM** links, detects games, supports the **Collections** plugin, and can **backpatch Skyrim SE** via Steam depots.

An MO2 environment builder that helps modding Bethesda games with NXM, backpatching Skyrim, handling prefixes, installing MO2 plugins, reconnecting NXK per prefix, auto-installs instances to non-steam games, and is disconnected from MO2, so the AppImage only handles the environment, not MO2. Based off [NaK](https://github.com/bobbycomet/NaK) but redesigned from the ground up. 

Some limitations on LOOT, use the internal MO2 LOOT until that is patched later.

Back patch for Skyrim supports 1.5.97, 1.6.640, 1.6.1130, and 1.6.1170. A back up will automatically be made.

Version 1.0.0 works as is, but as stated, some limitations, but tools like Pandora engine do work, LOOT is the outlier because of the way Proton handles MO2 and the virtual file system (VFS), and prefers Wine to launch. [Documentation](https://github.com/bobbycomet/Kalium/wiki)

[First setup](https://github.com/bobbycomet/Kalium/wiki#3-first-mo2-setup)

[Screenshots](https://github.com/bobbycomet/Kalium/tree/main/screenshots)

---

## What if I used NaK before, and have the MO2 and prefix still installed?

Using the Existing MO2 Installation feature.

**Before doing this**, it is important that you back up your mods and any other files you want kept safe. I cannot guarantee this will be a perfect port of the old NaK prefixes, but it follows a similar structure that all it should do is just update the files for MO2 without touching the mod and ini files.

Go to:

- MO2 → Setup Existing MO2

Select the folder containing:

- ModOrganizer.exe

- Choose the Proton version and start the setup.

- Kalium will configure the Proton/Steam environment without downloading another copy of MO2.

---

## What is next? 

1.1.0 will have some more features such as: 

- **Upgrading USVFS to v0.5.7.2**. This feature will be automatic for new MO2 installs, while older MO2 installs will get a button in settings to update any MO2 instance via the prefix chosen. This will be more compatible if you use Wine/Proton 10.20+. This will create a backup as needed.
- **Better support for multiple drives**. As it stand, it already works with multi-drive support, but "max_memory=" when having to deal with multiple drives can cause issues with some tools. However, 1.0.0 has already proven to work just fine with tools like the Pandora Behaviour Engine Plus.
- **Better support for GOG and Heroic**. This should already work pretty well with them, but I will be focusing on more compatibility features.
- **Integration with the Griffin Updater**. Griffin Updater is another one of my projects, and can update AppImages, which will be useful for Kalium. No need to go to releases every update with this pairing.
- More CLI commands for those that prefer them.
- Decided against keeping the LOOT.exe install, as it only works in Wine, and could not see MO2 files, this is LOOT/MO2 issue, you can still use the integrated LOOT in MO2.
- Set VFS max memory to 2 GB
- Add a MO2 pluging not in the market menu by pasting its link. Needs your API key to work, a link to get it is provided in the app.
- Marketplace catalog: NMC (#1899) + Sync Plugins (#47325) + Collections
- Backpatch for Fallout 4, Starfield, Cyberpunk, and The Witcher 3 using app_ids to make sure each game is targeted. You just choose your game, copy the commands, steam console opens, paste the commands, click "apply-already downloaded depots." No need to move files, no need to make backups, all of that is automated, the only thing not automated is copying and pasting the commands.

Dynamic libraryfolders.vdf parsing:

- parse_library_folders_detailed() — path + AppID set per library
- find_library_for_app(489830) — which drive owns Skyrim SE
- find_compatdata_for_app(489830) → e.g., /mnt/sdb1/SteamLibrary/steamapps/compatdata/489830
- find_pfx_for_app() used when resolving game Proton prefixes

Diagnostics:

```
kalium check-steam
```

Shows libraries, AppID ownership (Skyrim SE / FNV / FO4), and:

```
export STEAM_COMPAT_MOUNTS=...
```

MO2 will still use its own non-Steam compatdata (Steam’s rule for shortcuts). Game files on other drives are reached via STEAM_COMPAT_MOUNTS, not by sharing game prefixes (that would break multi-game MO2 instances).
