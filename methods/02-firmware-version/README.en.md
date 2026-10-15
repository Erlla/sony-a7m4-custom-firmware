# Method 2: set the reported firmware version

[中文](README.md) · [Risks and backups](../../README.en.md)

This changes the reported version, not AP/CP programs or hardware capabilities. It does not guarantee removal of every downgrade restriction: model, package version, compatibility and signature checks remain separate requirements.

## Storage and BCD

Read your own `nflasha2` settings partition, traverse FAT directories/chains and locate `updater/dat4`. It contains exactly two bytes: **minor first, major second, in BCD**. Each nibble represents a decimal digit; decoding is `(byte >> 4) * 10 + (byte & 15)`.

| Reported version | Hex bytes in dat4 |
|---|---|
| 0.00 | `00 00` |
| 6.02 | `02 06` |
| 6.15 | `15 06` |
| 6.20 | `20 06` |
| 9.99 | `99 09` |

Writing decimal 20 as binary `0x14` makes the camera report 6.14. Printing stored `0x15` as an ordinary decimal integer incorrectly reports 6.21. Both directions are corrected in this implementation.

Evidence: 6.02 `libInfraGetVersion.so`, SHA-256 `3a69e737c04b50d120d00e8a0b977f1d60dbb4228abe3b41083e7ab9178be620`; getter ELF VA `0x12F0`, BCD helper `0xDF0`. These are binary-analysis findings, not Sony source code.

## Procedure

Read the backup requirements and [setup](../../docs/setup.en.md), then:

```powershell
python -m a7m4 maintain --action set_version
```

Alternatively use `advanced/查看或设置固件版本.bat`. Every invocation first creates a fresh complete backup. Blank input inspects only; `X.YY` prepares an edit. The supported input range is major `0`–`9`, minor `00`–`99`, covering the verified single-digit-major usage rather than claiming unlimited version fields throughout the firmware.

For offline examination of your backup:

```powershell
python -m a7m4.offline version local/my-backup/nflasha2.bin
python -m a7m4.offline version local/my-backup/nflasha2.bin --set 6.20 --output output/nflasha2-version.bin
```

Offline commands never operate hardware. The live workflow displays old/new versions, partition hashes and an exact confirmation string before writing, then verifies the complete partition readback. Text is UTF-8; BAT launchers select the Windows UTF-8 code page.

## Constraints and recovery

- Existing data must be two valid BCD bytes; unknown encodings are refused rather than guessed.
- Input is strictly bounded. `6.2`, `06.02`, negatives, command text and out-of-range major values are rejected.
- FAT copies, directories and allocation chains are validated. Partition size, allocation and unrelated files remain unchanged; differences are limited to zero, one or two dat4 bytes.
- Restore the original reported value or deliberately restore your own complete settings backup. Full partition restoration also rolls back newer settings.
- Identify actual firmware compatibility by binary hashes, never by an editable menu version. Do not combine mismatched AP/CP, loaders or calibration merely to force a downgrade.

See [implementation](../../a7m4/patching.py) and [tests](../../tests) for BCD boundary, synthetic FAT and unrelated-data preservation checks.
