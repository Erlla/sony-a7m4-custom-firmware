# USB installer fault matrix

These are development checks, not operations performed during a user's patch run.
Use `run_offline.py` as described in [OFFLINE.md](OFFLINE.md). Do not run package
checks on a used installation: the runner creates isolated copies instead.

| Failure boundary | Injection | Expected result / test |
|---|---|---|
| New Windows setup | Empty deployment, task principal readback, UAC refusal, existing task | No assumed developer environment; `run_clean_setup.py`, `test_usb_recovery.py` |
| StageBind | Reboot-required receipt, unknown dispatch, pending task | Request real Windows restart or original-task reconciliation; no repeated dispatch; connection/driver suites |
| Identity | Missing language descriptor, wrong body, ambiguous devices | Bounded identity reads, refuse incompatible body; identity suites |
| Reader launch | Truncated or foreign ready, missing cleanup, foreign cleanup | No second upload/START; only matching worker cleanup unlocks known read-only recovery; reader/fault suites |
| Native audit | Missing maps/directory, disappearing fd, libJit still retained, malformed entries, EINTR, evidence save failure | Production C returns exact stage; only fd ENOENT gets at most three reader scans, writer stays at one; `test_native_audit.py` |
| Reader data | Truncated chunk, changed digest, wrong PID, lost ACK | No completed-read label until full data and matching cleanup; `test_fault_matrix_unit.py` |
| Writer transport | Lost module/staging/PREPARE/COMMIT reply, wrong nonce/PID, terminal timeout | At most one upload/PREPARE/COMMIT; uncertainty remains explicit; `test_writer_faults_unit.py` |
| Native block IO | Partial/zero/oversized write, EINTR exhaustion, ENOSPC, reverse rollback, sync/digest/rollback mismatch | Production pwrite/rollback functions with inert syscalls; no actual block device; `test_native_audit.py` |
| Write/readback | Exception at each engine boundary, rollback failed, readback mismatch | Never turn a failed write into success or a pre-write recovery; engine/writer suites |
| Menu | Local build failure, pre-read cleanup, missing normal identity, insufficient window | Preserve p1 completion separately; no `passed: true` for incomplete handoff; both lineage package suites |
| Handoff recovery | Confirmation absent/present | Require actual camera restart confirmation, then driver-only recovery, never a new window or writer; connection recovery suite |
| Host storage | Disk full, access denied, missing/corrupt state, failed atomic rename | Preserve original error and earlier valid state; state/fault suites |
| Exit | Stop/dispose/report failure after primary error | Retain original cause and secondary errors; fault suite |
| UI/concurrency | Double click, simultaneous claim, child exits without JSON, failed worker | No duplicate task, no overwritten claim, visible exit code/cause, UI busy flag released; fault suite |

Native tests compile the production functions into Windows executables with all
camera/filesystem syscalls replaced by inert fixtures. Package tests additionally
compile real AArch64 materials and inspect/seal them but do not execute them on
a camera. No tests simulate actual battery failure electrically or establish
physical flash recovery. Actual UAC, driver binding and complete installation on
a clean Windows machine still require device acceptance.

Diagnostic JSON is explanatory, not an authorization receipt. Nonce-bound native
frames, complete data checks and existing recovery proofs remain authoritative.
