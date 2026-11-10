# macOS 后续适配

当前没有可用 Mac，禁止宣称 macOS 可写入。平台检测返回 `PLATFORM_NOT_VALIDATED`，不加载 Windows Provider，不安装驱动、不发送 USB 命令。

共用部分：Agent 待办／任务编号、诊断、补丁匹配、相机端 worker 和完整回读规则。

需实现的主机接口：

- 设备枚举和稳定机身标识、普通与服务身份匹配。
- libusb／系统 USB 接口接管与释放；调查占用、授权、重新枚举，不假定 sudo 足以解决所有设备占用。
- 对应架构的 Python、libusb、压缩与构建组件，以及资产和许可清单。
- 原生可信入口、受保护执行目录、授权与独立后台进程；不能沿用 Windows EXE、SID、计划任务、WinUSB 或 msvcrt。
- macOS 目录、锁、断连后收尾和存储连接恢复。

验收顺序：平台组件启动 → 无设备检查 → 真实 M4 枚举 → 普通／服务切换和退出 → 完整只读 p1 与恢复 → 单次补丁和独立回读 → 菜单交接与实际安装。只开放通过验收的 OS 版本／架构；Intel 和 Apple Silicon 分别记录。

libusb 后端参考：https://github.com/libusb/libusb/blob/master/libusb/os/darwin_usb.c 。借鉴接口实现不等于已验证 M4 更新链。
