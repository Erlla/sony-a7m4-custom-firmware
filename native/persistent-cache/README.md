# LUT 编译与声音转换缓存 / Persistent LUT and audio caches

此模块在机内保存 LUT 基础编译结果和声音 F0 转换结果。LUT 的八项微调与强度仍独立保存、正常应用；声音在音频或音量变化时重新转换。原 JSON、WAV 和设置继续保留，缺少或失效的缓存由原处理路径重建。

## 组件与构建

这是组合布局的 AP 模块，与 [CP LUT 引用缓存](../custom-lut/README.md)及[声音交接模块](../custom-sounds/handoff/README.md)分别工作。固定输入与输出身份、调用点和安装字节见[精确配方](../../a7m4/profiles/persistent-cache.json)。它不修改 CP、声音播放仲裁或更新器。

使用外部 **Zig 0.14.1**，从仓库根目录运行：

```powershell
python -m pip install -e ".[test]"
python tools/build_persistent_cache.py --zig C:/tools/zig/zig.exe --output output/persistent-cache
python -m a7m4.persistent_cache --input local/integrated/appFw.so --output output/appFw.cached.so
```

构建器核对源码、依赖头文件和编译段摘要。补丁工具只接受配方指定的完整 AP，输出同长度 AP 组件；它不生成可安装的固件。文件系统回写、分区校验和容器签名沿用原组装流程。

代码位于 `0x9048000..0x9048DDF`，共 3551 字节，扩展现有 `0x9030000` RX LOAD 的文件与内存长度至 101855 字节。没有新增 BSS、线程或常驻音频缓冲。两个库读取调用、一个导入回读调用和一个声音转换调用进入包装函数；原函数保留为缓存未命中路径。固定 VA、结构偏移和缓存 ABI 仅适用于指定布局。

## 缓存合同

| 对象 | 机内位置 | 身份与更新 |
| --- | --- | --- |
| LUT 基础编译结果 | `/setting/clut/looks/C00.BIN`～`C63.BIN` | 绑定原内容记录身份、编译 ABI 与 CRC；编号跟随内部记录复用，不代表用户槽位数量 |
| 两个声音槽的 F0 结果 | `/setting/csnd/f0_0.bin`、`f0_1.bin` | 绑定源 WAV SHA-256、音量、PCM 格式和转换 ABI；临时文件同步后替换 |

导入 LUT 完成原写入和回读后保存编译结果。旧记录首次读取时补建缓存，后续开机可直接读取；微调和强度不要求重新编译基础内容。AP 编译缓存不代替 CP 内容传输和参数应用，首次选择另一款 LUT 仍需完成这些步骤。

声音缓存包含 F0、原 guard 和转换信息；命中后继续原有资源准备、传输与提交流程。合焦、快门和 GUI 回调不执行新增文件操作。编译结构或转换算法变化时须同步更新缓存 ABI，不能只沿用旧文件名。

## English

This AP module persists compiled base LUTs and converted F0 audio internally. The eight LUT adjustments and strength remain independent. Audio is regenerated when its source or volume changes. Original JSON, WAV and settings remain authoritative; missing or invalid caches use the original processing path.

Use external Zig **0.14.1** and the commands above. The builder checks source identities and the installed code digest. The component patcher accepts only the complete AP identity in the recipe and produces an AP component, not installable firmware. The module adds 3551 bytes of RX code and no BSS, threads or resident audio buffers. Existing CP playback arbitration, transfer and resource lifetimes remain in place.

LUT files follow internal record reuse, independently of the 16 user slots. Audio cache keys include source SHA-256, volume, PCM format and conversion ABI. Updating compiler-result structures or conversion algorithms requires updating the cache ABI. AP compilation caching does not replace CP content transfer or parameter application when first selecting another LUT.
