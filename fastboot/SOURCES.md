# 来源与构建资料

本次许可变更后的新增原创主机维护代码及修改采用 [GNU GPLv3（GPL-3.0-only）](../LICENSE)，历史内容继续按 [原 MIT 许可](../LICENSE-MIT-LEGACY) 授权。相机端启动程序、RP2040 桥及其历史源码来自 [DavidBuchanan314/ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE)，其许可范围见下方来源说明。

| 项目 | 对应资料 |
|---|---|
| 相机 fastboot.bin | `source/payload/`，历史源码提交 `2328d18ce640e6c8cd9341efcf0043ce9042a135` 的 `payloads/fastboot`，含 Cetus 子程序；入口 `0xFE020000` |
| RP2040 UF2 | `source/uart_boot/`，保留该 UF2 归档构建使用的 Arduino 生成 C++ 和 PIO 头；仅规范化文件行号中的构建路径 |
| RP2040 构建配置 | Arduino-Pico 6.3.0；`rp2040:rp2040:waveshare_rp2040_zero`；`-DOPEN_DRAIN -DUART_TX` |

上游现有[总许可说明](https://github.com/DavidBuchanan314/ILCE-7M4-RE/blob/main/LICENSE)要求按子目录区分；[Fastboot 子目录声明](https://github.com/DavidBuchanan314/ILCE-7M4-RE/blob/main/payloads/fastboot/LICENSE)提及 MIT 惯例及可能涉及 GPL-2.0 的参考内容，并未给出单一清晰许可。历史 RP2040 桥目录没有独立 LICENSE。这里保留来源、原作者注释和源码资料，不声明这些组件已取得统一 MIT 授权。Arduino-Pico、Pico SDK 及其库分别沿用原许可。

`assets/` 保存原有运行文件，未重新编译或修改。源码资料用于追溯和构建，不承诺不同编译环境能逐字节生成相同 BIN/UF2。

## 重新构建

相机端：安装 AArch64 GNU GCC/Binutils 和 GNU make，在 `source/payload/` 执行 `make`。以该目录 Makefile 和 Cetus Makefile 的工具链变量为准；构建不会连接相机。

RP2040：安装 Arduino CLI、Arduino-Pico 6.3.0。在新建 `uart_boot` sketch 中，用本目录归档 C++ 内容作为 `.ino`，同时放入 `serialboot.pio.h`，执行：

```powershell
arduino-cli compile --fqbn rp2040:rp2040:waveshare_rp2040_zero --build-property "compiler.cpp.extra_flags=-DOPEN_DRAIN -DUART_TX" --build-path build uart_boot
```

归档 C++ 已有 Arduino 函数声明；代码中的相对 `#line` 只用于编译诊断。GPIO28/29/27分别用于Multi TX/RX/RST，硬件电平与接线要求仍按接线文档执行。
