# M4 相机工具 1.0.0 源码

[English](README.en.md) · [用户指南](../TOOL-1.0.0.md) · [安装方法](../README.md) · [修改原理](../IMPLEMENTATION.md)

通过普通 USB 为 Sony ILCE-7M4 准备更新环境，再由用户在相机菜单中安装 SD 卡上的固件。当前版本已获用户测试通过反馈。本次同步源码，**暂不发布 Release 分发包**。

软件提供“写入补丁”和独立的“恢复普通 USB”。用户自行放置安装包，软件不读取、检查、复制或绑定 DAT。完整固件暂不提供，待功能全部更新完毕后再提供。

## 当前行为

- 首次使用按 Windows 用户和机身建立配置。匹配安装及空任务目录可复用，只补建缺失任务；运行中任务和未知操作不会作为残留删除。
- 任务账户名和 SID 按解析后的身份比较。具体未通过字段写入私人安装收据。
- 普通／服务 USB 身份均准备 WinUSB。信任 libwdi 自签名证书需要明确同意，默认取消；这些不是索尼或微软发布者证书。
- 补丁与菜单期间复用驱动。完整 p1 备份、按内容匹配、单次写入和独立完整回读保留；未知布局停止，显示版本号不设白名单。
- 固件操作完成与电脑盘符恢复分开记录。每次打开新界面会话，保留备份和日志，结果未知的任务不自动重发。
- 日常操作只执行完整性校验，不运行 ARM64 仿真或故障注入。

## Windows x64 构建

需要 Python 3.12+ 和 Windows 自带的 .NET Framework C# 编译器。构建不提权、不访问相机、不安装驱动。运行组件独立提供，不作为源码二进制提交。

`assets-files.json` 锁定 **3257 个文件、9 个分组**。普通／服务的 INF、CAT 和共享共同安装器共 6 个文件，全部属于 `tools/driver` 资产分组；不再依赖研究目录或源码里的额外二进制。其余分组摘要保持。

在本目录使用另行取得的可信便携包：

```powershell
py -3 prepare_assets.py --from-package D:\M4-portable.zip --output D:\M4-runtime
py -3 build.py --assets D:\M4-runtime --output D:\M4-build
D:\M4-build\M4相机工具.exe --verify
```

包含全部锁定文件的便携 ZIP 也可直接传给 `build.py --assets`。输入 app、state 和固件均忽略，app 始终来自当前源码；输出必须是新目录。来源和许可见 [THIRD_PARTY.md](THIRD_PARTY.md) 与 [assets-sources.json](assets-sources.json)。精确导出不是从每个上游归档下载重建的完整配方。

原生入口在 Python、CLR 和管理员授权前核对文件与导入目录；正常运行使用受保护的 ProgramData 副本，状态与缓存留在解压目录。只读句柄约束运行中的内容替换。`--verify` 只校验本地文件，不提权或建立设备会话。可信来源的启动 EXE 仍是信任起点；未提供 Authenticode 签名，完整性检查不能代替安全软件判定。

## 开发验证

使用独立测试构建，测试后的 state 不能分发：

```powershell
D:\M4-build\runtime\python\python.exe -I -B tests\run_clean_setup.py --package D:\M4-build
D:\M4-build\runtime\python\python.exe -I -B tests\test_driver_reuse.py --package D:\M4-build
powershell -NoProfile -ExecutionPolicy Bypass -File tests\test_driver_trust.ps1 -Package D:\M4-build
```

完整初始化替身从无工具配置、任务、相关驱动和证书状态开始，并模拟 Windows 把 SID 登记读回为账户名。可选 `test_task_user_readback.ps1 -Source <源码目录>` 需要已有真实参考任务，仅只读观察，不能当作空白安装测试。实际 UAC、ACL、驱动绑定和相机结果须另行现场验收。

## 致谢与范围

免 Fastboot 方案参考 [YuuLuo/a7c2-camera-tools](https://github.com/YuuLuo/a7c2-camera-tools)；驱动复用和独立恢复参考 [QAQLeonard/a7c2-fl23-research](https://github.com/QAQLeonard/a7c2-fl23-research)。其余来源见 [REFERENCES.md](../../REFERENCES.md)。

源码不含机身绑定、备份、日志、私钥、完整固件或相机固件库。第三方组件沿用各自许可。
