# Agent 启动与进度

[返回索引](README.md) · [机器检索索引](index.json)

先核对当前任务和构建，再用本轮证据验证历史线索。入口自身有缺陷时，按[自主排障规则](../PROMPT.zh-CN.md#8-自主诊断修复与恢复)追踪源码、修复主机端逻辑并验证。

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

匹配线索包括 `LAUNCH_FAILED`、`launch-error.json`、`IsProcessInJob`、`BREAKAWAY` 和“Windows 独立后台仍受进程作业约束，未开始相机操作。”

### 已确认的执行位置

在 `1.03-agent-20261111-r1` 中，`Launcher.cs` 先校验管理员身份，再检查 Job。首次检查发现所属 Job 后通过 WMI 启动独立进程，独立进程仍返回 attached 时抛出上述错误。这个报错发生在启动 Python worker 之前，尚未进入该派发的驱动及 p1 操作。匹配时核对原 build_id、dispatch 和完整错误文本。

该构建的 `status_result` 只在返回 JSON 时覆盖 status、message 和 diagnostic。持久记录仍可能为 `DISPATCHING/AWAITING_SYSTEM_AUTHORIZATION`，next_step 仍要求查询，doctor 又返回旧状态。符合上述源码路径时，管理员检查已经通过，后续要处理后台启动和状态收尾。

`IsProcessInJob` 的空 JobHandle 检查进程是否属于任意 Job。还需检查实际限制及进程生命周期，确定宿主关闭是否会终止后台。[微软 API 说明](https://learn.microsoft.com/en-us/windows/win32/api/jobapi/nf-jobapi-isprocessinjob)，[Job 生命周期说明](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)

### Agent 如何继续处理

1. 核对同一 dispatch 的 launch-error、worker claim、会话记录、相关进程和共享任务记录。根据源码确认报错之前实际执行的操作。
2. 读取当前宿主、父进程链、Job 限制和 WMI 返回结果，提出后台启动的具体假设。先用惰性 worker 验证包含实际授权流程的启动路径及父进程退出后的存活。
3. 按主提示词第 8 节在源码副本修复启动与终止状态收尾，复用受保护入口，给出本地构建标识和定向测试结果。
4. 已确认设备前终止且相关进程均结束时，保留原派发证据，归档失效活动状态，再创建新的尝试。1.03 r1 当前缺少通用失败归档接口，需要先落实相应修复。

现有日志只记录错误文本及 dispatch，宿主名称、父链、Job 限制与 WMI 进程信息需要在故障电脑补采。早期 r5 的本机安装成功与后续惰性测试，覆盖各自实际执行的环境。此条记录 1.03 的已定位故障及排查路径，程序修复和现场验证进度需另行记录。

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
