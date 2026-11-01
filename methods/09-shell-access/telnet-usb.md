# 恢复 ULOGIO 的 Telnet 与 USB Shell

[总览](README.md) · [组件身份](reference-layout.json) · [验证边界](validation.md)

普通启动使用 p7 根文件系统，并将 p15 挂到 `/usr`。本方法仅修改 p15 的 `/lib/libosal_ulogio.so` 与 `/lib/libsencore.so`，运行时分别为 `/usr/lib/...`。PTY 子进程执行 p7 中已有的 `/bin/ash --login`。

## 恢复终端创建代码

1.05 p15 的 ULOGIO 库包含网络监听、PTY 与 ash 创建；6.02 同库删除了这些创建路径，但保留部分 `telnetd` 名称。整库回退会丢失 6.02 的 PROX 配置／分派，采用有边界的函数移植。

从 1.05 供体提取以下半开区间，地址为 ELF VA：

```text
0x4448..0x4490    0x4490..0x44cc    0x44cc..0x4884
0x496c..0x49e0    0x4ad4..0x4bbc    0x4bbc..0x4e9c
0x5afc..0x5da8
```

这七段共 2852 字节。重定位其中的直接分支、ADRP/ADD、GOT/全局引用和 PLT 调用；不能直接拼接原字节。移植保留 6.02 原代码 VA、80 个公开导出及 PROX 路径，新 libc 依赖使用独立 GOT 槽和 AArch64 桩。新增 libc 导入绑定 `GLIBC_2.17`，不要沿用原 `open` 的 libpthread 版本标签。

| 6.02 ULOGIO VA | 修改 |
|---|---|
| `0x50b4` | init 转入移植实现，创建 TCP 23 监听 |
| `0x4dac`、`0x4db0`、`0x4db4` | accepted socket 交给网络 PTY/ash helper |
| `0x48e8` | input=2 或 output bit1 时创建 USB PTY；保存寄存器和标志并重放原 LDR |
| `0x4100` | 删除终端节点前释放两条 ring |
| `0x49b8` | USB 停用只对正 PID 发 kill，处理子进程已退出状态 |
| `0x49d0` | 避免重复关闭同一 USB slave fd |

初始化结束必须把 listener 纳入 `select` 的 `nfds`，不能依赖 UART 分支稍后重算。遗漏时 TCP 可能握手成功，却永远不执行 `accept`。网络主循环接收连接后创建 `/dev/ptmx`、完成 `grantpt/unlockpt/ptsname`，将 PTY 交给 ash；另保留 USB 终端创建与销毁生命周期。

移植的 `vfork` 失败和分配失败进入清理路径；子 shell 退出后，终端必须可以关闭并再次创建。ELF 重建需保留段权限、原 VA 和动态重定位对齐，不能仅看反汇编中出现 `/bin/ash` 就认定完成。

## 放行普通系统 TERM_MODE

仅对 JSON 中绑定的 **6.02 p15 libsencore**：

```text
文件偏移 0x26e13：80 → 00
block 0x0601 / code 0x801f → code 0x001f
```

这不是 p1 的 `0x2bc43`。只改 p1 同名库，不能恢复普通 p15 的终端创建路径。新文件放回本机完整 p15 后重建文件系统，按[共同集成流程](README.md#共同的集成流程)部署和完整读回。

## 使用网络终端

相机和电脑取得互通 IP 后，用 Telnet 客户端连接：

```text
<相机IP>:23
```

这是 TCP 23 **免口令、明文**终端，不使用 SSH 私钥。Wi-Fi 可承载这条 IP 连接，但仅存在 Wi-Fi 驱动或 TCP 监听不代表网络已经配置完成。连接后可执行：

```sh
echo NETWORK_SHELL_READY
grep -E '^(Uid|Gid):' /proc/self/status
```

UID/GID 四项均应为 0。`exit` 结束该会话，随后可以新建连接。

## 开启与关闭 USB 终端

USB 走 Sony 服务模式，不是 USB 网卡或串口类设备。Windows 需要相应正常／服务身份的 WinUSB；正常海量存储驱动恢复后，下次使用需重新准备驱动。先按实际接口枚举端点并完成 Senser keyappend 三轮认证。

协议顺序：

```text
ProductInfo TERM_CHANGE : (0, 0x00f1, 01)          成功码 1
AdjustControl TERM_MODE : (0x0601, 0x001f, 02 02) 成功码 0
终端读取：0x83 IN       终端写入：0x04 OUT
```

`02 02` 分别指定 USB 输入和输出。单字节 `02` 在此链上会被补为 `02 00`，只开输入、关闭输出；不能用它验证双向 Shell。端点是各方向 bulk 列表的第二项，不能按旧 `base+1` 算成 82/03。

结束顺序：

```text
TERM_MODE 00 00 → TERM_CHANGE 00 → StopSenser
```

`exit` 后仍须能停用并重新开启。`ulogio telnet up/down` 修改的是过滤字段，不能当作已恢复监听或 PTY 创建的证明。只出现 `Terminal activated` 也不等于收发已打通。

## 组合与回退

本方案不新增 SSH 账号、密钥或 SFTP 子程序。与 SSH 方案组合时，在同一离线 p15 中合并文件级修改，不能互相覆盖整分区；组合后另行验证。

撤销本方案时使用本机对应的原 p15 备份，完整写回并读回一致后正常启动。不能恢复其他机身镜像。当前 ash 路径可执行交互命令，但报告无 controlling tty，作业控制不可用。
