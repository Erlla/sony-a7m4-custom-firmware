# LUT runtime source cleanup

[中文方法](../../../methods/08-custom-lut/RUNTIME-CLEANUP.md) · [English method](../../../methods/08-custom-lut/RUNTIME-CLEANUP.en.md) · [Exact layout](layout.json)

本目录提供五个自有源文件的统一差异、控制层及后端链接脚本、模块与绑定清单，以及可独立构建的 LUT 缓存配方。完整 AP 重链接依赖本地持有的匹配 LUT 基线源码、头文件和颜色数据。

`source-changes.patch` 使用 UTF-8 LF，保留基线的相对 include 写法。各文件补丁前后摘要见 `layout.json` 的 `source_patch`，计算摘要前将行尾规范为 LF。将五个匹配基线源文件复制到独立工作目录后应用差异，编译时把原源文件目录追加到 include 搜索路径。`modules.source_order` 列出链接顺序，`removed_translation_units` 列出删除的诊断单元。控制层先链接，后端再绑定其符号。

```powershell
git apply --check path/to/source-changes.patch
git apply path/to/source-changes.patch
```

LUT 缓存直接复用仓库的 `native/persistent-cache` 源码。以下命令在仓库根目录执行，按精确配方构建 1,694 字节 RX 模块，输出 `cache.elf` 和校验收据。

```powershell
python tools/build_persistent_cache.py --lut-only --zig path/to/zig.exe --output output/lut-runtime-cache
```

`cache-build.json` 记录编译器、依赖、原函数地址与机器码摘要。AP 安装需使用本目录的重绑定表及完整组件身份。`control.ld`、`backend.ld` 保留固定 ABI 和地址边界，原生全局函数调用还依赖基线的 `p6_compile.h` 及 PIC 实现。

The patch contains authored source changes for five files. Normalize line endings to LF when checking its preimage and postimage hashes. Copy the matching baseline files into a separate directory, apply the patch there, and add their original source directories to the compiler include search paths. Full AP relinking requires the matching locally held LUT sources, headers and color data. The manifest lists source order, removed translation units, linked segment hashes, native branches, factory addends, cache calls and complete component identities.

The public cache command builds the exact LUT-only module using the existing cache sources. Its profile pins the compiler, dependencies, original function addresses and linked bytes. The control/backend scripts supply the fixed ABI and address layout for the matching full source integration.
