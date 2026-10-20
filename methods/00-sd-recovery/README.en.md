# 0. One-click recovery through the camera's SD updater

English · [中文](README.md) · [Home](../../README.en.md)

For a camera **already in fastboot**, this tool backs up the current body, prepares internal recovery flags, and reboots into the existing SD updater. The camera installs **`BODYDATA.DAT` from the root of the card in slot 1**. No firmware package is included.

**ILCE-7M4 only. The exact updater initrd SHA-256 must match the [reviewed profile](../../a7m4/profiles/sd-recovery.json), which currently lists one previously verified modified updater. This is not blanket support for stock or custom firmware.** Do not add an unknown hash just to bypass refusal. A damaged updater, card-reading path or earlier boot stage may prevent recovery.

Use a sufficiently charged **original Sony battery** and reliable power. Read the [risk and backup requirements](../../README.en.md#risk-and-mandatory-backups). The recovery entry automatically writes the prepared trigger, verifies readback and reboots without another interactive confirmation. Prepare the correct DAT first.

## Use

1. Install Python 3.11+ and this repository following [setup](../../docs/setup.en.md). Register a complete resource pack, or use the minimal registration below when fastboot entry already works.
2. Put a known-good package for your body, acceptable to its **currently installed updater**, at slot 1 card root as `BODYDATA.DAT`. The host neither selects nor reads/validates that file.
3. Enter fastboot using the reviewed [Multi-port/RP2040 setup](../../docs/wiring.en.md), and connect the camera's data USB cable. Connect only one camera. This tool does not enter fastboot, install a driver or issue serial commands.
4. Run [只检查fastboot连接.bat](../../advanced/只检查fastboot连接.bat). It only enumerates and queries `product`: no partition reads, writes or reboot. Run recovery promptly afterwards; an idle camera may leave fastboot.
5. Run [一键救砖_从SD卡恢复.bat](../../advanced/一键救砖_从SD卡恢复.bat). It backs up, checks the environment, writes the settings candidate at most once, verifies the entire readback and sends one normal reboot. Maintain power and leave the card inserted while the camera updates.
6. Check live view, menus, reported version and a normal power cycle. Independently inspect the update log/NOR when NOR recovery matters. Host success means **update triggered, camera confirmation pending**.

Equivalent commands from repository root:

```powershell
.\.venv\Scripts\python.exe -m a7m4.recover_sd --check-connection
.\.venv\Scripts\python.exe -m a7m4.recover_sd
```

BAT uses the repository `.venv` or `A7M4_PYTHON`. Backups and logs default to ignored `local/sd-recovery/sessions/<timestamp_id>/`; `--sessions` selects another local parent. These contain camera personalization and must stay private.

### Minimal recovery resources

If a complete `vendor/manifest.local.json` already exists, keep it. Otherwise obtain [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools), retain its matching DLLs/notices, and arrange:

```text
local/recovery-resources/bin/fastboot.exe
local/recovery-resources/bin/AdbWinApi.dll       (if required by that distribution)
local/recovery-resources/bin/AdbWinUsbApi.dll    (if required by that distribution)
```

```powershell
.\.venv\Scripts\python.exe tools/register_resources.py local/recovery-resources --recovery-only
```

Registration copies local files and records SHA-256 without hardware access. Do not mix DLL distributions. The general `doctor` still reports missing boot payload/driver/SquashFS resources in a minimal pack; the recovery entry checks only fastboot and registered adjacent DLLs. External binaries are not redistributed here.

## Mechanism

| Stage | Action | Limit |
|---|---|---|
| Fastboot backup | Identify one ILCE-7M4, validate the partition table, back up `nflashaB0/B1/1/2/8/13` | Six partitions, **not a whole-camera backup**, no physical CP NOR |
| Updater check | Read `nflasha1:/boot/initrd.img`, match its MD5 in `p1chksum` and exact SHA-256 profile | Does not replace keys or patch `verifyKey` |
| Trigger | In `nflasha2` FAT, temporarily set packed-BCD `updater/dat4` to `0.00`; create empty `updater/mode` and `updater/mode5` | Internal `/setting/updater/…` paths, **not files on the SD card** |
| Write and verify | Recheck same-body B0/B1/settings and layout; allow only the prepared `nflasha2` candidate; verify all 20 MiB before reboot | Preserve FAT, root directory, `Backup.bin` and other original files; no filesystem expansion/rebuild |
| Camera update | Existing updater reads slot 1 `BODYDATA.DAT`, validates and installs it | Native chain performs required eMMC/NOR work; host does not write NOR or guarantee every package updates it |
| Completion | Camera behavior, update logs and optional independent NOR/partition readback | Host keeps `update_completed=false`; installation needs separate evidence |

`dat4=0.00` addresses the native version gate for same-version reinstall/recovery rollback. It **does not alter signatures**: the package still must satisfy the installed updater's key, model and other rules. The card's DAT determines the installed contents and may overwrite custom changes. If installation fails, temporary version/flags may remain; preserve the session backup.

Only the two DAT4 bytes and up to two existing 32-byte directory slots may differ. Conflicting update modes, malformed flags, insufficient slots, unknown layout, invalid FAT, changed backups/candidate or changed device contents stop the operation.

## Results and failures

| Result | Interpretation |
|---|---|
| `CONNECTION_OK` | Read-only query succeeded; no recovery performed |
| `USB_TIMEOUT` / `USB_TRANSPORT` | No valid transport response. Recheck fastboot, cable, driver and power, then run the read-only check. Error 121 alone does not identify one physical cause |
| `MODEL` / `UPDATER_PROFILE` | Unsupported model/environment; retain logs and review compatibility, do not remove the gate |
| `STOPPED_KEEP_FASTBOOT` | Stopped before reboot. Consult `flash_attempted` and `readback_verified`; this label does not guarantee USB remains present or the body stayed in fastboot |
| Write/readback failure | No automatic retry, rollback or reboot. A failed write may be partial |
| `REBOOT_OUTCOME_UNCERTAIN` | Reboot was attempted; observe the camera before taking further action |
| `SD_UPDATE_TRIGGERED_PENDING_CAMERA` | Host readback passed and reboot command returned; camera installation remains unconfirmed |

The transport recognizes `FAILED (…)` even when fastboot exits with status 0, so USB 121 is no longer misreported as a model mismatch. Write authorization is consumed before issuing the command, preventing automatic retry after a potentially partial write.

## Source and validation

[Core](../../a7m4/sd_recovery.py), [entry point](../../a7m4/recover_sd.py), [profile](../../a7m4/profiles/sd-recovery.json), [workflow tests](../../tests/test_sd_recovery.py), [connection regressions](../../tests/test_sd_recovery_connection.py), [public integration tests](../../tests/test_sd_recovery_public.py), [validation record](validation.md).

Tests use synthetic images and mocked transports, including failures before/after write and uncertain reboot. Historical same-body MODE5 recovery has update-log/NOR-readback and normal-boot evidence. **This public adaptation has not completed a new physical recovery test and is not a cure for every fault.** The other five patch recipes are unchanged.

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pytest -q tests/test_sd_recovery.py tests/test_sd_recovery_connection.py tests/test_sd_recovery_public.py
```
