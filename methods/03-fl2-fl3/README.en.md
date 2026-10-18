# Method 3: port/install FL2 / FL3 and synchronize CP NOR

[中文](README.md) · [Risks and backups](../../README.en.md)

This guide covers FL2/FL3 independently. **Look coefficients, matrix endpoints and curves come from stock FX2 data. The current default fixes all four matrix banks to their own A1 endpoint, targeting Imaging Edge look re-selection.** Camera readback and new photographs support this selection. The major earlier color shift has been addressed; measured JPEG mean DeltaE76 remains about 1.0. This is not pixel identity or all-scene equivalence to a physical FX2. See [current color evidence](color-validation-20261017.md).

Enabling a menu or flashing only `nflasha8` is insufficient. The complete combination involves AP, CP, color data, settings copies and separate physical CP NOR.

## Lossless RAW acceptance and exact-source recipe

The lossless RAW repair passed complete eMMC/NOR CP readback and post-boot A1 persistence after a scoped nfa2 settings repair. Fresh **original** DSC02788_FL2 and DSC02789_FL3 RAW files each match all 105 root-SR2 matrix values to their own FX2 A1. FL2 writes 1614. See [RAW acceptance evidence](../../docs/fl23-raw-lossless-validation-20261017.json). Corresponding re-selection JPEGs give mean smooth-area DeltaE76 of 1.0007/0.9754, with small residual differences. See the [latest figures and metrics](color-validation-20261017.md#raw无损写出修复后的jpeg对照); the first fixed-A1 acceptance remains a separate measurement set.

The [RAW lossless recipe](../../a7m4/profiles/fl23/cp-raw-lossless-recipe.json) requires the exact fixed-A1 custom source CP `acecf071…505b2`, producing `9e312f58…611b` with212 actual changed bytes. It does **not** accept the public official 6.02 baseline output and is not implicitly merged by `firmware build-fl23`. `patch_program(source, recipe)` performs whole-source, local preimage and whole-target validation; the Python example in the Chinese guide writes a new local CP file only.

The guarded path applies only to FL23 root RAW with matching selector, all four WB gains>1024, identity auxiliary matrix and neutral calibration/gain-cap conditions. It copies the internal matrix, preserves additional-transform/mode9/saturation handling, and falls back otherwise. It does not change JPEG processing or hardcode1615 into1614. Installation still requires an appropriate same-camera signed SD package, physical NOR synchronization, and fresh post-update color/settings restoration. Full firmware and original photographs are not distributed.

## Exact baseline and published artifacts

Target: **official A7M4 6.02**. Color donor: **FX2 1.01**. Identify actual programs by hashes, not an editable menu version.

| File | SHA-256 |
|---|---|
| Official A7M4 6.02 DAT | `ad6df47a0a93a46336b9920a0d8891d0c766f8c96fa68ebda8685f6c21621188` |
| Stock `appFw.so` | `1e1b9202eaa69198f20df03dbfdab2f103b206cc4ebcd2e7bd817e6a710018a2` |
| Target `appFw.so` | `d17e61fb4ba193d8e7d802196edff5f578d5691b3fcc4abcd1cbbb6e58bdd8ff` |
| Stock `CPAPP-B.BIN` | `7b9b137d696e5972d20db7f9119076172ed8e0730805d7f0b4c31b87689e2c2b` |
| Target CP v7, 16,236,816 bytes | `4551c73386c27a0a9b247fd3e05c3bd5e3425bdb9fe9f8374c201c96533b3479` |
| FX2 1.01 CP | `eba723db657117a36d9593dacf640840aca893c0d6ee5d728de9d1996b8c5e29` |
| FX2 CC1 | `c87f4dad18225b0b6a5a273bd27211fd93ad0ca0ab8ac2f1b65f680daec4d996` |
| FX2 block13 | `d783cf223304e67d6d671642c8b1102a0c663bc114a64c7f76a1d160d8a3feee` |

Source: [fl23.py](../../a7m4/fl23.py), [firmware.py](../../a7m4/firmware.py). Exact recipes: [AP](../../a7m4/profiles/fl23/ap-recipe.json), [CP v7](../../a7m4/profiles/fl23/cp-v7-recipe.json). Recipes contain offsets, preimage hashes and patch bytes, not complete Sony programs or donor curves/coefficients. Twenty donor operations read/convert user-supplied data; 416 remaining difference runs contain 1,595 patch bytes. Entire target hashes are checked after reconstruction.

## Functional mapping and storage

| Look | AP main enum / slot / look | CP color | Photo selector / bank / gamma | Movie selector / bank / gamma | CP metadata enum |
|---|---|---:|---|---|---:|
| FL2 | 17 / 16 / 10 | 19 | 54 / 22 / 47 | 56 / 23 / 49 | 22 |
| FL3 | 18 / 17 / 11 | 20 | 55 / 24 / 48 | 57 / 25 / 50 | 23 |

These are distinct numbering spaces, not interchangeable values.

| Location | Changes |
|---|---|
| `nflasha15:/lib/appFw.so` | Existing menu/resource availability, look support and look→CP color routing |
| `nflasha8:/CPAPP-B.BIN` | Selectors, gamma, matrix/coefficient gates, consumers, primary/secondary names, metadata enums and loading attributes |
| Your `nflasha6` | New CC1/block13 mapping, converted coefficients and matrices |
| Your `nflasha2:/BACKUP.BIN` and `BACKUP.BAK` | Two color copies, six slot records and affected BK4 checksums |
| Separate physical CP NOR | Complete CP synchronization through matching official update scripts; not an eMMC partition |
| `nflasha1` | Installed updater must trust the signing key; see separate Method 1 |
| `nflasha5` | Current combination changes `WBI2` to `WBI3` to avoid restoring a stale warm-boot snapshot |

### AP

On this exact baseline ELF VA equals file offset at the patched sites. `0x35E6258` changes 40 bytes to route look10/11 to color19/20; `0x3FDE5B4` and `0x3FDE634` each replace 40 bytes with twenty enabled uint16 profile flags; `0x4AB894A` and `0x4AB9B21` each enable two support entries. Actual differences total 66 bytes. Old look0–9 mappings remain; invalid look12 still fails. Existing packaged FL2/FL3 text/icons are reused.

### Complete CP v7

The normal CP mapping is `address = file offset + 0x108000`; bootstrap segment metadata must not be confused with executable addresses. Actual differences total 5,845 bytes. The recipe includes the v7 secondary-name patch and retained early data copies; the old v5 inventory alone is insufficient.

| Block | CP file offset | Contents |
|---|---:|---|
| A | `0xA9B240` | Extended gamma pointer table/reserved area, `0x5E0` bytes |
| B | `0xA9B820` | Color→photo/movie gamma mapping, `0xB0` bytes |
| C | `0xA9B8D0` | Six curves, 6 × 576 bytes |
| D | `0xA9C650` | Four converted coefficient records, 4 × 64 bytes |
| Consumer trampolines | `0xA9C750` onward | Eight look-consumer extensions |
| Primary names/enums | `0xA9CA00` onward | FL2/FL3 and metadata22/23 for color19/20 |
| Secondary names | `0xA9CAC0` onward | Extension reached from CP `0x23583A` |

The current code-cave design changes a rodata mapping parameter from `0xD` to `0xF`, affecting execution permissions for the whole region. This is a specific engineering tradeoff, not an inherent requirement for every port. Segment bounds, special paths, Thumb return bits and existing look behavior must remain consistent.

Curve donor CP addresses are `0xEBB2BC`, `0xEBB500`, `0xEBBBCC`, `0xEBB744`, `0xEBB988`, `0xEBBE10`. Copy the first 572 bytes of each 580-byte donor record, using target stride576 with four trailing zero bytes. Photo slots0–5 share one record; slot6 uses another; video uses its slot6 record.

### Per-camera colors and settings

On the reviewed baseline, nfa6 CC1 is at `0x19CC00`, size `0x2000`; block13 at `0x1A0C00`, size `0x7000`. Inside BIN/BAK locate BKID `0x02A40001` and `0x02A4000D` through parsing, never another camera's fixed file offsets.

- Write `[22,24,23,25]` to CC1 `0x1236..0x1239` and block13 `0x1CC..0x1CF`.
- CC1 banks22–25 reside at `0x1250 + bank*64`; each contains 24 int16 coefficients/48 valid bytes. FX2 flag `CC1+0xEFE=1` represents absolute B/A1/A2; M4 flag0 represents base/deltas. Convert to **B / (A1−B) / (A2−B)** while retaining M4's flag and unrelated calibration.
- Copy 3,072 matrix bytes from the specified donor's block13 `0x43E0..0x4FDF`.
- In both BIN and BAK set six one-byte, attribute`0x60` records: `02CF12C8=10`, `02CF12CA=11`, `02CF13B0=10`, `02CF13D0=11`, `02CF143E=10`, `02CF1440=11`, covering current/still/movie slots16/17.
- Validate every BK4 checksum and recompute affected sums: extent=`u32(+0x18)+u32(+0x1C)`; checksum=sum of bytes `[0,0x20)` and `[0x24,extent)`, excluding the four-byte checksum. Preserve other records, file lengths, FAT allocation and partition sizes.

### Fixed A1 matrix selection

The default `--matrix-mode fixed-a1` takes each bank’s own 192-byte A1 from `base+0xC0..base+0x180`, where `base=0x1E0+bank*0x300`, and repeats it across B/A1/A2 for banks22/23/24/25. Both photo and movie banks are covered. Imported bank tails, original looks and body WB/calibration remain outside this additional matrix change. `--matrix-mode dynamic` retains donor endpoints for controlled research. Apply/check all three copies: active nfa6 plus BACKUP.BIN and BACKUP.BAK. Re-read after SD migration before rebuilding a local delta.

## Offline reproduction

First back up your own eMMC **and separate NOR**, and verify the actual camera AP/CP against the stock hashes above. The following commands build files only:

```powershell
python -m pip install -e ".[firmware]"
python -m a7m4.firmware decode local/M4-Ver.6.02.DAT --output local/m4-6.02-plain.bin
python -m a7m4.firmware extract-target local/m4-6.02-plain.bin --output local/stock
```

Unpack FX2 1.01 using a matching tool such as [fwtool a7iv](https://github.com/DavidBuchanan314/fwtool.py/tree/a7iv), whose upstream syntax is `fwtool unpack -f <package> -o <directory>`. Obtain its raw CP and a BK4 defaults file under `0110_backup/SYSIPSX-DSLR/`. Confirm content hashes rather than guessing from names. Extract color records:

```powershell
python -m a7m4.fl23 extract-donor --backup local/fx2/profile.bin --output local/fx2-color
```

`profile.bin` is an example path for the actual extracted BK4 file. The command refuses records that do not match the specified FX2 1.01 donor. Build using **fresh backups from your camera**:

```powershell
python -m a7m4.fl23 build --ap local/stock/appFw.so --cp local/stock/CPAPP-B.BIN --fx2-cp local/fx2/CPAPP-B.BIN --fx2-cc1 local/fx2-color/cc1.bin --fx2-block13 local/fx2-color/block13.bin --nflasha2 local/my-backup/nflasha2.bin --nflasha6 local/my-backup/nflasha6.bin --matrix-mode fixed-a1 --output output/fl23-components
```

Outputs are AP, CP, your modified nfa2/nfa6 and hash manifests. Optionally supply `--nflasha8 <your-stock-partition>` to build that FAT image too. Inputs are hash-checked and existing output paths are refused. The builder does not downgrade your camera automatically.

Build a complete SD package with the same key trusted by your installed updater. This example deliberately selects the public research identity; you can supply your own matching private pair instead:

Set the PowerShell variable `$ReleaseVersion` to the planned `X.YY` release assigned during unified packaging. The builder requires it explicitly and does not assign an internal test number.

```powershell
python -m a7m4.firmware build-fl23 --official local/M4-Ver.6.02.DAT --components output/fl23-components --fx2-cc1 local/fx2-color/cc1.bin --fx2-block13 local/fx2-color/block13.bin --public-key keys/published/A7M4_updater_public.pem --private-key keys/published/A7M4_updater_private.pem --version "$ReleaseVersion" --output output/fl23-sd
```

The builder emits `BODYDATA.DAT` and `verification.json`. It updates AP/CP, the warm-boot marker, updater trust, partition checksum manifests and header version/CRC; preserves TAR layout and other members; recalculates/re-encrypts all 739,727 blocks; signs and updates DEND; then decodes the entire package for byte-for-byte comparison. Never install `work/UNSIGNED_DO_NOT_INSTALL.DAT`. SquashFS build timestamps can change the final package hash between builds; AP/CP hashes remain fixed. Historical package hashes cannot replace validation of a newly built package.

SD member images can be shorter than physical partitions; do not treat extracted DAT members as complete fastboot partition images. Run the [independent audit](../../docs/validation.md) to recheck all blocks, signatures and six image CRCs.

**SD builds now repair ten FL2/FL3 colour fields in all32 generic BK4 templates and update backup.sum.** This addresses colour data lost during SD settings migration for already-enabled looks. No personalized nfa2/nfa6, LOOK defaults or reset data are embedded/changed; factory-reset activation and physical NOR synchronization are not implied. See [repair and validation boundaries](sd-colour-preservation.md).

## Physical installation sequence

1. Check the baseline, recoverable personal eMMC/boot0/boot1 backups, independent physical NOR backup, power, wiring and all source/output hashes. Connect only one camera.
2. Establish installed updater trust for the final package's signing key using separate Method1. A new key inside a package cannot bootstrap an original updater that does not yet trust that key.
3. Write only the newly generated personal nfa2/nfa6 images to their corresponding partitions and verify complete readbacks. Experienced upstream-payload users can use `fastboot flash nflasha2 <personal-image>` and `fastboot flash nflasha6 <personal-image>` in an already backed-up fastboot session. **These are direct external fastboot writes, outside the host menu's backup/confirmation gate.** Complete and check backups yourself first; never flash another camera's complete personalization.
4. Make a new full backup and compare nfa2/nfa6 SHA-256 hashes with the generated outputs. On mismatch keep fastboot available and recover deliberately; do not continue into SD installation with unresolved state.
5. Boot normally, place the final validated `BODYDATA.DAT` at the SD card root and follow the official SD update procedure matching your baseline, including battery/model/version conditions. If a reported-version adjustment is necessary, consult separate Method2 and recheck the actual binary base.
6. The SD updater installs AP/CP and invokes the existing `nor_loader_writer.sh` / `nor_update` chain to synchronize physical CP NOR. Conditions depend on LSI/boot type; related loader regions may also be updated. **Fastboot-writing `nflasha8` alone does not run this chain.**
7. Read back eMMC and physical NOR, checking target CP, three color copies and all six slots in BIN/BAK. Updater configuration migration may alter settings; regenerate affected fields from fresh post-update readbacks if necessary instead of blindly restoring an old whole settings partition.

The repository's eMMC backup host does not back up physical NOR. Use an independently reviewed readout method and verify the EXBL layout. Without that capability, an eMMC “complete backup” must not be treated as NOR coverage.

## NOR comparison and acceptance

The historical camera's EXBL item5 located CP at NOR `0x200000`, length16,236,816. This is an observed location, not a universal offset. Its indirect SPI readout required swapping each adjacent byte pair before comparing with CP. After verifying your reader's representation and EXBL location:

```powershell
python -m a7m4.fl23 verify-nor --nor local/post-update-nor.bin --cp output/fl23-components/CPAPP-B.BIN --offset 0x200000 --swap16
```

Omit `--swap16` if the dump is already normalized. This command compares local files only.

Take new FL2 and FL3 ARW/JPEG photographs and verify shooting menus, colors, playback icons, movies, power-cycle persistence and old looks. Expected new-image MakerNote B020 is FL2/FL3; B029 is22/23. Old photographs do not gain new metadata. Test factory reset, special modes and migration separately.

Fixed-A1 configuration passed full write readback and post-boot persistence checks. Fresh photos record FL2/22 and FL3/23. After the lossless RAW repair, both original RAWs match all 105 A1 values; FL2 writes 1614. The separate recipe accepts only its documented exact source hash and is not implicitly merged into the official 6.02 baseline build. Existing camera acceptance does not validate a future unified package. See [current evidence](color-validation-20261017.md).

Correct menu/playback names and matching donor records do not establish official color equivalence: **the current fixed-A1 samples closely match Imaging Edge re-selection, with measured residuals**. Optional battery and lens changes are documented separately in [Method 4](../04-third-party-battery/README.en.md) and [Method 5 (untested on hardware)](../05-third-party-lens-af/README.en.md); neither is included in default FL2/FL3 builds.

**Use an original Sony battery for every SD update or recovery update, even when the third-party battery patch is installed.** [Fixed-condition three-recipe photo report](../../docs/fl23-colour-comparison-20261018/README.md).
