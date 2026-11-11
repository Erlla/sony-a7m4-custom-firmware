# Camera-written FL2/FL3 RAW alternatives

[中文](raw-alternative-looks.md) · [Method 3](README.en.md) · [Validation scope](raw-alternative-looks-validation.md)

New camera ARW files carry FL2/FL3 alternative-look parameters, allowing Imaging Edge Edit to offer both looks directly from the original file. A separate desktop directory-injection step is unnecessary. The extension applies to RAW files captured afterward.

## Data being extended

The root SR2 records the look selected during capture. Tag `0x74C0` lists alternative-look directories for software re-selection. The earlier root-matrix writeout repair and this alternative list are separate components. This layer expands the original ten choices to twelve while retaining native name, coefficient, A1 matrix, curve and white-balance producers. The model remains ILCE-7M4.

The original choices are Standard, Vivid, Neutral, Portrait, FL, VV2, IN, SH, BW and Sepia, followed by the added FL2 and FL3. The root still has 169 tags and each child has 114. The component changes CP only; AP, MPR, image resources and the sensor-pixel processing path are unchanged.

## Exact component and order

[Python builder](../../a7m4/raw_alternative_looks.py) · [Native C](../../native/raw-alternative-looks/raw_list.c) · [Linker script](../../native/raw-alternative-looks/raw_list.ld) · [Complete recipe](../../native/raw-alternative-looks/layout.json)

The recipe accepts the exact integrated CP containing FL2/FL3, custom LUT/sound support, [Capture aspect inheritance](../07-custom-aspect-ratios/README.en.md) and [AWB priority](../10-awb-priority/README.en.md). It is a later Method 3 component and does not accept stock CP or the earlier standalone port output.

| Stage | Complete CP SHA-256 |
|---|---|
| After Capture aspect inheritance, before AWB | `28f3e21710ee4af035fa4c2f8661a43b5de6a23d017b5b4dabcd89b2f2a466d1` |
| This component's input, AWB applied | `c9399d46f231639d467f73316243bfae2620195502c8cc21fc2779ce810211aa` |
| Output | `5ec4dee8e126ed54ff476b349e4d76318c98d3cc2f0ac9a5583ec98155b93fc4` |

The file remains 16,236,816 bytes. Earlier recipes retain their exact boundaries; this layer is not implicitly included in `firmware build-fl23`. The [LUT component reference](../08-custom-lut/reference-layout.json) retains its pre-AWB identity and lists this extension separately.

## Six patch sites

Addresses are CP VAs; subtract `0x108000` for file offsets. The six written regions total 128 bytes, of which 113 bytes actually change.

| Address | Implementation |
|---|---|
| `A04144` | Route the original constructor call through resident `BA4960` |
| `BA4960` | A 32-byte helper writes two mappings, publishes the count, then tail-calls original `A02A60` |
| `9FF88C` | Branch to the replacement quantity implementation |
| `9FF8E0` | Accept ten before initialization and twelve after construction; retain failure for other counts |
| `9FF8A4` | Search the actual configured count; unknown values return -4 without changing the output |
| `B8EE78` | Replace old RAW gamma colour IDs 4/9 for entries 10/11 with FL2/FL3 IDs 19/20 |

The helper changes three bytes in the RAM record associated with BKID `0x300AF`: base `014F6FC1`, `+7A=10`, `+7B=11`, then `+3=12`. The remaining 253 bytes are retained. Every invocation through the constructor call applies these fields, without writing the persistent backup or importing an entire FX2 record.

Runtime construction overwrites the static TIFF count. Changing that template alone is ineffective. Extending only the count/mapping leaves the added choices using older looks' gamma curves. The first ten gamma mappings remain unchanged.

## Native length and space

Original loops still construct directories, link pointers, populate fields and build export descriptors. Each child occupies `C26` (3,110) bytes. SR2 length is `10CA + N*C26`: 35,398 becomes 41,618 bytes, an increase of 6,220. The twelve-child region ends at structure offset `A2AA`, below the next region at `AED0`; existing reserved space and pointer-array capacity are reused.

The helper uses checked resident space, adds no heap/BSS and preserves the optional P3 prefix and CRC. A separate fixed-`9000` encryption call handles `C634/7250` metadata, not the main `7200` SR2 length; this component leaves it alone.

## Offline build

Use the source checkout with its adjacent `native/` directory, the listed input CP, an existing `output` directory and the recipe's pinned ARM GCC. Input, compiler and source identities are checked by SHA-256.

```powershell
python -m a7m4.raw_alternative_looks --input local/CPAPP-B.integrated-awb.BIN --compiler local/toolchain/bin/arm-none-eabi-gcc.exe --output output/CPAPP-B.raw-looks.BIN
```

The builder compiles three sections and checks preimages, section identities and the complete output hash. It creates a CP file only. Follow [Method 3 installation](README.en.md) for composition, package checks and separate NOR synchronization. Preserve LUT touch, aspect icons and the other components through their own recipes.

## Use

After updating, capture RAW or RAW+JPEG and open the original camera ARW directly in Edit. Check that FL2/FL3 appear in Creative Look selection. The maintainer confirmed recognition; see the [validation record](raw-alternative-looks-validation.md). Recognition, JPEG export and final colour agreement have separate evidence boundaries.
