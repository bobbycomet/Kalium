# Kalium Issue Report

Thank you for taking the time to report an issue with Kalium.

Before submitting an issue, please check the existing documentation and `bug_reports.md`.

> **Important:** An **issue** is not necessarily a bug in Kalium.
>
> Kalium runs across different Linux distributions, kernels, Steam installations, Proton versions, filesystems, hardware, and configurations. Something that does not work correctly in your environment may be caused by Kalium, Proton, Steam, Wine, MO2, the game, or another part of the system.
>
> This report is designed to collect enough information to determine the actual cause.

---

## 1. Issue Summary

**Briefly describe the problem:**

```text
Describe what is going wrong.
```

**What were you trying to do?**

```text
Example:
I was trying to launch MO2 and run LOOT through it.
```

---

## 2. Expected Behavior

What did you expect to happen?

```text
Describe what should have happened.
```

---

## 3. Actual Behavior

What happened instead?

```text
Describe exactly what happened.
Include error messages if available.
```

---

## 4. Steps to Reproduce

Please provide the steps required to reproduce the issue.

1. 
2. 
3. 
4. 

If the issue cannot be reproduced consistently, explain when it happens and how often.

---

## 5. Kalium Information

**Kalium version:**

```text
Example: 1.1.0 Beta
```

**Installation method:**

```text
AppImage / Other
```

**Command used, if applicable:**

```bash
/path/to/Kalium-1.1.0-x86_64.AppImage <command>
```

**Was this a new MO2 installation or an existing installation?**

```text
New / Existing
```

---

## 6. Linux Environment

**Distribution:**

```text
Example: Linux Mint 22.2
```

**Desktop Environment:**

```text
Example: KDE Plasma / Cinnamon / GNOME / XFCE
```

**Kernel:**

```text
Example: 6.14.0-37-generic
```

**Architecture:**

```text
x86_64 / Other
```

---

## 7. Hardware

**CPU:**

```text
```

**GPU:**

```text
```

**GPU Driver:**

```text
```

**RAM:**

```text
```

---

## 8. Steam & Proton

**Steam installation:**

```text
Example: Native Steam package / Flatpak Steam
```

**Steam version:**

```text
```

**Proton version being used for MO2:**

```text
```

**Proton version being used for the game:**

```text
```

**Steam library location:**

```text
Example:
/home/user/.steam/steam
```

**Is the game installed on a different drive from Steam?**

```text
Yes / No
```

If yes, provide the general mount/library layout:

```text
Example:
/mnt/games/SteamLibrary
```

---

## 9. MO2 Information

**MO2 version:**

```text
```

**MO2 installation path:**

```text
```

**MO2 instance path:**

```text
```

**Game being managed:**

```text
```

**Game AppID:**

```text
```

**Is the game installed on the same drive as MO2?**

```text
Yes / No
```

---

## 10. Kalium Diagnostics

Please run:

```bash
/path/to/Kalium-1.1.0-x86_64.AppImage diagnose
```

Kalium will generate a diagnostic report.

Attach the generated:

```text
kalium_diagnose_YYYYMMDD_HHMMSS.txt
```

to this issue whenever possible.

If you also believe the problem is related to Steam configuration, run:

```bash
/path/to/Kalium-1.1.0-x86_64.AppImage check-steam
```

and include the output.

---

## 11. Relevant Logs or Errors

Paste any relevant terminal output, error messages, crash information, or logs here.

```text
Paste logs here.
```

Please do not upload passwords, API keys, authentication tokens, or other sensitive information.

---

## 12. Additional Configuration

If relevant, provide information about:

- Custom Steam library locations
- Multiple drives
- External drives
- Filesystem type
- Flatpak vs native Steam
- Custom Proton builds
- Custom Wine components
- Existing MO2 configurations
- Custom MO2 plugins
- Custom launch options
- Non-standard game installations
- Other modifications to the Proton prefix

```text
Additional configuration:
```

---

## 13. What Have You Already Tried?

List anything you have already attempted.

- [ ] Restarted Steam
- [ ] Restarted the computer
- [ ] Re-ran the Kalium command
- [ ] Ran `diagnose`
- [ ] Ran `check-steam`
- [ ] Updated Proton
- [ ] Updated MO2
- [ ] Updated USVFS
- [ ] Recreated the MO2 shortcut
- [ ] Tested with a clean MO2 instance
- [ ] Tested with another Proton version
- [ ] Tested without mods
- [ ] Other:

```text
```

---

## 14. Does It Work Outside Kalium?

If possible, determine whether the same operation works when performed manually.

**Does the problem occur when using MO2 without Kalium's helper functionality?**

```text
Yes / No / Not Tested
```

**Does the problem occur with another Proton version?**

```text
Yes / No / Not Tested
```

**Does the problem occur with a clean MO2 instance?**

```text
Yes / No / Not Tested
```

**Does the problem occur on another Linux environment?**

```text
Yes / No / Not Tested
```

---

## 15. Regression

Did this previously work?

```text
Yes / No / Unknown
```

If yes:

**Last known working Kalium version:**

```text
```

**What changed before the issue appeared?**

```text
```

---

## 16. Frequency

How often does the issue occur?

```text
Always / Usually / Sometimes / Rarely / Once
```

If intermittent, describe the circumstances under which it occurs:

```text
```

---

## 17. Screenshots or Videos

If the issue is graphical or otherwise difficult to describe, screenshots or a short video can be useful.

```text
Attach screenshots/videos here.
```

---

## 18. Anything Else?

Provide any additional information that may help reproduce or diagnose the issue.

```text
```

---

# Reporter Checklist

Before submitting, please make sure you have included:

- [ ] Kalium version
- [ ] Linux distribution and version
- [ ] Kernel version
- [ ] CPU and GPU
- [ ] GPU driver
- [ ] Steam installation type
- [ ] Proton version
- [ ] MO2 version
- [ ] Game and AppID
- [ ] Steps to reproduce
- [ ] Expected behavior
- [ ] Actual behavior
- [ ] Relevant error messages/logs
- [ ] `diagnose` report
- [ ] `check-steam` output, if Steam integration is involved
- [ ] Any unusual configuration or multi-drive setup
- [ ] Anything already attempted to fix the problem

---

# For Maintainers

This report is intended to help determine the **root cause** of the issue.

Do not assume that an issue is a Kalium bug simply because the user encountered it while using Kalium.

Possible causes include:

- Kalium
- Steam
- Proton
- Wine
- MO2
- USVFS
- The game
- Filesystem configuration
- Linux distribution
- GPU/driver
- Steam library configuration
- User configuration

After investigation, classify the issue appropriately.

**Potential Kalium bug:**  
The problem can be reproduced and is caused by incorrect behavior in Kalium.

**Environment-specific issue:**  
The problem is caused by a particular system, configuration, Proton/Wine behavior, filesystem, Steam installation, or other external factor.

**Upstream issue:**  
The problem originates from another project such as Steam, Proton, Wine, MO2, USVFS, or the game itself.

**Unable to reproduce:**  
The available information is insufficient or the problem cannot currently be reproduced.

> **Do not remove environmental details from an issue simply because they do not appear to be related.** Those details can be critical for determining why a problem occurs on one system but not another.
