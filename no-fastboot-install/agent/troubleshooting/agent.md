# Agent 启动与进度

[返回索引](README.md) · [机器检索索引](index.json)

先核对当前任务和构建。以下是已归纳的历史经验，不是对新故障的自动诊断；处理始终服从当前正式入口的待办。

<a id="usb-022"></a>
## USB-022 · Agent doctor 检测不到实际已连接的相机

**匹配线索：** `CONNECTION_REQUIRED`、`normal_count`、`PnP`、`正则`、`UTF-8`。

**阶段：** Agent 只读枚举。**原因状态：** 同症状有多个可能原因。

**历史原因：** 旧实验 Agent 的 Python 普通字符串影响了 PowerShell USB 正则转义/诊断编码，曾导致检测或输出异常；未来未连接、多设备也会正确返回连接要求。

**本轮应核对：** 核对 build_id、普通/服务枚举计数和原始只读枚举错误；是否进入设备任务以当前状态为准。

**处理：** 通过资源清单使用包含修复的构建；真实连接问题按用户待办设置普通海量存储并重查。无活动任务才在新目录使用新构建。

**不要这样做：** 不运行未知USB脚本、不修改现场包内正则绕过启动校验、不清旧状态。

**证据与验证范围：** 2026-11-10 演练定位；修复已包含在实验r5/r6及独立Agent1.00本地构建，不能由同名Release标签推断旧附件已更新。

<a id="usb-023"></a>
## USB-023 · 提权后台仍受 Windows Job 约束

**匹配线索：** `LAUNCH_FAILED`、`launch-error.json`、`IsProcessInJob`、`BREAKAWAY`、`受作业约束`。

**阶段：** Agent 后台启动。**原因状态：** 历史案例已确认。

**历史原因：** 普通子进程脱离Job成功，不代表UAC后的进程也能脱离；早期实验构建在设备操作前拒绝启动。对话关闭可能杀掉受约束任务，不能忽略此检查。

**本轮应核对：** 查同一 dispatch 的 launch-error、进程是否真正独立、原任务是否已有device_started。没有JSON/前端超时不等于无后台。

**处理：** 保留原任务，使用正式状态查询。已确认设备前终止后，按程序待办使用修复构建继续；启动修复通过同一受保护入口完成，不由Agent临时编写后台命令。

**不要这样做：** 不去掉 IsProcessInJob 检查、不用前台终端超时运行写入器、不把普通Job替代测试当成UAC实测。

**证据与验证范围：** 2026-11-10 多轮失败保留记录；实验r5受保护WMI分离和后续真实流程成功，独立Agent1.00继承实现但未重新硬件验收。

<a id="usb-024"></a>
## USB-024 · Agent 解释器与 Provider 摘要不一致

**匹配线索：** `pythonw.exe`、`python.exe`、`解释器`、`runtime`、`digest`、`摘要`。

**阶段：** 启动/Provider校验。**原因状态：** 历史案例已确认。

**历史原因：** 旧实验Agent后台用pythonw.exe，但Provider绑定python.exe；不是靠修改预期摘要可以解决的权限问题。

**本轮应核对：** 对照明确的校验错误、选用解释器和本构建标识；仅泛称“完整性失败”不能认定就是此项。

**处理：** 使用正确区分Agent python.exe和GUI pythonw.exe的正式构建。原任务先按查询/恢复结果结束，不混入新包状态。

**不要这样做：** 不手工替换解释器、不改Provider/发布哈希、不跳过校验。

**证据与验证范围：** 实验r5修正并完成本机相机流程；独立Agent1.00沿用同一已修正入口。

<a id="usb-025"></a>
## USB-025 · 进度查询慢、确认菜单又弹授权、提示相互矛盾

**匹配线索：** `monitor_arguments`、`--watch`、`无需操作`、`管理员授权`、`766/766`。

**阶段：** Agent 监控与引导。**原因状态：** 历史案例已确认。

**历史原因：** 旧提示词每3—5秒重新启动完整入口；菜单观察也派管理员后台；旧Reporter可能保留上一阶段进度或给授权消息附加“无需操作”。

**本轮应核对：** 查看当前构建是否返回 monitor_arguments、真实 pending 和 progress。下载ZIP检查与程序内部启动检查是两个层次。

**处理：** 有 monitor_arguments 时直接使用；最多45秒JSONL监控结束后查询原任务。旧构建无该字段时使用原status，不猜新参数。菜单反馈只提交当前resume，用户动作仍等真实回复。

**不要这样做：** 不并发派多个监控/写入，不额外逐文件哈希或重复 --verify，不将退出码0解释为相机安装成功。

**证据与验证范围：** 实验r6新增并通过源码、正式入口及两条菜单包级检查；离线准备耗时约减少46%，不是整机安装耗时。

<a id="usb-027"></a>
## USB-027 · p1 已完成，但普通 USB 恢复后缺少菜单继续入口

**匹配线索：** `MENU_CONNECTION_STOPPED`、`P1_COMPLETE`、`normal_usb_restored=false`、Issue #24/#25。

**阶段与原因：** p1 已验证后的菜单预检。独立 r1 将该状态引向恢复 USB，恢复成功后结束恢复任务；缺少接回菜单准备的路径。电脑卡可读不能自动更新程序的验证字段。最初的 USB 身份失败原因仍需现场证据，不能由本条关键词推断。

**本轮应核对：** 原 job、build_id、完整 p1 结果、菜单 stopped_before_session/safe_to_restore、window_started/preread_started/installation_may_be_running，以及两项菜单 job 是否已有 claim。相机已安装目标 DAT、窗口已启动或写入结果未知，不属于本续接范围。

**处理：** 按正式提示词的 1.03 原任务续接指南，保留原目录和 state 升级后执行 `--agent status <原job>`、`--agent resume <原job>`，取得当前用户确认；1.03 可先检查连接并继续菜单，也可选择独立恢复 USB。工具保留 patch_run，建立新菜单 attempt，重新完整预读当前 p1，不重新派发 p1 writer。

**边界：** 不删除旧计划、claim 或 state，不改 phase，不把 USB_RESTORE_COMPLETE 当作安装成功。旧桌面任务不是 Agent job，不能直接套用此命令。修复通过源码及包内替代边界回归，没有替代真实相机与全新 Windows 验收。


<a id="usb-028"></a>
## USB-028 · 连接等待慢或描述符错误无法定位阶段

**匹配线索：** USB_IDENTITY_UNAVAILABLE、MENU_COMMUNICATION_PENDING、WINDOWS_SNAPSHOT_TIMEOUT、LIBUSB_ERROR_ACCESS/BUSY/TIMEOUT/PIPE/NO_DEVICE。

**原因与范围：** 旧等待循环反复启动 PowerShell、抓取和校验完整快照，一次快照又分别枚举普通与服务身份；会增加主机开销，两个计数也可能来自不同瞬间。旧描述符错误固定写“菜单未准备”，即使发生在备份之前。

**1.03 处理：** 一次 PowerShell 进程内轮询 PnP，每轮单次枚举，最终只保存一个快照；不扫描存储盘符。描述符诊断提供实际 stage、failure_kind、errno、backend_error_code、attempts、elapsed_seconds。菜单连接停止时只重做尚未开始的菜单步骤。

**本轮核对：** code 与 stage、同机身份、普通/服务枚举、p1 是否完成、窗口及写入是否开始、当前待办。ACCESS 等代码不能单独证明是 Defender、线材或某种驱动导致。先按程序检查连接/恢复，不自动重认证或重发上传、START、COMMIT。

**验证边界：** 惰性 PnP fixture 覆盖服务→短暂消失→普通、多设备、超时和禁用存储扫描；源码与打包回归验证路由和旧任务。没有新的干净 Windows 或相机实测，没有整机刷写提速百分比结论。
