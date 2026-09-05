# Kalium 1.0.0 Beta

An MO2 environment builder that helps modding Bethesda games with NXM, backpatching Skyrim, handling prefixes, installing MO2 plugins, reconnecting NXK per prefix, auto-installs instances to non-steam games, and is disconnected from MO2, so the AppImage only handles the environment, not MO2. Based off [NaK](https://github.com/bobbycomet/NaK) but redesigned from the ground up. 

Some limitations on LOOT, use the internal MO2 LOOT until that is patched later.

Back patch for Skyrim supports 1.5.97, 1.6.640, 1.6.1130, and 1.6.1170. A back up will automatically be made.

Version 1.0.0 works as is, but as stated, some limitations, but tools like Pandora engine do work, LOOT is the outlier because of the way Proton handles MO2, and prefers Wine to launch. A dix is already being investigated. Documentation soon to come.

---

## What if I used NaK before, and have the MO2 and prefix still installed?

Using the Existing MO2 Installation feature.

**Before doing this**, it is important that you back up your mods and any other files you want kept safe. I cannot guarantee this will be a perfect port of the old NaK prefixes, but it follows a similar structure that all it should do is just update the files for MO2 without touching the mod and ini files.

Go to:

- MO2 → Setup Existing MO2

Select the folder containing:

- ModOrganizer.exe

-Choose the Proton version and start the setup.

- Kalium will configure the Proton/Steam environment without downloading another copy of MO2.

---

## What is next? 

1.1.0 will have some more features such as: 

- **Upgrading USVFS to v0.5.7.2**. This feature will be automatic for new MO2 installs, while older MO2 installs will get a button in settings to update any MO2 instance via the prefix chosen. This will be more compatible if you use Wine/Proton 10.20+. This will create a backup as needed.
- **LOOT.exe and installation, as well as register with MO2**. This feature will be in Beta as it does not launch from MO2 properly, and usually times out after 130ms. So, why add it? To prepare for a fix in the future. You will be able to launch it via Wine, however, I am still working on proper comp paths to make sure the MO2 and game folders allow LOOT to see the mods, as the instance never touches your actual game files. For now, it will default to Skyrim Special Edition, but it can be changed. 
- **Better support for multiple drives**. As it stand, it already works with multi-drive support, but "max_memory=" when having to deal with multiple drives and can cause issues with some tools. However, 1.0.0 has already proven to work just fine with tools like the Pandora Behaviour Engine Plus.
- **Better support for GOG and Heroic**. This should already work pretty well with them, but I will be focusing on more compatibility features.
- **Integration with the Griffin Updater**. Griffin Updater is another one of my projects, and can update AppImages, which will be useful for Kalium. No need to go to releases every update with this pairing.
- More CLI commands for those that prefer them.
