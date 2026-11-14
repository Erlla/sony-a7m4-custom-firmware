# Six custom ratios and automatic review

[中文](README.md) · [Method 7](../../methods/07-custom-aspect-ratios/README.en.md) · [Exact recipe](layout.json)

Adds 21:9 and 2.35:1 to the integrated aspect-ratio implementation and corrects stretched automatic review without a histogram. The existing 17:6, 65:24, 5:4, 7:6 and four factory ratios are retained.

The maintainer reported both added ratios working, then confirmed the automatic-review stretch was fixed. The reported context is RAW+JPEG without a histogram. A complete format, physical-output and orientation matrix was not supplied. Keep the [acceptance record](acceptance.json) separate from [offline validation](validation.json).

## Inputs and build

The exact inputs are the title-glyph/runtime-cleanup AP, the subsequent sound-buffer-recovery CP, the existing playback-compatible libmpr and matching 68 text/two image banks. Full identities are in layout.json. The CP input includes a sound-recovery layer without a standalone builder in the older base recipe; the cleanup CP cannot be substituted. This recipe does not rebuild every preceding firmware layer.

Extract compatible inputs from your own baseline; they are not distributed here. Use the project Python dependencies, Zig 0.14.1 and the exact ARM GCC toolchain pinned in the manifest. Resource generation also needs Pillow and the pinned Arial Bold font.

Run from the repository root, with inputs under input, compilers under tools/local and an existing output directory:

```powershell
python -m a7m4.aspect_autoreview --component ap --input input/appFw.so --compiler tools/local/zig/zig.exe --output output/appFw.so
python -m a7m4.aspect_autoreview --component cp --input input/cp.bin --compiler tools/local/gcc/bin/arm-none-eabi-gcc.exe --output output/cp.bin
python -m a7m4.aspect_autoreview --component mpr --input input/libmpr.so --compiler tools/local/zig/zig.exe --output output/libmpr.so
python -m a7m4.aspect_ratio_resources --input-directory input/resources --output-directory output/resources --font C:/Windows/Fonts/arialbd.ttf
```

Resource directories use original bank filenames; layout.json lists their camera paths. The output resource directory must not already exist. These commands operate on local files only. Firmware assembly still requires the existing filesystem, partition-CRC, block-checksum and signing workflow; these commands do not generate a DAT or operate the camera.

## Components

| Component | Change |
| --- | --- |
| AP state/menu | Logical IDs4–9 and ten menu rows; IDs4–7 retain their meaning. Token ID uses bits0–3, completion bit4, epoch bits5+; settings schema2 is retained |
| Preview | Selection, Fn and shooting masks cover all six ratios; BSS layout is unchanged |
| CP capture | Frozen per-photo ratio follows task copies, JPEG/HEIF output and1005/1012 automatic-review YC construction; RAW retains its full area |
| AP review | Fit this photo's YC PIN dimensions into a centered explicit destination, preventing a later3:2 auto layout |
| Playback | Both AP and libmpr dimension tables expand to 18 pairs |
| Resources | AB66/AB67 in 68 text banks and six Fn/menu images in both image banks; prior live payloads retained |

21:9 uses 7/3 and 2.35:1 uses 47/20. Full-frame L JPEG dimensions are7008×3000 and 7008×2984 after native alignment. RAW retains its original area.

## Why an explicit rectangle alone failed

CP 627A8C dispatches on byte 1 of the 014B command body. Auto mode 1 calls 628004 to rebuild the destination from the native aspect, overriding the submitted rectangle. The final adapter sets the temporary custom-image geometry mode to 0, preserving the fitted region and margins.

To reproduce the accepted machine code exactly, fit.c retains the common calculation and the builder replaces one LDRB at 901F0F0 with MOV W10,WZR using layout.json. explicit_mode.S records that instruction; equivalent C semantics are geometry[2]=0. NZCV, native-aspect bypasses and existing addresses are preserved.

Only the three calls in normal automatic review 316B974 are wrapped. Histogram review 316BD70 and the zero-size sentinel layout are outside this validation. The maintainer's RAW+JPEG acceptance does not establish every format, output or orientation.

## Integration

Apply after [title glyphs/runtime cleanup](../../methods/08-custom-lut/RUNTIME-CLEANUP.md) and the exact CP sound-recovery baseline. The earlier [playback](../aspect-playback/README.md), [capture-copy](../aspect-capture-clone/README.md) and [menu-icon](../menu-ui-fixes/README.md) recipes keep their original hash restrictions and must not be reapplied to these outputs.

Existing LUT capture wrappers, RAW FL2/FL3 alternatives, sound-recovery page, AWB and resident gates are retained. AP keeps LUT touch/title glyphs, persistent caching and sound lifecycle code; AVCAM is unchanged. Update AP, CP, libmpr and all 70 resource banks together. Older token consumers or dimension tables cannot be mixed with this layer.
