# M4 相机工具 / AI Agent 1.03 源码

桌面端与 AI Agent 使用本目录的同一套补丁、连接和恢复逻辑。普通用户下载成品，不需要 Python、Git 或编译器。

- [桌面下载](https://github.com/Erlla/sony-a7m4-custom-firmware/releases/tag/A7M4-ToolKit-v0.1.2)
- [AI Agent 入口](../agent/README.md) · [操作提示词](../agent/PROMPT.zh-CN.md) · [资源清单](../agent/resources.json)
- [English](README.en.md) · [构建与发布](RELEASING.md) · [源码来源](SOURCE.json)

## 1.03 改进

1. 普通 USB 通信等待在一个 PowerShell 进程内轮询，每轮只枚举一次 PnP，结束后保存一次快照。补丁与菜单之间继续复用已核对驱动，不等待盘符。
2. p1 已完成、菜单会话尚未开始时，桌面端提供“检查连接并继续菜单”；Agent 返回当前待办。先核对原证据及同一机身，连接可用则仅创建新的菜单尝试，不再次派发 p1 writer。连接仍异常时保留独立 USB 恢复。
3. 描述符错误区分设备未枚举、LANGID 缺失、身份字符串缺失、底层传输失败；保留实际阶段、errno、libusb 错误码和等待次数，不把所有错误都说成菜单失败。
4. 独立 Agent 1.00/1.01 的已停止菜单任务可在原路径保留 state 后升级并查询原 job；旧运行中任务、未知写入结果和未知构建仍不重新派发。

固件兼容性按实际库内容判断，显示版本号不设白名单。完整备份、单次按需写入、独立完整回读、菜单就绪检查保持。没有移植 A7C2 的认证重试、服务协议或读写补丁字节。

## 使用范围

桌面默认启动 M4相机工具.exe；Agent 调用同一原生入口的 --agent doctor/status/start/resume/recover-usb。软件不读取、检查、复制或安装 DAT，卡升级由用户在相机上执行。每次操作只做完整性校验，不运行开发故障测试。

普通连接恢复、p1 完成、菜单就绪和用户报告安装完成分别记录。驱动任务要求 Windows 重启时必须真正重启电脑。只读检查失败须有清理证据，未知写入结果不能靠删除状态解除。

首次初始化复用匹配配置、补齐缺失任务；普通/服务身份均准备驱动。新电脑的证书和 UAC 需要用户自行确认。原生入口保留完整性检查、受保护运行目录和读句柄缓存；未提供 Authenticode 签名，完整性校验不代表杀毒软件不会误报。

## 构建

开发电脑需要 Windows x64、Python 3.12+ 和系统 C# 编译器；用户运行包自带依赖。

```powershell
py -3 -I -B prepare_assets.py --download --cache D:\M4-cache --output D:\M4-assets
# 也可 --from-package D:\可信便携包.zip，离线提取锁定资产。
py -3 -I -B build.py --assets D:\M4-assets --output D:\M4-build
D:\M4-build\M4相机工具.exe --verify
py -3 -I -B tests\run_offline.py --package D:\M4-build --report D:\M4-tests.json
```

assets-files.json 锁定 3257 文件、9 个分组。输入包只提供匹配资产；app 来自当前源码，不复制旧状态和固件。构建只允许新输出目录。版本统一为 **1.03**，Agent build_id 为 **1.03-agent-20261111-r1**。历史桌面 1.02 与独立 Agent 1.00/1.01 是不同构建，不能仅按数字混用任务。

包级测试使用一次性临时副本和替身，不得对用户安装目录运行。详见[离线检查](tests/OFFLINE.md)与[故障矩阵](tests/FAULT_MATRIX.md)。干净 Windows、实际 UAC/驱动和相机安装仍需分别验收；离线 PASS 不等于实机通过。

## 参考与许可

免 Fastboot 方案参考 [YuuLuo/a7c2-camera-tools](https://github.com/YuuLuo/a7c2-camera-tools)。连接状态、驱动复用及恢复分离参考 [QAQLeonard/a7c2-tools](https://github.com/QAQLeonard/a7c2-tools/tree/ef7db116e13e37be91e9af20360dc9bba8d64a9b)。本轮独立实现 M4 主机侧改进，没有复制其受不同许可约束的源码。

第三方运行组件沿用各自许可，见 [THIRD_PARTY.md](THIRD_PARTY.md)。公开源码与运行包不含完整固件、相机固件库、机身绑定、p1 备份或私人日志。
