# Component layout and concurrency review

**No new firmware defect was confirmed in this review.** This is an offline review result, not camera acceptance or a claim that the firmware is bug-free. No firmware implementation or pinned artifact was changed.


| Artifact | SHA-256 |
| --- | --- |
| Combined CP | `92a1b6ccdd2a92e94af7377858c79b08595cbb86ccb4b9a0464015ea8bdabae3` |
| Combined AP | `cc9c0b3fc9722e957ab9d046835c4a7d083285ca02b2f2a9fe2f5258d67cad2c` |

New checks executed against the saved combined components:

- Nine AP layout/linkage groups: eight LOADs, thirteen PHDRs, 4/64 KiB page separation, offset congruence, 1,004,897 dynamic relocation targets and symbol indices, RELACOUNT, four unique appended relocations, shared constructor chains, retained main payloads and active T22 selection entries. Four existing aspect descriptor redirects are intentional; the rest of the relocation prefix and live PLT remain intact.
- Twenty shared CP state cases: LUT Off/slot 1, native 3:2/four custom ratios, both selection orders. Native color messages, capture snapshots, per-task ratios and JPEG request geometry preserve each other's state. These checks do not render ISP pixels or encode JPEGs.
- Two OS-context models of the outer pool locking sequence, described below.

Component identities are recorded in [layout.json](layout.json), with the offline scope in [validation.json](validation.json). Package and per-run acceptance records are maintained separately in the research repository.

## Withdrawn pool-reuse hypothesis

In [cp_capture_latch.c](cp/cp_capture_latch.c), `aspect_pool_release()` clears the sidecar after the inner native release returns. An isolated interleaving starting at `0xA06172`, and calling the inner allocator `0xA061B8` directly, can clear a new owner's ratio. **That is not a demonstrated firmware defect:** it bypasses the native outer mutex.

The real allocation wrapper `0xA05BC0` and release wrapper `0xA05C0A` both acquire mutex 9 through `0x54E73C` before entering the inner pool. The sidecar clear finishes before the outer wrapper releases mutex 9 through `0xA05238 → 0xA05698 → 0x54F1C4`. A new allocation waits until that clear completes. Replaying these native wrappers with explicit mutex blocking, separate thread stacks and unchanged CP instructions preserved custom ID 7 and the `5456×4672` request in both OS-context cases.

Direct branch and absolute-pointer scans found no alternate bypass caller in this image; this does not rule out every computed indirect edge. OS synchronization was modeled, not measured on a camera. The isolated counterexample was withdrawn, and no cleanup-order patch was made on its basis.

## Evidence boundaries

Cold-start and playback-return first-frame timing, real burst scheduling, encoded pixels, RAW/HEIF auxiliary lifetimes, hardware/display behavior and combined UI/sound acceptance cannot be inferred from these offline checks. The LUT interface is one independent slot at fixed 100%; this review does not establish JSON import or multi-slot fitting.

中文版摘要：本轮未确认新缺陷；早期“对象归还后清掉新比例”的局部反例漏掉原厂外层 mutex 9，补齐后已排除并撤回。审查时必须检查全部外层锁，不能把局部模型构造的交错直接当成机内故障。
