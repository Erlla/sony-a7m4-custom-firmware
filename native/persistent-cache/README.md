# LUT 编译缓存 / Persistent LUT compilation cache

当前精简布局使用 1,694 字节的 LUT 专用构建，方法与命令见[运行时精简源码](../custom-lut/runtime-cleanup/README.md)。本页以下配方用于重建原始共享缓存阶段。

The cleaned layout uses the 1,694-byte LUT-only build described in the [runtime cleanup sources](../custom-lut/runtime-cleanup/README.md). The recipe below rebuilds the original shared-cache stage.

此模块保存 LUT 基础编译结果。八项微调与强度仍独立保存、正常应用；缺少或失效的缓存由原编译路径重建。原 JSON 和设置继续保留。

## 组件与构建

这是组合布局的 AP 缓存接入层，与 [CP LUT 引用缓存](../custom-lut/README.md)分别工作。[精确配方](../../a7m4/profiles/persistent-cache.json)保留固定链接布局及基础输入／输出身份；当前组合随后必须应用[声音生命周期层](../custom-sounds/lifecycle/README.md)，由后者将声音转换调用恢复到原 WAV 转换器。当前声音不读取或保存持久 F0 结果。

使用外部 Zig 0.14.1，从仓库根目录运行：

```powershell
python tools/build_persistent_cache.py --zig C:/tools/zig/zig.exe --output output/persistent-cache
python -m a7m4.persistent_cache --input local/integrated/appFw.so --output output/appFw.cached.so
python -m a7m4.custom_sound_lifecycle --component ap --input output/appFw.cached.so --output output/appFw.sound-lifecycle.so
```

构建器核对源码、依赖头文件和编译段摘要。缓存模块保留 `0x9048000..0x9048DDF` 的3551字节及固定导出，不新增 BSS。文件系统回写、分区校验及签名沿用原组装流程。这些工具输出 AP 组件，不能直接安装。

## LUT 缓存合同

基础编译结果位于 `/setting/clut/looks/C00.BIN`～`C63.BIN`，绑定内部内容记录、编译 ABI 与 CRC。编号跟随内部记录复用，不代表16个用户槽位的数量。导入完成原写入与回读后保存编译结果；旧记录首次读取时补建，之后可在开机读取。微调与强度不要求重新编译基础内容。

AP 编译缓存不代替 CP 内容传输、资源准备与参数应用。固定模块仍包含 `sound_cache.c` 及其导出以保持原编译布局；在当前完整组件链中，该 F0 包装不被声音调用。原 WAV、音量和声音设置继续由声音模块管理。

## English

This AP module persists compiled base LUTs. The eight adjustments and strength remain independent. Original JSON and settings remain authoritative; missing or invalid caches use the original compiler.

The fixed cache recipe preserves its linked module and exports. Apply the current AP sound lifecycle layer after it, as shown above. That layer restores the original WAV conversion call; persistent F0 audio-result reuse is not active in the current composition. The retained `sound_cache.c` export keeps the module layout reproducible. Base LUT cache files follow internal content records, independently of the 16 user slots. Caching does not replace CP transfer, resource preparation or parameter application.
