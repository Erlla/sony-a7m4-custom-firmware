# Method 5: third-party lens capability filtering / focus-speed restriction patch

[中文](README.md) · [Flashing risks and backups](../../README.en.md)

**UNTESTED: focus-speed restriction removal has not undergone physical speed, AF-tracking or burst-performance testing.** No particular Sigma/Tamron lens improvement, fixed FPS or first-party parity is promised. Byte checks and bounded instruction replay are not camera tests.

## Preserve capabilities the lens actually reports

In automatic configuration, CP classifier `0x9975D6` marks some IDs whose top two bits are 3 and low 12 bits are not `0xFFF` as a compatibility category. Subsequent info7/info8/info3D filters and publication gates reduce already-reported parameters. The original info3D filter clears 22 bytes starting at packet`+0x2A`, including dynamic `MaxFcSpeed` profile flags, potentially selecting a static-table/legacy drive path instead.

Only five specified consumers see zero when the original compatibility flag is 1 and configuration is automatic 0. Reported capability/speed data is retained. Explicit compatibility, unknown configurations and unknown flags preserve their original values. The global classifier and seven other compatibility consumers remain. No unsupported AF capability, fixed motor speed, increased calibration value or changed timing/frame-interval floor is introduced.

The research cross-checked categories against [ExifTool's Sony LensType2 table](https://exiftool.org/TagNames/Sony.html). That is not a runtime ID/telemetry sample from the user's lens or proof that every matching lens was tested.

## Exact delta

Target: `nflasha8:/CPAPP-B.BIN`. Normal mapping: `VA = file offset + 0x108000`.

| CP VA | File offset | Purpose |
|---|---|---|
| `0x3B3CB4` | `0x2ABCB4` | info7 raw lens descriptor call |
| `0x3B3006` | `0x2AB006` | info8 drive-parameter call |
| `0x3B321E` | `0x2AB21E` | info3D extended AF/profile call |
| `0x990ADC` | `0x888ADC` | Publication of reported bits 12/15/21 |
| `0x990BAC` | `0x888BAC` | Publication of reported bits 28/29 and related fields |
| `0xBA4E00` | `0xA9CE00` | 34-byte scoped getter helper |

Five Thumb BL instructions redirect to the helper. It preserves R1/R2 and SP/LR, returning zero only under the automatic-category condition. Existing post-call comparisons/branches still execute. Total: **six regions, 52 changed bytes**.

See [lens-af.json](../../a7m4/profiles/lens-af.json) for preimages, output bytes and whole-file hashes, and [features.py](../../a7m4/features.py) for the offline implementation. An earlier global-classifier two-byte proposal removed existing AF commands and was rejected; it is not included.

## Strictly bound inputs

CP size must be 16,236,816 bytes, with the existing executable rodata mapping instruction `0F 30 A0 E3` at file`0x4EC` and a zeroed helper preimage.

| Input | Source SHA-256 | Patched SHA-256 |
|---|---|---|
| Published FL2/FL3 v7 CP derived from 6.02 | `4551c73386c27a0a9b247fd3e05c3bd5e3425bdb9fe9f8374c201c96533b3479` | `fdf131baa7c951ecf07e14ab47137fd00bbff71301995faf55f2e136b2e0a160` |
| Historical experimental 6.13 CP | `290e1ccec739ddf9604dc928663c934cb2e04c5976fef32ca35ebe582042380d` | `1c34764fe413d4c0d720d629e323996498305fc29e5c53d2c52d0cca0c0d1504` |

The first is a **newly bound experimental profile** for the public baseline: six preimages, existing execute mapping and four related code ranges were compared with 6.13. Historical full 6.13 review does not automatically validate the complete new baseline. The second reproduces the original 6.14/6.15 feature delta. Neither has completed physical focus-speed acceptance.

Stock 6.02 CP is refused because its executable layout differs. There is no skip-hash, arbitrary-address or disable-mapping-check option. The existing FL2/FL3 input is a supported file layout; lens filtering does not conceptually depend on filter colors.

## Offline reproduction and reversal

```powershell
python -m a7m4.features lens-af local/CPAPP-B.BIN --output output/CPAPP-B-lens-af.BIN
python -m a7m4.features lens-af output/CPAPP-B-lens-af.BIN --undo --output output/CPAPP-B-restored.BIN
```

For a matching personal complete nfa8 FAT image:

```powershell
python -m a7m4.features lens-af local/my-backup/nflasha8.bin --partition --output output/nflasha8-lens-af.bin
```

The tool checks complete identity, mapping, all preimages, bounds/nonoverlap, output hash and 52 changed bytes while retaining FAT allocation, unrelated contents and partition size. It never operates devices and records the untested status.

With Method 3's original components, explicitly add `--lens-af` to its SD build command. The builder checks original FL2/FL3 components first, applies this independent recipe, and records the untested state in `verification.json`. Default builds do not include it. Do not pass an already lens-patched CP into the default component input.

Installation requires eMMC **and separate CP NOR** backups and matching installed signing trust. Fastboot-writing nfa8 alone does not synchronize NOR. Use a matching SD update chain and read back both CP copies/settings. See [Method 3 installation](../03-fl2-fl3/README.en.md#physical-installation-sequence). Never install a historical whole CP onto an unknown base. Rollback also requires consistent eMMC/NOR copies.

## Evidence and mandatory status

Historical 6.13 evidence includes 1,216 source/candidate cases, 52 request-to-speed-consumer cases, 16 unknown-flag cases and 98 independent cases / 13 checks. Inputs are synthetic and documented SDK/hardware boundaries use stubs. Profile values 7000/9000 demonstrate parameter preservation, not measured lens speed.

Historical 6.15 general-use feedback reporting no problems does not validate AF acceleration. This release does not sample actual lens IDs, capability snapshots, calibration or tracking performance, and does not access/flash a camera. **Publication status remains UNTESTED ON HARDWARE; performance effects are unknown.**
