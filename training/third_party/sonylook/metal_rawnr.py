"""Metal ZcTaskRawNR (CFA-domain noise reduction), as sony_rawnr.rawnr on the whole image."""
from __future__ import annotations

import ctypes
import numpy as np

import metal_itp
import sony_rawnr as N


class NrArgs(ctypes.Structure):
    _fields_ = [("width", ctypes.c_uint32), ("height", ctypes.c_uint32),
                ("off", ctypes.c_int32 * 3), ("gain", ctypes.c_int32 * 3),
                ("lim", ctypes.c_int32 * 3), ("wm", ctypes.c_int32 * 3), ("s", ctypes.c_float)]


def apply(raw, look, iso=100, settings=(0, 0, 0), strength_override=None):
    """RawNR on a uint16 RGGB raw (RGGB at even/even); returns a new uint16 array."""
    raw = np.ascontiguousarray(raw, dtype=np.uint16)
    if raw.ndim != 2 or min(raw.shape) < 21:
        raise ValueError("expected a 2D raw of at least 21 x 21")
    tb = N.tables(look, *settings)
    s = N.strength(iso) if strength_override is None else np.float32(strength_override)
    L18, L1c, L20, L24, L28 = (look[o] for o in (0x1018, 0x101c, 0x1020, 0x1024, 0x1028))
    a = NrArgs()
    for k, off in enumerate((L18 - L20, L18 - (L1c + L28), L18 - L24)):
        a.off[k] = int(off)
        a.gain[k] = int(tb["gain"][k])
        a.lim[k] = int(tb["lim"][k])
        a.wm[k] = int(tb["W"][k])
    a.s = float(s)
    thr = np.ascontiguousarray(np.stack([np.asarray(t, np.int64) for t in tb["T"]]), dtype=np.int32)
    out = metal_itp.empty(raw.shape)
    lib = metal_itp._load()
    lib.sonylook_metal_rawnr.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                                        ctypes.POINTER(NrArgs), ctypes.c_void_p, ctypes.c_void_p]
    rc = lib.sonylook_metal_rawnr(raw.ctypes.data, raw.shape[1], raw.shape[0], ctypes.byref(a),
                                 thr.ctypes.data, out.ctypes.data)
    if rc:
        raise RuntimeError(lib.sonylook_metal_error().decode())
    return out
