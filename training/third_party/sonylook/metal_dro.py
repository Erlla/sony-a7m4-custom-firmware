"""Metal DRO grid analysis and local tone mapping."""
from __future__ import annotations

import ctypes
import numpy as np

import metal_itp
import sony_dro


def apply(raw, planes, black, curve, *, origin=(0, 0), strength=1.0,
          k_up=1.0, k_down=1.0, scale=1.0, debug=False):
    """Build the DRO grid from raw and apply it to three uint16 ITP planes."""
    raw = np.ascontiguousarray(raw, dtype=np.uint16)
    planes = tuple(np.ascontiguousarray(p, dtype=np.uint16) for p in planes)
    black = np.ascontiguousarray(black, dtype=np.int32)
    curve = np.ascontiguousarray(curve, dtype=np.float32)
    if raw.ndim != 2 or raw.shape[0] < 336 or raw.shape[1] < 448:
        raise ValueError("DRO raw grid requires at least 448 x 336 pixels")
    if len(planes) != 3 or planes[0].ndim != 2 or any(p.shape != planes[0].shape for p in planes):
        raise ValueError("expected three identically shaped 2D planes")
    if black.shape != (3,) or curve.shape != (104,):
        raise ValueError("expected three black levels and a 104-element curve")
    if len(origin) != 2:
        raise ValueError("origin must contain x and y")
    out = [metal_itp.empty(p.shape) for p in planes]
    sub = np.empty((84, 112), np.float32) if debug else None
    W = np.empty((6, 8, 14), np.float32) if debug else None
    S = np.empty((6, 8, 14), np.float32) if debug else None
    lib = metal_itp._load()
    lib.sonylook_metal_dro.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
        ctypes.c_void_p, ctypes.c_int32, ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    rc = lib.sonylook_metal_dro(raw.ctypes.data, raw.shape[1], raw.shape[0],
        *(p.ctypes.data for p in planes), planes[0].shape[1], planes[0].shape[0],
        black.ctypes.data, int(origin[0]), int(origin[1]), sony_dro.LOG_T.ctypes.data,
        curve.ctypes.data, sony_dro.LOG2_MAX, float(strength), float(k_up), float(k_down), float(scale),
        *(p.ctypes.data for p in out), *(p.ctypes.data if p is not None else None for p in (sub, W, S)))
    if rc:
        raise RuntimeError(lib.sonylook_metal_error().decode())
    return (tuple(out), (sub, W, S)) if debug else tuple(out)
