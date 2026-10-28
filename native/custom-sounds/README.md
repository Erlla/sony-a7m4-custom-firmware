# 自定义声音原生源码 / Native custom-sound source

六个模块共 65 份固定链接输入（C、头文件、汇编和链接脚本）。它们是本项目编写的适配代码，不是索尼原厂源码。机身固件版本号不参与构建；固定 VA、协议常量、菜单 ID 和 schema 是参考布局的 ABI 数据。

| 模块 | 功能 |
|---|---|
| `runtime/` | RIFF/PCM 校验、双槽状态、名称和波形持久化、SD 列表与原厂 controller 适配 |
| `worker/` | 有界事件队列、去重、Q24/F0 转换、原生租约、AP/CP 事务、重启恢复 |
| `volume/` | 10%–100% 菜单、50% 基准、持久 sidecar 与排队提交 |
| `ui/` | 异步提交完成后在原 GUI 周期内刷新三个 profile 与父页 |
| `owner/` | CP 私有 BIND/PREPARE/COPY/COMMIT/POLICY 和原生短音生命周期 |
| `cp-gain/` | 只对私有声音的 CP 标量校正、descriptor/cookie 验证和状态范围 |

## 复现编译

已验证工具为外部 Zig 0.15.2 的 AArch64 freestanding 编译器和 ARM GNU GCC 16.1.0 / Binutils。工具不随源码打包；编译器版本不同可能改变代码布局，脚本会拒绝摘要不一致，不能忽略错误后安装。

```powershell
python -m pip install -e ".[test]"
python tools/build_custom_sound_native.py --zig C:/tools/zig/zig.exe --arm-gcc C:/tools/arm/bin/arm-none-eabi-gcc.exe --output output/sound-native
```

`source-manifest.json` 核对每份固定布局输入；`build-plan.json` 记录完整参数、链接绑定、段地址/大小、编译段摘要与已明确的 post-link 修订。所有模块无未解析符号；AArch64 保留 `-mgeneral-regs-only`、禁浮点/SIMD、无运行库的合同。调试标志保留，以复现原编译段指令布局；不分发本机调试 ELF 或机器路径。

Windows 下编译参数采用相对于模块工作目录的路径，避免部分 GCC 链接器误解非 ASCII 绝对路径。推荐项目与 `output/` 位于同一盘、以本页命令在仓库根目录运行。两个回调模块不是独立启动程序；链接器关于未提供 `_start` 的提示不代表存在未解析调用符号。

每个模块保留原始编译 ELF，同时生成 `installed.elf`，后者在同长度分配段中应用计划列出的后链接修订，并严格核对最终安装段摘要。runtime 的后链接修订包含机械／前帘快门支持、切换时保留开关和 `PRIVATE/M4ROOT/GENERAL/SOUNDS/` 扫描／读取路径；实际安装使用 `installed.elf` 的段。它们都不是可以直接刷入的分区或完整固件，完整文件配方另见[方法 6](../../methods/06-custom-sounds/README.md)。

## C 核心回归

```powershell
python tools/prepare_current_sound_sources.py --output output/sound-policy-source
C:/tools/zig/zig.exe cc -O2 -std=c11 -Inative/custom-sounds/runtime/include tests/native/custom_sound_core.c output/sound-policy-source/sound_core.c -o output/sound-core-test.exe
output/sound-core-test.exe
```

生成器将固定输入派生为当前策略源码，原输入不被覆盖。检查覆盖 PCM 解码、AF-S/AF-A/AF-C/MF 路由、默认回退、静音、机械／前帘播放、切换保持开关、失败提交不改状态、完整 snapshot 恢复及篡改拒绝。它们是主机逻辑检查，不是机内音频或断电实验。

## English

The six modules contain the project's own adaptation code, not original Sony source. Their fixed addresses and protocol/schema IDs describe the exact reference ABI, never a firmware display release. Use external Zig 0.15.2 and ARM GCC 16.1.0, run the build command above from the repository root, and select a fresh output directory. The builder validates the source inventory, complete compile/link arguments, section address/size/hash, unresolved symbols and explicit post-link corrections. `installed.elf` reproduces the final installed sections; it is not an installable firmware or partition image. The installed runtime includes mechanical/front-curtain support and the `PRIVATE/M4ROOT/GENERAL/SOUNDS/` directory through explicit post-link edits. Generate current-policy C with `tools/prepare_current_sound_sources.py` for the host harness; the fixed-layout compiler inputs remain intact. The C harness checks policy/persistence with synthetic PCM and no camera I/O.
