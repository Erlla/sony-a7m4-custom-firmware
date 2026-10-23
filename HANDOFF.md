# Maintainer handoff

## 2026-10-23: combined 6.62

- This public checkout is separate from the private research Git history. Publish relevant authored code, recipes and reports only; keep generated firmware and manufacturer inputs local.
- `native/combined-662/` and `a7m4/combined662.py` reproduce exact components, not a complete DAT from stock firmware. The tool requires a source checkout with adjacent `native/`, pinned input images and compiler.
- T22 aspect text IDs AB60–AB63 collide with current sound dialogs. Combined IDs are AB4C–AB4F; only aspect-owned references change.
- AP new RX ranges do not overlap: LUT starts at 0x09000000, aspect at 0x09010000. Actual conflicts are shared metadata, relocation tails and constructor chains. Do not replace the whole AP with the older standalone T22 file.
- CP uses relocated aspect RX/BSS and an independent READY word. ARM calls to absolute Thumb symbols need STT_FUNC/Thumb typing; `.thumb_set` avoids incorrect BL state.
- Repack live UXC records instead of appending indefinitely. Offsets are u16 words, so longest-record-last matters for Hindi/Thai banks.
- CP/AP/68 banks reproduced byte-identical to the signed research package. 218 public tests pass. The combined firmware is not yet camera-tested; LUT P2 remains open.
- `layout.json` hashes authored sources with LF line endings, as required by this repository's attributes. The frozen research source ID in AP is an artifact identity, not a live hash of arbitrary future edits.
