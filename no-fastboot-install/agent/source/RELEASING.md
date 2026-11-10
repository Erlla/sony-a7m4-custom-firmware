# Agent 1.00 构建与发布核对

在开发用 Windows x64 电脑、`no-fastboot-install/agent/source/` 目录运行，使用 Python 3.12+ 和系统 C# 编译器。以下步骤构建新目录并进行离线检查，不请求管理员授权或访问相机。

```powershell
py -3 -I -B prepare_assets.py --download --cache D:\M4-cache --output D:\M4-assets
# 已有可信 ZIP 时，改用 --from-package D:\M4-portable.zip。
py -3 -I -B build.py --assets D:\M4-assets --output D:\M4-Agent-build
D:\M4-Agent-build\M4相机工具.exe --verify
py -3 -I -B tests\run_offline.py --package D:\M4-Agent-build --report D:\M4-checks.json --junit D:\M4-checks.xml
powershell -NoProfile -ExecutionPolicy Bypass -File tests\test_agent_download.ps1
```

资产导出器只保留 `assets-files.json` 中锁定的 3257 个运行组件，排除输入包的 app、state 和固件。应用始终由本目录源码构建。下载来源、摘要和许可见 `assets-sources.json` 与 [THIRD_PARTY.md](THIRD_PARTY.md)。这条开发构建链需要完整核对资产；普通 Agent 用户只下载既有成品并核对整份 ZIP，不重复执行开发检查。

版本来自 `app/product_version.py`，必须与 `dependencies.json` 一致。独立 Agent 1.00 与历史桌面 1.00 是不同构建，不能修改清单或摘要让旧应用通过。输入/输出目录分开，构建不得覆盖用户安装目录或记录。

检查范围见[离线测试说明](tests/OFFLINE.md)。测试使用临时目录和替身，报告记录缺失范围及平台跳过；离线 PASS 不表示全新 Windows、真实 UAC/驱动或相机安装验收通过。下载器测试使用惰性 ZIP，不联网或执行其中的 EXE。

发布时保存源码提交、构建标识、ZIP 字节数和 SHA-256，填写上层 `resources.json`。ZIP 中只放干净的成品，不带 enrollment、备份、运行记录或个人配置。运行源码和第三方依赖遵循各自许可。

现有正式 ZIP 不因源码提交而变化。需要替换时应从统一源码重新构建、核对并发布新构建标识，再更新资源清单。不得把更新过的说明文档误记成旧包已经包含的内容。
