#!/usr/bin/env python3
"""Apply the LUT SD fast-scan patch to an extracted appFw.so.

Standalone: no BODYDATA encode/sign. Output is a new .so for integrators to
pack with their own toolchain (Erlla a7m4.firmware / custom builder).

Usage:
  python apply_to_appfw.py --input appFw.so --output appFw.sd.so --baseline community_1119
  python apply_to_appfw.py --input appFw.so --output appFw.sd.so --baseline author_0.12
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _hex(s: str) -> bytes:
    return bytes.fromhex(s.replace(" ", "").replace("0x", ""))


def _int(v) -> int:
    return int(v, 0) if isinstance(v, str) else int(v)


def load_json(name: str) -> dict:
    return json.loads((HERE / "patches" / name).read_text(encoding="utf-8"))


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


def validate_baseline(appfw: bytearray, baseline: dict, name: str) -> None:
    if len(appfw) != baseline["appfw_size"]:
        raise SystemExit(f"{name} input size mismatch: {len(appfw)} bytes")
    digest = hashlib.sha256(appfw).hexdigest()
    if digest != baseline["appfw_sha256"]:
        raise SystemExit(f"{name} input SHA-256 mismatch: {digest}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument(
        "--baseline",
        choices=("community_1119", "author_0.12"),
        default="community_1119",
    )
    args = ap.parse_args()

    if args.output.exists():
        raise SystemExit(f"refusing overwrite: {args.output}")

    appfw = bytearray(args.input.read_bytes())
    baselines = json.loads((HERE / "layout.json").read_text("utf-8"))["verified_baselines"]
    validate_baseline(appfw, baselines[args.baseline], args.baseline)
    apply_fast_scan(appfw, load_json("fast_scan.json"))
    apply_import_relax(appfw, load_json("import_relax.json"))
    report = {"input": str(args.input), "bytes": len(appfw), "baseline": args.baseline,
              "fast_scan": True, "import_relax": True}

    args.output.write_bytes(appfw)
    report["output"] = str(args.output)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
