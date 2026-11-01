# 通过 p1 与 Cetus 获取 Multi UART root shell

[总览](README.md) · [接线](../../docs/wiring.md) · [验证边界](validation.md)

这条终端在 **p1 更新环境** 运行，不依赖普通系统 p15 的 ULOGIO 或 sshd。接入链为：

```text
电脑客户端 ↔ RP2040 PIO ↔ Multi / Cetus UART0
           ↔ CP RAM程序 ↔ AP SPI0 ↔ p1静态桥接程序 ↔ PTY ↔ BusyBox ash
```

相机侧串口为 **115200、8N1**。内核参数中的 AP `ttyAMA0,460800n8` 是另一条接口，仅修改console参数不能替代本方法。启用期间不能拍摄，移除启动标记后恢复普通系统。

## 修改范围

| 对象 | 实现 |
|---|---|
| p1 `/sbin/init` | 原模块加载后检查 `/setting/updater/cpuart`；存在时挂devpts并exec桥接程序，不存在时继续原更新脚本 |
| p1 `/usr/bin/cp_uart_bridge.elf` | 静态AArch64 Linux程序，释放SPI0控制器、映射MMIO、加载CP程序并用forkpty启动ash |
| CP RAM | 载入 `0xfe020000`；4096字节RX环、原始TX和SPI状态接口，仅RAM加载 |
| RP2040 | PIO按开漏方式拉低／释放，保留原BootROM/Fastboot握手和共有命令 |
| p2 `/updater/` | 空 `mode`、`mode1` 选择生产更新环境，空 `cpuart` 选择桥接分支 |

CP NOR、WBI与p15无需因本方法写入。新增代码在p1，启动选择还会写p2，因此不能称整个过程“只写p1”。

## 硬件和RP2040发送

使用 Multi 启动线、RP2040-Zero、相机USB数据线及合适的1.8V电平接口；通用接线见[仓库说明](../../docs/wiring.md)。桥接接收／发送与reset要分别接对。

RP2040原参考实现中的GPIO `OD` 是 **Output disable**，不能直接作为开漏UART发送。采用PIO将输出值始终保持0，仅切换方向实现拉低或释放。UART控制路径必须使用这条PIO发送实现，而非仍被禁用的普通UART TX。

电脑COM口承载RP2040封包协议，不能用普通串口软件直接打开后就期待Linux文本。客户端应保留半包、按截止时间处理ACK，并提供UART字节收发命令。桥接客户端的Ctrl+C传给Shell，关闭电脑端连接不等于已恢复相机普通模式。

## AP与CP程序

以 [ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE) 的Fastboot/Cetus/SPI参考实现为基础，自行取得对应源与工具链。

- AP侧使用 `/dev/mem` 映射SPI0、GPIO1、SCU三页，并解绑 `ssp-pl022` 对SPI0的占用；复位Cetus到SPI ROM monitor，加载CP RAM程序。
- CP侧在SPI等待循环中持续轮询UART RX，用4096字节环保存数据，原始TX不插入日志字符。SPI状态返回缓存与错误计数，超时须适应Linux调度。
- Linux桥接程序作为PID1管理PTY子进程，执行原有 `/bin/ash --login`。`waitpid`发现Shell结束后先排空PTY剩余输出，再关闭并创建新Shell。
- AP/CP通信按实际字节长度分包，检查二进制0～255、环形跨界及溢出恢复，不能只用可打印文本推断透明传输成立。

参考构建环境为 **Zig 0.13.0**。CP使用 `aarch64-freestanding-none`，静态链接并关闭LTO、自动向量化和SIMD；Linux程序使用 `aarch64-linux-musl` 静态构建。CP选项包括：

```text
-O2 -fno-lto -mgeneral-regs-only -fno-vectorize -fno-slp-vectorize
-mstrict-align -ffreestanding -fno-builtin -fno-stack-protector
-fno-pic -ffunction-sections -fdata-sections -nostdlib -static
```

仅给函数加 `noinline` 不保证裸机ABI或指令集约束，检查实际编译指令。RP2040参考构建使用Arduino-Pico 6.3.0与Waveshare RP2040-Zero板型；PIO汇编使用SDK的pioasm。工具链和上游payload继续自行取得，不从不明来源混用二进制。

## 构建和安装p1

1. 保存本机完整物理p1及当时p2备份。包内较短的updater成员不能代替Fastboot整分区回读。
2. 解出p1 FAT内的 `/boot/initrd.img`，以保留元数据的方式修改SquashFS：仅增加条件init分支和静态桥接程序；保留原库、内核、kemco、权限及链接。
3. 重建initrd并更新FAT文件长度、全部FAT副本及p1chksum。需要新增簇时使用真实空闲簇，保留其他文件及物理尾部；不要硬套别人的簇号。
4. 对候选做结构和非目标内容检查，再按[共同流程](README.md#共同的集成流程)写p1并完整读回。
5. 安装匹配的RP2040 PIO实现。CP子程序由Linux桥接程序在进入该环境时加载到RAM，不刷CP NOR。

## 开启、使用与关闭

**开启**：重新读当前p2，在 `/updater` 下加入空 `mode`、`mode1`、`cpuart`，只改变这三个标记；写入并读回一致后重启。p1 init发现cpuart才exec桥接程序。客户端通过RP2040连接115200通道即可进入root ash。

```sh
cp_tag=ROOT
echo CP_${cp_tag}_READY
cat /proc/self/status
uname -a
cat /proc/mounts
```

使用变量展开后的唯一标记区分命令回复与输入回显；p1可能没有printf，使用已有echo。UID/GID四项应全0；该环境使用更新内核4.9.186-scel、BusyBox 1.26.2，挂载表不应依赖普通p15。

**关闭并恢复拍摄**：关闭电脑终端，进入Fastboot后重新读取当前p2，仅移除这三个模式标记，保留其他当前文件；写后读回一致再正常重启。不要把长期保存的旧p2整分区当作日常模式开关。

`exit`只结束当前ash，PID1桥接程序会重新生成ash；它不移除启动标记。电脑端断开连接同样不会自动退出更新环境。

## 回退和集成边界

日常退出只改当前p2标记。若撤销桥接功能，另将本机修改前p1完整恢复并读回。无cpuart时保留了原更新代码分支，但该桥接候选执行一次真实SD固件安装未验证。长时间高负载、其他机身或其他二进制布局不在现有实机结论内。
