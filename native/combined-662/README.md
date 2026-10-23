# 6.62：LUT、纵横比与声音的合并配方

[2026-10-23 从头复审](REVIEW-20261023.md)：未确认新缺陷。对象复用的局部反例因遗漏原厂外层互斥锁而撤回；新增布局、共享状态和外层锁检查通过，该次审查时实机待验，后续结果见下一段。固件实现及固定哈希不变。

本目录发布将纵横比 T22 功能移入当前 LUT／声音主线的原创 CP 源码、精确布局与离线组件合并工具。已重建出与研究版 **6.62 组合测试包** 完全一致的 CP、AP 和 68 份语言方向容器。完整包离线核验通过。用户随后完成 A～J 与两页系统／声音复测：单机组合功能符合预期，照片支持 LUT 启动／相册返回保持、关闭恢复、JPEG 裁切与 RAW 幅面；四张裁切 JPEG 的 EXIF 宽高仍错误。该缺陷已有 [6.63 修正候选](../jpeg-exif-663/README.md)，离线通过、实机待测；**LUT P2 仍未完成**。

这不是从官方 6.02 一步生成完整固件的入口。需要自行持有 [layout.json](layout.json) 中列明的三个 AP、一个 CP 和原资源文件；不匹配的文件立即拒绝。完整厂商程序、颜色模板、DAT、编译中间件和私有研究历史没有随本次同步发布。

## 修复了什么

| 对象 | 旧分支整段套用的问题 | 组合 6.62 的处理 |
| --- | --- | --- |
| CP | 纵横比代码覆盖原生 LUT 数据；常驻适配器覆盖 BOOT/codec/JPEG/QUERY | RX 改到 `0x11B000..0x11D000`，BSS 改到 `0x11D000..0x11D400`；独立 READY `0x1565F0C`，合并原 BOOT、CRC 与 MMU 映射 |
| ARM/Thumb | 绝对符号丢失 Thumb 类型，ARM BL 错误进入状态 | `.type` 与 `.thumb_set` 保留函数类型，生成 BLX |
| AP | 旧元数据和共享入口会覆盖主线 LUT/声音注册 | 保留主线 LOAD，追加纵横比两个 LOAD；13 个 PHDR，4 项重定位接在主线 106 项新增记录之后；两个构造入口串接主线 |
| 文字 | T22 比例 ID `0x0200AB60..AB63` 已被声音确认框占用 | 只把纵横比新段的 8 个引用移到 `0x0200AB4C..AB4F`，声音记录保留 |
| 字符串容器 | 追加记录使部分语言的 u16 word offset 溢出 | 重排活跃记录，最长项最后，68 银行逻辑记录及原生解码核验 |

AP 新增纵横比 RX `0x09010000..0x0901831C` 与 LUT RX `0x09000000..0x0900C232` **没有重叠**；合并处理的是旧共享段、程序头、重定位和构造入口。AVCAM 与两份图标资源使用 [T22 参考文件](../../methods/07-custom-aspect-ratios/reference-layout.json)，声音 `libmpr.so` 保留当前主线，SHA-256 为 `d417c96feac369a82e0f2ba2ae415f450bbdd48cf416b7ddfe0eb5921a65d5f1`。

## 公开内容与运行

`cp/` 包含裁切计算、选择器、拍摄冻结、12 处适配入口、独立门、启动清零/映射与链接布局。工具在 [a7m4/combined662.py](../../a7m4/combined662.py)，测试在 [tests/test_combined662.py](../../tests/test_combined662.py)。AP 使用与共同基线逐字节比较的三方合并，再显式协调冲突；资源按字符串记录合并。输出只写新文件，拒绝覆盖已有输出；不访问设备、不签名、不安装。

从源码 checkout 运行（依赖从根目录安装；该研究工具需要相邻 `native/`，不作为独立 wheel 功能）：

```powershell
python -m pip install -e ".[firmware,test]"
python -m a7m4.combined662 cp --main local/main-cp.bin --gcc path/to/arm-none-eabi-gcc.exe --output local/combined-cp.bin
python -m a7m4.combined662 ap --base local/base638.so --main local/main662.so --aspect local/aspectT22.so --output local/combined-appFw.so
python -m a7m4.combined662 string --name string_english_horizontal.uxc --base local/base.uxc --main local/main.uxc --aspect local/aspect.uxc --output local/combined.uxc
python -m pytest -q
```

CP 编译器也按 SHA-256 固定，使用研究构建所用 ARM GNU 工具链；不能任意更换后仍宣称相同产物。不要用 Python `-O`，工具会拒绝关闭二进制不变量检查的模式。`layout.json` 的 `frozen_research_source_id` 是已验证固件内的诊断身份，便携重放保留它，不代表任意后续源码修改都可继续使用该 ID。

**这三个组件不足以单独刷入。** 完整合并仍需当前主线声音库、AVCAM、图标、全部语言银行、文件系统增长与分区校验、版本和整包封装验证。精确输入由调用者自行取得，仓库不提供这些完整厂商文件，也不提供本布局的通用 DAT 构建命令。此前独立 T22 文件不能直接覆盖当前主线。

## 核验与待测

[validation.json](validation.json) 保存最终包身份及离线验证摘要：5,444 项组合检查；739,727 个编码块、5 个分区 CRC、169 个 TAR 项、32 套不变颜色模板；AP/CP/AV/MPR、声明修改补集与 1,836 次原生文字查询通过。公开配方另经实际输入重放，CP、AP、68 银行输出逐字节一致。公开仓库全套测试为 **218 passed**；这不是 218 项相机测试。

6.62 继承主线 CP 原生九消息与参数重建时的颜色发布修复。当前 LUT 为 **独立槽 1、固定 100%**，JSON 机内导入和多槽生产拟合尚未开放。本次单机启动早拍与相册返回照片保持槽 1，用户未报告跳色；没有逐帧录像，不作定量时延结论。

已完成本次单机功能复测的范围：槽 1 冷启动最早可拍与稳定后照片、相册返回是否跳色；LUT 与四个比例一起拍 RAW+JPEG；菜单/Fn 横竖屏遮罩；两页 MENU/半按快门/关机/LCD-EVF/翻屏；两种自定义声音标题、子菜单、播放、音量与重启保留。上述状态来自本次组合 6.62 反馈；不扩大为全模式、压力或定量性能验收。

完整 DAT 仅留本地，SHA-256 为 `b2959d877b262bd506c1cc6bc9815d8b8aa6e5fb91f48a278f6d5cc5b1a78ad2`。版本号同为 6.62 的旧包不能凭版本号视作相同文件。
