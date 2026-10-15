# 自制刷机线

[English](wiring.en.md) · [返回](../README.md)

需要 RP2040-Zero、可正确引出 Sony Multi 信号的插头/转接板、导线、经过核对的电平接口，以及连接电脑的 USB 线。相机 USB 用于 fastboot，RP2040 USB 用于启动桥；两者作用不同。

| RP2040 GPIO | 相机信号 | 方向 |
|---|---|---|
| GP28 | Multi RX | RP2040 → 相机，发送串行启动数据 |
| GP29 | Multi TX | 相机 → RP2040，接收启动状态 |
| GP27 | RESET | 复位控制 |
| GND | GND | 共地 |

**GP 编号不是相机插头针脚编号。** 相机连接器的针脚位置、正反面与观察方向请按 [上游 Multi pinout 图](https://github.com/DavidBuchanan314/ILCE-7M4-RE/blob/main/images/multi_pinout.png) 和 [转接线实物参考](https://github.com/DavidBuchanan314/ILCE-7M4-RE/blob/main/images/multi_breakout.jpg) 核对；本项目不凭接头颜色猜测针号。

相机接口约 1.8 V；RP2040 为 3.3 V 器件。默认上游桥使用 `OPEN_DRAIN`。开漏只通过拉低/释放与目标上拉配合，不代表任意方向都已完成电平转换。应核对目标上拉、电压、输入阈值、RESET 电路与所用桥接板，必要时采用适合信号时序的电平转换。不要把相机信号接到 3.3 V/5 V 推挽输出，也不要凭本表给相机注入电源。

建议先在相机断开的状态用万用表核对短路、共地和线序，再验证桥输出和目标接口电平。不能仅因插头能插入就认为线序正确。

启动桥发送 BootROM 记录到 SRAM，再由相机端 payload 建立 USB fastboot。本项目只接收启动完成日志，不提供交互串口控制台。保留串行启动线路是使用这种 fastboot 入口的必要条件。

上游默认构建板型是 `rp2040:rp2040:waveshare_rp2040_zero`，使用 `-DOPEN_DRAIN`；不需要启用 `UART_TX`。首次安装桥固件按住 BOOTSEL 接入板子的 USB。读完 [风险与备份](../README.md) 和 [环境准备](setup.md) 后再使用实机入口。
