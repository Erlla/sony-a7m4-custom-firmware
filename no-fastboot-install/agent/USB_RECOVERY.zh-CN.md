# 只恢复普通 USB 连接

适用于 M4 Agent 工具 1.03。此模式只处理 Windows 普通 USB 驱动及连接恢复，不备份或写入 p1、不准备更新菜单、不安装固件，也不需要 BODYDATA.DAT、LUT 或声音文件。

## 复制给 Agent

> 请按本项目的正式 Agent 流程，只恢复相机的普通 USB 连接。获取并校验资源清单指定的工具包后，先查询已有任务，再使用 `--agent recover-usb` 入口。不要运行补丁、菜单准备或固件安装；不需要下载固件或素材。系统授权、USB 拔插、Windows 重启或相机操作，请明确提示并等待我回复。恢复后查询原任务并确认普通连接；出错时查阅历史问题库，保留现有记录。

将这段话与[主提示词链接](PROMPT.zh-CN.md)一并交给可以操作本机终端的 Agent。

## Agent 执行顺序

1. 按[资源清单](resources.json)获取 Windows x64 工具包，核对整个 ZIP 的大小和 SHA-256 后解压。已有原任务目录时优先复用；不覆盖状态，不对解压内容再逐文件计算哈希。
2. 用正式入口 `M4相机工具.exe --agent status` 查询已有任务。**本模式不以 doctor 开始**：当前版本 的 doctor 在空闲且检测到相机时会创建补丁确认待办。只恢复 USB 不需要这个待办。
3. 调用 `M4相机工具.exe --agent recover-usb`。不带任务编号时，该命令只展示原未结束任务，或在空闲时建立恢复确认；这一步不会立即切换驱动。
4. 若当前待办为恢复，向用户确认相机已连接、没有正在安装固件或其他相机任务。等待真实回复后，使用返回的 `commands[].arguments` 执行带当前 `job` 和 `pending.id` 的恢复命令。首次运行可能需要 Windows 管理员授权，说明用途后等待用户在系统窗口确认。
5. 后台工作期间查询同一任务；有 `monitor_arguments` 时使用它。只有当前待办要求拔插、重启 Windows 或重启相机时，才提示相应动作，并等回复后继续。驱动已恢复但盘符尚未出现时，不重复调度恢复，更不重写 p1。
6. 查询结果明确 `normal_usb_restored=true` 后报告恢复成功。退出码 0、`query_ok=true` 或仅显示 USBSTOR 都不能代替这个结果。恢复结束即停止，不自动开始补丁或安装。

## 已有任务时

- 另一目录或桌面端任务未结束：按返回的原目录查任务，不在新目录另起恢复。
- 原任务当前允许恢复：沿用对应待办，不另建写入任务。
- 1.03 的 MENU_CONNECTION_STOPPED 待办同时提供 continue-menu 和 restore-usb。仅恢复 USB 时只选择 restore-usb，按返回的 resume 参数提交；不能把 continue-menu 当作恢复操作。
- 返回写入确认、无恢复选项的继续菜单或结果待核对：**不能为了恢复 USB 提交这些操作**。当前版本 不会把任意未结束任务强制转换成独立恢复；先查状态和原因。若正式入口没有可用恢复命令，说明阻塞点并保留记录，不删除状态解锁，也不绕过程序强切驱动。
- 相机仍在安装：等待安装结束与用户反馈，不因恢复电脑盘符而中断安装。

## 出错时查哪里

先按[历史问题索引](troubleshooting/index.json)检索，再核对当前证据：

- [USBSTOR 已切回、PMHOME／盘符未出现](troubleshooting/connection.md#usb-009)。
- [恢复被写入状态阻塞](troubleshooting/connection.md#usb-010)。
- [另一目录仍有未结束任务](troubleshooting/connection.md#usb-011)。
- [明确要求重启 Windows](troubleshooting/setup.md#usb-002)。

只恢复 USB 不会自动解决所有硬件连接问题；需要用户操作时逐步说明，原因未知时继续保留为未知。

