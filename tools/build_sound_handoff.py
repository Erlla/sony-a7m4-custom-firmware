"""Build the integrated CP handoff and verify every allocated section."""
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
from a7m4.custom_sound_handoff import load_profile
from elftools.elf.elffile import ELFFile


def build(compiler: Path, output: Path) -> dict:
    profile = load_profile()
    source = ROOT / "native/custom-sounds/handoff"
    for name, expected in profile["sources"].items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Source identity mismatch: " + name)
    output.mkdir(parents=True, exist_ok=False)
    output = output.resolve()
    relative = Path(os.path.relpath(source, output))
    command = [str(compiler.resolve()), *profile["compiler_flags"], "-Wl,-e,sound_handoff_admit",
               "-Wl,-T," + str(relative / "handoff.ld"), str(relative / "handoff.c"),
               str(relative / "handoff.S"), "-o", "handoff.elf"]
    subprocess.run(command, cwd=output, check=True)
    elf = ELFFile(io.BytesIO((output / "handoff.elf").read_bytes()))
    undefined = [s.name for s in elf.get_section_by_name(".symtab").iter_symbols()
                 if s.name and s["st_shndx"] == "SHN_UNDEF"]
    if undefined:
        raise ValueError("Undefined symbols: " + ", ".join(undefined))
    sections = []
    for expected in profile["sections"]:
        section = elf.get_section_by_name(expected["name"])
        if section is None or section["sh_addr"] != int(expected["va"], 16) or section["sh_size"] != expected["bytes"]:
            raise ValueError("Section layout mismatch: " + expected["name"])
        if expected["nobits"]:
            if section["sh_type"] != "SHT_NOBITS":
                raise ValueError("Expected zero-initialized BSS")
        elif hashlib.sha256(section.data()).hexdigest() != expected["sha256"]:
            raise ValueError("Compiled section mismatch: " + expected["name"])
        sections.append(expected)
    report = {"sections": sections, "undefined_symbols": undefined, "camera_io": False}
    (output / "verification.json").write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm-gcc", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    build(args.arm_gcc, args.output)
    print("PASS: handoff sources, sections and link bindings verified")
