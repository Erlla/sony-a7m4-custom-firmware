#!/usr/bin/env python3
"""Apply LUT SD fast-scan + edge page-flip patches to an extracted appFw.so.

Standalone: no BODYDATA encode/sign. Output is a new .so for integrators to
pack with their own toolchain (Erlla a7m4.firmware / custom builder).

Usage:
  python apply_to_appfw.py --input appFw.so --output appFw.sd.so --baseline community_1119
  python apply_to_appfw.py --input appFw.so --output appFw.sd.so --baseline author_0.12
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from asm import NOP, build_clear, build_total, build_wrap, enc_b, enc_bl  # noqa: E402


def _hex(s: str) -> bytes:
    return bytes.fromhex(s.replace(" ", "").replace("0x", ""))


def _int(v) -> int:
    return int(v, 0) if isinstance(v, str) else int(v)


def load_json(name: str) -> dict:
    return json.loads((HERE / "patches" / name).read_text())


def apply_fast_scan(appfw: bytearray, spec: dict) -> None:
    p = spec["patch"]
    off = _int(p["offset"])
    before, after = _hex(p["before"]), _hex(p["after"])
    if len(before) != len(after):
        raise SystemExit("fast-scan before/after length mismatch")
    cur = bytes(appfw[off : off + len(before)])
    if cur != before:
        raise SystemExit(f"fast-scan mismatch @0x{off:x}: got {cur.hex()}")
    appfw[off : off + len(after)] = after


def apply_import_relax(appfw: bytearray, spec: dict) -> None:
    for p in spec["patches"]:
        off = _int(p["offset"])
        before, after = _hex(p["before"]), _hex(p["after"])
        cur = bytes(appfw[off : off + len(before)])
        if cur != before:
            raise SystemExit(f"import-relax mismatch @0x{_int(p['va']):x}: {cur.hex()}")
        appfw[off : off + len(after)] = after


def apply_pagination(appfw: bytearray, baselines: dict, name: str) -> dict:
    shared = baselines["shared"]
    base = baselines["baselines"][name]
    va_delta = _int(shared["va_delta"])
    bss = _int(shared["bss"])
    cave_clear = _int(shared["cave_clear"])
    cave_wrap = _int(shared["cave_wrap"])
    cave_total = _int(shared["cave_total"])
    total_site = _int(shared["total_site"])
    wrap_site = _int(base["wrap_site"])
    wrap_resume = _int(base["wrap_resume"])
    open_branch = _int(base["open_branch"])
    open_continue = _int(base["open_continue"])
    msg_page = _int(base["msg_page"])
    msg_off = _int(base["msg_off"])

    clear = build_clear(cave=cave_clear, bss=bss, continue_va=open_continue)
    total = build_total(cave=cave_total, bss=bss)
    wrap = build_wrap(cave=cave_wrap, bss=bss, msg_page=msg_page, msg_off=msg_off)

    for va, blob, label in (
        (cave_clear, clear, "clear"),
        (cave_wrap, wrap, "wrap"),
        (cave_total, total, "total"),
    ):
        off = va - va_delta
        if bytes(appfw[off : off + len(blob)]) != b"\x00" * len(blob):
            raise SystemExit(f"cave {label} not empty @ {va:#x}")
        appfw[off : off + len(blob)] = blob

    off = open_branch - va_delta
    # Rewrite unconditional branch to clear cave (any prior b target is replaced).
    appfw[off : off + 4] = enc_b(open_branch, cave_clear)

    off = total_site - va_delta
    expect = _hex(shared["total_site_before"])
    if bytes(appfw[off : off + 8]) != expect:
        raise SystemExit(f"total site mismatch: {bytes(appfw[off:off+8]).hex()}")
    appfw[off : off + 4] = enc_bl(total_site, cave_total)
    appfw[off + 4 : off + 8] = NOP

    off = wrap_site - va_delta
    if "wrap_site_before" in base:
        expect_w = _hex(base["wrap_site_before"])
        if bytes(appfw[off : off + len(expect_w)]) != expect_w:
            raise SystemExit(f"wrap site mismatch: {bytes(appfw[off:off+48]).hex()}")
    patch = enc_bl(wrap_site, cave_wrap) + enc_b(wrap_site + 4, wrap_resume) + NOP * 10
    if len(patch) != 48:
        raise SystemExit("wrap patch size")
    appfw[off : off + 48] = patch

    return {
        "baseline": name,
        "wrap_site": hex(wrap_site),
        "open_branch": hex(open_branch),
        "msg_va": hex(msg_page + msg_off),
        "cave_sizes": {"clear": len(clear), "wrap": len(wrap), "total": len(total)},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument(
        "--baseline",
        choices=("community_1119", "author_0.12"),
        default="community_1119",
    )
    ap.add_argument("--skip-pagination", action="store_true")
    ap.add_argument("--skip-fast-scan", action="store_true")
    args = ap.parse_args()

    if args.output.exists():
        raise SystemExit(f"refusing overwrite: {args.output}")

    appfw = bytearray(args.input.read_bytes())
    report: dict = {"input": str(args.input), "bytes": len(appfw), "baseline": args.baseline}

    if not args.skip_fast_scan:
        apply_fast_scan(appfw, load_json("fast_scan.json"))
        apply_import_relax(appfw, load_json("import_relax.json"))
        report["fast_scan"] = True
        report["import_relax"] = True

    if not args.skip_pagination:
        report["pagination"] = apply_pagination(
            appfw, load_json("pagination_baselines.json"), args.baseline
        )

    args.output.write_bytes(appfw)
    report["output"] = str(args.output)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
