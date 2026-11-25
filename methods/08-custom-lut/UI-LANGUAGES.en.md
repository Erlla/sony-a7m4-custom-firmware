# English resources inside the LUT interface

[中文](UI-LANGUAGES.md) · [LUT method](README.en.md) · [Source and exact layout](../../native/custom-lut/ui-languages/README.md)

This update addresses the internal LUT interface described in [Issue #49](https://github.com/Erlla/sony-a7m4-custom-firmware/issues/49). It adds 50 labels for card and file selection, delete/clear confirmation, nine adjustments, empty/off placeholders, import status and errors. Simplified and Traditional Chinese have their own text; the other 32 languages use English. User LUT names, filenames, percentages and page numbers retain their original content.

## Resource placement

IDs `0x0204E85E`–`0x0204E88F` live in the 34 common `share/app/string_<language>.uxc` banks (`0x27`), shared by landscape and portrait views. Each index grows from 2142 to 2192 entries. Existing index values and record contents remain intact; the record area moves after the expanded index. Common banks have room that some portrait banks lack within the native 16-bit record-offset limit.

Custom shutter and focus sounds use orientation-specific bank `0x05`. Both mechanisms use the original AP language table and the same `libObj` database, XDB routing and UXC lookup. No separate language preference or replacement language switcher is introduced. LUT IDs do not overwrite sound strings.

## Display integration

`lut_ui_text.c` accepts product-owned labels, writes the native resource ID at parameter `+0x30`, clears stale formatting arguments at `+0x58`, and sets the active flag at `+0x2C`. The inline byte table contains no absolute pointers and adds no writable state.

The derived `lut_localized_render_overlay` and `lut_localized_stock_bind` functions reuse the existing GUI state and pointer. User names retain the original dynamic text binder, including names that happen to match a product label. Only product placeholders such as Off, Empty and Invalid Name use localization.

On the pinned, cleaned AP layout, the RX component occupies virtual addresses `0x0904D000`–`0x0904FBF0` (11,248 bytes). The old `lut_stock_bind` (`0x09004948`) and `p4_gui_render_overlay` (`0x0903F664`) entries branch to the new functions, and the existing RX segment is extended. The shared GUI pointer remains at `0x09050098`. Full identities, entry points and file-offset edits are in [reference.json](../../native/custom-lut/ui-languages/reference.json).

Earlier touch-component layouts used this address differently. This recipe applies only to the pinned post-cleanup baseline. Existing touch, fast scanning, pagination, import transactions and color processing remain intact.

## Composition

Integrate the AP and all 34 language banks together. The resource builder checks complete input/output hashes and preservation of existing records; see the [source instructions](../../native/custom-lut/ui-languages/README.md). Full AP compilation also requires the matching locally held LUT headers and ABI. This is not a one-command build from stock firmware.

The reference also records the AP/MPR identities after composition with menu shortcuts, the corrected registered sound menus and HEIF playback support. The localized display bytes remain intact in that composition; CP and updater are unchanged. Other methods retain their exact input restrictions. Do not replace the combined AP or MPR with an older whole-file output.

## Validation limits

Native language selection, bank switching and string lookup were replayed on the combined AP across all 34 languages, both orientations and two load biases, alongside sound resources. Display replay covers cards, file pages, deletion, adjustments, status and name preservation. File services, allocation and display-device queries use explicit fixtures.

The new English interface has not yet passed camera acceptance. Font rasterization, clipping and wrapping of longer English prompts require physical checks. Earlier shortcut or HEIF acceptance does not establish acceptance of this English composition.
