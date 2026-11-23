# 电子快门高速连拍 / Electronic shutter burst playback

适用于 ILCE-7M4 已集成自定义声音的下列组件。命令从仓库根目录运行。先为本机的两个输入核对 SHA-256，准备 ARM GNU GCC 16.1.0 和 Zig 0.14.1。构建命令从 C 和汇编重建两个模块，核对每个分配段的地址、长度和内容摘要。随后两条命令各自校验完整组件、应用修改并核对完整输出。将两个输出一起用于同一套固件。回退时使用原来成对保存的输入组件。

From the repository root, use ARM GNU GCC 16.1.0 and Zig 0.14.1 to rebuild and verify the native modules. Apply the recipe to both integrated components identified below. Integrate the resulting AP and CP together. To roll back, use the saved input pair.

| Component | Input SHA-256 | Output SHA-256 |
|---|---|---|
| AP · `appFw.so` | `5fce9c73b9dff3f42f8ade3effc848ddbf1c24f39f8cea036e5c29700759a8fa` | `01a89f1cba17c995cf6525b83c68c9f081c01e57247135b53b022ed89ffe1941` |
| CP · `cpapp-b.bin` | `cebf825e159fbf6974dbbf95a5e987d18b7db8526a98a96130257a2b808ae5da` | `13f744e25ebb46d2a5f82e6fc5fbd33e9b2989ed89c74e940d25b2a8be9c7b51` |

```powershell
python tools/build_sound_lifecycle.py --burst --arm-gcc C:/tools/arm/bin/arm-none-eabi-gcc.exe --zig C:/tools/zig/zig.exe --output output/burst-native
python -m a7m4.custom_sound_lifecycle --burst --component ap --input local/integrated/appFw.so --output output/appFw.burst.so
python -m a7m4.custom_sound_lifecycle --burst --component cp --input local/integrated/cpapp-b.bin --output output/cpapp-b.burst.bin
```

## 播放原理 / Playback

AP 在 `0x8FB31F4` 调用转换包装函数（`0x9048E00`）。原转换器完成后，快门槽中不超过 78 个编码块的短音复用已清零的缓冲区尾部，有效长度扩至 155 块。每块 32 字节，在 24 kHz 下容纳 31 个采样点。补尾后的资源共 200.21 ms，原音频样本及音量保留。容量检查为末端预留 64 字节。[AP 源码](pad.c)

CP 在同类自定义快门声正在播放时，以原生 DMA 停止和启动调用将播放位置移回开头，沿用当前音量、缓冲区和完成回调。拍摄间隔短于资源总时长时，每张都可复用该播放器。最后一次重播后，播放器自然走完尾部并释放。若后一次触发早于前一声的有声部分结束，仍会截断前一声。首声等待属性初始化期间，重复触发可能合并。[CP 源码](handoff.c) · [组件配方](../../../a7m4/profiles/custom-sound-burst.json)

The AP extends the encoded length of shutter-slot clips of up to 78 blocks into the zeroed tail of the conversion buffer. The resulting 155 blocks last 200.21 ms. The CP rewinds an active custom shutter clip through the native DMA calls, retaining its gain, buffer and completion callback. The final clip plays through the tail and releases the player. An exposure that arrives while audible samples are still playing can interrupt them. Requests arriving during initial setup can still coalesce.

## 验证范围 / Validation

原生代码回放使用 69.75 ms 的快门声音资源，每 100 ms 触发一次。首次属性回调延迟分别设为 10、20、30 ms，三组均为 20 次触发、20 次 DMA 起播。每组后 19 次均在触发所在的模拟步起播。间隔变为 100–130 ms 时，10 次触发也逐一对应起播。上述时间来自调度模型，实机曝光到扬声器的延迟仍待测量。

Native replay used a 69.75 ms clip and a 100 ms trigger interval. With modeled initial delays of 10, 20 and 30 ms, each run produced 20 starts for 20 triggers. After the first shot, every start occurred in the same simulation step as its trigger. A ten-shot run with varying 100–130 ms intervals also produced one start per trigger. Camera exposure-to-speaker latency remains unmeasured.
