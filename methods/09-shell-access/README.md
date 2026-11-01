# Shell / SSH：网络、USB 与 Multi UART

[English](README.en.md) · [返回 Fastboot 修改方法](../../README.md#二fastboot-修改方法)

为 Sony ILCE-7M4（A7 IV）提供四种 root 终端接入方法。普通系统以官方 **6.02** 的已核对 ELF 布局为基线，Telnet/USB 创建代码来自官方 **1.05 的 p15**；UART 使用 p1 原有的 BusyBox ash。

| 接入方式 | 连接与认证 | 所在环境 | 修改方法 |
|---|---|---|---|
| Telnet | IP 网络 TCP 23；免口令、明文 | 普通拍摄系统 | [恢复 ULOGIO 网络和 USB 终端](telnet-usb.md) |
| USB Shell | Sony 服务 USB bulk；Senser 服务认证 | 普通拍摄系统 | [同一套 ULOGIO 修改](telnet-usb.md#开启与关闭-usb-终端) |
| SSH / SFTP | IP 网络 TCP 22；公钥认证，登录名 service、实际 UID/GID 0 | 普通拍摄系统 | [复用 sshd，补齐启动与账号](ssh-sftp.md) |
| Multi UART | Multi 线、RP2040 和 Cetus 桥接；115200 8N1 | p1 更新系统 | [建立独立 UART root shell](uart.md) |

SFTP 是 SSH 的子系统，Wi-Fi 是 IP 网络承载，不分别增加一种 Shell。Sony USB bulk 终端不依赖 USB 网卡；Multi UART 在相机侧走 CP 串口，不是普通 USB 终端。

这些文档是**离线固件集成方法**：给出修改位置、组件身份、启动条件、接入协议和回退方法。先用自己的分区备份重建候选，再部署；登录命令用于已经包含对应修改的相机。组件哈希和地址类型集中在 [reference-layout.json](reference-layout.json)，验证边界见 [validation.md](validation.md)。

## 选择与组合

- **正常拍摄时需要网络或 USB root 终端**：ULOGIO 方法恢复 Telnet 与 USB 两个入口，两者已验证可共存。
- **需要加密登录、PTY 或文件传输**：SSH 方法复用现有 sshd，支持公钥认证和 SFTP。
- **需要不依赖普通 p15 系统的维护终端**：Multi UART 方法在更新环境运行，启用期间不能拍摄；移除启动标记后恢复普通启动。

ULOGIO 与 SSH 是两份独立的 p15 修改方案。它们的叠加未做整合实测；不要用其中一份整分区镜像覆盖另一份后，仍认为两套功能都保留。UART 新代码位于 p1，切换启动模式还需要修改 p2 标记，不能称为整个操作“只写 p1”。

## 共同的集成流程

1. 按[接线](../../docs/wiring.md)和[环境配置](../../docs/setup.md)准备 Multi 启动桥与 Fastboot。通过[进阶维护入口](../../advanced/)保存自己的完整备份，并保留同机原分区供回退。
2. 从本机备份提取目标文件。根据具体组件完整 SHA-256 核对布局，离线修改 ELF 和文件系统；适用性取决于字节布局，不能只看相机显示的版本号。
3. 保持非目标文件、权限、所有者、链接、文件系统计数及物理分区尾部。查询 `partition-size:nflasha1` / `partition-size:nflasha15` 确定实际长度；包内较短镜像不等于完整物理分区。
4. 在 Fastboot 写入对应候选，完成**独立完整回读**后再正常启动。若写入已经完成而回读中断，只续读，不为读失败重复刷写。
5. 用命令返回、实际 UID/GID、退出重连和对应传输验收；普通模式另确认拍摄、保存、回放。只出现启动 marker、TCP 握手或 `Terminal activated` 不算终端验收。

例如写入已经完成离线验证的普通 p15 候选：

```powershell
fastboot.exe getvar product
fastboot.exe getvar partition-size:nflasha15
fastboot.exe flash nflasha15 .\local\nflasha15.modified.img
# 完整回读与候选比较后再 reboot。
```

读回协议沿用已配套的 Fastboot payload：`oem partition dump <name> <offset> <size>` 的偏移和长度是**十六进制的 512 字节扇区**，然后用 `get_staged`取出该段。按不超过 16 MiB 的范围读取，拼接至查询得到的物理长度，再比较整幅 SHA-256。不要把字节数直接填进扇区参数。

## 参考与归属

[ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE) 提供 BootROM/Fastboot、RP2040 与 Cetus/SPI 参考；[Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) 提供 Sony 服务协议参考；平台参考见 [Sony-ILCE-7M4-Linux](https://github.com/DavidBuchanan314/Sony-ILCE-7M4-Linux)。本方法不分发 Sony 固件、机身镜像、个人密钥或无明确再分发许可的上游二进制。资源来源继续按仓库[第三方说明](../../THIRD_PARTY_NOTICES.md)处理。
