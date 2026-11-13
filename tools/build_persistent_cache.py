"""Build the shared persistent-cache module without firmware or camera IO."""
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
from a7m4.persistent_cache import load_profile
from elftools.elf.elffile import ELFFile


def build(zig: Path, output: Path, lut_only: bool = False) -> dict:
    profile = load_profile()
    if lut_only:
        profile = json.loads((ROOT / "native/custom-lut/runtime-cleanup/cache-build.json").read_text("utf-8"))
        if hashlib.sha256(zig.read_bytes()).hexdigest() != profile["compiler_sha256"]:
            raise ValueError("Compiler identity mismatch")
    source = ROOT / "native/persistent-cache"
    for name, expected in profile["source_hashes"].items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Source identity mismatch: " + name)
    for name, expected in profile["source_header_dependencies"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Header identity mismatch: " + name)
    output.mkdir(parents=True, exist_ok=False)
    output = output.resolve()
    linker = (source / "cache.ld").read_text("utf-8") + "\n"
    linker += "".join(f"{name} = 0x{value:x};\n" for name, value in profile["original_functions"].items())
    script = output / "cache-final.ld"
    script.write_text(linker, "utf-8", newline="\n")
    flags = "-target aarch64-freestanding-none -mcpu=generic-neon-fp_armv8 -mgeneral-regs-only -mno-outline-atomics -mstrict-align -fpie -Os -g -std=c11 -Wall -Wextra -Werror -ffreestanding -fno-builtin -fno-stack-protector -fno-unwind-tables -fno-asynchronous-unwind-tables -nostdlib -static".split()
    sources = ("lut_cache.c", "memory.c") if lut_only else ("lut_cache.c", "sound_cache.c", "memory.c")
    sound_exports = [] if lut_only else ["-Wl,-u,snd_convert_cached"]
    command = [str(zig.resolve()), "cc", *flags, "-Wl,-no-pie", "-Wl,-e,lut_read_cached",
               "-Wl,-u,lut_verify_cached", *sound_exports, "-Wl,-T," + str(script),
               *[str(source / name) for name in sources],
               "-o", str(output / "cache.elf")]
    subprocess.run(command, cwd=ROOT, check=True)
    elf = ELFFile(io.BytesIO((output / "cache.elf").read_bytes()))
    undefined = [s.name for s in elf.get_section_by_name(".symtab").iter_symbols()
                 if s.name and s["st_shndx"] == "SHN_UNDEF"]
    segments = [s for s in elf.iter_segments() if s["p_type"] == "PT_LOAD"]
    if undefined or len(segments) != 1:
        raise ValueError("Unexpected module segments or unresolved symbols")
    segment = segments[0]
    expected = profile["module"]
    if segment["p_vaddr"] != expected["VA"] or segment["p_filesz"] != expected["bytes"] or segment["p_memsz"] != expected["bytes"] or hashlib.sha256(segment.data()).hexdigest() != expected["code_sha256"]:
        raise ValueError("Compiled module differs from pinned installed code")
    if any(s["sh_type"] in ("SHT_REL", "SHT_RELA") and s["sh_size"] for s in elf.iter_sections()):
        raise ValueError("Unexpected runtime relocations")
    report = {"module": expected, "undefined_symbols": undefined, "added_BSS_bytes": 0,
              "camera_io": False, "lut_only": lut_only}
    (output / "verification.json").write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zig", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--lut-only", action="store_true", help="Build the runtime-cleanup LUT cache")
    args = parser.parse_args()
    build(args.zig, args.output, args.lut_only)
    print("PASS: persistent-cache sources and installed module match")
