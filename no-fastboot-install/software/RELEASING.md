# USB source-aligned release checks / USB 发布前验收

Run only on a development PC, using new output directories and Python 3.12+.
These commands prepare files, compile the Windows launchers and run offline
checks. They do not start the normal GUI, request UAC or operate a camera/driver.

```powershell
# Run from no-fastboot-install/software/.
py -3 -I -B prepare_assets.py --download --cache D:\M4-cache --output D:\M4-assets
# Offline alternative: --from-package D:\M4-portable.zip instead of --download.
py -3 -I -B build.py --assets D:\M4-assets --output D:\M4-release-candidate
D:\M4-release-candidate\M4相机工具.exe --verify
py -3 -I -B tests\run_offline.py --package D:\M4-release-candidate --report D:\M4-checks.json --junit D:\M4-checks.xml
```

`prepare_assets.py` verifies the published ZIP hash, exports only the 3257 pinned
runtime files and checks all nine original group locks. An existing correct ZIP
is reused. `--download` also reuses a verified asset output on a repeated call;
it never overwrites a mismatching output. Network errors retain resume material
and HTTP status/reasons in the cache's `.download.json`. Incorrect range or hash
responses are refused. No certificate-verification or system-proxy exceptions
are used.

The published author ZIP has a `1.00` app, while this source uses `1.0.1`. Its
app is not a test package for this checkout. Export its locked assets and rebuild
as above. Do not edit its manifest, accept a version alias or change any locked
hash to pass the tests. `app/product_version.py` supplies the version used by
Python consumers, the C# launcher and the native bootstrap. It must agree with
`dependencies.json`; a mismatch stops before creating output.

Export/build stage in an owned temporary sibling. Exceptions remove that
staging directory, including Windows extended-path caches, and do not leave a
partial published output. The same destination can then be retried. An existing
destination, including a newly appearing one, is preserved. The builder checks
the local Python and native verification results before publication and removes
its own `_launcher_build` and build-only `state` cache. Compiler diagnostics are
retained on stderr.

The runner must report PASS, zero failed/blocked checks and the expected platform
coverage. Its ten package cases use separate disposable copies; the candidate
itself retains no test state. The Issue #9 case additionally checks the previously
reported integrity/startup/session boundaries. Never distribute a manually tested
directory containing enrollment, backups, transaction state or logs. Retain the
JSON/JUnit reports separately and record the candidate's SHA-256 and source commit.

USB recovery accepts readable card volumes only when the disk's PnP ancestry
reaches the exact bound normal-mode camera. A `PMHOME` label is not required and
cannot identify a camera by itself. The shared read-only helper is included in
the protected broker's hashed file set; legacy snapshots/failure records remain
readable. Native hub-port identity guards are unchanged; refusal diagnostics now
include the returned descriptor fields. The cause of a particular port refusal
still requires evidence and is not declared fixed by this source change.

This is a local source-build acceptance path, not an independent claim of publisher
authenticity, redistribution rights, real elevated ACL deployment or physical
camera installation. A replacement public app ZIP must be built/reviewed and
uploaded by the maintainer; a source PR does not change the already hosted ZIP.

## 中文

以上命令只进行电脑端准备、编译及离线验收。先下载／复用可信 USB ZIP，
核对原摘要并精确导出资产，再由当前源码构建新的候选目录。现有 `1.00`
发布包只作为资产来源，不能通过改版本字符串或清单来冒充 `1.0.1` 候选。

源码共用一个运行版本，构建前核对依赖元数据，构建后核对 Python 和原生校验。
失败的导出／构建不留下发布半成品，也不会覆盖旧安装或未完成任务。源码回归、
十组独立包检查和历史审计边界均通过后，再由维护者审查和发布，报告与成品分开保存。
原厂归档独立重建配方、完整的逐文件许可映射、真实提权部署及相机验收不由这些
离线结果代替；该 PR 也不会自动替换已发布的二进制或操作任何机身。
