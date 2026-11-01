# M4 Camera Tool 1.0.0 source

[中文](README.md) · [User guide](../TOOL-1.0.0.md) · [Installation](../README.en.md) · [Implementation](../IMPLEMENTATION.md)

Prepare the Sony ILCE-7M4 update environment over ordinary USB, then let its owner install firmware from the SD card using the camera menu. The current build has received a successful user-test report. This update publishes source only; **no binary Release is published yet**.

The UI provides patch preparation and standalone ordinary-USB recovery. Users place the package on the card themselves. The tool does not read, validate, copy or bind DAT files. Complete firmware will be provided after all feature updates are finished.

## Behavior

- Setup binds one Windows user and camera. Matching installations and empty task folders are reused; missing tasks are added. Running tasks and unknown operations are preserved.
- Account names and SIDs are resolved to the same Windows identity before comparison. Mismatch fields are recorded in private setup receipts.
- Reviewed WinUSB packages cover normal and service USB identities. Trusting the libwdi self-signed certificates requires explicit consent, defaulting to cancellation; these are not Sony or Microsoft publisher certificates.
- Patch and menu stages reuse the driver. Full p1 backup, content matching, one write and independent complete readback remain; unknown layouts stop. Displayed firmware labels are not a whitelist.
- Operation completion is separate from storage recovery. Each launch opens a fresh UI session, preserving backups and logs. Unknown tasks are not automatically dispatched again.
- Normal operations use integrity checks without ARM64 simulation or fault injection.

## Build on Windows x64

Use Python 3.12+ and the Windows .NET Framework C# compiler. Building does not elevate, access a camera or install drivers. Runtime components are supplied separately rather than committed as source binaries.

`assets-files.json` pins **3257 files across nine groups**. Both WinUSB INF/catalog pairs and their shared coinstallers are six locked `tools/driver` assets. No research directory or extra source-tree binaries are required; other group locks are unchanged.

From this directory, with a separately supplied trusted portable package:

```powershell
py -3 prepare_assets.py --from-package D:\M4-portable.zip --output D:\M4-runtime
py -3 build.py --assets D:\M4-runtime --output D:\M4-build
D:\M4-build\M4相机工具.exe --verify
```

A portable ZIP containing all locked assets can also be passed directly to `build.py --assets`. Input app, state and firmware are ignored; app source comes from this checkout. The output must be new. See [THIRD_PARTY.md](THIRD_PARTY.md) and [assets-sources.json](assets-sources.json). Exact export is not a complete recipe for independently reconstructing every component from upstream archives.

The native launcher verifies files and imports before Python, CLR or elevation. Normal execution uses a protected ProgramData runtime; state and caches stay in the extracted folder. Read handles constrain replacement while running. `--verify` is local-only without elevation or a device session. A trusted launcher EXE remains the starting assumption; no Authenticode signature or antivirus verdict is provided.

## Development checks

Use a disposable build; never distribute its test state:

```powershell
D:\M4-build\runtime\python\python.exe -I -B tests\run_clean_setup.py --package D:\M4-build
D:\M4-build\runtime\python\python.exe -I -B tests\test_driver_reuse.py --package D:\M4-build
powershell -NoProfile -ExecutionPolicy Bypass -File tests\test_driver_trust.ps1 -Package D:\M4-build
```

Full setup simulation starts without tool state, tasks, related driver packages or certificates. Its scheduler models Windows returning an account name after SID registration. The optional `test_task_user_readback.ps1 -Source <source-directory>` requires reference tasks and is read-only; it is not a clean-machine installation test. Actual UAC, ACLs, driver binding and camera behavior require separate physical acceptance.

## Acknowledgements and scope

The approach references [YuuLuo/a7c2-camera-tools](https://github.com/YuuLuo/a7c2-camera-tools). Driver reuse and independent recovery draw on [QAQLeonard/a7c2-fl23-research](https://github.com/QAQLeonard/a7c2-fl23-research). Other sources are in [REFERENCES.md](../../REFERENCES.md).

No enrollment, backups, logs, private keys, full firmware or camera firmware libraries are included. External components keep their original licenses.
