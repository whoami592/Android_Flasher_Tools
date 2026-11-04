# Android ROM Flasher Toolkit

Coded by **Mr Sabaz Ali Khan** (Cyber Security Engineer)

A guided, menu-driven Python wrapper around the **official** `adb` / `fastboot`
bootloader-unlock and flashing commands that manufacturers themselves ship
(e.g. `fastboot flashing unlock`, `fastboot oem unlock`). Built for flashing
custom recoveries and ROMs onto a device **you own**, after you have enabled
"OEM Unlocking" in Developer Options yourself.

## What this tool does

- Lists connected ADB and Fastboot devices
- Reads device info and current bootloader-unlock state (`fastboot getvar unlocked`)
- Runs the official unlock/re-lock fastboot commands, with an explicit
  typed-consent gate before anything destructive happens
- Flashes a partition image you supply (recovery, boot, vbmeta, etc.)
- Runs `adb sideload` for installing a ROM/OTA zip through custom recovery
- Logs every command run to `~/.android_rom_flasher/flasher.log`

## What this tool deliberately does NOT do

- No FRP (Factory Reset Protection) bypass
- No carrier/SIM lock, IMEI, or baseband/modem unlocking
- No bundled exploits, "universal unlock" codes, or third-party unlock services
- It will refuse to proceed with any unlock/flash step until you type the
  exact consent phrase confirming you own the device

## Requirements

- Python 3.8+
- [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools)
  (`adb` and `fastboot`) installed and on your `PATH`
- USB debugging enabled on the device (Settings > Developer Options)
- "OEM Unlocking" toggle enabled on the device (Settings > Developer Options)
  — this is required by the manufacturer before `fastboot flashing unlock`
  will work at all; this tool cannot unlock a device whose owner has not
  enabled that toggle

```bash
pip install -r requirements.txt
```

## Usage

```bash
python3 flasher.py
```

Walk through the numbered menu:

1. Connect the phone via USB, confirm it shows up under ADB devices.
2. Reboot to bootloader (option 3), confirm it shows up under Fastboot devices.
3. Check the unlock status (option 4).
4. If locked, run option 5 to unlock — you'll need to confirm on the device
   screen with the volume keys, same as doing it manually.
5. Flash your recovery/ROM/boot image(s) with option 7, or sideload an OTA
   zip through a custom recovery with option 8.
6. Reboot to system (option 9) when done.

## Responsible use

Only run this against hardware you own or are explicitly authorized to
modify. Unlocking wipes all data on the device and may void its warranty.
Flashing an incompatible image can brick the device — always use images
built for your exact device model.
