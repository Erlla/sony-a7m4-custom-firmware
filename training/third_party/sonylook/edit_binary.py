#!/usr/bin/env python3
"""Read constant tables from the user's own Imaging Edge Edit installation (nothing from it is stored here).

The table addresses in this project are written for Edit 4.0.00.10312, arm64 slice SHA-256
EXPECTED_SHA256. The same tables in 4.1.00.03062 sit at different addresses; BUILD_MAPS translates
them, so callers keep using the 4.0 addresses with either build.
Location: $SONY_EDIT_BINARY, else the default macOS install path. Universal (fat) binaries are handled;
the arm64 slice is used as is (same bytes as `lipo -thin arm64`).
Set SONY_EDIT_SKIP_CHECK=1 to use another build anyway (addresses will most likely be wrong).
"""
import hashlib
import os
import struct
from functools import lru_cache
from pathlib import Path

DEFAULT = "/Applications/Imaging Edge/Edit.app/Contents/MacOS/Edit"
RESOURCES = "/Applications/Imaging Edge/Edit.app/Contents/Resources"
EXPECTED_SHA256 = "a03b2449625f01003ee41d1a3f42630a20119059f65a74944c35eca81d5da442"
CPU_ARM64 = 0x0100000C

# arm64 slice SHA-256 -> (version, {4.0 table VA: table VA in that build}).
# 4.1's tables are byte-identical where they are used; the addresses were found by searching
# the 4.1 arm64 slice for each 4.0 table and checking the surrounding bytes.
_BUILD_MAPS = {
    "a03b2449625f01003ee41d1a3f42630a20119059f65a74944c35eca81d5da442": ("4.0.00.10312", {}),
    "c250f466835c5380d244de33a6824e9930fe3f250ce9b1d948d5e379cc4c8133": ("4.1.00.03062", {
        0x100237504: 0x10023abd4,   # decoder_params FUN_1000be0c8
        0x1002375dc: 0x10023acac,   # decoder_params FUN_1000be0f0
        0x100237550: 0x10023ac20,   # decoder_params FUN_1000be110
        0x10023759c: 0x10023ac6c,   # decoder_params FUN_1000be138
        0x1002375c4: 0x10023ac94,   # decoder_params FUN_1000be158
        0x100234730: 0x100237e00,   # sony_look HUE_ATAN_TABLE
        0x100246790: 0x100249e60,   # sony_look CONTRAST_FAMILY
        0x1002e6950: 0x1002eab38,   # sony_ycc SAT_TABLE
        0x100237c8c: 0x10023b35c,   # sony_ycc_stages DEFAULT_PAIRS
        0x100243f50: 0x100247620,   # sony_ycc_stages CS_T1
        0x100244000: 0x1002476d0,   # sony_ycc_stages CS_T2
        0x1002440b0: 0x100247780,   # sony_ycc_stages CS_T3
        0x100237bd8: 0x10023b2a8,   # build_color_table mode2_param8_nonzero
        0x100237bfc: 0x10023b2cc,   # build_color_table mode2_param8_zero
        0x100237c44: 0x10023b314,   # build_color_table mode1_param8_zero
        0x100237c68: 0x10023b338,   # build_color_table mode0_param8_nonzero
    }),
}

# Byte length of each 4.0 table, so reads at base + offset (the chroma-suppression curves)
# can be translated too. Addresses outside a table are left alone.
_TABLE_SIZES = {
    0x100237504: 76, 0x1002375dc: 40, 0x100237550: 76, 0x10023759c: 40, 0x1002375c4: 24,
    0x100234730: 2048, 0x100246790: 37 * 0x1004, 0x1002e6950: 152, 0x100237c8c: 40,
    0x100243f50: 176, 0x100244000: 176, 0x1002440b0: 176,
    0x100237bd8: 36, 0x100237bfc: 36, 0x100237c44: 36, 0x100237c68: 36,
}


def binary_path():
    return Path(os.environ.get("SONY_EDIT_BINARY", DEFAULT))


def resources_path():
    return Path(os.environ.get("SONY_EDIT_RESOURCES", RESOURCES))


@lru_cache(maxsize=1)
def arm64_slice():
    p = binary_path()
    if not p.exists():
        raise FileNotFoundError(f"Imaging Edge Edit not found at {p}; install Edit 4.0.00.10312 or "
                                "4.1.00.03062, or set SONY_EDIT_BINARY")
    data = p.read_bytes()
    if struct.unpack_from(">I", data)[0] in (0xCAFEBABE, 0xCAFEBABF):        # fat header (big endian)
        magic, n = struct.unpack_from(">II", data)
        wide = magic == 0xCAFEBABF
        for i in range(n):
            if wide:
                cpu, _, off, size = struct.unpack_from(">iiQQ", data, 8 + 32 * i)
            else:
                cpu, _, off, size = struct.unpack_from(">iiII", data, 8 + 20 * i)
            if cpu == CPU_ARM64:
                data = data[off:off + size]
                break
        else:
            raise ValueError(f"{p}: no arm64 slice")
    sha = hashlib.sha256(data).hexdigest()
    if sha not in _BUILD_MAPS and os.environ.get("SONY_EDIT_SKIP_CHECK") != "1":
        known = ", ".join(v for v, _ in _BUILD_MAPS.values())
        raise RuntimeError(f"{p}: arm64 slice SHA-256 {sha} is not one of the known builds ({known}); "
                           "table addresses are version specific (SONY_EDIT_SKIP_CHECK=1 to override)")
    return data


@lru_cache(maxsize=1)
def _default_sha():
    return hashlib.sha256(arm64_slice()).hexdigest()


def resolve_va(va, sha=None):
    """Translate a 4.0 table address (or an address inside one) to the installed build."""
    if sha is None:
        sha = _default_sha()
    entry = _BUILD_MAPS.get(sha)
    if not entry or not entry[1]:
        return va
    for old, new in entry[1].items():
        if old <= va < old + _TABLE_SIZES[old]:
            return new + (va - old)
    return va


@lru_cache(maxsize=1)
def segments():
    data = arm64_slice()
    magic, cpu, _, _, ncmds, _, _, _ = struct.unpack_from("<8I", data)
    assert magic == 0xFEEDFACF and cpu == CPU_ARM64
    out, off = [], 32
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", data, off)
        if cmd == 0x19:                                                     # LC_SEGMENT_64
            name, vmaddr, vmsize, fileoff, filesize = struct.unpack_from("<16sQQQQ", data, off + 8)
            out.append((name.rstrip(b"\0").decode(), vmaddr, vmsize, fileoff, filesize))
        off += size
    return out


def read_va(va, n):
    va = resolve_va(va)
    for name, vmaddr, vmsize, fileoff, filesize in segments():
        if vmaddr <= va and va + n <= vmaddr + filesize:
            o = fileoff + va - vmaddr
            return arm64_slice()[o:o + n]
    raise ValueError(f"0x{va:x}+{n} is not file-backed")
