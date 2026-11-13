# LUT runtime cleanup

[中文](RUNTIME-CLEANUP.md) · [Custom LUTs](README.en.md) · [Source changes and link layout](../../native/custom-lut/runtime-cleanup/README.md)

This integration reduces the existing LUT control, backend and cache code. Its functional contracts include SD JSON import, 16 slots, eight adjustments, strength, touch preview, confirmation and cancellation, persistent caching, and AP/CP lifecycle handling. The maintainer tested the integrated camera firmware and reported normal operation with no observed problems.

## Integration order

For AP, apply the sound lifecycle, magnified-playback, LUT touch and aspect-menu components, followed by the Picture Profile and Custom LUT title glyph changes. Then relink and install the cleaned modules. For CP, apply capture-copy aspect inheritance, AWB and camera-written RAW FL2/FL3 alternatives before removing the BUSY diagnostic wrapper. The title glyph update also uses all 68 language/orientation banks. [Title glyph method](../../native/menu-ui-fixes/TITLE-ICONS.md)

| Component | Input SHA-256 | Output SHA-256 |
| --- | --- | --- |
| AP | `5f559e84f5e43be45116455b366faf97a9bb846e881db7bc924882f87857a1b1` | `b9e5a6b2a1b644ed9966d644dc1cbb4e110f45c743f37c04f84dceb69c169c71` |
| CP | `5ec4dee8e126ed54ff476b349e4d76318c98d3cc2f0ac9a5583ec98155b93fc4` | `5502802f647234e1323022fb7b412b6d4934028c0196aabf1f8f62b53aef8255` |

AP is 99,221,508 bytes and CP is 16,236,816 bytes. The exact hashes identify the supported layout. The component reference records these final identities under `runtime_cleanup` and retains the earlier recipe identities. [Component reference](reference-layout.json)

## Source changes

| Area | Implementation |
| --- | --- |
| Legacy diagnostics | Remove P2 sampling, process reads, diagnostic clocks, SD export and worker calls. Retain the native color execution bridge `p2_job_exec` |
| Event recording | Remove trace, power-observer and entry-snapshot state and calls. Retain source qualification, owner handling and lifecycle dispatch |
| RAM statistics page | Remove the formatter, history, GUI fields and handlers left behind by the disabled entry |
| Upload scheduling | Replace the 896-byte statistics structure with the 72-byte `upload_schedule_state` containing the functional timestamps, sequence and active flag |
| Persistent cache | Link `lut_cache.c` and `memory.c`, removing the idle sound-cache code and export |
| Touch selection | Integrate the native selected-row event into `p4_gui_dispatch` and clear the 280-byte helper at `0x904D000` |
| CP sound reply | Clear the 168-byte diagnostic wrapper at `0x11FF00`, restore the branch at `0xBA5216` to `0x11F97C`, and update the module CRC at `0xBA51EC` |

The worker retains its eight baseline WRITEs and conditional extension to at most 32 per round, using a 4 ms admission window. Healthy WRITE requests use a 1 ms sleep and other phases use 10 ms. ACK retry, epoch, cancellation and resume decisions still require the retained scheduling fields.

Existing cache records remain usable. Missing or invalid cache files invoke the original compiler and are rebuilt. Touch uses the absolute row in the native `0x020F0001`, type 4, widget 9, scene D9 notification. Row zero selects Off and rows 1–16 select the look slots. The original transaction queue handles preview, OK commits and MENU restores the entry snapshot.

## Relinking and installation

1. Apply the source patch and remove the ten listed diagnostic translation units. Link the control module first, then bind its new symbols in the backend linker script. Control RX starts at `0x9000000` and state at `0x8F73000`.
2. Retain the backend's 33 four-byte exports at `0x9031000`. Preserve the AP program-header table in the backend's first reserved page.
3. Rebind the 13 native branch entries and six factory pointers, including each matching `R_AARCH64_RELATIVE` addend. The layout lists all old and new targets.
4. Rebuild the LUT-only cache at `0x9048000`, rebind two `readrecord` calls and one `verify_written_record` call, and clear the old module tail.
5. Clear the standalone touch helper and update the meaningful LOAD lengths. The backend LOAD ends at `0x904C110` to include the existing sound resume, token reuse and playback helpers.
6. Apply the three CP changes. Compute the CRC over `0x11E000..0x120000` as `zlib.crc32(bytes) ^ 0xFFFFFFFF` and write the little-endian u32 to `0xBA51EC`.
7. Write AP and CP through the local filesystem assembly process, recalculate partition checksums and sign the container. Use the source hashes, module identities, bounded write ranges and binding tables to check the result.

Map AP VAs through `PT_LOAD`. CP file offsets equal VA minus `0x108000`. Native entries and factory addends must refer to the same link result. [Exact layout](../../native/custom-lut/runtime-cleanup/layout.json)

## Size and verification

| Object | Before | After |
| --- | ---: | ---: |
| Control RX | 61,424 B | 42,228 B |
| Backend RX including ABI reservation | 77,436 B | 75,732 B |
| Cache RX | 3,551 B | 1,694 B |
| Standalone touch helper | 280 B | 0 B |
| CP BUSY wrapper | 168 B | 0 B |
| Control static state | 53,128 B | 31,520 B |
| GUI context | 12,696 B | 12,320 B |

The RX and constant reduction totals 23,205 bytes. Control static state decreases by 21,608 bytes. Fixed address reservations and 64 KiB alignment still consume space, and the existing layout determines AP/container lengths. Available device RAM and speed gains remain unmeasured.

Native-entry binding, factory relocation, module relocation, final component identities and write ranges were checked. Machine-code replay covers power dispatch at two load biases, slot selection, cancellation, nine-control editing, old-cache migration, invalid-cache fallback, full AP/CP upload, abnormal clocks and restart without an SD card. Filesystem, scheduling, clock and rendering services use models.

The physical feedback reports overall normal operation. The earlier intermittent black-screen shutdown and magnified-focus exit symptoms still lack a reproducible sequence and established root cause. Long-term stability requires continued observation.
