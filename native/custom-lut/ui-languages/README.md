# LUT UI language sources

[中文方法](../../../methods/08-custom-lut/UI-LANGUAGES.md) · [English method](../../../methods/08-custom-lut/UI-LANGUAGES.en.md) · [Exact reference](reference.json)

`strings.json` holds 50 Simplified Chinese / Traditional Chinese / English triples. `labels.inc` maps product-owned source labels to native resource IDs. `lut_ui_text.c` provides the binder; `overlay.c` and `projection.c` are the two display-only derivatives. `ui.ld` fixes their imports and addresses for the exact reference layout.

Build the language resources from the locally held, matching extracted `share/app` directory:

```powershell
python native/custom-lut/ui-languages/build_resources.py --input path/to/extracted/share/app --output output/lut-ui/share/app
```

The output directory must be new. `resources.json` pins all 34 input and output files. The builder rejects unsupported banks, preserves old records and generates the reviewed set. It does not extract, sign, install or distribute firmware.

Full display compilation requires the matching existing LUT headers (`p4_gui.h`, `p4_import_layout.h`, `p4_completion_detail.h`, control/layout/numeric/gauge headers and their dependencies), plus the baseline `p6_compile.h` PIC helpers. These are not all bundled here. Use Zig 0.14.1 targeting `aarch64-freestanding-none`, `-include p6_compile.h`, `-mgeneral-regs-only -mno-outline-atomics -mstrict-align -fpie -Os -ffreestanding -fno-builtin -fno-stack-protector -ffunction-sections -fdata-sections -nostdlib -static`, and link the three C files with `-Wl,-no-pie -Wl,--gc-sections -Wl,-u,lut_localized_render_overlay -Wl,-u,lut_localized_stock_bind -Wl,-T,ui.ld`. Add this directory and the matching header directories to the include search path.

Check that the linked RX payload matches the component edit hash in `reference.json`, has no unresolved symbols or runtime relocations, and ends before `0x09050000`. Installation is specific to the pinned AP: map the two entry branches through its ELF segments, extend the existing RX segment, and preserve all bytes outside the listed edits. Both AP and resources are required. The repository does not provide proprietary application binaries, full GUI build dependencies or an installable package here.

本目录的源文件可审阅并用于匹配布局集成。资源命令可独立运行；完整显示模块还依赖本地持有的基线头文件及 ABI。`reference.json` 分开记录英文层与快捷键／HEIF 合并后的身份，不能把旧独立配方的地址直接用于任意固件。用户自定义名称始终由原动态文本绑定处理。
