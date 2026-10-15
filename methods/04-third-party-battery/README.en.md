# Method 4: remove third-party battery percentage/caution restrictions

[中文](README.md) · [Flashing risks and backups](../../README.en.md)

This publishes two local AP policies: displaying genuine reported battery percentage and suppressing the “continue using a third-party battery” caution. It does not replace battery authentication or guarantee every third-party battery will work. Charging, temperature/low-power shutdown protection and communication protocols are outside the patch.

## Mechanism and exact scope

Target: `nflasha15:/lib/appFw.so`. ELF VA equals file offset at these reviewed 6.02 sites:

| Path | Addresses | Replacement |
|---|---|---|
| Active battery percentage | `0x241A238`, `0x241A2C8` | Local NG reads → `mov w21,#0` |
| Secondary battery percentage | `0x241A488`, `0x241A4F4` | Local NG reads → `mov w21,#0` |
| Aggregate percentage | `0x241A758`, `0x241A760`, `0x241A77C`, `0x241A7E0`, `0x241A844`, `0x241A940`, `0x241A950` | Local NG reads → `mov w0,#0` |
| Aggregate percentage | `0x241A784` | Local NG read → `mov w1,#0` |
| Active/secondary caution | `0x1BAE40C`, `0x1BAE480` | Local accepted reads → `mov w0,#1` |
| Startup cautions | `0x2108814`, `0x2108CD0` | `mov w28,#1`, `mov w27,#1` respectively |

The display paths see a local NG value of zero; authentication source properties, setters and actual reported charge remain unchanged. A battery that cannot report percentage does not gain fabricated telemetry.

Four local reads treat `is_3rd_party_battery_caution_accepted` as accepted, avoiding resource `0x462`. Global accepted/authentication state remains unchanged. Total: **16 instructions, 64 covered bytes, 60 changed bytes**: 48 display bytes and 12 caution bytes. Exact preimages, output bytes and identities are in [battery.json](../../a7m4/profiles/battery.json); implementation is [features.py](../../a7m4/features.py).

## Supported input identities

AP size must be 98,212,632 bytes with an exact whole-file SHA-256 match:

| Input | Source SHA-256 | Patched SHA-256 |
|---|---|---|
| Official A7M4 6.02 AP | `1e1b9202eaa69198f20df03dbfdab2f103b206cc4ebcd2e7bd817e6a710018a2` | `6fb340604f6dc1a2abb8dbd208e3e380d3789f2756d7abde0f521fdeb49f6920` |
| Published FL2/FL3 AP | `d17e61fb4ba193d8e7d802196edff5f578d5691b3fcc4abcd1cbbb6e58bdd8ff` | `6aad5c6400170365523c1737404053f53c05b89734a89e5fda734dde5eff7e2a` |

The battery patch itself does not require FL2/FL3. The second profile preserves the existing published AP modifications. Other experimental/already-patched files are refused; an editable menu version is insufficient identification.

## Independent offline reproduction and reversal

```powershell
python -m a7m4.features battery local/appFw.so --output output/appFw-battery.so
python -m a7m4.features battery output/appFw-battery.so --undo --output output/appFw-restored.so
```

The tool validates the whole input, every preimage, bounds/overlaps, final hash and change count. Existing output paths are refused. Reversal accepts only a recognized complete patched file and restores the exact original input.

Alternatively build a full-size image from **your fresh complete nfa15 backup**:

```powershell
python -m pip install -e ".[firmware]"
python -m a7m4.features battery local/my-backup/nflasha15.bin --partition --output output/nflasha15-battery.bin
```

It maps ext file extents, replaces the same-length `lib/appFw.so` and reopens it for verification. CP, kernel, other AP files and calibration remain untouched; partition length is retained. Offline commands never operate devices.

After the required backups and wiring checks, experienced users can flash their generated complete image with external `fastboot flash nflasha15 <image>`, then make a fresh complete backup and compare nfa15 SHA-256. External fastboot bypasses this host menu's confirmation gate. Preserve recovery access on a readback mismatch. SD member images may be shorter than physical partitions and must not be substituted as whole-partition images.

With Method 3's original FL2/FL3 components, its SD build command also accepts an explicit `--battery` flag. The default build does not add this feature. This is a combined-package option, not a battery-only package; do not feed pre-patched battery components into the default component input.

## Validation limits

Historical display evidence covers 4,800 combinations/14,400 original-instruction executions; caution evidence covers 64 bounded cases, with synthetic inputs and documented external stubs rather than complete camera emulation. Historical feedback reports working percentage display without a running AP hash readback. The new caution removal has not completed dedicated physical acceptance. General use of later combined firmware does not replace battery-model, grip, hot-swap and cold-boot testing.

This release rechecks exact bytes against historical artifacts without device access. Retaining protection code is not a safety guarantee for arbitrary batteries.
