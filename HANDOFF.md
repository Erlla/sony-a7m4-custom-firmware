# Maintainer handoff

## Publication scope

- Publish reusable implementation methods, authored source, input hashes and component verification boundaries. Do not publish specific experimental firmware versions, versioned delivery directories, package manifests or per-round test progress to GitHub. Keep those in the research repository.
- Preserve the root README structure: introduction and method index, without dated version announcements or a test-progress feed. The maintainer explicitly requested this separation.
- The custom-sound gallery uses the maintainer's corrected five-photo set: two menu locations, two settings screens and the audio picker. Match shutter/focus captions to the visible menu title, update both language guides together and remove superseded gallery assets in a normal commit.
- Functional directories and commands are `native/feature-integration/` / `a7m4.feature_integration` and `native/jpeg-exif-dimensions/` / `a7m4.jpeg_exif_dimensions`. Exact input/output hashes remain mandatory; renaming a recipe does not make its fixed addresses portable.
- Do not rewrite repository history to remove older announcements. Make a normal scoped cleanup commit; generated firmware, manufacturer inputs and camera originals remain local.

## Integration pitfalls

- See `native/feature-integration/REVIEW.md`. The isolated `aspect_pool_release` reuse counterexample omitted native mutex 9 around both allocation and release wrappers. With the outer mutex modeled, clearing finishes before reuse. Review every enclosing lock before reporting a concurrency defect.
- Per-thread replay needs separate stacks and actual blocking semantics at the modeled OS boundary; unconditional lock-success shims can create impossible schedules.
- Four old `.rela.dyn` aspect descriptor redirects are intentional; five legacy aspect entries branch to atomic selection. Inspect active paths rather than assuming every old entry executes old logic.
- Aspect text IDs AB60–AB63 collide with sound dialogs. Use AB4C–AB4F and modify only aspect-owned references.
- AP RX ranges for LUT and aspect do not overlap; shared metadata, relocation tails and constructors still need composition. Do not replace the main AP with an older standalone file.
- CP aspect code/BSS and its READY word must be independent of LUT. Preserve Thumb symbol typing for ARM calls.
- UXC offsets are u16 words: repack live records with the longest record last instead of appending indefinitely.
- Component tools require the source checkout and adjacent `native/`, pinned inputs and compiler, and LF source bytes. They do not produce a flashable package by themselves.
- Sound libmpr uses the active program-header table at 0x370000. Preserve sound extensions when adding the JPEG-specific EXIF source copy; do not use an old stock-library patch blindly.
- Offline native replay, encoded image structure and physical camera behavior are distinct evidence. Keep precise limits and avoid claims of complete color equivalence or performance from metadata alone.
