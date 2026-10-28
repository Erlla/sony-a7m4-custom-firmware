"""Fixed-layout shutter policy and SD directory updates for local AP files.

The native build applies these edits after linking to preserve existing exports,
callers and state addresses. No camera or firmware-container operations occur.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import struct

OLD_DIRECTORY = b"/PRIVATE/SONY/PRO/SOUNDS/"
SOUND_DIRECTORY = b"/PRIVATE/M4ROOT/GENERAL/SOUNDS/"

# VA, original instruction/data, replacement, role. Keep validation and silence.
EDITS = (
    (0x8F990F4, "63000034", "03000014", "Allow enabling in valid shutter modes"),
    (0x8F99430, "41030034", "1a000014", "Preserve setting when shutter type changes"),
    (0x8F996DC, "6afdff35", "1f2003d5", "Route all valid exposure mechanisms"),
    (0x8F928F0, "28008052", "08008052", "Clear obsolete mechanical-off latch"),
    (0x8F98228, "61000054", "68000054", "Accept native mechanical/electronic menu values"),
    (0x8F93378, "22038052", "e2038052", "Scanner prefix length"),
    (0x8F9338C, "806e0091", "80860091", "Scanner wildcard position"),
    (0x8F9339C, "ffb30039", "ffcb0039", "Scanner terminator position"),
    (0x8F936CC, "22038052", "e2038052", "Importer prefix length"),
    (0x8F936DC, "c06e0091", "c0860091", "Importer filename position"),
    (0x8F936F8, "1f6d0039", "1f850039", "Importer terminator position"),
    (0x8F9A18F, (OLD_DIRECTORY + bytes(7)).hex(), (SOUND_DIRECTORY + bytes(1)).hex(), "Shared directory"),
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def edits_in_section(data: bytes, va: int) -> bytes:
    """Apply edits fully inside one pinned section, checking each original span."""
    result = bytearray(data)
    for address, before_hex, after_hex, _ in EDITS:
        before, after = bytes.fromhex(before_hex), bytes.fromhex(after_hex)
        if va <= address < va + len(data):
            offset = address - va
            if len(before) != len(after) or offset + len(before) > len(data) or data[offset:offset + len(before)] != before:
                raise ValueError(f"Shutter policy preimage mismatch at {address:#x}")
            result[offset:offset + len(after)] = after
    return bytes(result)


def patch_ap(data: bytes, identities: dict[str, str]) -> bytes:
    """Patch a complete ELF only when both input/output identities are known."""
    source = digest(data)
    if source not in identities:
        raise ValueError("Unsupported AP SHA-256")
    if data[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", data, 18)[0] != 183:
        raise ValueError("Expected little-endian AArch64 ELF")
    phoff = struct.unpack_from("<Q", data, 32)[0]
    size, count = struct.unpack_from("<HH", data, 54)
    result = bytearray(data)
    applied = set()
    for index in range(count):
        kind, _, offset, va, _, length, _, _ = struct.unpack_from("<IIQQQQQQ", data, phoff + index * size)
        if kind != 1:
            continue
        for address, before_hex, after_hex, _ in EDITS:
            before, after = bytes.fromhex(before_hex), bytes.fromhex(after_hex)
            if va <= address and address + len(before) <= va + length:
                at = offset + address - va
                if address in applied or data[at:at + len(before)] != before:
                    raise ValueError(f"Shutter policy mapping/preimage mismatch at {address:#x}")
                result[at:at + len(after)] = after
                applied.add(address)
    if len(applied) != len(EDITS) or digest(result) != identities[source]:
        raise ValueError("Shutter policy output identity mismatch")
    return bytes(result)


def main() -> None:
    import json
    from importlib.resources import files
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    identities = json.loads(files("a7m4").joinpath("profiles/custom-sound-policy.json").read_text("utf-8"))["AP_identities"]
    result = patch_ap(args.input.read_bytes(), identities)
    with args.output.open("xb") as stream:
        stream.write(result)
    print(digest(result))


if __name__ == "__main__":
    main()
