# 0. 一键救砖：通过 fastboot 触发 SD 更新

[English](README.en.md) · [返回首页](../../README.md)

相机已能进入 **fastboot** 时，备份当前机身、准备内部恢复标志，重启后由机内 SD 更新器安装**卡槽 1 根目录的 `BODYDATA.DAT`**。这是恢复入口工具，不含固件包。

**只支持 ILCE-7M4，以及[配置文件](../../a7m4/profiles/sd-recovery.json)列出的精确更新器 initrd SHA-256。当前清单只有一份此前验证过的修改版更新器，不代表所有原厂或自定义固件均受支持。未知环境会停止，不能仅为绕过报错而添加哈希。** 更新器、SD 读取链或更早启动阶段损坏时，此方法可能无法使用。

固件更新和恢复必须使用**电量充足的索尼原厂电池**，保持可靠供电。请先读[首页风险和备份要求](../../README.md#先读风险与备份要求)。本入口会自动准备并写入恢复标志、核对读回并重启，没有第二次交互确认；务必先准备好正确的 DAT。

## 使用方法

1. 按[环境说明](../../docs/setup.md)安装 Python 3.11+ 和本仓库。完整资源包已注册的用户直接使用；否则按下方“仅准备救砖依赖”注册 fastboot。
2. 将适用于自己机身、且能被**机内现有更新器接受**的正常升级包命名为 `BODYDATA.DAT`，放到 SD 卡根目录，插入**卡槽 1**。电脑端不会替你选择 DAT，也不会读取或验证卡内文件。
3. 用已验证的 [Multi 接口 / RP2040 接线与启动方案](../../docs/wiring.md)让相机进入 fastboot，并连接相机的数据 USB；只连接这一台相机。**本脚本不负责进入 fastboot**，不安装驱动、不操作串口。
4. 双击[只检查 fastboot 连接](../../advanced/只检查fastboot连接.bat)，确认型号查询成功。此入口只枚举设备并查询 `product`，不读取分区、不写入、不重启。检查后及时运行恢复，避免相机长时间空闲后退出 fastboot。
5. 双击[一键救砖：从 SD 卡恢复](../../advanced/一键救砖_从SD卡恢复.bat)。自动备份、检查环境、写入一次设置候选、完整读回验证，然后发送一次普通重启。等待相机执行更新，期间保持供电，不拔卡、不强制退出。
6. 更新完成后，检查取景、菜单、报告版本及正常关机再开机。需要确认 CP NOR 修复时，还应独立读取更新日志或回读 NOR；脚本退出成功只表示**已触发更新，待相机确认**。

等价命令，从仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe -m a7m4.recover_sd --check-connection
.\.venv\Scripts\python.exe -m a7m4.recover_sd
```

BAT 使用仓库 `.venv`，也可用环境变量 `A7M4_PYTHON` 指定解释器。无需修改包含本机绝对路径的配置。默认备份和日志在忽略目录 `local/sd-recovery/sessions/时间_编号/`；可用 `--sessions` 指定另一个本地父目录。目录包含机身个体数据，不能提交到公开仓库。

### 仅准备救砖依赖

已有完整 `vendor/manifest.local.json` 时无需重新注册。尚无资源包且相机已经能进入 fastboot 时，仅需自行取得 [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools) 的 fastboot 主机程序及该发行包配套 DLL、许可说明，按如下布局放好：

```text
local/recovery-resources/bin/fastboot.exe
local/recovery-resources/bin/AdbWinApi.dll       （该发行包需要时）
local/recovery-resources/bin/AdbWinUsbApi.dll    （该发行包需要时）
```

```powershell
.\.venv\Scripts\python.exe tools/register_resources.py local/recovery-resources --recovery-only
```

这一步只复制本地文件并登记 SHA-256，不访问相机。不要混用不同发行包的 DLL。精简资源包缺少启动 payload、驱动和 SquashFS 工具，因此一般维护入口的 `doctor` 会报告这些资源缺失；救砖入口只检查 fastboot 及已登记的相邻 DLL。仓库不捆绑外部二进制。

## 工作原理

| 阶段 | 脚本或相机做什么 | 边界 |
|---|---|---|
| fastboot | 识别唯一一台 ILCE-7M4，检查分区表并备份 `nflashaB0/B1/1/2/8/13` | 六个分区，**不是全机备份**，不含物理 CP NOR |
| 更新环境 | 从 `nflasha1` 读取 `/boot/initrd.img`，核对 `p1chksum` 内 MD5 及配置白名单 SHA-256 | 不替换公钥、不修改 `verifyKey`，不临时绕过检查 |
| 恢复入口 | 在 `nflasha2` 的 FAT 中，将 `updater/dat4` 两字节打包 BCD 临时设为 `0.00`，准备空文件 `updater/mode`、`updater/mode5` | 机内挂载路径为 `/setting/updater/…`；这些文件**不放在 SD 卡上** |
| 写入核验 | 再查同机 B0/B1/设置及分区表，只允许写本次候选到 `nflasha2`，完整 20 MiB 读回一致后重启 | 保留 FAT、根目录、`Backup.bin` 和其他原文件，不扩容、不重建文件系统 |
| 机内更新 | 原有 SD 更新器读取卡槽 1 `BODYDATA.DAT`，执行其包校验和更新流程 | 由正常更新链处理所需 eMMC/NOR 更新；主机不直接写 NOR，不保证任意包都更新 NOR |
| 完成确认 | 检查更新日志、正常启动及必要的分区/NOR 回读 | 主机结果始终保留 `update_completed=false`，直到另外取得机内结果证据 |

`dat4=0.00` 用于满足原更新器的版本比较，使同版本重装或恢复回退有机会进入安装流程。它**不改变签名**；DAT 仍须满足已安装更新器的密钥、机型和其他校验规则。安装目标由卡内 DAT 决定，可能覆盖现有修改；成功安装后的实际版本以机内结果为准。若更新失败，临时版本和恢复标志可能仍保留，请保留本次备份排查。

两份空标志仅使用既有目录的最多两个 32 B 空槽；允许变化范围为 DAT4 的 2 B 和这两个目录项。存在其他更新模式、异常标志、空间不足、未知布局或文件系统错误时停止。候选、备份或设备状态在写前发生变化时也停止。

## 错误处理

| 状态 / 错误 | 含义与下一步 |
|---|---|
| `CONNECTION_OK` | 只读连接检查成功；还没有执行救砖 |
| `USB_TIMEOUT` / `USB_TRANSPORT` | 通信未得到有效应答，不能当作机型错误；重新确认 fastboot、线缆、驱动和供电，先再做只读检查。错误 121 本身不能确定唯一原因 |
| `MODEL` / `UPDATER_PROFILE` | 型号或更新环境不受支持；保留日志并审查，不删除门控 |
| `STOPPED_KEEP_FASTBOOT` | 恢复流程在重启前停止；结合 `flash_attempted`、`readback_verified` 判断阶段，保留目录。此状态不保证 USB 仍在线或相机确实留在 fastboot |
| 写入或读回失败 | 不自动重试、回滚或重启；不要凭错误码推断“完全没写” |
| `REBOOT_OUTCOME_UNCERTAIN` | 已尝试发重启，结果未知；先观察相机，不能直接重刷 |
| `SD_UPDATE_TRIGGERED_PENDING_CAMERA` | 主机写后校验通过且重启命令返回；仍需机内完成更新并验收 |

修复后的传输层会识别“进程退出 0，但输出 `FAILED (…)`”的情况；不再把 USB 121 超时误报为不支持的机型。每次写入授权在命令执行前消耗，潜在部分写入后不会自动重试。

## 验证范围与源码

- [核心实现](../../a7m4/sd_recovery.py) · [命令入口](../../a7m4/recover_sd.py) · [更新环境白名单](../../a7m4/profiles/sd-recovery.json)。复用公开主机的 FAT、通用校验和 fastboot 传输模块，未改变其他五项补丁配方。
- [恢复流程测试](../../tests/test_sd_recovery.py)与[连接错误回归测试](../../tests/test_sd_recovery_connection.py)覆盖候选差分、BCD、同机绑定、备份短读/篡改、未知环境、一次写入、写失败、读回失败和重启结果未知；使用合成镜像和模拟后端，不连接设备。
- [公开适配测试](../../tests/test_sd_recovery_public.py)验证资源登记、真实 BAT 的参数/中文路径、未知 profile 拒绝和默认日志边界；[发布验证记录](validation.md)区分历史实机路线与本次离线适配。
- 此前已有同机 MODE5 恢复成功记录，包括日志中的 `NOR_FLASH END`、`WRITE NOR_IMG END`、`User Update OK`，以及 NOR 回读与正常取景反馈。**不等于本次公开适配版已重新完成实机救砖，也不代表任何变砖原因都能恢复。**

运行测试不会操作相机：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pytest -q tests/test_sd_recovery.py tests/test_sd_recovery_connection.py tests/test_sd_recovery_public.py
```
