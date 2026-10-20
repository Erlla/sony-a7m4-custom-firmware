# SD 更新救砖公开适配验证

日期：2026-10-21。范围为本仓库方法 0 的源码适配、文档、资源登记和离线验证；本轮不接入相机、不写入设备。公开版复用现有主机模块，恢复写入仍限制为本次 `nflasha2` 候选。其余五个方法的补丁、配置及共享 FAT/fastboot 模块未修改。

## 结果

- **167 项全仓库测试通过，0 失败、0 跳过**。其中恢复流程/连接回归 33 项、公开集成 8 项，共 41 项新增恢复相关测试；其余 126 项是现有功能回归。
- Windows 上运行了真实 BAT，后端替换为隔离的假 Python 模块；确认中文和空格/`&` 路径、只读参数及退出码传递。没有执行真实 fastboot 程序。
- 使用合成 FAT 镜像验证精确 initrd SHA-256 与 MD5 门控；未知 profile、损坏校验均被拒绝。外部资源缺失/修改在取得设备锁前停止。
- 已核对公开适配与原救砖核心的 13 个关键函数/方法 AST 一致，包括 `make_trigger`、`inspect_sd_environment`、`recover`、命令白名单和一次写入授权。适配差异为包内导入、复用本地资源清单、可移植启动和默认本地日志路径。
- 首次全量测试有一项原有镜头 CLI 测试因 Windows 子进程输出使用系统编码而解码失败；设置 `PYTHONUTF8=1` 后完整重跑通过，没有修改镜头测试或配方。

复现（从仓库根目录执行，不访问相机）：

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m pip install -e ".[test,firmware]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tools/check_public_tree.py
```

## Evidence → Finding → Path

| 证据 | 可复核内容 | 结论与边界 |
|---|---|---|
| E-001：[核心](../../a7m4/sd_recovery.py) `make_trigger` / `recover` / `RecoveryTransport` | 仅 DAT4 两字节和最多两个 32 B 目录项可变；六分区新备份、写前内容复核、一次写入、完整读回 | F-001：离线验证通过的受限恢复触发器，不是整机还原工具 |
| E-002：[恢复测试](../../tests/test_sd_recovery.py)、[连接测试](../../tests/test_sd_recovery_connection.py) | 模拟备份/设备变化、命令 FAILED、USB 121、写失败、读回失败和重启超时 | F-002：拒绝路径不误报安装成功，不自动重试潜在部分写入 |
| E-003：[公开集成测试](../../tests/test_sd_recovery_public.py) | 合成 updater、资源登记、真实 BAT 和本地默认会话目录 | F-003：公开适配可在外部资源由用户准备的条件下使用；不依赖维护者电脑路径 |
| E-004：既往维护者同机实机记录（原始备份、日志留在本地） | 曾观察到 `NOR_FLASH END`、`WRITE NOR_IMG END`、`User Update OK`，NOR 回读一致及正常取景 | 支持既有 MODE5 路线的历史可行性；原始机身证据未公开，本次没有重新验收公开版实机安装 |

P-001（callflow）：已有 fastboot → 单机与资源检查（E-001/E-003，F-003）→ 六分区备份和更新器匹配 → 生成/复核设置候选（E-001，F-001）→ 最多一次设置写入与完整读回（E-001/E-002，F-001/F-002）→ 普通重启 → 机内 SD 更新器独立校验和安装 → 由机内状态/日志/回读另外确认结果。

残余限制：当前 profile 仅包含一份精确的修改版更新环境；不能外推到所有原厂固件。机内更新器损坏、卡不可读、包不被现有密钥接受或其他硬件故障可能阻止恢复。主机不能读取卡内 DAT，也不确认机内安装完成。使用方法和错误处理见[中文方法](README.md) / [English](README.en.md)。

## 本次关键文件 SHA-256

以下哈希按仓库 LF 文本字节计算；BAT 的 Git 文本归一化与 Windows 工作树 CRLF 不混作同一字节序列。

| 文件 | SHA-256 |
|---|---|
| `a7m4/sd_recovery.py` | `79a9597a783e466e6a3b66cbbf5760c18502ec1695f659b55c2162444afed7a1` |
| `a7m4/recover_sd.py` | `d4bedb4da6f5300698c1caf727e5304fabaf3e75791242be03dd22365dc52193` |
| `a7m4/profiles/sd-recovery.json` | `c4123a98d0718f1ed8a8feb124f31a9c473c3e457b2ae4b3957c9ae735a74dec` |
| `tests/test_sd_recovery.py` | `f53c0b58f2d246466fec5399cb1bea594e0d44e53c4f6412e0f6666c34298c36` |
| `tests/test_sd_recovery_connection.py` | `5a50349d15d479567c06a6dc6ba47ccb355d23c1291149709441f6d6188ae16a` |
| `tests/test_sd_recovery_public.py` | `a8c66c7fcc33dfc046c6c902dcbbaf2e7f828b3f33213336d775eda1ecbe35ff` |
