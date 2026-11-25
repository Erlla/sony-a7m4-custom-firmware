# LUT joystick and dial input

[中文](INPUT.md) · [LUT method](README.en.md) · [Source and build](../../native/custom-lut/input-adapter/README.md)

[Issue #52](https://github.com/Erlla/sony-a7m4-custom-firmware/issues/52) reported unusable joystick/dial input in the LUT interface while touch remained available. Offline replay of the current combined AP reproduced ignored joystick and four dial-pair events, with ordinary direction keys working. After the event mappings were added, the maintainer confirmed the reported problem was resolved on 2026-11-25.

## Operation

- The joystick's four directions act as ordinary direction keys, including direction repeats. Press its center to confirm.
- In selection/list pages, turn a dial right to move down or left to move up.
- In the adjustment page, select a parameter with Left/Right or the joystick, then turn a dial right to increase or left to decrease it.
- Touch, ordinary direction keys, OK and MENU retain the existing preview, save and cancel behavior.

## Cause and implementation

The AP's event-name table and ELF relocations distinguish ordinary keys, the joystick and dials. The existing `lut_native_key` at VA `0x9001074` recognizes only ordinary direction keys, confirmation and MENU. The GUI entry did not translate the other input families. Replay reproduced an ignored joystick input followed by successful touch, but did not reconstruct every intermittent condition from the original report.

The LUT-owned entry at `0x903104C` now branches to a 368-byte adapter at `0x904FC00`, which calls the existing dispatcher at `0x903E5E0`. Mapping applies to D9 selection/list and DA adjustment scenes. Other scenes use the original dispatcher directly. Only the event argument changes; the borrowed event record remains untouched.

| Input events | Mapping |
| --- | --- |
| `02010011/13`, `02010014/16` | Joystick Up/Down and repeats → ordinary Up/Down |
| `02010017/19`, `0201001A/1C` | Joystick Left/Right and repeats → ordinary Left/Right |
| `0201001D` | Joystick center press → confirm |
| `02050000/02/04/06` | Four dial-right events → down in D9, increase in DA |
| `02050001/03/05/07` | Four dial-left events → up in D9, decrease in DA |

Release, center hold-repeat, diagonal and unlisted events remain unchanged. There is no new writable state or heap allocation. The existing GUI owns preview queuing/coalescing, asynchronous completion, confirmation locking, cancellation and touch.

## Exact component and integration

| Component | SHA-256 |
| --- | --- |
| Input AP | `0cb44d4b8b4a7a9675603de6c10c5e7b4dbeae06e6226566e420f565bff8b1a0` |
| Output AP | `db820a263c23e29b15e98057976bc58a6af9c2aa9885709216ea7c2fc8b23666` |

Both are 99,221,508 bytes. Apply this after the [combined UI-language, shortcut and HEIF AP](UI-LANGUAGES.en.md). The only edits are the four-byte entry branch, 368-byte adapter and 16-byte RX segment size fields. The adapter follows the language module ending at `0x904FBF0`; the RX segment now ends at `0x904FD70`. All other AP bytes are preserved.

Use the [public build command](../../native/custom-lut/input-adapter/README.md) with the pinned input. [reference.json](../../native/custom-lut/input-adapter/reference.json) records exact offsets and hashes. Keep the existing 34 language banks, CP, MPR and other files, then update partition checksums through the existing packaging process. Older independent recipes retain their own input constraints; do not overwrite this AP with an older complete component. This method does not change the updater or signing process.

## Validation scope

The baseline has 15 replay cases. The fix passed 43 GUI regressions and 10 installed-entry checks at two load offsets. Coverage includes all 17 mappings compared with ordinary keys using complete GUI state/backend requests, all four dial pairs in the editor, a 40-event burst, confirmation locking, mixed input, MENU, scene/readiness gates and all 17 touch rows.

The replay executes actual AP instructions for GUI dispatch and transactions. Drawing, timers, directory snapshots, backend completion and page-exit receivers use fixtures. This does not establish complete hardware scheduling or peripheral coverage. The maintainer confirmed the reported input problem without supplying a per-case hardware matrix. The publicly rebuilt AP is byte-identical to the accepted component.
