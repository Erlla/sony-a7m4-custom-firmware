# Install firmware without Fastboot

[中文](README.md) · [Patch locations](IMPLEMENTATION.md) · [M4 Camera Tool 1.00](TOOL-1.00.md)

A normal USB data cable prepares the Sony ILCE-7M4 updater; the camera then installs `BODYDATA.DAT` from its SD card. This route needs no Multi-port flashing cable, boot bridge or Fastboot session. The camera must boot normally and support USB mass-storage mode. It is not a recovery route for an unbootable camera.

The tool writes the p1 updater partition. Preserve your own backups, use an original battery, meet the updater's charge requirement and maintain stable power. The automatic p1 backup is not a complete eMMC, calibration or CP NOR backup.

## Use

1. Manually place a suitable `BODYDATA.DAT` in the root of the card in **slot 1**. The tool does not bundle, read, validate or copy it.
2. Extract the complete **1.00** Windows package to a short path, such as `D:\M4`. Turn on the camera and connect in USB mass-storage mode.
3. Open `M4相机工具.exe`, confirm readiness and select **写入补丁**. Approve the normal Windows administrator prompt during first-time setup.
4. Wait for the full backup, compatibility checks, any required patch and independent full readback. If prompted, keep the camera on and unplug/replug USB, then continue. Do not start the update yet.
5. Only when the tool explicitly permits it, unplug USB without turning off the camera. Return to shooting, open Version / Software Update, check the target and start installation.
6. Start within the approximately ten-minute menu window. Once installation has started, wait for completion; the computer countdown is not an instruction to interrupt power.
7. After installation and a normal reboot, check the version, shooting, saving and playback, then follow the tool's instructions to finish and restore normal USB.

The installed custom updater must retain correct handling of subsequent updates. With that condition met, obtain a suitable unmodified official package with an increasing target version and use Sony's normal update procedure. No further patch run is required. A return to official 6.02 has been accepted on the tested camera; see [VALIDATION.md](VALIDATION.md).

## Mechanism and limits

The normal USB service path runs a bounded native worker. The tool reads the complete current p1, patches its receiving updater if necessary, verifies a separate full readback, and temporarily changes two menu checks in RAM. The user performs the actual SD installation on the camera.

Signature verification returns success status **0**, while the version predicate returns Boolean **1**. Two additional local version-rejection results become success. Exact bytes and layout constraints are in [IMPLEMENTATION.md](IMPLEMENTATION.md) and [patches.json](patches.json). Retaining the original signature bytes does not make a modified DAT pass official RSA verification; acceptance relies on the receiving updater patch.

Compatibility follows actual reviewed contents and instruction layouts, without a displayed-version allowlist. This does not establish support for arbitrary firmware, cameras or packages. The tool keeps full backups, integrity checks, independent readback and unresolved-operation records. Normal operations do not run full ARM64 simulation or fault-injection regression tests.

This directory contains the current method, recipe and software guide. **The complete 1.00 Windows distribution still requires separate cleanup; this candidate includes no binary download.** Cloning this repository does not install that desktop tool.

## Acknowledgements

The installation approach references the research and implementation shared by [YuuLuo/a7c2-camera-tools](https://github.com/YuuLuo/a7c2-camera-tools). Thank you for making this work public.
