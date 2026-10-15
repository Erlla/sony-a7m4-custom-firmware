# 环境与外部资源

[English](setup.en.md) · [返回](../README.md)

主机工具只依赖 Python 3.11+、pySerial、pyelftools 和 cryptography，不需要 GUI、完整逆向工作区或串口控制台。BAT 源码 UTF-8、CRLF；Python/Markdown/JSON 为 UTF-8。

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

以后命令中的 `python` 指这个虚拟环境的解释器，可先运行 `.\.venv\Scripts\Activate.ps1`，或始终使用完整相对路径。BAT 自动寻找仓库 `.venv`；也可设 `A7M4_PYTHON` 为其他合适的 Python。

## 自行取得的二进制

按如下相对布局准备 `local/resources/`，不是相机分区镜像：

```text
local/resources/
  bin/fastboot.exe
  bin/AdbWinApi.dll              # 该 fastboot 发行包需要时
  bin/AdbWinUsbApi.dll           # 该 fastboot 发行包需要时
  bin/fastboot.bin              # 相机端启动 payload
  bin/uart_boot.ino.uf2          # RP2040 启动桥
  driver/android_winusb.inf
  driver/...                    # 原包对应 catalog、DLL、架构目录
  squashfs/sqfs2tar.exe
  squashfs/tar2sqfs.exe
  squashfs/...                  # 发行包依赖 DLL 及许可文件
```

来源与要求：

| 资源 | 获取或构建方式 |
|---|---|
| fastboot 主机程序 | [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools)，或 [AOSP 源码](https://android.googlesource.com/platform/system/core/+/refs/heads/main/fastboot/) 自行构建；保留对应 DLL/notices |
| 相机 `fastboot.bin` | [ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE) 的 `payloads/fastboot`，按其 Makefile 用 AArch64 工具链构建；源码版本和功能需匹配本文主机协议 |
| RP2040 UF2 | 同一项目的 `tools/uart_boot`，`make setup` 后 `make build`；板型 Waveshare RP2040-Zero；保留默认 `-DOPEN_DRAIN`，无需开启 `UART_TX` |
| USB 驱动 | [Google USB Driver](https://developer.android.com/studio/run/win-usb) 原包，INF 必须包含 `VID_18D1&PID_4EE0`；遵守 SDK 条款。若已安装正确驱动可直接使用，仍保留原包供检查 |
| SquashFS | [squashfs-tools-ng 1.3.2](https://github.com/AgentD/squashfs-tools-ng/tree/v1.3.2)，提供该版本的 `sqfs2tar`/`tar2sqfs` Windows 构建及运行库，用于保留元数据地重建更新器 |

主机接受 `uart_boot 1` 与 `uart_boot 2` 握手，只使用共有命令 1–5。相机 payload 须支持 `getvar product`、`oem partition`、`oem partition dump`、`get_staged`、完整分区 `flash` 和 `reboot`，并产生 `[mira] fastboot ready` 日志。代码还限制 payload 小于 `0xF000` 字节，避免越过已审查 SRAM 窗口；不兼容时应审查源码和布局，不应直接取消限制。

本地历史 payload/UF2 与上游 HEAD 未证明可复现一致。参考来源中记录了已审查 checkout，不意味着任意最新构建都经过实机验证。不要从不明网盘混用二进制。

注册后，每个资源使用前会核对 SHA-256：

```powershell
python tools/register_resources.py local/resources
python -m a7m4 doctor
```

已有旧工具目录和 SquashFS 工具目录时，也可用 `tools/import_local_resources.py --legacy-tool <旧工具目录> --squashfs <SquashFS目录>` 创建本地资源包。两个导入方式均只生成忽略的 `vendor/local/` 与 `vendor/manifest.local.json`，不授予这些资源再分发许可，也不复制机身镜像或密钥。

进入 fastboot 时，如确实需要安装驱动，工具只请求 Windows 以管理员运行 `pnputil`，不关闭驱动签名检查、不建立常驻提权任务。第一次 RP2040 安装需要按住 BOOTSEL 插入板子的 USB。先按 [接线说明](wiring.md) 确认硬件。

## 离线固件构建（可选）

只有需要完整 DAT 解码/重封装时才安装额外依赖：

```powershell
python -m pip install -e ".[firmware]"
```

它增加 NumPy（批量块校验）、Dissect extfs/util（按已验证文件 extent 修改 ext 镜像）。单独版本操作、备份和更新器解锁不需要这些依赖。请预留至少 10 GB 临时磁盘空间；完整构建会保留原明文、修改后明文、未签名中间包和最终包。
