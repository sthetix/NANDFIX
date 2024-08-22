# NANDFIX - The Nintendo Switch Unbricker

https://github.com/sthetix/NANDFIX/blob/main/nandfix.jpg

NANDFIX is a versatile tool that allows users to unbrick, rebuild, or upgrade the Nintendo Switch consoles. It features a graphical user interface (GUI) that is powered by the EmmcHaccGen and NxNandManager cores, making complex tasks like NAND generation, decryption, encryption, and rebuilding straightforward and accessible. NANDFIX serves as a user-friendly front end, designed to reduce errors and streamline operations compared to using command-line tools alone.

## Features

- **NAND Generation (GENERATE)**: Uses the EmmcHaccGen core to create NAND partitions and files based on the provided `prod.keys` and firmware version.
- **NAND Decryption (DECRYPT), NAND Encryption (ENCRYPT), and NAND Rebuild (BUILD)**: Powered by NxNandManager, these operations decrypt donor NAND partitions with `donor.keys`, re-encrypt them with `prod.keys`, and compile them into a new NAND.

## Prerequisites

Before using NANDFIX, ensure you have:

- **Operating System**: Windows 7 or higher.
- **.NET Desktop Runtime 7.0.20**: Download and install from [here](https://dotnet.microsoft.com/en-us/download/dotnet/7.0).
- **`prod.keys`**: Extracted from your console using the Lockpick_RCM payload.
- **Firmware Files**: Available from sources like [darthsternie.net](https://darthsternie.net) or [sthetix.info](https://sthetix.info).

## Usage

1. **Launch NANDFIX**:
   - Double-click `NANDFIX.exe` to start the application.

2. **Select Console Type**:
   - Choose between `Patched & Unpatched V1 (Erista)` and `V2, Lite, OLED (Mariko)`.

3. **Select Necessary Files**:
   - Use the GUI to select `prod.keys`, firmware folder, `donor_rawnand.bin`, `donor.keys`, and `prodinfo`.

4. **Choose an Operation**:
   - **GENERATE**: Creates NAND partitions and files using the EmmcHaccGen core.
   - **DECRYPT, ENCRYPT, and BUILD**: Decrypts donor NAND partitions, re-encrypts them, and compiles them into a new NAND using NxNandManager.

## Credits

NANDFIX is built on the powerful cores of two key projects:

- **EmmcHaccGen**: https://github.com/suchmememanyskill/EmmcHaccGen
- **NxNandManager**: https://github.com/eliboa/NxNandManager
