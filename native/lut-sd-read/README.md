# LUT SD read: fast-scan + edge page-flip

[自定义 LUT](../../methods/08-custom-lut/README.md) · [Exact component recipe](layout.json)

AP patches for Custom LUT **Import from SD**: speed up listing many `.json` files, then flip pages at the list edges using the existing `type=2` backend.

## Capability

| Piece | Effect | Limit kept |
|---|---|---|
| **fast-scan + import-relax** | Listing ~150 SD `.json` files stays responsive | In-camera USER slots remain 16 |
| **edge page-flip** | Top/bottom wrap enqueues `type=2` page load | No new Next/Prev widgets |
| Page size **16** | Matches author batch API | Do not raise window `0x10→0x40` (crashed on ~151 json) |

“151” means how many valid SD `.json` files can be browsed (directory entry count must still be ≤256). See [ANALYSIS.md](ANALYSIS.md). Integrator notes: [INTEGRATION.md](INTEGRATION.md).

## Layout

```
native/lut-sd-read/
  README.md
  ANALYSIS.md
  INTEGRATION.md
  layout.json
  apply_to_appfw.py
  asm/
  patches/
    fast_scan.json
    import_relax.json
    pagination_baselines.json
```

## Apply to an extracted `appFw.so`

From a source checkout (Python 3.11+; no camera I/O):

```powershell
python native/lut-sd-read/apply_to_appfw.py `
  --input appFw.so `
  --output appFw.sd.so `
  --baseline community_1119
```

Use `--baseline author_0.12` for Toolkit/author appFw sites (wrap/open/msg offsets differ). The tool refuses overwrite, writes only the `.so`, and does not encode, sign, or access a device. Pack with the existing nflasha15 → `part_image.sum` → encode → resign flow.

Pinned before/after bytes and cave VAs are in `patches/` and `layout.json`. Relocate sites before applying to an unlisted appFw baseline.
