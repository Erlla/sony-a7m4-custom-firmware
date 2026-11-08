# 拍摄任务复制中的自定义比例

本组件补全原生 Capture 任务复制时的比例传递，使“人脸／眼部优先 AF”开启时，JPEG／RAW+JPEG 成片继续使用所选自定义比例。维护者已确认该问题修复；RAW 保留原始幅面。

[裁切方法](../../methods/07-custom-aspect-ratios/IMPLEMENTATION.md#9-拍摄任务复制与人脸眼部优先-af) · [精确组件配方](layout.json) · [构建器](../../a7m4/aspect_capture_clone.py)

## 修改合同

原生 A03612 复制照片参数，但不经过初次捕获的 A03142 入口。外部 `task_ids` 因而没有继承：新槽可能变回原生3:2，复用槽可能残留另一张照片的比例。A03650 的原生 memcpy 完成后，本组件从源任务取得已冻结 ID，写入目标任务的原有 sidecar。源 ID 为0时也写入0；不重新读取当前菜单。

目标原生比例必须是2（3:2 backing）；池指针与容量仍由已有任务访问器核对。原生任务的所有字节、JPEG/HEIF编码路径、RAW几何、菜单、预览、LUT和声音保持。拍摄输出的相册放大继续由独立的[读取兼容层](../aspect-playback/README.md)处理。

| VA | 处理 |
|---|---|
| `0xA03650` | 原 Capture 参数 memcpy 调用转到既有 `0xBA54B0` resident gate |
| `0xBA5508` | 复用已由 LUT 接管的旧冻结 dispatch 行；新 LR=`0xA03655`，冷态仍调用原 ARM memcpy `0x585FB8` |
| `0x11B700` | 84字节 Thumb helper，位于已映射的比例 RX 预留内；新增BSS/堆均0 |
| `0xBA5A10` | 更新原生启动检查的 `0x118000..0x11E000` prefix CRC |

以上地址仅适用于配方列明的完整组件身份。旧冻结调用 A049B0 已进入 LUT 的 BA5F30 包装，再直接调用比例冻结函数；因此该旧 dispatch 行可以复用。不要在独立旧版CP中按同一地址套用。

## 重建组件

从源码 checkout 运行，保留相邻 `native/`。使用 layout.json 列明的完整输入和编译器 SHA-256；编译器是 arm-none-eabi-gcc，不能只凭同名工具判断兼容。

```powershell
python -m a7m4.aspect_capture_clone --input local/cpapp-b.sound-lifecycle.bin --compiler path/to/arm-none-eabi-gcc.exe --output output/cpapp-b.aspect-copy.bin
```

输出父目录需已存在；工具拒绝覆盖文件，只生成CP组件，不访问相机或生成升级包。正常顺序为声音生命周期CP → 本组件 → 可选AWB配置；也接受配方列明的已应用AWB输入，两种顺序的完整输出相同。原有独立配方继续保持各自输入限制。

## 验证边界

公开源码重建与维护者验收的CP逐字一致。实际原生复制函数、编码请求和主/副格式Notify回放保留来源字节与RAW尺寸；源照片的选择与当前菜单不同时仍继承源选择。启动/MMU及helper损坏拒绝路径独立核对。硬件眼部检测与任务调度没有离线模拟，机身问题解决的结论来自维护者确认，不扩展为所有拍摄模式和HEIF实拍验收。

English: this component carries the source Capture task's frozen custom-ratio ID through the native copy constructor, including ID zero for an ordinary photo. It preserves native task bytes and RAW geometry, uses the existing optional-page readiness gate, and maintains the original memcpy fallback. The maintainer confirmed the face/eye-priority AF capture issue is resolved. Rebuild only from the exact CP/compiler identities in the recipe; apply after sound lifecycle and before optional AWB. No firmware, camera originals or device operations are included.
