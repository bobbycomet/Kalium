# Kalium 1.0.0 Beta

**Linux modding helper** for Steam and [Mod Organizer 2](https://github.com/ModOrganizer2/modorganizer).

Kalium installs or attaches MO2 as a **non-Steam game** under Proton, prepares the Wine prefix, registers **NXM** links, detects games, supports the **Collections** plugin, and can **backpatch Skyrim SE** via Steam depots.

An MO2 environment builder that helps modding Bethesda games with NXM, backpatching Skyrim, handling prefixes, installing MO2 plugins, reconnecting NXK per prefix, auto-installs instances to non-steam games, and is disconnected from MO2, so the AppImage only handles the environment, not MO2. Based off [NaK](https://github.com/bobbycomet/NaK) but redesigned from the ground up. 

Some limitations on LOOT, use the internal MO2 LOOT until that is patched later. Found a reliable fix, and it will be implemented in 1.1.0.

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

**Because of 1.7.99 and 1.7.104, some of the mods I would typically use are not working (mostly SKSE mods), and some mods are having issues installing, which is slowing testing. This is not because of Kalium itself; it is NXM and mod issues. What has worked is deleting and reinstalling mods (LOTD and Skyland AIO are known to do this). With LOTD being a manual download, the issue is with MO2's install a mod feature. This is something I can't control. You might see an alert pop up saying something is wrong, but it still installed. This is a dirty install. Re-downloading from Nexus usually fixes this, and I am unsure why LOTD and Skyland AIO cause this error, as MO2 only touches the mod after it is downloaded, Kalium does not touch the mods ever. I will keep investigating and find a fix, but I will not make the tool "fix" MO2, as that becomes me managing MO2, and that is a whole other mess. The goal is to get as close to Windows-like modding as possible, and making it act like a Linux MO2 would break a few things the modding community relies on.**

---

## What is next? 

**1.1.0 will have some more features such as:** 

- **Upgrading USVFS to v0.5.7.2**. This feature will be automatic for new MO2 installs, while older MO2 installs will get a button in settings to update any MO2 instance via the prefix chosen. This will be more compatible if you use Wine/Proton 10.20+. This will create a backup as needed.
- **Better support for multiple drives**. As it stands, it already works with multi-drive support, but "max_memory=" when having to deal with multiple drives can cause issues with some tools. However, 1.0.0 has already proven to work just fine with tools like the Pandora Behaviour Engine Plus.
- **Better support for GOG and Heroic**. This should already work pretty well with them, but I will be focusing on more compatibility features.
- **Integration with the Griffin Updater**. Griffin Updater is another one of my projects, and can update AppImages, which will be useful for Kalium. No need to go to releases every update with this pairing.
- More CLI commands for those that prefer them. With the AppImage, you will need to do `/path to the AppImage/Kalium-1.1.0-x86_64.AppImage fix-paths -p /path to MO2 instance/instance folder/` 
- Set VFS max_memory to 2 GB, this helps tools like NEMESIS and larger mod lists
- Add a MO2 plugin not in the market menu by pasting its link. Needs your API key to work, a link to get it is provided in the app.
- Marketplace catalog: NMC (#1899) + Sync Plugins (#47325) + Collections
- Backpatch for Fallout 4, Starfield, Cyberpunk, and The Witcher 3 using app_ids to make sure each game is targeted. You just choose your game, copy the commands, steam console opens, paste the commands, click "apply-already downloaded depots." No need to move files, no need to make backups, all of that is automated, the only thing not automated is copying and pasting the commands.
- A diagnostics window, and if the auto detect fails, you will get alerted what instance is the issue, you can target the `MO2.exe` location, and it will update, but usually this is from deleting a prefix without deleting the MO2 instance.
- Removing the need for dual skse, and only needing one in the root folder for MO2

Dynamic libraryfolders.vdf parsing:

- parse_library_folders_detailed() — path + AppID set per library
- find_library_for_app(489830) — which drive owns Skyrim SE
- find_compatdata_for_app(489830) → e.g., /mnt/sdb1/SteamLibrary/steamapps/compatdata/489830
- find_pfx_for_app() used when resolving game Proton prefixes

Decided to give adding the LOOT.exe one more try, and finally, it worked. What happens when you press install LOOT:
- LOOT portable is downloaded and installed.
- ModOrganizer.ini is edited with a command

```
6\arguments=
6\binary=Z:/path/MO2 instance/LOOT/run_loot.bat
6\hide=false
6\ownicon=true
6\steamAppID=
6\title=LOOT
6\toolbar=true
6\workingDirectory=Z:/path/MO2 instance/LOOT
```
This forces LOOT to look at the .bat file and it stores in that .bat file:

```
cat > /path/MO2 instance/LOOT/run_loot.bat << 'EOF'
@echo off
cd /d "%~dp0"
LOOT.exe --game="The game you chose"
EOF
```

This makes it reliably launch LOOT.exe with your mod list. Even if it switches to Z:\... in the editor it will not be launching that way, as it will launch as Z:/... every time, and no crashes or failed 130ms LOOT renders because of CEF (Chromium Embedded Framework). 

Once that .bat file has run, you will see this in the ModOrganizer.ini file:

```
6\arguments="--game=Skyrim Special Edition"
6\binary=Z:/path/MO2 instance/LOOT/LOOT.exe
6\hide=false
6\ownicon=true
6\steamAppID=
6\title=LOOT
6\toolbar=true
6\workingDirectory=Z:/path/MO2 instance/LOOT
```

As long as you do not forcibly change the file location, it will work reliably. I already tested this out by changing a location of SKSE to be sure it does not silently overwrite the INI file to use Z:\...

What I did was make two buttons, one installs Windows `LOOT.exe` and runs a command, which the second button `Wnsure vcrun2022` is a failsafe and runs the same command:

```
WINEPREFIX="$HOME/.steam/steam/steamapps/compatdata/<app_id>/pfx"   winetricks -q vcrun2022
```

### Why run this when vcrun2022 is already installed? 

This targets the `WINEPREFIX` to the prefix to be able to run LOOT, and this guarantees LOOT will run. It does not change how the installation of MO2 already works, as this is run only after LOOT is installed, which is long after the MO2 install happens. Why do this? It Reapplies/registers the runtime into the exact prefix LOOT is going to execute inside. This works across all instances. So, if you have multiple instances, it is not going to say, "Oh, LOOT is here, now. I have to change my `WINEPREFIX` target." The `WINEPREFIX` only registers that target, it does not swap targets. This means it can see inside of USVFS and the merged data folder, giving it a similar accuracy to Windows, but further testing will be done before I will claim that fully. If you end up having issues, just update USVFS to 0.5.7.2 in Kalium, this fixes bugs from the previous version. This is why the `WINEPREFIX` is so important as it ensures it will launch inside of proton, for it to work and see everything properly. 

>**NOTE:** You may have a very small graphical issue. Your window controls to minimize, Fullscreen, or exit may cut off the `X` to exit LOOT. Just click full screen (varies on your theme and what distro you run on the design), and then make the window smaller, and it will fix that. Other than that, it should work fine.

Diagnostics:

```
kalium check-steam
```

Shows libraries, AppID ownership (Skyrim SE / FNV / FO4), and:

```
export STEAM_COMPAT_MOUNTS=...
```

MO2 will still use its own non-Steam compatdata (Steam’s rule for shortcuts). Game files on other drives are reached via STEAM_COMPAT_MOUNTS, not by sharing game prefixes (that would break multi-game MO2 instances).
