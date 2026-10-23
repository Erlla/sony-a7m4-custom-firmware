# Maintainer handoff

## 2026-10-23: independent integration review

- See `native/combined-662/REVIEW-20261023.md`. No new defect was confirmed; firmware sources/hashes remain unchanged. New checks cover nine AP layout/linkage groups, twenty shared LUT/aspect state combinations and two outer-lock contexts.
- Do not report the isolated `aspect_pool_release` reuse counterexample as a product bug. It omitted native mutex 9 around both allocation and release wrappers. With explicit outer mutex blocking, clear completes before reuse and the new ratio remains intact. Review every enclosing lock before claiming a concurrency failure.
- A per-thread replay needs separate stacks and real blocking semantics at the modeled OS boundary; unconditional lock-success stubs can manufacture impossible schedules.
- Old `.rela.dyn` has four intentional aspect descriptor redirects, and five legacy aspect entries branch to the T22 atomic selection implementation. Inspect active paths instead of treating old source names as executed code.
- Camera startup/playback timing, burst pixels, UI/display and sound acceptance remain open. Existing 5,444 checks were not represented as rerun in this review.

## 2026-10-23: combined 6.62

- This public checkout is separate from the private research Git history. Publish relevant authored code, recipes and reports only; keep generated firmware and manufacturer inputs local.
- `native/combined-662/` and `a7m4/combined662.py` reproduce exact components, not a complete DAT from stock firmware. The tool requires a source checkout with adjacent `native/`, pinned input images and compiler.
- T22 aspect text IDs AB60–AB63 collide with current sound dialogs. Combined IDs are AB4C–AB4F; only aspect-owned references change.
- AP new RX ranges do not overlap: LUT starts at 0x09000000, aspect at 0x09010000. Actual conflicts are shared metadata, relocation tails and constructor chains. Do not replace the whole AP with the older standalone T22 file.
- CP uses relocated aspect RX/BSS and an independent READY word. ARM calls to absolute Thumb symbols need STT_FUNC/Thumb typing; `.thumb_set` avoids incorrect BL state.
- Repack live UXC records instead of appending indefinitely. Offsets are u16 words, so longest-record-last matters for Hindi/Thai banks.
- CP/AP/68 banks reproduced byte-identical to the signed research package. 218 public tests pass. The combined firmware is not yet camera-tested; LUT P2 remains open.
- `layout.json` hashes authored sources with LF line endings, as required by this repository's attributes. The frozen research source ID in AP is an artifact identity, not a live hash of arbitrary future edits.
