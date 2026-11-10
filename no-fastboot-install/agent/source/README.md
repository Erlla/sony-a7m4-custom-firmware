# M4 Agent 工具 1.01 源码

独立 Agent 工具的当前源码快照，构建标识 `1.01-agent-20261111-r1`。使用[正式 Agent 入口](../README.md)；运行包已在[Release](https://github.com/Erlla/sony-a7m4-custom-firmware/releases/tag/A7M4-Agent-ToolKit-V1.01)提供。普通用户无需克隆源码或现场构建。

[English](README.en.md) · [安装方法](../../README.md) · [修改原理](../../IMPLEMENTATION.md) · [命令规则](../PROMPT.zh-CN.md)

本目录独立于桌面源码，共用其补丁与恢复实现。Agent 通过原生 EXE 的 `--agent` 入口运行包内 Python，提供后台任务、待办编号、持续进度与独立 USB 恢复。程序不读取、检查或复制卡上的 DAT；下载固件和配套素材由 Agent 按用户选择处理。

本构建修正了 p1 完成后的菜单续接：普通 USB 恢复后保留原任务，为新菜单 attempt 重新封存计划并执行当前 p1 预读。日常不重放 p1 writer，旧计划不覆盖。构建来源记录见 [SOURCE.json](SOURCE.json)。离线检查不替代新电脑、真实 UAC、驱动与相机验收。桌面版与 Agent 独立编号，不按版本数字混用任务记录。

## 当前行为

- 首次使用按 Windows 用户和机身建立配置。匹配安装及空任务目录可复用，只补建缺失任务；运行中任务和未知操作不会作为残留删除。
- 任务账户名和 SID 按解析后的身份比较。具体未通过字段写入私人安装收据。
- 普通／服务 USB 身份均准备 WinUSB。信任 libwdi 自签名证书需要明确同意，默认取消；这些不是索尼或微软发布者证书。
- 补丁与菜单期间复用驱动。完整 p1 备份、按内容匹配、单次写入和独立完整回读保留；未知布局停止，显示版本号不设白名单。
- 固件操作完成与电脑盘符恢复分开记录。每次打开新界面会话，保留备份和日志，结果未知的任务不自动重发。
- 日常操作只执行完整性校验，不运行 ARM64 仿真或故障注入。
- 原生只读预检失败后，有限等待同任务、同进程的清理结果；确认完成且菜单窗口未启动时正常退出服务并允许独立 USB 恢复。不重发读取／写入，不把缺少清理证明的历史任务当作已完成。
- 固件库与已支持的 6.02 基线不一致时，日志显示“当前相机固件非6.02版本”，保留实际摘要并停止，不写入补丁。这是库内容兼容性判断，不按版本页标签推断兼容性。
- StageBind 返回需要重启时，在 USB 认证和 p1 读取前停止并提示重启 Windows；重开软件或插拔相机不会清除待重启状态。读取任务开始前的失败可独立恢复 USB，不要求提供尚未生成的写入材料。

## Windows x64 构建

需要 Python 3.12+ 和 Windows 自带的 .NET Framework C# 编译器。构建不提权、不访问相机、不安装驱动。运行组件独立提供，不作为源码二进制提交。

`assets-files.json` 锁定 **3257 个文件、9 个分组**。普通／服务的 INF、CAT 和共享共同安装器共 6 个文件，全部属于 `tools/driver` 资产分组；不再依赖研究目录或源码里的额外二进制。其余分组摘要保持。

在本目录使用另行取得的可信便携包：

```powershell
py -3 prepare_assets.py --download --cache D:\M4-downloads --output D:\M4-runtime
# 已有可信 ZIP 时可改用 --from-package D:\M4-portable.zip，完全离线导出。
py -3 build.py --assets D:\M4-runtime --output D:\M4-build
D:\M4-build\M4相机工具.exe --verify
```

包含全部锁定文件的便携 ZIP 也可直接传给 `build.py --assets`。输入 app、state 和固件均忽略，app 始终来自当前源码；输出必须是新目录。来源和许可见 [THIRD_PARTY.md](THIRD_PARTY.md) 与 [assets-sources.json](assets-sources.json)。精确导出不是从每个上游归档下载重建的完整配方。

原生入口在 Python、CLR 和管理员授权前核对文件与导入目录；正常运行使用受保护的 ProgramData 副本，状态与缓存留在解压目录。只读句柄约束运行中的内容替换。`--verify` 只校验本地文件，不提权或建立设备会话。可信来源的启动 EXE 仍是信任起点；未提供 Authenticode 签名，完整性检查不能代替安全软件判定。

下载器只获取锁定摘要的 USB ZIP，支持断点续传、有限重试和缓存复用；不下载 DAT 或其他路线的组件，不执行远程脚本，不修改代理或 TLS 验证。导出和构建先在独立临时目录完成，失败不留下已发布的半成品，可以使用同一输出路径重试；已存在的安装目录和状态不会被覆盖。两个资产入口共同拒绝 ZIP 重复项、Windows 名称别名、符号链接和目录联接。

**版本区别：** 本目录只生成独立 Agent 1.01，桌面软件保持自己的发布分支。历史桌面 1.00、实验 Agent 1.02 与独立 Agent 1.00 不能仅按数字视为同一个包，需核对完整 build_id 和 ZIP 摘要。3257 个运行资产与原锁匹配，可用于重建，其旧 app 不会被复制。运行版本集中于 `app/product_version.py`，要求与依赖元数据一致；构建时确认 Python 与原生版本和完整性，不通过改清单放行旧包。

## 开发验证

失败时界面和运行记录会保留失败阶段、原始错误及下一步操作。读取器另记录相机端失败步骤、errno、相关 fd 和审计次数；没有取得证据时明确说明原因尚未确定。退出服务或保存日志的后续异常不会覆盖最初错误。菜单未交接不表示补丁失败，也不表示可以安装。

读取器仅对枚举后消失的 loader fd 最多复查三次，每次重新检查 maps 和 fd；写入器仍只检查一次。USB 上传、START、PREPARE、COMMIT 不自动重发，任务标记以排他方式持久保存。故障模拟只在开发测试中执行，正常使用仍执行完整性校验、完整备份和独立回读。场景见 [故障测试矩阵](tests/FAULT_MATRIX.md)。

统一离线入口可以直接检查源码，不需要外部运行组件、完整便携包或相机：

```powershell
py -3 -I -B tests\run_offline.py --source-only --report build\source-tests.json --junit build\source-tests.xml
# 有完整、可信的本机构建包时，同时运行包级检查；每项使用独立临时副本。
py -3 -I -B tests\run_offline.py --package D:\M4-build --report build\package-tests.json
```

源码检查覆盖构建资产复制、USB 身份重试策略（Fake 设备）、会话继承／隔离、状态 IO 和测试运行器本身；Windows 上实际验证文件共享。目录资产在整组复制完成后重新计算输出摘要，依赖锁不变。

未指定 `--source-only` 或 `--package` 时，源码检查仍会执行，缺少完整包的检查逐项列为 `BLOCKED`，总体 `PARTIAL`。退出码：`PASS=0`、`FAIL=1`、`PARTIAL=2`；源码范围的 PASS 不代表发布包或相机安装通过。运行器支持每项超时与 JSON/JUnit 报告，不生成替代运行时或 release.json，也不修改原包的状态。详见 [离线测试说明](tests/OFFLINE.md)。

以下命令只用于新构建的测试目录，不能对用户运行目录执行；它们会生成虚拟任务和绑定。不会调用 Windows 驱动或相机，但会留下测试 state，测试目录不能直接分发。

```powershell
D:\M4-build\runtime\python\python.exe -I -B tests\run_clean_setup.py --package D:\M4-build
D:\M4-build\runtime\python\python.exe -I -B tests\test_driver_reuse.py --package D:\M4-build
powershell -NoProfile -ExecutionPolicy Bypass -File tests\test_driver_trust.ps1 -Package D:\M4-build
```

完整初始化替身从无工具配置、任务、相关驱动和证书状态开始，并模拟 Windows 把 SID 登记读回为账户名。可选 `test_task_user_readback.ps1 -Source <源码目录>` 需要已有真实参考任务，仅只读观察，不能当作空白安装测试。实际 UAC、ACL、驱动绑定和相机结果须另行现场验收。

## 致谢与范围

免 Fastboot 方案参考 [YuuLuo/a7c2-camera-tools](https://github.com/YuuLuo/a7c2-camera-tools)；驱动复用和独立恢复参考 [QAQLeonard/a7c2-fl23-research](https://github.com/QAQLeonard/a7c2-fl23-research)。其余来源见 [REFERENCES.md](../../../REFERENCES.md)。

源码不含机身绑定、备份、日志、私钥、完整固件或相机固件库。第三方组件沿用各自许可。
