# Setup and external resources

[中文](setup.md) · [Back](../README.en.md)

The host needs Python 3.11+, pySerial, pyelftools and cryptography. It does not need a GUI, the original research workspace or a UART console. BAT files use UTF-8/CRLF; Python, Markdown and JSON use UTF-8.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

Use this environment's interpreter for subsequent `python` commands. Activate it or keep the full relative interpreter path. BAT launchers find the repository's `.venv`; `A7M4_PYTHON` can select another suitable interpreter.

## Obtain external binaries separately

Create this user-supplied tree under `local/resources/`:

```text
bin/fastboot.exe
bin/AdbWinApi.dll               # if required by that fastboot distribution
bin/AdbWinUsbApi.dll            # if required
bin/fastboot.bin               # camera boot payload
bin/uart_boot.ino.uf2           # RP2040 boot bridge
driver/android_winusb.inf
driver/...                     # matching catalogs, DLLs and architecture folders
squashfs/sqfs2tar.exe
squashfs/tar2sqfs.exe
squashfs/...                   # matching DLLs and license notices
```

- Host fastboot: obtain [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools), or build [AOSP fastboot](https://android.googlesource.com/platform/system/core/+/refs/heads/main/fastboot/). Keep matching DLLs and notices.
- Camera payload: build `payloads/fastboot` in [ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE) with its AArch64 Makefile. The revision/features must match the host protocol below.
- RP2040 UF2: build that project's `tools/uart_boot` with `make setup`, then `make build`, targeting Waveshare RP2040-Zero. Retain default `-DOPEN_DRAIN`. `UART_TX` is not needed.
- USB driver: obtain the original [Google USB Driver](https://developer.android.com/studio/run/win-usb) package under its SDK terms. The INF must contain `VID_18D1&PID_4EE0`. An already correctly installed driver can be used, while retaining the original pack for validation.
- SquashFS utilities: use a Windows build of [squashfs-tools-ng 1.3.2](https://github.com/AgentD/squashfs-tools-ng/tree/v1.3.2), including runtime libraries and notices. The updater builder uses `sqfs2tar` and `tar2sqfs` to retain metadata.

The host accepts `uart_boot 1` and `uart_boot 2` handshakes, using only common commands 1–5. Camera payload requirements are `getvar product`, `oem partition`, `oem partition dump`, `get_staged`, complete-partition `flash`, `reboot` and the `[mira] fastboot ready` log. Payload size must remain below `0xF000`, the reviewed SRAM window. Review code/layout rather than removing this bound to accommodate an incompatible build.

Historical local payload/UF2 binaries have not been shown reproducibly identical to upstream HEAD. A recorded checkout is a research reference, not hardware acceptance of every new upstream build. Avoid mixing unknown binaries.

Register resources to create a local SHA-256 manifest:

```powershell
python tools/register_resources.py local/resources
python -m a7m4 doctor
```

Alternatively import an existing local tool with `tools/import_local_resources.py --legacy-tool <tool-directory> --squashfs <squashfs-directory>`. Both helpers create ignored `vendor/local/` and `vendor/manifest.local.json`; neither copies camera images/keys or grants redistribution rights.

If driver installation is necessary, the host requests Windows elevation only for `pnputil`. It does not disable signature enforcement or create persistent elevated tasks. Hold BOOTSEL while plugging in the RP2040 for initial setup. Follow [wiring](wiring.en.md) before connecting camera signals.

## Optional complete firmware builds

```powershell
python -m pip install -e ".[firmware]"
```

This adds NumPy for batch block checks and Dissect extfs/util for validated in-place extent mapping. Backup, version editing and updater unlocking do not require these extras. Reserve at least 10 GB of temporary disk space for original/modified plaintext, unsigned intermediates and the final package.
