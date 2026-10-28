# 对焦／快门声音交接 / Focus–shutter handoff

`handoff.c`、`handoff.S` 和 `handoff.ld` 实现当前 LUT／纵横比／声音组合 CP 的双向抢占：最后触发的对焦或快门请求优先，最后一段自然结束。原 Sysnd 线程负责派发，原生 Stop、回包和资源退休负责结束当前播放。

```powershell
python tools/build_sound_handoff.py --arm-gcc C:/tools/arm/bin/arm-none-eabi-gcc.exe --output output/sound-handoff
python -m a7m4.custom_sound_handoff --input local/integrated/cpapp-b.bin --output output/cpapp-b.handoff.bin
```

编译器使用 ARM GNU GCC 16.1.0，参数、源码摘要、安装段与 CP 输入／输出身份见 [profile](../../../a7m4/profiles/custom-sound-handoff.json)。常驻门、包装和逻辑必须同时集成，BSS 必须由原 BODY 清零；新增段的 CRC 必须与原页预检一致。不同布局不能直接重放这些固定地址。

基础声音模块保持其参考 ABI；本目录作为组合布局的独立链接模块构建。详细入口、空间归属和交接规则见[修改方法](../../../methods/06-custom-sounds/IMPLEMENTATION.md#8-对焦快门双向抢占与连拍)。这些工具只生成本地 ELF 或 CP 组件，完整固件仍需正确封装、校验和签名。

The latest focus or shutter trigger preempts either active sound through native Stop and retirement. APP admission, PIN admission and common begin retain their distinct dispatch paths. Pending requests carry values only, superseded requests receive native cancellation replies, and the original Sysnd scheduler starts the latest request after release. The final sound finishes naturally.

Use the commands above with ARM GNU GCC 16.1.0. The profile pins source bytes, allocated sections and complete CP identities for the integrated layout. The basic six-module sound recipe remains a separate ABI; do not substitute its CP or replay this module into an unknown layout. These commands produce components, not flashable firmware packages.
