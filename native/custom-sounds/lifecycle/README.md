# 声音生命周期 / Sound lifecycle

此层在组合 AP/CP 中处理启动资源准备、原生预约取消、连续对焦重播、双向抢占、共享增益读取与已完成请求的编号复用。**刚开机时，自定义声音可能尚未生效，请等待数秒。**

```powershell
python tools/build_sound_lifecycle.py --arm-gcc C:/tools/arm/bin/arm-none-eabi-gcc.exe --zig C:/tools/zig/zig.exe --output output/sound-lifecycle
python -m a7m4.custom_sound_lifecycle --component ap --input local/integrated/appFw.cached.so --output output/appFw.sound-lifecycle.so
python -m a7m4.custom_sound_lifecycle --component cp --input output/cpapp-b.handoff.bin --output output/cpapp-b.sound-lifecycle.bin
```

使用 ARM GNU GCC 16.1.0 与 Zig 0.14.1，构建器核对各模块的源码身份、全部分配段和未解析符号。[组件配方](../../../a7m4/profiles/custom-sound-lifecycle.json)仅接受列明的完整文件身份；它在[基础交接层](../handoff/README.md)与 AP 缓存层之后应用。已含或尚未含可选白平衡修改的 CP 都有独立输入／输出身份。输出是组件，完整固件仍需文件系统回写、分区校验与签名。

| 模块 | 作用 |
|---|---|
| `handoff.c`、`reservation.c` | 最新事件优先、同类对焦重播、共享 reader 下的 PIN 预约发布及原生取消 |
| `sound_boot_busy.c`、`late_start.c` | 区分完成的 Stop 与待播 Start；让原生已接收请求完成其原回调 |
| `gain_reader.c` | 增益读取共享资源锁，保留嵌套 reader |
| `busy_reply.c` | 在 BUSY 回复中保留状态快照；标记中的 bit31 不是原忙位 |
| `resource_policy.c`、`prepare_resource.c` | AP 租约、准备与原异步停止屏障 |
| `token_reuse.c` | 在完成确认后复用请求编号，永久避开可能收到迟到回复的编号 |

当前声音准备从已保存 WAV 执行原转换，日常播放使用已准备的内存数据。持久 F0 包装不参与当前声音读取或保存；[LUT 编译缓存](../../persistent-cache/README.md)保留。新层不增加 BSS，也不清除原生 busy 或伪造资源退休。完整入口及共享空间见[实现方法](../../../methods/06-custom-sounds/IMPLEMENTATION.md#9-启动资源交接预约取消与共享增益)。

The layer composes AP resource preparation with CP reservation cancellation, repeated-focus DMA restart, shared gain reads and reuse of completed request identifiers. Custom sounds may take a few seconds to become active after power-on. Use the commands above with ARM GCC 16.1.0 and Zig 0.14.1. Source and allocated-section identities are pinned; the tool handles only the listed local component inputs and never accesses a camera. Native Stop, reservation cancellation, replies and resource lifetimes remain authoritative. Completed request identifiers can be reused after ACK consumption and queue draining. Tokens reserved for late query replies stay excluded, and pending or uncertain requests keep their identity. Saved WAV conversion stays active, persistent audio-result caching is bypassed, and LUT compilation caching remains enabled.
