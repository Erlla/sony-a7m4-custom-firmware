# M4 相机工具源码

[English](README.en.md) · [安装方法](../README.md) · [修改原理](../IMPLEMENTATION.md)

这是 **M4 相机工具 1.00** 的当前源码：简化桌面界面、Windows 驱动准备与独立 USB 恢复、完整 p1 读取、按内容生成补丁、单次写入与独立完整回读、两处限时 RAM 菜单窗口，以及中断任务的证据校验。

不附完整固件、相机库、预编译工作器、机身绑定、备份或运行状态。用户自行放置 SD 卡安装包，软件不检查或复制安装包。每次启动使用新会话，历史任务不影响新会话；备份与日志保留。参考方案致谢：[YuuLuo/a7c2-camera-tools](https://github.com/YuuLuo/a7c2-camera-tools)。

## 目录

| 路径 | 内容 |
|---|---|
| `app/ui`、`app/workflow` | 单窗口界面、补丁／菜单流程、独立 USB 恢复和本地菜单准备续接 |
| `app/driver`、`app/driver_restore` | Windows 管理员任务、普通驱动恢复 |
| `app/reader`、`app/writer`、`app/native` | 每轮按随机数与摘要生成的原生读取／写入任务及引导 |
| `app/receiver_stock`、`app/receiver_custom`、`app/receiver_shared` | 当前已审查更新器的兼容性和 p1 修改 |
| `app/menu_stock`、`app/menu_custom`、`app/menu_transport` | 菜单任务、短指令锚点与协议；不包含完整固件库 |
| `build.py`、`Launcher.cs` | 独立便携构建、发布完整性清单和 Windows 启动器 |
| `dependencies.json` | 外部运行组件的版本与目录摘要锁 |
| `tests` | 只使用本地材料和模拟 Windows 状态的开发检查 |

未使用的实验安装入口和固定实验版本分支不在公开源码中。当前界面可达流程、原生工作器和证据门禁保留；本仓库不引入研究日志作为运行依赖。

## 构建 Windows x64 便携目录

需要 Windows x64、Python 3.12 或更新版本用于构建，以及 Windows 的 .NET Framework C# 编译器。构建过程不请求管理员权限、不接触相机，也不安装驱动。

第三方运行组件独立提供，不随源码克隆。准备与 `dependencies.json` 完全匹配的干净运行目录或工具便携 ZIP，包含 `runtime/python`、四个 `vendor` 目录、`tools/zig`、`tools/squashfs`、`tools/driver` 和 `licenses`。各组的文件名与内容摘要必须匹配；版本字符串相同并不足够。来源和许可见 [THIRD_PARTY.md](THIRD_PARTY.md)。本次源码同步没有发布运行时二进制附件，也没有创建 GitHub Release。

在本目录执行：

```powershell
py -3 build.py --assets D:\M4-runtime --output D:\M4-build
# --assets 也可指向包含上述目录的干净便携 ZIP。
D:\M4-build\M4相机工具.exe --verify
```

输出目录必须不存在。构建器只从输入复制锁定的运行组件，始终使用本目录的 app 源码，不读取输入中的 app、state 或固件。它生成统一 `app/release.json`、编译启动器，并执行仅本地完整性检查。桌面图标属于可选资源，不影响操作。

完成后打开输出目录的 EXE。不要直接运行源码中的 entry.py：它需要构建时生成的完整性清单与运行组件。不要将构建覆盖到正在使用或存在未完成任务的目录。

正常启动 EXE 时会请求 Windows 管理员权限，取消授权则退出；已经具有管理员权限时直接打开。`--verify` 仅做本地完整性检查，不请求提升权限，也不建立操作会话。

每次打开均回到“写入补丁”初始界面，“恢复普通 USB”可直接点击。每次启动在 `state/sessions/` 创建独立目录，同一窗口的后台子进程继承该会话。历史任务不再作为下次启动的流程入口或写入门禁；机身配置、备份和日志继续保留。全局进程锁和相机实时状态检查仍生效，每次新操作重新完整读取当前 p1。

驱动重绑后的普通 USB 字符串检查最多等待约 8 秒，只重试标准描述符读取，并在每次失败后释放句柄、重新枚举。语言码取自设备实际返回的列表，型号、序列号和已绑定机身仍须一致；不使用固定语言码或 Windows 文本替代实际 USB 身份。底层 USB 错误单独记录。菜单准备阶段若在认证前持续读不到描述符，自动恢复普通驱动并停止该轮菜单；等待重新插拔时按提示确认，不会重发补丁或菜单任务。

## 离线开发检查

以下命令只用于新构建的测试目录，不能对用户运行目录执行；它们会生成虚拟任务和绑定。不会调用 Windows 驱动或相机，但会留下测试 state，测试目录不能直接分发。

```powershell
D:\M4-build\runtime\python\python.exe -I -B tests\test_usb_recovery.py --package D:\M4-build
D:\M4-build\runtime\python\python.exe -I -B tests\test_local_failure.py --package D:\M4-build
D:\M4-build\runtime\python\python.exe -I -B tests\test_state_io.py --package D:\M4-build
D:\M4-build\runtime\python\python.exe -I -B tests\test_startup_session.py --package D:\M4-build
D:\M4-build\runtime\python\python.exe -I -B tests\test_usb_identity.py --package D:\M4-build
D:\M4-build\runtime\python\python.exe -I -B tests\test_menu_seal.py --package D:\M4-build --lineage stock
D:\M4-build\runtime\python\python.exe -I -B tests\test_menu_seal.py --package D:\M4-build --lineage user
```

检查覆盖初始恢复按钮、驱动状态与未决任务保护、菜单材料生成／封存／校验，以及本地失败的续接边界。菜单封存测试使用虚拟接收端证明，不能替代实机验证。构建成功或菜单出现也不等于 SD 固件安装成功。日常补丁只执行完整性校验，不运行 ARM64 仿真或故障回归。

状态 JSON 在 Windows 使用可共享删除的读取句柄和 ReplaceFileW 原子替换；短暂占用只对本地发布做有时限重试。创建初始记录时失败，须先核对双份记录、事件和本轮时间，证明没有进入设备步骤后才能结案并使用独立 USB 恢复。此逻辑不会重试驱动派发、原生 START 或 COMMIT。

本项目源码沿用仓库 [LICENSE](../../LICENSE)；第三方运行组件继续适用各自许可。完整固件暂不提供，待功能全部更新完毕后再提供。
