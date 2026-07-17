# Cult of the Lamb Save Sync & Backup Utility

A utility with a graphical user interface (GUI) for bidirectional transfer and automatic patching of Cult of the Lamb game saves between Nintendo Switch and PC (Steam).

---

## Transfer Requirements

Ensure the following requirements are met before using the utility:

1. On PC:
   - Python 3 installed (to run source code, if not using the compiled executable).
   - Node.js (version 16 or higher) installed to process MessagePack and LZ4 data.
   - For Linux users: Tkinter must be installed. On Arch Linux, install it via `sudo pacman -S tk`.
   - Steam Cloud disabled in the properties of Cult of the Lamb in Steam (to prevent Steam from overwriting synchronized files with older cloud copies).

2. On Nintendo Switch (modded console):
   - JKSV save manager installed.
   - FTP server running (via homebrew application like ftpd, or the built-in FTP server in Atmosphere/JKSV).
   - Console connected to the same local Wi-Fi network as the computer.

---

## Instructions: Syncing from Switch to PC (Switch -> PC Sync)

This mode downloads saves from the console, automatically fixes version incompatibilities, and resolves the follower AI freeze bug (TwitchSettings null-pointer freeze).

1. Launch the game on Switch, open JKSV, select Cult of the Lamb, and create a backup (Create Backup).
2. Start the FTP server on Switch and note the IP address and port.
3. Run SaveSync.exe (or SaveSyncGUI.py) on PC.
4. Enter the Switch IP address and port in the corresponding fields on the left side of the window.
5. Click the "Switch -> PC Sync" button.
6. The utility will automatically:
   - Download the latest backup via FTP.
   - Decompress LZ4 blocks and decode MessagePack structures.
   - Patch Twitch settings to be PC-compatible and expand the save array to the PC size of 1396 elements.
   - Encrypt the files to PC standard (AES-128-CBC) and deploy them to your Steam saves folder.
7. Launch the game on PC and load the corresponding save slot.

---

## Instructions: Syncing from PC to Switch (PC -> Switch Sync)

This mode takes your current PC saves, adapts them for Switch, and uploads a JKSV-compatible backup archive back to the console.

1. Ensure that you have at least one previously created backup in JKSV on your Switch (used as a template to preserve Switch-specific metadata files, screenshots, and .nx_save_meta.bin).
2. Start the FTP server on Switch.
3. In the utility on PC, click the "PC -> Switch Sync" button.
4. The utility will automatically:
   - Read your active PC saves.
   - Decrypt and decompress them.
   - Adapt structures for Switch (reset TwitchSettings to null and decrease the array size to 1395 elements).
   - Compress the slots and metadata back into LZ4 blocks with the Switch "MP" header.
   - Write them into a copy of the original JKSV archive named "sync_PC - [date].zip".
   - Upload this ZIP archive back to the Switch under the JKSV backups folder.
5. On Switch, open JKSV, select Cult of the Lamb, find the backup named "sync_PC - [date]" in the list, and press Restore.
6. Launch the game on Switch to load the imported progress.
---

Made by Sanchos from https://sanchos.su
