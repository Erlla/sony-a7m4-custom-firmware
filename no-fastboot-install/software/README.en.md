# M4 Camera Tool source

[中文](README.md) · [Installation](../README.en.md) · [Implementation](../IMPLEMENTATION.md)

Current **1.00** desktop source: the simplified UI, Windows driver setup and standalone USB recovery, full p1 backup, content-based receiver patches, single-attempt writes, independent full readback and the temporary two-site RAM menu window.

The source excludes complete firmware, camera libraries, precompiled workers, enrollment, backups and run state. Users prepare the SD package manually; the tool does not inspect or copy it. Each launch starts a new operation session while preserving earlier logs and backups. The no-Fastboot approach references [YuuLuo/a7c2-camera-tools](https://github.com/YuuLuo/a7c2-camera-tools).

Unused experimental installation entry points and fixed experimental labels have been removed. Current UI-reachable operations, native workers and evidence checks remain. Research logs are not runtime dependencies.

## Build on Windows x64

Use Python 3.12+ and the Windows .NET Framework C# compiler. Building does not request elevation, install drivers or access a camera.

Runtime components are supplied separately. Provide a clean runtime directory or portable ZIP containing the groups locked by `dependencies.json`: `runtime/python`, the four `vendor` groups, Zig, SquashFS tools, reviewed driver files and licenses. Each directory's filename/content digest must match. Equal version labels alone are insufficient. See [THIRD_PARTY.md](THIRD_PARTY.md). This source publication does not upload runtime binaries or create a GitHub Release.

```powershell
py -3 build.py --assets D:\M4-runtime --output D:\M4-build
D:\M4-build\M4相机工具.exe --verify
```

The output must be a new directory. Only locked runtime groups are copied from the asset input; app source always comes from this checkout. Input app, state and firmware files are ignored. The builder generates `app/release.json`, compiles `Launcher.cs` and performs local-only integrity validation. An application icon is optional.

Launch the output EXE; running the raw entry.py without its generated manifest and runtime is unsupported. Never build over an existing user installation or unresolved run.

Normal launch requests Windows administrator privileges. Cancelling the UAC prompt exits; an already elevated process opens directly. `--verify` remains a local integrity check without elevation or an operation session.

Every launch opens the initial patch screen with USB recovery available. A new directory under `state/sessions/` isolates workflow, patch and recovery state; child processes inherit the current session. Previous tasks do not gate a new session. Enrollment, logs and backups remain available. Global process locks and live camera-state checks still apply, and a new operation reads the complete current p1 again.

After driver rebinding, normal USB identity checks wait up to about eight seconds, releasing handles and re-enumerating between standard descriptor reads. Only a language advertised by the device is requested; model, serial and saved identity must still match. Underlying USB errors are recorded. A persistent descriptor failure before menu-session authentication restores the normal driver and stops menu preparation, without replaying firmware writes or starting a menu worker.

## Offline checks

Run the scripts under `tests/` with the built package's isolated Python and `--package D:\M4-build`, including `test_startup_session.py` for process-level restart isolation and Tk controls. `test_menu_seal.py` also needs `--lineage stock` or `--lineage user`. Use a disposable build: tests create fake enrollment and run state, so the tested directory must not be distributed.

Tests cover recovery UI/state guards, real local job construction and menu sealing/validation, stopping before real device operations. Their receiver proof is synthetic and cannot establish physical-camera behavior. Normal patch operations use integrity checks without ARM64 simulation or fault-injection regression.

`test_state_io.py` also exercises real Windows file-sharing behavior inside temporary directories. JSON readers permit delete sharing and existing documents use ReplaceFileW. Bounded retries apply only to publishing local JSON. An initial-record failure is retired only after paired records, events and flow timing prove that no device step began; driver dispatch, native START and COMMIT are never retried by this helper.

Project-authored code follows the repository [LICENSE](../../LICENSE); external components keep their original licenses. Complete firmware packages are not available yet and will be provided after all feature updates are complete.
