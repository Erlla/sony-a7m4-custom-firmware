# USB offline regression runner

Run from `no-fastboot-install/software/` with Python 3.12+. No test framework installation is needed for source checks. The runner never downloads dependencies, prepares drivers or sends camera commands.

## Source scope

```powershell
py -3 -I -B tests\run_offline.py --source-only --report build\source.json --junit build\source.xml
```

The source suites exercise the actual checkout modules:

| Suite | Boundary covered |
|---|---|
| build-assets | Directory/ZIP copying, locked scope, copy-time changes and IO failures using inert text |
| normal-identity | Fake devices, advertised language selection, bounded retries, body mismatch and handle disposal |
| operation-session | Session records, preserved history, invalid identifiers and actual child-process inheritance |
| state-io | UTF-8/BOM, atomic publication, sharing-error retry deadlines, failed-write preservation and real Windows sharing |
| runner | Failed/missing worker records, timeouts, report semantics, copy isolation and package dispatch coverage |

Each suite runs in its own isolated Python process. Source tests use temporary paths and synthetic data; they do not generate `release.json`, load a USB library, import the camera workflow or build camera workers. The fake descriptor tests check retry policy rather than PyUSB's real descriptor decoders; the latter remain covered by the package-level USB identity test.

Windows sharing tests are skipped explicitly on other operating systems. JSON and JUnit retain these skips; a source PASS does not imply those platform checks ran elsewhere. Only Windows execution has been exercised for this contribution.

## Package scope

```powershell
py -3 -I -B tests\run_offline.py --package D:\M4-build --report build\package.json --junit build\package.xml
```

Use only a trusted, locally built Windows package. The preflight uses code from this checkout to hash release files, verify the original nine dependency groups and compare packaged app content with this checkout. It does not import package code. These consistency checks are not publisher-signature authentication for the supplied EXE.

For each check, the runner copies only app/runtime/vendor/tools/licenses and the EXE into a fresh temporary directory, checks the copy again, and executes the check there. Original state, logs and backups are never copied into the test run or modified. Reports cannot be written inside the supplied package, app or tests directories.

The package catalogue includes native `--verify`, USB recovery, local failure, state IO, startup session, USB identity, and both stock/user menu sealing. It has one shared specification rather than a separate hard-coded test count. Unknown or missing runtime materials are not replaced, checks are not bypassed, and incomplete packages cannot be marked successful.

Tests are deliberately sequential. `--timeout SECONDS` bounds each suite/check (default 900, maximum 3600); timeout cleanup targets only the owned test process tree. Output capture retains at most the final 64 KiB in the report. A failure in one check does not suppress the remaining checks.

## Results

| Result | Exit | Meaning |
|---|---:|---|
| PASS | 0 | All requested checks passed; inspect scope and platform skips |
| FAIL | 1 | A requested check or consistency check failed |
| PARTIAL | 2 | No check failed, but required package checks are blocked |

With no scope option, source tests run and all eight package checks are explicitly blocked until `--package` is supplied. With `--source-only`, those checks are outside the requested scope. Neither mode establishes physical-camera safety or successful firmware installation; every report records `camera_validated=false`.

JSON reports use `m4-usb-offline-tests/1`, containing per-suite exit codes, timing, timeout flags, unit outcomes and blocked reasons. JUnit represents blocked package cases as skipped with a `BLOCKED` message and preserves worker failures even if some unit rows passed. Report/test artifacts belong in ignored `build/` or another local output directory, not Git.

The runner's package dispatch tests use mocks only to check orchestration. Their success is not evidence that a full package integration check ran. A genuine full locked package is still required to validate that path end to end.

## 中文摘要

- `--source-only`：无需完整运行组件即可运行源码回归，使用标准库 unittest 和临时文本／假设备；不伪造发布包。
- 默认运行：源码检查正常执行，八项完整包检查逐项显示 BLOCKED，总体 PARTIAL，避免把缺少运行时误报为全部通过。
- `--package`：只用于可信的本机构建包；原始依赖锁、发布文件和 app 源码一致性预检通过后，每项检查使用独立临时副本，不污染原目录或相机状态。
- 报告支持 JSON 与 JUnit，保留失败、超时、平台跳过和阻塞原因。只有 Windows 上验证了本次实现；源码测试通过不等于完整 EXE、真实提权部署或机身安装通过。
