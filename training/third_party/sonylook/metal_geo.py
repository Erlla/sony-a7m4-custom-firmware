"""Metal lens distortion and lateral chromatic aberration correction."""
from __future__ import annotations

import ctypes
import numpy as np

import metal_itp


def apply(planes, origin, region, lens):
    """Correct three uint16 planes for a region in decoder-image coordinates."""
    planes = tuple(np.ascontiguousarray(p, dtype=np.uint16) for p in planes)
    if len(planes) != 3 or planes[0].ndim != 2 or min(planes[0].shape) == 0 or any(p.shape != planes[0].shape for p in planes):
        raise ValueError("expected three identically shaped nonempty 2D planes")
    if len(origin) != 2 or len(region) != 4:
        raise ValueError("origin and region must contain 2 and 4 coordinates")
    x0, y0, x1, y1 = map(int, region)
    if x1 <= x0 or y1 <= y0:
        raise ValueError("output region must be nonempty")
    n = int(lens['n'])
    tables = tuple(np.ascontiguousarray(t, dtype=np.float32) for t in lens['tables'])
    if len(tables) != 3 or n < 2 or any(t.shape != (n,) for t in tables):
        raise ValueError("expected three lens tables with n >= 2 entries")
    params = np.array([lens['cx'], lens['cy'], lens['s'], lens['s2'], lens['step'],
                       *(v for pair in lens['off'] for v in pair)], dtype=np.float32)
    if params.shape != (11,) or params[4] <= 0:
        raise ValueError("lens offsets or knot spacing are invalid")
    out = [metal_itp.empty((y1-y0, x1-x0)) for _ in range(3)]
    lib = metal_itp._load()
    lib.sonylook_metal_geo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_uint32, ctypes.c_uint32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32,
        ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    rc = lib.sonylook_metal_geo(*(p.ctypes.data for p in planes), planes[0].shape[1], planes[0].shape[0],
        int(origin[0]), int(origin[1]), x0, y0, x1-x0, y1-y0, params.ctypes.data,
        *(t.ctypes.data for t in tables), n, *(p.ctypes.data for p in out))
    if rc:
        raise RuntimeError(lib.sonylook_metal_error().decode())
    return tuple(out)
