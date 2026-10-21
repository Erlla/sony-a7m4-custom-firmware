"""Rebuild the six original sound modules and check their installed sections.

No camera, firmware container, version metadata, or proprietary image is needed.
Local compiler paths are explicit arguments, not machine-specific dependencies.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from a7m4.custom_sound import apply_delta
from elftools.elf.elffile import ELFFile


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def build(zig: Path, arm_gcc: Path, output: Path):
    if output.exists():
        raise ValueError("Choose a new output directory")
    manifest = json.loads((ROOT / "native/custom-sounds/source-manifest.json").read_text("utf-8"))
    for row in manifest["files"]:
        if digest((ROOT / row["path"]).read_bytes()) != row["sha256"]:
            raise ValueError("Published source changed: " + row["path"])
    plan = json.loads((ROOT / "native/custom-sounds/build-plan.json").read_text("utf-8"))
    output.mkdir(parents=True)
    output = output.resolve()
    report = {"modules": {}, "camera_io": False, "firmware_metadata_changed": False}
    for name, module in plan["modules"].items():
        (output / name).mkdir()
        # GCC's linker on Windows can mishandle non-ASCII absolute paths.
        # Build from the module directory with relative source/output arguments.
        substitutions = {"root": os.path.relpath(ROOT, output / name),
                         "out": "..", "zig": str(zig.resolve()),
                         "arm_gcc": str(arm_gcc.resolve())}
        for template in module["commands"]:
            command = [token.format(**substitutions) for token in template]
            subprocess.run(command, cwd=output / name, check=True)
        elf_path = (output / name / module["elf"].format(**substitutions)).resolve()
        raw = bytearray(elf_path.read_bytes())
        elf = ELFFile(io.BytesIO(raw))
        symbols = elf.get_section_by_name(".symtab")
        undefined = [s.name for s in symbols.iter_symbols() if s.name and s["st_shndx"] == "SHN_UNDEF"]
        if undefined:
            raise ValueError("Undefined sound symbols: " + ", ".join(undefined))
        checks = []
        for expected in module["sections"]:
            section = elf.get_section_by_name(expected["name"])
            if section is None or section["sh_addr"] != expected["va"] or section["sh_size"] != expected["bytes"]:
                raise ValueError("Compiler/layout mismatch: " + name + " " + expected["name"])
            if expected["nobits"]:
                if section["sh_type"] != "SHT_NOBITS":
                    raise ValueError("Expected uninitialized state")
            else:
                original = section.data()
                if digest(original) != expected["source_build_sha256"]:
                    raise ValueError("Compiler code mismatch: " + name + " " + expected["name"])
                installed = apply_delta(original, expected["post_link_ops"], len(original))
                if digest(installed) != expected["installed_sha256"]:
                    raise ValueError("Post-link mismatch: " + name)
                at = section["sh_offset"]
                raw[at:at + len(installed)] = installed
            checks.append({k: v for k, v in expected.items() if k not in ("post_link_ops", "source_build_sha256")})
        with elf_path.with_name("installed.elf").open("xb") as stream:
            stream.write(raw)
        report["modules"][name] = {"undefined_symbols": undefined, "sections": checks}
    (output / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zig", required=True, type=Path)
    parser.add_argument("--arm-gcc", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    build(arguments.zig, arguments.arm_gcc, arguments.output)
    print("PASS: six modules, source/installed sections and link bindings verified; no camera I/O")
