# LUT、纵横比与声音的组件合并

本目录提供 CP 适配源码、精确地址布局和离线组件合并工具，用于将独立纵横比实现接入已有 LUT 与声音框架。公开内容按功能组织；测试固件版本、安装包、逐轮验收与研究进度在研究库维护。

需要自行持有 [layout.json](layout.json) 列明的 AP、CP 和资源文件。输入和编译器均按完整 SHA-256 检查；这些约束定义适用范围，不能把固定地址当作跨固件通用地址。

## 合并方法

| 对象 | 需要解决的问题 | 实现 |
| --- | --- | --- |
| CP | 独立纵横比代码占用 LUT 数据和常驻适配区 | 纵横比 RX 移到 `0x11B000..0x11D000`、BSS 移到 `0x11D000..0x11D400`，使用独立 READY `0x1565F0C`，协调 BOOT、CRC 与 MMU 映射 |
| ARM/Thumb | 绝对符号丢失 Thumb 类型 | 通过 `.type`、`.thumb_set` 保留类型，生成 BLX |
| AP | 程序头、重定位尾部和构造入口共享 | 保留主线 LOAD，追加纵横比 LOAD；13 个 PHDR、4 项新增重定位接在主线 106 项记录之后，串接两个构造入口 |
| 文字 | 比例 ID `0x0200AB60..AB63` 与声音对话框冲突 | 只把纵横比段的 8 个引用改到 `0x0200AB4C..AB4F` |
| 字符串容器 | 追加记录可能溢出 u16 word offset | 重排活跃记录，把最长项放在最后，保留 68 个语言方向银行的逻辑记录 |

AP 纵横比 RX `0x09010000..0x0901831C` 与 LUT RX `0x09000000..0x0900C232` 不重叠；须协调的是旧共享段、程序头、重定位和构造入口，不能整段覆盖已有主线。AVCAM／图标输入参见 [纵横比参考布局](../../methods/07-custom-aspect-ratios/reference-layout.json)。

## 工具

[合并工具](../../a7m4/feature_integration.py)与[对应测试](../../tests/test_feature_integration.py)。CP 源码在 `cp/`；AP 使用共同基线的三方字节比较并显式处理冲突，资源按字符串记录合并。

```powershell
python -m pip install -e ".[firmware,test]"
python -m a7m4.feature_integration cp --main local/main-cp.bin --gcc path/to/arm-none-eabi-gcc.exe --output local/combined-cp.bin
python -m a7m4.feature_integration ap --base local/base.so --main local/main.so --aspect local/aspect.so --output local/combined-appFw.so
python -m a7m4.feature_integration string --name string_english_horizontal.uxc --base local/base.uxc --main local/main.uxc --aspect local/aspect.uxc --output local/combined.uxc
python -m pytest -q tests/test_feature_integration.py
```

从源码 checkout 运行，需相邻 `native/`；不支持只有 wheel 的独立安装。输出须为新文件，工具拒绝覆盖和 Python `-O`，不签名或操作设备。`frozen_research_source_id` 是精确输入对应的诊断身份，不能视为任意后续源码的实时哈希。

## 范围与验证

[组件检查摘要](validation.json)、[布局与并发审查方法](REVIEW.md)。CP、AP 和 68 个银行已用所列输入重建比对，源码及输出身份保持固定。原生回放的 OS 服务采用模型，不能用离线检查替代机内像素、实际调度或性能测试。

本目录冻结的基础合并配方保留早期独立参考槽接口。当前完整 LUT 方法已支持 SD JSON 导入、16 槽、八项微调、强度和缓存复用，见[自定义 LUT](../../methods/08-custom-lut/README.md)。不要把本目录旧配方输出当成当前完整 LUT 实现，也不要对新组合文件重放旧地址。JPEG 裁切还需要独立同步元数据，见 [JPEG EXIF 尺寸修正](../jpeg-exif-dimensions/README.md)。

输出组件不足以单独刷入，完整集成还需声音库、AVCAM、图标、语言资源、文件系统和分区校验。厂商程序、颜色模板、DAT、构建副产物与具体测试版本记录不在本目录分发。
