"""Metal implementation of Sony's integer near-saturation colour suppression."""
from __future__ import annotations

import ctypes
import numpy as np

import metal_itp


def apply(planes, params):
    """Apply SSCS to three uint16 planes and return an interleaved RGB image."""
    planes = tuple(np.ascontiguousarray(p, dtype=np.uint16) for p in planes)
    if len(planes) != 3 or planes[0].ndim != 2 or min(planes[0].shape) == 0 or any(p.shape != planes[0].shape for p in planes):
        raise ValueError("expected three identically shaped nonempty 2D planes")
    values = np.asarray([params['T'], params['tR'], params['tG'], params['tB'], *params['w']], dtype=np.int32)
    if values.shape != (7,):
        raise ValueError("SSCS parameters must include three channel weights")
    out = metal_itp.empty((*planes[0].shape, 3))
    lib = metal_itp._load()
    lib.sonylook_metal_sscs.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                       ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p]
    rc = lib.sonylook_metal_sscs(*(p.ctypes.data for p in planes), planes[0].shape[1],
                                planes[0].shape[0], values.ctypes.data, out.ctypes.data)
    if rc:
        raise RuntimeError(lib.sonylook_metal_error().decode())
    return out
