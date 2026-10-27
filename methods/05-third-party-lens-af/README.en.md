# Method 5: lens AF mechanisms and compatibility capability-filter patch

[中文](README.md) · [Flashing risks and backups](../../README.en.md)

**UNTESTED: focus-speed restriction removal has not undergone physical speed, AF-tracking or burst-performance testing.** No particular Sigma/Tamron lens improvement, fixed FPS or first-party parity is promised. Byte checks and bounded instruction replay are not camera tests.

## Two separate AF decision mechanisms

A numeric lens-ID compatibility filter and a separate category/capability/profile-based AF range gate have been identified. **The current patch selectively addresses the former. It does not remove the range gate or establish removal of every AF restriction.**

The addresses below bind to one stock CP analysis input: 16,236,816 bytes, SHA-256 `7b9b137d696e5972d20db7f9119076172ed8e0730805d7f0b4c31b87689e2c2b`, with normal mapping `VA = file offset + 0x108000`. It is an analysis/replay input, **not an accepted patch input listed later**. These addresses are not portable across arbitrary firmware versions.

### Mechanism 1: lens-ID-triggered compatibility capability filtering

CP callback `0x3B3C88` obtains an info7 response through `0x98ED0E` and combines bytes `+0x0A/+0x0B` into a little-endian 16-bit numeric ID. The processed response is copied to lens-record offsets `+0x21` and `+0x116`, placing the ID at `+0x2B/+0x2C` in the first copy. This is a numeric ID, not a 16-byte lens-name string.

Classifier `0x9975D6` first clears global compatibility byte `0x14F3774`, then reads configuration `0x104C730+0x17`: value 1 forces compatibility, value 0 evaluates the expression below, and other nonzero values leave the newly initialized zero flag.

```c
compatibility = ((lens_id >> 14) == 3)
             && ((lens_id & 0x0FFF) != 0x0FFF);
```

Getter `0x997618` returns the flag. Automatic-mode fixtures `0xC530/0xD123` set it; `0x8050/0xFFFF` do not. The first-party-category control retains its original data on this path, which does not establish absence of every other constraint for all first-party lenses and modes.

| Data and stage | Original function | Established behavior |
|---|---|---|
| info7 basic information | `0x997624` | Masks, clears or replaces selected fields; retains numeric ID |
| info8 drive parameters | `0x997670` | Masks, clears or substitutes selected reported parameters |
| info3D extended AF information | `0x997940` | ANDs the capability word at packet `+0x21/+0x22` with `0x0C01`, clears related fields, and clears 22 bytes starting at packet `+0x2A` |
| info3D cache | `0x3B321E..0x3B3248` | Copies the filtered response to lens record `+0x139` using size metadata; replay input is 64 bytes |

Packet `+0x21` therefore maps to extended capabilities at lens record `+0x15A`; packet `+0x32` maps to dynamic speed-profile support bits `0x30` at record `+0x16B`. Those flags fall inside the cleared region, so a reported speed profile can become unavailable before the downstream algorithm uses it.

Protocol support has a separate gate. Apart from mandatory command 1, `0x3AD130` intersects the lens-reported command bitmap with a compatibility mask or the body's normal protocol mask. Startup window `0x3B31EC` reaches request path `0x3B3762` when cached command3D support is 1, even without optional command5A. Missing 3D support retains the extended-record clear fallback. The global compatibility flag is consequently broader than an AF speed switch.

After other state guards pass, speed consumer `0x394978 → 0x9579D0` checks record `+0x16B & 0x30`. A valid dynamic profile supplies calibrated values for the drive frequency; otherwise the code searches the 53-entry static ID table at `0x103F582`. If no speed parameter is obtained, the interface can return zero and later scheduling can select a legacy drive path under the applicable conditions. Zero does not mean total AF failure. Original move-time calculation `0x95A5B0` and the frame-interval floor continue to constrain driving and are not modified by this patch.

### Mechanism 2: category, capability and profile-based AF range gating

Entry `0x47B9FC` interprets a lens descriptor and dispatches categories 0..4 from input word `+0x00`. Category 1 and values above 4 enter fallback `0xA3FFBC`; other categories have different capability/version conditions. **Category 1's upstream producer and product meaning are not fully bound; it must not be labeled third-party.**

The established fallback branch behaves as follows:

1. Input `+0x14` is copied to output `+0x11`. If that output or any of the eight prohibition fields at input `+0x17..+0x1E` is nonzero, output `+0x10/+0x12/+0x13` is cleared.
2. Once those conditions pass, `0x47E12C` queries an internal profile by category and numeric ID.
3. A profile hit still checks input `+0x13`: zero clears the output flags above; passing that check selects profile initialization. With no profile, an availability indication at input `+0x15` selects the corresponding alternative initialization path.
4. With no profile and no `+0x15` indication, `0xA40048..0xA40050` normally sets `+0x10=1,+0x12=1,+0x13=1`, producing a center-range state. ID `0x8010` retains an additional input `+0x13` exception check.

The normal publication chain at `0xA3FD3C` passes result fields `+0x10/+0x12` to registered setter `0x941DD6`, which stores them at `0x14F1193/0x14F1194`. Consumer `0x91D12A` returns range classification 2 or 1 according to whether the second byte is zero, provided the first byte is 1; otherwise it returns 0. One downstream consumer can enter a `CenterOnlyLens` branch for classification 1 and reject the corresponding Scanless path. This state is not a master switch for all AF functionality.

A separate `this lens is not permitted` path is also insufficient evidence of a brand allowlist. `0x132E32` first checks special IDs `0x8051/0x8019`, then checks whether the low nibble of lens record `+0x4E` is 4. The generic protocol condition can still permit the operation. Deleting the warning does not replace protocol and capability checks.

**No AF range-gate removal recipe is published here.** Missing-profile fallback may involve calibration requirements. Existing evidence neither attributes every fallback to a third-party policy nor establishes that the user's physical lens traversed this branch.

### How name lookup relates to these mechanisms

Internal profiles can supply `VX…` parameter-file keys. For example, original `0x47E12C(category=1, ID=0x8011)` returns the stock CP's internal string `VX9101` at `0xD46734`. Subsequent name lookup `0x47B444` compares at most 16 bytes, ending early at NUL, to select parameter data; a miss returns failure. In the traced chain the name comes from an internal profile. That does not establish a direct 16-byte hardware-name read for brand admission, nor make a name-lookup miss equivalent to a missing-profile fallback in another AF branch.

### Current patch coverage

Only five specified consumers see zero when the original compatibility flag is 1 and configuration is automatic 0, retaining reported capability/speed data. Explicit compatibility, unknown configurations and unknown flags retain the original getter value. The global classifier and seven other compatibility consumers remain unchanged. No unsupported AF capability, fixed motor speed, increased calibration value or changed timing/frame-interval floor is introduced. The AF range gate above is also unchanged.

Physical benefit depends on whether the lens triggers classification, reports valid capabilities/speed profiles and encounters other mode constraints. These chains do not establish AE auto-exposure restrictions or physical acceleration of a particular lens.

The research cross-checked categories against [ExifTool's Sony LensType2 table](https://exiftool.org/TagNames/Sony.html). That is not a runtime ID/telemetry sample from the user's lens or proof that every matching lens was tested.

## Reproduce the stock flows offline

The [replay script](../../tools/replay_lens_af_flow.py) and [raw JSON results](native-flow-results.json) publish 16 bounded original-instruction cases: five info7 read/classification/filter cases, six 3D support/request/filter/copy/speed cases, four range fallback/consumer cases, and one numeric-ID-to-internal-name query. Supply your own stock CP matching the analysis hash above.

Research replay additionally requires Unicorn 2.1.4, which is not a required dependency of the fastboot host:

```powershell
python -m pip install unicorn==2.1.4
python tools/replay_lens_af_flow.py --cp local/CPAPP-B-stock.BIN --report local/lens-af-flow.json
```

The script refuses incorrect input and overwriting an existing report, and runs only in the emulator. Protocol records, support caches, size metadata, operating mode, frequency and calibration are explicit synthetic inputs. The 3D cases execute original metadata reading, memcpy/memclr and speed consumers without SDK stubs. Only the info7 response-reader boundary and range-setter logging use stubs. Passing the two range-result fields to the setter is an explicit bridge, not replay of complete callback registration/dispatch; category 1 is also a fixture. The name case verifies only the internal key source, not `lensfile.bin` transfer.

With the same synthetic extended capabilities `0x30209000`, speed flags `0x30` and calibration, stock automatic-category `0xC530/0xD123` records lose those fields and return `[0,0]` from the speed interface. Controls `0x8050/0xFFFF` retain the fields and select `[7000,9000]`. These values originate in the fixture and are not measured speeds. Stock-flow replay does not replace validation of the exact patch or its individual accepted baselines below.

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
| Published FL2/FL3 CP derived from 6.02 | `4551c73386c27a0a9b247fd3e05c3bd5e3425bdb9fe9f8374c201c96533b3479` | `fdf131baa7c951ecf07e14ab47137fd00bbff71301995faf55f2e136b2e0a160` |
| Historical integrated CP | `290e1ccec739ddf9604dc928663c934cb2e04c5976fef32ca35ebe582042380d` | `1c34764fe413d4c0d720d629e323996498305fc29e5c53d2c52d0cca0c0d1504` |

The first is a **newly bound experimental profile** for the public baseline: six preimages, existing execute mapping and four related code ranges were compared with the historical integrated CP. Historical full integrated-CP review does not automatically validate the complete new baseline. The second reproduces the original AF capability delta. Neither has completed physical focus-speed acceptance.

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

Historical integrated-CP evidence includes 1,216 source/candidate cases, 52 request-to-speed-consumer cases, 16 unknown-flag cases and 98 independent cases / 13 checks. Inputs are synthetic and documented SDK/hardware boundaries use stubs. Profile values 7000/9000 demonstrate parameter preservation, not measured lens speed.

Historical general-use feedback reporting no problems does not validate AF acceleration. This release does not sample actual lens IDs, capability snapshots, calibration or tracking performance, and does not access/flash a camera. **Publication status remains UNTESTED ON HARDWARE; performance effects are unknown.**

## Address coordination with custom LUTs

The integrated layout moves the unchanged 34-byte helper to `0xBA5718`, with all five callers targeting it. The standalone location `0xBA4E00` is now occupied by LUT resident code. Do not replay the old recipe over this CP. This is structural preservation, not new AF-speed acceptance. See [integration](../08-custom-lut/INTEGRATION.md).
