# LUT SD read: fast scan

[自定义 LUT](../../methods/08-custom-lut/README.md) · [Exact component recipe](layout.json)

The Custom LUT SD import list scans candidate JSON filenames before opening the
list and reads the selected file at import. Use Left/Right to switch pages and
Up/Down to select a file on the current page. The import directory allows up
to 256 entries, including hidden files and subdirectories. Camera storage
has 16 custom slots.

[Technical analysis](ANALYSIS.md) · [Integration](INTEGRATION.md)

## What the import list shows

Fast scan lists candidate files by name. A malformed or oversized JSON file may
appear in the list and fail when selected for import. The camera still reads the
selected file, enforces the 128 KiB limit, and parses the JSON at confirmation.
The scan no longer stores a copy of each file's size and metadata for comparison
at confirmation.

## Apply to an extracted `appFw.so`

From a source checkout (Python 3.11+; no camera I/O):

```powershell
python native/lut-sd-read/apply_to_appfw.py `
  --input appFw.so `
  --output appFw.sd.so `
  --baseline community_1119
```

Use `--baseline author_0.12` for the pinned Toolkit/author appFw. The tool refuses overwrite, writes only the `.so`, and does not encode, sign, or access a device. Pack with the existing nflasha15 → `part_image.sum` → encode → resign flow.

The script checks the exact input size and SHA-256 for both baselines, then checks
the original instructions at each of the three patch sites. Inputs outside these two baselines require a new verified layout.
