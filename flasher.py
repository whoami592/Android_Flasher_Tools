#!/usr/bin/env python3
"""
================================================================================
  ANDROID ROM FLASHER TOOLKIT
  Official bootloader-unlock + custom ROM flashing assistant
  (built on top of the manufacturer's own `fastboot` unlock flow)
--------------------------------------------------------------------------------
  Coded by: Mr Sabaz Ali Khan (Cyber Security Engineer)
================================================================================

SCOPE / WHAT THIS TOOL IS:
  This tool is a guided wrapper around the OFFICIAL, documented fastboot
  commands that device manufacturers themselves expose for bootloader
  unlocking (e.g. `fastboot flashing unlock`, `fastboot oem unlock`).
  It is meant for a device YOU OWN, where YOU have already enabled
  "OEM Unlocking" in Developer Options.

WHAT THIS TOOL IS NOT:
  - It is NOT an FRP (Factory Reset Protection) bypass tool.
  - It does NOT touch carrier locks, SIM locks, IMEI, or baseband/modem.
  - It does NOT contain exploits, universal unlock codes, or anything that
    works on a device without the owner's own OEM-unlock toggle enabled.
  - It will not run against a device it cannot positively confirm consent for.

Every destructive action requires the user to type an explicit confirmation
phrase and passes straight through to the stock `adb`/`fastboot` binaries -
no hidden network calls, no bundled exploits, no third-party unlock services.
"""

import os
import sys
import json
import time
import shutil
import logging
import subprocess
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------------
# Optional color support (falls back gracefully to plain text if missing)
# --------------------------------------------------------------------------
try:
    from colorama import init as _colorama_init, Fore, Style
    _colorama_init(autoreset=True)
    C_RED = Fore.RED + Style.BRIGHT
    C_GREEN = Fore.GREEN + Style.BRIGHT
    C_YELLOW = Fore.YELLOW + Style.BRIGHT
    C_CYAN = Fore.CYAN + Style.BRIGHT
    C_MAGENTA = Fore.MAGENTA + Style.BRIGHT
    C_BLUE = Fore.BLUE + Style.BRIGHT
    C_WHITE = Fore.WHITE + Style.BRIGHT
    C_RESET = Style.RESET_ALL
except ImportError:
    C_RED = C_GREEN = C_YELLOW = C_CYAN = C_MAGENTA = C_BLUE = C_WHITE = C_RESET = ""

APP_NAME = "Android ROM Flasher Toolkit"
APP_VERSION = "1.0.0"
AUTHOR = "Mr Sabaz Ali Khan"
LOG_DIR = Path.home() / ".android_rom_flasher"
LOG_FILE = LOG_DIR / "flasher.log"
CONSENT_PHRASE = "I OWN THIS DEVICE"

# Known manufacturer unlock command variants.
# Both commands are OFFICIAL fastboot subcommands shipped by AOSP/manufacturers -
# not reverse-engineered or exploit-based.
UNLOCK_COMMANDS = {
    "modern": ["flashing", "unlock"],       # current AOSP standard (Pixel, many others)
    "legacy": ["oem", "unlock"],            # older devices (pre-Android 9 ish)
}
RELOCK_COMMANDS = {
    "modern": ["flashing", "lock"],
    "legacy": ["oem", "lock"],
}

# --------------------------------------------------------------------------
# Banner
# --------------------------------------------------------------------------
BANNER = rf"""{C_CYAN}
   ▄▄▄       ███▄    █ ▓█████▄  ██▀███   ▒█████   ██▓▓█████▄
  ▒████▄     ██ ▀█   █ ▒██▀ ██▌▓██ ▒ ██▒▒██▒  ██▒▓██▒▒██▀ ██▌
  ▒██  ▀█▄  ▓██  ▀█ ██▒░██   █▌▓██ ░▄█ ▒▒██░  ██▒▒██▒░██   █▌
  ░██▄▄▄▄██ ▓██▒  ▐▌██▒░▓█▄   ▌▒██▀▀█▄  ▒██   ██░░██░░▓█▄   ▌
   ▓█   ▓██▒▒██░   ▓██░░▒████▓ ░██▓ ▒██▒░ ████▓▒░░██░░▒████▓
   ▒▒   ▓▒█░░ ▒░   ▒ ▒  ▒▒▓  ▒ ░ ▒▓ ░▒▓░░ ▒░▒░▒░ ░▓   ▒▒▓  ▒
    ▒   ▒▒ ░░ ░░   ░ ▒░ ░ ▒  ▒   ░▒ ░ ▒░  ░ ▒ ▒░  ▒ ░ ░ ▒  ▒
    ░   ▒      ░   ░ ░  ░ ░  ░   ░░   ░ ░ ░ ░ ▒   ▒ ░ ░ ░  ░
        ░  ░         ░    ░       ░         ░ ░   ░     ░
                         ░                             ░
{C_WHITE}        R O M   F L A S H E R   T O O L K I T  v{APP_VERSION}
{C_YELLOW}        Official fastboot unlock flow  |  Owner-consented only
{C_MAGENTA}        Coded by {AUTHOR}  (Cyber Security Engineer)
{C_RESET}
{C_WHITE}        ░▒▓ ⠠⠉⠕⠙⠑⠙⠀⠃⠽⠀⠍⠗⠀⠎⠁⠃⠁⠵⠀⠁⠇⠊⠀⠅⠓⠁⠝ ▓▒░
{C_RESET}
"""

SAFETY_NOTICE = f"""{C_YELLOW}
--------------------------------------------------------------------------------
 LEGAL / SAFETY NOTICE
--------------------------------------------------------------------------------
 - Only use this tool on a device YOU own or have explicit written
   authorization to modify.
 - Unlocking the bootloader WILL factory-reset the device and erases all data.
 - This tool uses only the official `fastboot flashing unlock` / `oem unlock`
   commands that the manufacturer itself ships - the same ones you would run
   by hand. It does not bypass FRP, carrier locks, or baseband/IMEI locks.
 - Flashing the wrong image, or flashing on a device with a locked bootloader
   that this flow could not unlock, can permanently brick the device.
   Proceed only if you understand and accept this risk.
--------------------------------------------------------------------------------
{C_RESET}"""


def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(LOG_FILE),
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def log(msg, level="info"):
    getattr(logging, level)(msg)


def banner():
    os.system("cls" if os.name == "nt" else "clear")
    print(BANNER)


def which_or_die(binary):
    path = shutil.which(binary)
    if not path:
        print(f"{C_RED}[!] '{binary}' was not found on PATH.")
        print(f"{C_YELLOW}    Install Android platform-tools and ensure it is on PATH.{C_RESET}")
        return None
    return path


def run(cmd, capture=True, timeout=120):
    """Run a command, returning (returncode, stdout, stderr). Always logs."""
    log(f"RUN: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=timeout,
        )
        if capture:
            log(f"RC={result.returncode} STDOUT={result.stdout.strip()[:500]} "
                f"STDERR={result.stderr.strip()[:500]}")
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        return result.returncode, "", ""
    except FileNotFoundError:
        return 127, "", f"{cmd[0]} not found on PATH"
    except subprocess.TimeoutExpired:
        return 124, "", "command timed out"


def pause():
    input(f"\n{C_CYAN}Press Enter to continue...{C_RESET}")


def confirm_ownership():
    print(SAFETY_NOTICE)
    typed = input(
        f"{C_WHITE}Type exactly '{C_RED}{CONSENT_PHRASE}{C_WHITE}' to continue, "
        f"or anything else to abort: {C_RESET}"
    )
    ok = typed.strip() == CONSENT_PHRASE
    log(f"Consent prompt answered: {'ACCEPTED' if ok else 'DECLINED'}")
    return ok


# --------------------------------------------------------------------------
# Device state helpers
# --------------------------------------------------------------------------
def adb_devices():
    which_or_die("adb")
    rc, out, err = run(["adb", "devices", "-l"])
    lines = [l for l in out.splitlines() if l.strip() and "List of devices" not in l]
    return lines


def fastboot_devices():
    which_or_die("fastboot")
    rc, out, err = run(["fastboot", "devices"])
    lines = [l for l in out.splitlines() if l.strip()]
    return lines


def adb_getprop(prop):
    rc, out, err = run(["adb", "shell", "getprop", prop])
    return out.strip()


def fastboot_getvar(var):
    rc, out, err = run(["fastboot", "getvar", var])
    # fastboot prints getvar output to stderr historically
    text = (out + "\n" + err).strip()
    for line in text.splitlines():
        if line.startswith(f"{var}:"):
            return line.split(":", 1)[1].strip()
    return "unknown"


def reboot_to_bootloader():
    which_or_die("adb")
    rc, out, err = run(["adb", "reboot", "bootloader"], capture=False)
    print(f"{C_GREEN}[*] Reboot command sent. Waiting for bootloader mode...{C_RESET}")
    time.sleep(5)


def detect_unlock_command_style():
    """
    Probe which unlock command style the connected bootloader supports.
    Tries the modern 'flashing unlock' first (current AOSP standard),
    falls back to legacy 'oem unlock'.
    """
    rc, out, err = run(["fastboot", "flashing", "get_unlock_ability"])
    combined = (out + err).lower()
    if "unknown command" not in combined and rc != 127:
        return "modern"
    return "legacy"


# --------------------------------------------------------------------------
# Menu actions
# --------------------------------------------------------------------------
def action_check_adb_devices():
    print(f"{C_CYAN}[*] Scanning for ADB (Android debugging) devices...{C_RESET}\n")
    devices = adb_devices()
    if not devices:
        print(f"{C_YELLOW}No devices found. Ensure USB debugging is enabled and the "
              f"device is connected + authorized.{C_RESET}")
    else:
        for d in devices:
            print(f"{C_GREEN}  {d}{C_RESET}")
    pause()


def action_check_fastboot_devices():
    print(f"{C_CYAN}[*] Scanning for Fastboot-mode devices...{C_RESET}\n")
    devices = fastboot_devices()
    if not devices:
        print(f"{C_YELLOW}No fastboot devices found. Boot the device into bootloader "
              f"mode first (Option 3, or Power+VolDown on most devices).{C_RESET}")
    else:
        for d in devices:
            print(f"{C_GREEN}  {d}{C_RESET}")
    pause()


def action_device_info():
    print(f"{C_CYAN}[*] Reading device info (ADB mode)...{C_RESET}\n")
    fields = {
        "Manufacturer": "ro.product.manufacturer",
        "Model": "ro.product.model",
        "Android version": "ro.build.version.release",
        "Build ID": "ro.build.display.id",
        "Device codename": "ro.product.device",
    }
    for label, prop in fields.items():
        val = adb_getprop(prop) or "unavailable (check connection)"
        print(f"  {C_WHITE}{label:<20}{C_RESET}: {val}")

    print(f"\n{C_CYAN}[*] Reading bootloader state (fastboot mode, if available)...{C_RESET}")
    unlocked = fastboot_getvar("unlocked")
    print(f"  {C_WHITE}{'Bootloader unlocked':<20}{C_RESET}: {unlocked}")
    pause()


def action_reboot_bootloader():
    print(f"{C_CYAN}[*] Rebooting device into bootloader/fastboot mode...{C_RESET}")
    reboot_to_bootloader()
    pause()


def action_unlock_bootloader():
    banner()
    print(f"{C_RED}{Style.BRIGHT if 'Style' in dir() else ''}"
          f"=== OFFICIAL BOOTLOADER UNLOCK (fastboot flashing/oem unlock) ==={C_RESET}\n")
    if not confirm_ownership():
        print(f"{C_YELLOW}Aborted - ownership not confirmed.{C_RESET}")
        pause()
        return

    devices = fastboot_devices()
    if not devices:
        print(f"{C_RED}[!] No device in fastboot mode detected.{C_RESET}")
        print(f"{C_YELLOW}    Reboot to bootloader first (menu option 3).{C_RESET}")
        pause()
        return

    style = detect_unlock_command_style()
    cmd = ["fastboot"] + UNLOCK_COMMANDS[style]
    print(f"\n{C_CYAN}[*] Using '{style}' unlock command: {' '.join(cmd)}{C_RESET}")
    print(f"{C_YELLOW}[*] Your device will now show an on-screen confirmation."
          f" Use the volume keys to confirm UNLOCK on the device itself.{C_RESET}\n")

    rc, out, err = run(cmd, timeout=180)
    if rc == 0:
        print(f"{C_GREEN}[+] Unlock command completed. Device will factory reset "
              f"and reboot.{C_RESET}")
        log(f"Bootloader unlock command succeeded (style={style})")
    else:
        print(f"{C_RED}[!] Unlock command returned an error (rc={rc}).{C_RESET}")
        print(f"{C_WHITE}{out}\n{err}{C_RESET}")
        log(f"Bootloader unlock command FAILED (style={style}) rc={rc} err={err}")
    pause()


def action_relock_bootloader():
    banner()
    print(f"{C_CYAN}=== RE-LOCK BOOTLOADER (restore stock state) ==={C_RESET}\n")
    print(f"{C_YELLOW}Re-locking should only be done AFTER flashing back to full "
          f"stock firmware, or the device may become unbootable.{C_RESET}")
    if not confirm_ownership():
        print(f"{C_YELLOW}Aborted - ownership not confirmed.{C_RESET}")
        pause()
        return

    devices = fastboot_devices()
    if not devices:
        print(f"{C_RED}[!] No device in fastboot mode detected.{C_RESET}")
        pause()
        return

    style = detect_unlock_command_style()
    cmd = ["fastboot"] + RELOCK_COMMANDS[style]
    print(f"{C_CYAN}[*] Running: {' '.join(cmd)}{C_RESET}")
    rc, out, err = run(cmd, timeout=180)
    if rc == 0:
        print(f"{C_GREEN}[+] Re-lock command completed.{C_RESET}")
    else:
        print(f"{C_RED}[!] Re-lock command returned an error (rc={rc}).{C_RESET}")
        print(f"{C_WHITE}{out}\n{err}{C_RESET}")
    pause()


def _pick_file(prompt):
    path = input(f"{C_WHITE}{prompt}: {C_RESET}").strip().strip('"').strip("'")
    if not path:
        return None
    p = Path(path).expanduser()
    if not p.exists():
        print(f"{C_RED}[!] File not found: {p}{C_RESET}")
        return None
    return p


def action_flash_image():
    banner()
    print(f"{C_CYAN}=== FLASH A SINGLE PARTITION IMAGE (fastboot flash) ==={C_RESET}\n")
    print(f"{C_WHITE}Common partitions: recovery, boot, vendor_boot, dtbo, "
          f"vbmeta, system{C_RESET}\n")

    devices = fastboot_devices()
    if not devices:
        print(f"{C_RED}[!] No device in fastboot mode detected.{C_RESET}")
        pause()
        return

    unlocked = fastboot_getvar("unlocked")
    if unlocked.lower() not in ("yes", "true", "1"):
        print(f"{C_YELLOW}[!] Bootloader does not report as unlocked "
              f"(unlocked={unlocked}).{C_RESET}")
        print(f"{C_YELLOW}    Flashing non-stock images on a locked bootloader will "
              f"likely fail or be rejected by the device.{C_RESET}")
        if input(f"{C_WHITE}Continue anyway? (y/N): {C_RESET}").strip().lower() != "y":
            return

    partition = input(f"{C_WHITE}Partition name to flash (e.g. recovery, boot): "
                       f"{C_RESET}").strip()
    if not partition:
        print(f"{C_RED}[!] No partition specified.{C_RESET}")
        pause()
        return

    img = _pick_file("Full path to the .img file to flash")
    if not img:
        pause()
        return

    if not confirm_ownership():
        print(f"{C_YELLOW}Aborted - ownership not confirmed.{C_RESET}")
        pause()
        return

    cmd = ["fastboot", "flash", partition, str(img)]
    print(f"\n{C_CYAN}[*] Running: {' '.join(cmd)}{C_RESET}\n")
    rc, out, err = run(cmd, timeout=300)
    if rc == 0:
        print(f"{C_GREEN}[+] Flashed '{partition}' successfully.{C_RESET}")
        log(f"Flashed partition={partition} image={img}")
    else:
        print(f"{C_RED}[!] Flash failed (rc={rc}).{C_RESET}")
        print(f"{C_WHITE}{out}\n{err}{C_RESET}")
        log(f"FLASH FAILED partition={partition} image={img} rc={rc} err={err}")
    pause()


def action_sideload_rom():
    banner()
    print(f"{C_CYAN}=== ADB SIDELOAD A ROM / OTA ZIP (via custom recovery) ===\n")
    print(f"{C_WHITE}Use this after booting into a custom recovery (e.g. TWRP/"
          f"stock recovery) and selecting 'Apply update > ADB sideload'.{C_RESET}\n")

    zip_path = _pick_file("Full path to the ROM/OTA .zip file")
    if not zip_path:
        pause()
        return

    if not confirm_ownership():
        print(f"{C_YELLOW}Aborted - ownership not confirmed.{C_RESET}")
        pause()
        return

    cmd = ["adb", "sideload", str(zip_path)]
    print(f"\n{C_CYAN}[*] Running: {' '.join(cmd)}{C_RESET}\n")
    rc, out, err = run(cmd, capture=False, timeout=900)
    if rc == 0:
        print(f"{C_GREEN}[+] Sideload finished (check the device screen for the "
              f"recovery's own result).{C_RESET}")
    else:
        print(f"{C_RED}[!] Sideload returned rc={rc}. Check device screen / logs.{C_RESET}")
    pause()


def action_reboot_system():
    print(f"{C_CYAN}[*] Rebooting device into system...{C_RESET}")
    run(["fastboot", "reboot"], capture=False)
    pause()


def action_view_log():
    banner()
    print(f"{C_CYAN}=== SESSION LOG ({LOG_FILE}) ==={C_RESET}\n")
    if LOG_FILE.exists():
        print(LOG_FILE.read_text()[-4000:])
    else:
        print(f"{C_YELLOW}No log entries yet.{C_RESET}")
    pause()


# --------------------------------------------------------------------------
# Main menu
# --------------------------------------------------------------------------
MENU = [
    ("1", "List ADB devices (phone powered on, USB debugging)", action_check_adb_devices),
    ("2", "List Fastboot devices (phone in bootloader mode)", action_check_fastboot_devices),
    ("3", "Reboot device to bootloader", action_reboot_bootloader),
    ("4", "Show device info & bootloader unlock status", action_device_info),
    ("5", "Unlock bootloader (official fastboot flow)", action_unlock_bootloader),
    ("6", "Re-lock bootloader (restore stock)", action_relock_bootloader),
    ("7", "Flash a partition image (recovery / boot / vbmeta / ...)", action_flash_image),
    ("8", "ADB sideload a ROM/OTA zip (via custom recovery)", action_sideload_rom),
    ("9", "Reboot device to system", action_reboot_system),
    ("L", "View session log", action_view_log),
    ("Q", "Quit", None),
]


def print_menu():
    print(f"{C_WHITE}Select an option:{C_RESET}\n")
    for key, label, _ in MENU:
        print(f"  {C_GREEN}[{key}]{C_RESET} {label}")
    print()


def main():
    setup_logging()
    log("=== Session started ===")
    while True:
        banner()
        print_menu()
        choice = input(f"{C_CYAN}>> {C_RESET}").strip().upper()
        match = next((m for m in MENU if m[0] == choice), None)
        if not match:
            print(f"{C_RED}Invalid option.{C_RESET}")
            pause()
            continue
        key, label, func = match
        if key == "Q":
            print(f"{C_MAGENTA}Goodbye. Stay safe - {AUTHOR}.{C_RESET}")
            log("=== Session ended ===")
            break
        banner()
        func()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{C_YELLOW}Interrupted by user. Exiting.{C_RESET}")
        sys.exit(0)
