# LUT joystick and dial input adapter

[中文方法](../../../methods/08-custom-lut/INPUT.md) · [English method](../../../methods/08-custom-lut/INPUT.en.md) · [Exact reference](reference.json)

`lut_input.c` normalizes 17 joystick/dial events at the LUT-owned entry, then calls the existing GUI dispatcher. It retains the original event record, touch handling, preview queue, confirmation and cancellation. The adapter has no writable globals or heap allocation.

## Build the exact AP component

Use Python 3.11+, `pyelftools==0.32` and Zig 0.14.1. Run from the repository root with a locally held AP whose full SHA-256 is listed in `reference.json`:

```powershell
python -m pip install pyelftools==0.32
python native/custom-lut/input-adapter/build.py --input local/combined-appFw.so --output output/lut-input/appFw.so --zig path/to/zig.exe
```

The output must be a new file. This recipe follows the **combined** UI-language, shortcut and HEIF AP in [the language reference](../ui-languages/reference.json), not the older language-only or touch component. The builder compiles the C source, checks the 368-byte RX payload, applies three exact edits, and verifies the complete output hash. The output matches the component used for the accepted fix. It does not generate or install a firmware package.

`input.ld` fixes the module at `0x904FC00`, the read-only import of the current scene at `0x8F73030`, and the existing dispatcher at `0x903E5E0`. The entry branch is at `0x903104C`. Extend the existing RX segment through `0x904FD70`; leave the previous language code ending at `0x904FBF0` intact. These addresses apply only to the pinned input.

## Evidence

- [Public build verification](build-verification.json): the rebuilt AP is byte-identical to the accepted component; unsupported input is rejected before compilation.
- [Baseline replay](baseline_replay.json): 15 cases reproduce ignored joystick/dial inputs while ordinary directions and subsequent touch work.
- [GUI regression](replay.json): 43 cases, including 17 mappings compared with the corresponding ordinary key, all four dial pairs in the editor, a 40-event burst, confirmation lock, mixed input, cancellation and gates. The touch check covers all 17 rows.
- [Relocation](relocation.json): 10 installed-entry cases at load offsets of +4 GiB and +16 GiB.

These JSON files are recorded results, not a self-contained replay harness. The research replay executes real AP instructions for GUI dispatch, queuing, confirmation and cancellation. Drawing, timer services, directory snapshots, backend completion and page-manager exit receivers use fixtures; editor readiness is also supplied by a fixture. Event names were resolved from the same AP's event table and ELF relocations. The maintainer confirmed that the reported input problem was resolved on 2026-11-25; no per-case hardware test matrix was supplied.

本目录仅发布适配源码、离线组件构建工具及小型证据。完整厂商 AP、调试 ELF 和固件安装包需本地持有，不随方法分发。公开构建输出已与验收组件逐字节比对；不同输入布局需要重新定位和验证，不能扩大哈希白名单后复用固定地址。
