"""Locate and decode the CFA raw in a Sony ARW.

Sony's lossless compressed raw (TIFF compression 7) is stored as tiles, each a
lossless JPEG (SOF3) whose four components carry a 2x2 block of the mosaic.
The tiles are independent, so the Rust core decodes them in parallel
(`ljpeg_tiles_u16`).  Other raw formats go through rawpy.
"""
from __future__ import annotations

import ctypes
import struct
from dataclasses import dataclass

import numpy as np

_TYPES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8, 13: 4}


@dataclass
class RawIFD:
    width: int
    height: int
    bps: int
    compression: int
    tile_width: int
    tile_height: int
    offsets: list
    counts: list
    cfa: bytes = b""          # CFAPattern (0x828e): b"\x00\x01\x01\x02" is RGGB


def _read_ifd(f, off, bo):
    f.seek(off)
    n = struct.unpack(bo + "H", f.read(2))[0]
    data = f.read(12 * n)
    nxt = struct.unpack(bo + "I", f.read(4))[0]
    tags = {}
    for i in range(n):
        tag, typ, cnt, val = struct.unpack(bo + "HHI4s", data[12 * i:12 * i + 12])
        size = _TYPES.get(typ, 1) * cnt
        if size > 4:
            here = f.tell()
            f.seek(struct.unpack(bo + "I", val)[0])
            raw = f.read(size)
            f.seek(here)
        else:
            raw = val[:size]
        if typ == 3:
            v = list(struct.unpack(bo + f"{cnt}H", raw))
        elif typ in (4, 13):
            v = list(struct.unpack(bo + f"{cnt}I", raw))
        else:
            v = raw
        tags[tag] = v
    return tags, nxt


def raw_ifd(path):
    """The tiled CFA raw IFD (main IFDs and their SubIFDs), or None."""
    with open(path, "rb") as f:
        head = f.read(8)
        bo = "<" if head[:2] == b"II" else ">"
        off = struct.unpack(bo + "I", head[4:8])[0]
        seen = set()
        todo = []
        while off and off not in seen:
            seen.add(off)
            tags, off = _read_ifd(f, off, bo)
            todo.append(tags)
            for sub in tags.get(0x14A, []):
                if sub not in seen:
                    seen.add(sub)
                    todo.append(_read_ifd(f, sub, bo)[0])
        for t in todo:
            if 0x144 in t and 0x145 in t and 0x142 in t and t.get(0x106, [32803])[0] == 32803:
                return RawIFD(width=t[0x100][0], height=t[0x101][0], bps=t[0x102][0],
                              compression=t[0x103][0], tile_width=t[0x142][0], tile_height=t[0x143][0],
                              offsets=list(t[0x144]), counts=list(t[0x145]),
                              cfa=bytes(t.get(0x828E, b"")))
    return None


def decode_lossless(path, threads=0, ifd=None):
    """Full raw array (raw_height x raw_width uint16) for compression-7 files, or None."""
    import fused_rust as FR
    ifd = raw_ifd(path) if ifd is None else ifd
    if ifd is None or ifd.compression != 7:
        return None
    import sr2
    data = sr2.file_bytes(path)
    buf = np.frombuffer(data, np.uint8)
    offs = np.ascontiguousarray(ifd.offsets, np.uint64)
    cnts = np.ascontiguousarray(ifd.counts, np.uint64)
    if len(offs) != len(cnts) or int((offs + cnts).max()) > len(data):
        raise ValueError("raw tile offsets outside the file")
    out = np.empty((ifd.height, ifd.width), np.uint16)
    fn = FR._load_symbol("ljpeg_tiles_u16")
    fn.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                   ctypes.c_size_t, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_size_t,
                   ctypes.c_void_p]
    fn.restype = ctypes.c_int32
    rc = fn(buf.ctypes.data, len(data), offs.ctypes.data, cnts.ctypes.data, len(offs),
            ifd.width, ifd.height, ifd.tile_width, ifd.tile_height, int(threads), out.ctypes.data)
    if rc != 0:
        raise RuntimeError(f"ljpeg_tiles_u16 failed on tile {rc - 1}" if rc > 0 else f"ljpeg_tiles_u16 failed: {rc}")
    return out


def read_raw(path, rust=True):
    """raw_image_visible as rawpy returns it, decoded by the Rust core when possible."""
    import rawpy
    rggb = "only RGGB sensors are wired through the full pipeline"
    with rawpy.imread(str(path)) as r:
        # rawpy's raw_pattern unpacks the whole raw; the Rust path checks the
        # IFD's CFAPattern tag instead and only uses LibRaw for the margins.
        assert r.color_desc == b"RGBG", rggb
        s = r.sizes
        full = None
        ifd = raw_ifd(path) if rust else None
        if ifd is not None and ifd.cfa == b"\x00\x01\x01\x02":   # otherwise rawpy decides the pattern
            try:
                full = decode_lossless(path, ifd=ifd)
            except OSError:          # Rust library missing or outdated
                full = None
            except (RuntimeError, ValueError) as exc:
                import warnings
                warnings.warn(f"Rust raw decoder failed ({exc}); using rawpy")
                full = None
        if full is not None and full.shape == (s.raw_height, s.raw_width):
            return np.ascontiguousarray(full[s.top_margin:s.top_margin + s.height,
                                             s.left_margin:s.left_margin + s.width])
        assert r.raw_pattern.tolist() == [[0, 1], [3, 2]], rggb
        return np.array(r.raw_image_visible, np.uint16, copy=True)
