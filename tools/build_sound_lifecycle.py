"""Build and verify the AP/CP sound lifecycle modules without camera I/O."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from a7m4.custom_sound_lifecycle import load_profile
from elftools.elf.elffile import ELFFile


def build(compiler: Path, zig: Path, output: Path) -> dict:
    profile = load_profile()
    source = ROOT / "native/custom-sounds/lifecycle"
    for name, expected in profile["source_hashes"].items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Source identity mismatch: " + name)
    output.mkdir(parents=True, exist_ok=False)
    output = output.resolve()
    report = {"modules": [], "camera_io": False}
    for module in profile["modules"]:
        architecture = module["architecture"]
        command = [str(compiler.resolve())] if architecture == "arm" else [str(zig.resolve()), "cc"]
        command += profile["compiler_flags"][architecture]
        if architecture == "aarch64":
            command.append("-Wl,-no-pie")
        command += ["-Wl,-e," + module["entry"], "-Wl,-T," + str(source / module["linker"])]
        command += module["extra_link_flags"]
        target = output / (module["name"] + ".elf")
        command += [str(source / name) for name in module["sources"]] + ["-o", str(target)]
        subprocess.run(command, cwd=source, check=True)
        elf = ELFFile(io.BytesIO(target.read_bytes()))
        undefined = [s.name for s in elf.get_section_by_name(".symtab").iter_symbols()
                     if s.name and s["st_shndx"] == "SHN_UNDEF"]
        if undefined:
            raise ValueError("Undefined symbols: " + ", ".join(undefined))
        actual = []
        for section in elf.iter_sections():
            if section["sh_flags"] & 2 and section["sh_size"]:
                row = dict(name=section.name, VA=section["sh_addr"], bytes=section["sh_size"],
                           nobits=section["sh_type"] == "SHT_NOBITS")
                if not row["nobits"]:
                    row["sha256"] = hashlib.sha256(section.data()).hexdigest()
                actual.append(row)
        if actual != module["sections"]:
            raise ValueError("Compiled section mismatch: " + module["name"])
        report["modules"].append(dict(name=module["name"], sections=actual))
        print("PASS " + module["name"], flush=True)
    (output / "verification.json").write_text(json.dumps(report, indent=2) + "\n", "utf-8", newline="\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm-gcc", required=True, type=Path)
    parser.add_argument("--zig", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    build(args.arm_gcc, args.zig, args.output)
