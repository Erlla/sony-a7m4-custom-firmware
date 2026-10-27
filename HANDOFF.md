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

## Custom LUT publication

- The SD JSON / 16-slot LUT method lives in methods/08-custom-lut. Publish functional descriptions and component identities, never internal firmware labels or per-round package manifests. Six screen photographs are maintainer-authorized.
- Preserve the AF helper relocation to 0xBA5718; old 0xBA4E00 belongs to LUT resident code in this integrated layout. Old standalone patch tools must keep their exact-input rejection.
- Retain the frozen basic feature-integration recipe, but do not describe its reference-slot limit as the current LUT feature. Preserve sound resources, aspect capture-copy chaining, MPR EXIF and AVCAM identities.
- Format/ABI versions, official input versions, software releases and BCD numeric examples are not internal firmware announcements. Do not alter measured numeric data when cleaning prose labels.

- User-facing feature introductions must describe current functions and operation only. Omit retired cache quotas, per-key cache explanations, iterative fixes, acceptance summaries and test-process conclusions in both languages and the root feature index. Keep implementation mechanics in technical references.

## README layout

- Keep the opening flashing warning, then no-Fastboot installation, then a concise Fastboot method table and navigation, followed by declarations and acknowledgements. Keep detailed reports linked rather than reproducing test conclusions on the homepage.
- Credit Hearts-Ace/sony-a7r5-custom-firmware for native colour parameters, grid lifecycle research and R5ColorLab LUT fitting. The user explicitly excluded menu attribution; retain the custom LUT method entry.
- State the supported camera and official firmware prominently near the top: Sony ILCE-7M4 (A7 IV / A7M4), official V6.02. This is the supported stock baseline, not an internal development version.
