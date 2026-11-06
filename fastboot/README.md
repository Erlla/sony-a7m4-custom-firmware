# Fastboot 维护脚本与启动文件

**刷写可能损坏相机或丢失数据。仅适用于 Sony ILCE-7M4（A7 IV / A7M4），以官方 V6.02 为修改基线。先备份本机，使用原厂电池，写入期间保持供电。**

需要 Windows 10/11、Python 3.11+、Multi 接口刷机线和 RP2040-Zero。[接线说明](../docs/wiring.md)。

## 文件与操作

| 文件或入口 | 用途 |
|---|---|
| [fastboot.bin](assets/fastboot.bin) | 加载到相机 RAM 的 Fastboot 服务程序 |
| [uart_boot.ino.uf2](assets/uart_boot.ino.uf2) | RP2040-Zero 串行启动桥，首次按住 BOOTSEL 接入后写入 |
| [进入fastboot.bat](../advanced/进入fastboot.bat) | 启动相机 Fastboot 服务，不读取或刷写分区 |
| [退出fastboot开机.bat](../advanced/退出fastboot开机.bat) | 发送 reboot，让相机退出 Fastboot |
| [备份全部数据.bat](../advanced/备份全部数据.bat) | 保存 payload 提供的全部 eMMC 分区，包括 boot0/boot1、分区表和校验值 |
| [查看或设置固件版本.bat](../advanced/查看或设置固件版本.bat) | 查看版本，或修改相机报告的版本号 |
| [刷入验签跳过版更新器.bat](../advanced/刷入验签跳过版更新器.bat) | 从本机备份生成自有公钥及 verifyKey 补丁，确认后刷写并读回 |
| [恢复官方验签公钥.bat](../advanced/恢复官方验签公钥.bat) | 从同机官方原始备份恢复更新器公钥及验签代码 |

“全部数据”指此 payload 能读取的 eMMC 分区；独立 CP NOR、其他 MCU 和全部硬件状态不在该备份范围内。版本修改只改变报告版本，不安装其他固件功能。自有公钥用于更新包 RSA 验签，verifyKey 补丁不会取消该 RSA 验签。

## 准备环境

1. 完整解压 Release 压缩包，双击根目录 `setup.bat` 安装 Python 依赖。
2. 自行准备 [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools)、[Google USB Driver](https://developer.android.com/studio/run/win-usb) 和 [squashfs-tools-ng 1.3.2](https://github.com/AgentD/squashfs-tools-ng/tree/v1.3.2) 的 Windows 工具及许可文件。这些外部发行包未重新打包。
3. 登记资源（路径替换为本机实际目录）：

```powershell
.\.venv\Scripts\python.exe tools/prepare_fastboot_resources.py --platform-tools C:/tools/platform-tools --usb-driver C:/tools/usb_driver --squashfs C:/tools/squashfs-tools-ng
.\.venv\Scripts\python.exe -m a7m4 doctor
```

SquashFS 目录可直接包含 EXE/DLL，或使用其原发行包的 `bin/` 结构。完整资源要求见[环境说明](../docs/setup.md)。UF2 内的 UART_TX 是历史构建选项；这些维护入口只使用启动桥命令 1–5，不提供交互 UART 发射。

## 使用顺序

进入 Fastboot → 备份全部数据 → 按需查看/设置版本或修改更新器 → 退出 Fastboot。

涉及修改的入口会在本次连接中先完成全部 eMMC 分区备份，再显示待写内容并要求输入确认文字。没有随包分发预制机身分区镜像。恢复官方验签时，应选择修改前、具有官方公钥和原始验签代码的同机完整备份；修改后的备份不能充当官方原件。

源码分别位于 [a7m4](../a7m4/) 和 [source](source/)。启动文件的来源、构建资料及许可范围见 [SOURCES.md](SOURCES.md)，文件身份见 [assets/manifest.json](assets/manifest.json)。

## 命令行

```powershell
python -m a7m4 enter
python -m a7m4 maintain --action backup --already-fastboot
python -m a7m4 maintain --action set_version --already-fastboot
python -m a7m4 maintain --action unlock --already-fastboot
python -m a7m4 maintain --action restore_official --already-fastboot
python -m a7m4 exit
```
