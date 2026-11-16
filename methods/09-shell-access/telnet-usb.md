# 恢复 ULOGIO 的 Telnet 与 USB Shell

[总览](README.md) · [组件身份](reference-layout.json) · [验证边界](validation.md)

普通启动使用 p7 根文件系统，并将 p15 挂到 `/usr`。本方法仅修改 p15 的 `/lib/libosal_ulogio.so` 与 `/lib/libsencore.so`，运行时分别为 `/usr/lib/...`。PTY 子进程执行 p7 中已有的 `/bin/ash --login`。

## 动态装载与初始化入口

以下地址对应组件身份文件绑定的原厂 6.02 ULOGIO 库。动态装载器处理重定位后，通过 ELF 构造函数数组调用初始化入口。

| 项目 | 原厂 6.02 值 |
|---|---|
| `DT_INIT_ARRAY` | `0x18d18` |
| `DT_INIT_ARRAYSZ` | `0x10`，共两个 8 字节项 |
| 第二个构造项 | VA `0x18d20`，文件偏移 `0x8d20` |
| 对应 `.rela.dyn` 项 | `r_offset=0x18d20`，`R_AARCH64_ABS64=257`，`r_addend=0` |
| 重定位目标 | 原厂 dynsym #112，`__ulogio_so_init @ 0x3238` |

第二个构造项在文件中的原值为 0，装载时由符号重定位填入地址。检查入口时需要解析重定位的符号索引。重建 dynsym 后，应让该项继续解析到 `__ulogio_so_init`，使用重建后的实际索引。

`__ulogio_so_init` 的函数范围为 `0x3238..0x3368`。它通过 OSAL 同步消息取得配置，再以 `0x362c` 为入口创建工作线程。线程体在 `0x38dc` 通过 PLT `0x3060` 调用 `ulogio_telnetd_init @ 0x50b4`，并在 `0x36b0` 经 PLT `0x2bd0` 进入主循环。

```text
动态装载器 → .init_array 的重定位后函数指针
  → __ulogio_so_init @ 0x3238
  → OSAL 配置消息、工作线程 @ 0x362c
  → 0x38dc 调用 ulogio_telnetd_init @ 0x50b4
  → 移植后的监听初始化
```

ELF 重建时一并核对 `DT_INIT_ARRAY/DT_INIT_ARRAYSZ`、`.rela.dyn`、dynsym 及符号版本。原 `.rela.plt` 的顺序只覆盖 PLT 调用相关检查，构造项使用的 `.rela.dyn` 仍需同步。实际执行还依赖库成功装载、OSAL 配置消息成功和线程创建成功。

## 恢复终端创建代码

1.05 p15 的 ULOGIO 库包含网络监听、PTY 与 ash 创建；6.02 同库删除了这些创建路径，但保留部分 `telnetd` 名称。整库回退会丢失 6.02 的 PROX 配置／分派，采用有边界的函数移植。

从 1.05 供体提取以下半开区间，地址为 ELF VA：

```text
0x4448..0x4490    0x4490..0x44cc    0x44cc..0x4884
0x496c..0x49e0    0x4ad4..0x4bbc    0x4bbc..0x4e9c
0x5afc..0x5da8
```

这七段共 2852 字节，需要重定位其中的直接分支、ADRP/ADD、GOT/全局引用和 PLT 调用。6.02 既有代码、80 个公开导出、数据地址及 PROX 路径保留，移植函数放入新增 RX 段，再由原入口跳转接入。新 libc 依赖使用独立 GOT 槽和 AArch64 桩，新增导入绑定 libc 的 `GLIBC_2.17` 版本项。

已验证实现采用下列地址映射，保留供体各段之间的相对间距。

```text
clone_base = 0x1a000
mapped(donor_va) = clone_base + donor_va - 0x4000
ulogio_telnetd_init 的新入口 = mapped(0x5afc) = 0x1bafc
6.02 原入口 0x50b4 改为 b 0x1bafc
```

原入口只需容纳跳转指令。供体 init 的 684 字节放在新段中，原函数的 `st_size=0x1c8` 保留。使用其他新增段基址或布局时，按该布局重新计算分支、引用和入口映射，并核对装载段范围与权限。

### 固定启用监听创建

本方法将移植 init 中两处读取启用参数的指令改成 `mov w0, #1`，小端机器码均为 `20 00 80 52`。

| 1.05 供体 VA | 上述映射下的 VA | 原指令 | 修改后 |
|---|---|---|---|
| `0x5b48` | `0x1bb48` | `ldr w0, [x21, #0x18]` | `mov w0, #1` |
| `0x5b6c` | `0x1bb6c` | `ldr w0, [x21, #0x18]` | `mov w0, #1` |

第一处控制是否调用 `socket`，第二处在 `socket` 返回负值时读取同一启用参数。原厂线程在 `0x38d0` 读取配置 `cfg+0x30`，再将它放入 init 参数 `+0x18`。上述修改使这两次读取固定得到 1，因此监听创建独立于 TELN 配置值。已验证方法通过 p15 两库修改实现，使用时无需另外置位 `/etc/ulogio.bin` 的 TELN 或发送 `ulogio telnet up`。

### 接入网络与 USB 生命周期

| 6.02 ULOGIO VA | 修改 |
|---|---|
| `0x50b4` | init 转入移植实现，创建 TCP 23 监听 |
| `0x4dac`、`0x4db0`、`0x4db4` | accepted socket 交给网络 PTY/ash helper |
| `0x48e8` | input=2 或 output bit1 时创建 USB PTY；保存寄存器和标志并重放原 LDR |
| `0x4100` | 删除终端节点前释放两条 ring |
| `0x49b8` | USB 停用只对正 PID 发 kill，处理子进程已退出状态 |
| `0x49d0` | 避免重复关闭同一 USB slave fd |

初始化结束时统一重算 `select` 的 `nfds`，把 listener 纳入事件循环。已验证实现从映射后的供体 `0x5d64` 跳转到辅助代码，调用映射后的 `0x4448` 重算函数，重放原 `ldp x19, x20, [sp, #0x10]`，再跳回映射后的 `0x5d68`，由原尾声恢复现场并返回。按上述基址，接入点为 `0x1bd64`。

遗漏这一步时，TCP 可能先握手成功，但主循环始终没有执行 `accept`，队列积压后后续连接也可能超时。网络主循环接收连接后，表中的 `0x4dac/0x4db0/0x4db4` 接线将 socket 传给 PTY/ash helper，完成 `/dev/ptmx`、`grantpt/unlockpt/ptsname` 和 ash 创建。USB 创建、终端销毁与退出回收分别由其余接入点处理。

移植的 `vfork` 失败和分配失败进入清理路径；子 shell 退出后，终端必须可以关闭并再次创建。ELF 重建需保留段权限、原 VA 和动态重定位对齐，不能仅看反汇编中出现 `/bin/ash` 就认定完成。

## 放行普通系统 TERM_MODE

仅对 JSON 中绑定的 **6.02 p15 libsencore**：

```text
文件偏移 0x26e13：80 → 00
block 0x0601 / code 0x801f → code 0x001f
```

这不是 p1 的 `0x2bc43`。只改 p1 同名库，不能恢复普通 p15 的终端创建路径。新文件放回本机完整 p15 后重建文件系统，按[共同集成流程](README.md#共同的集成流程)部署和完整读回。

## 监听未出现时的定位

先对实际烧录的候选库检查动态标签、重定位和符号表。

```sh
readelf -W -d libosal_ulogio.so
readelf -W -r libosal_ulogio.so
readelf -W --dyn-syms libosal_ulogio.so
readelf -W -x .init_array libosal_ulogio.so
```

按顺序核对构造项解析结果、`0x50b4` 跳转目标、移植后的两处启用指令、全局/GOT/PLT 引用，以及 init 末尾的 nfds 重算。若已有运行期观测通路，再检查库的实际装载路径、OSAL 配置与线程创建、`socket/bind/listen` 返回值、listener fd 和 `accept`。

端口超时可能出现在监听初始化、网络路径或 accept 队列积压等阶段，需要结合上述证据定位。文件系统检查和刷写回读验证的是镜像结构与部署内容，ELF 重定位及运行期调用链应单独核对。

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

