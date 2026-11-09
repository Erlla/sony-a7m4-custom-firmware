"""Metal look front (LinearMatrix16 through ChromaSuppress), spatial stages (Sharpness through YCC2RGB) and Marble."""
from __future__ import annotations

import ctypes
import numpy as np

import metal_itp


def apply(rgb, table, gamma, atan, thresholds=(0, 0, 0)):
    """Apply the full-resolution Sony look's first two stages to uint16 RGB."""
    rgb = np.ascontiguousarray(rgb, dtype=np.uint16)
    table = np.ascontiguousarray(table, dtype=np.float32)
    gamma = np.ascontiguousarray(gamma, dtype=np.int16)
    atan = np.ascontiguousarray(atan, dtype=np.float32)
    thresholds = np.ascontiguousarray(thresholds, dtype=np.float32)
    if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.shape[1] < 5 or rgb.shape[0] == 0:
        raise ValueError("expected nonempty H x W x 3 RGB with width >= 5")
    if table.shape != (1024, 18) or gamma.shape != (65536,) or atan.shape != (512,) or thresholds.shape != (3,):
        raise ValueError("invalid look table, gamma, atan or threshold shape")
    out = metal_itp.empty(rgb.shape, np.int16)
    lib = metal_itp._load()
    lib.sonylook_metal_look.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                                       ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                       ctypes.c_void_p, ctypes.c_void_p]
    rc = lib.sonylook_metal_look(rgb.ctypes.data, rgb.shape[1], rgb.shape[0], table.ctypes.data,
                                gamma.ctypes.data, atan.ctypes.data, thresholds.ctypes.data, out.ctypes.data)
    if rc:
        raise RuntimeError(lib.sonylook_metal_error().decode())
    return out


class FrontArgs(ctypes.Structure):
    _fields_ = [("width", ctypes.c_uint32), ("height", ctypes.c_uint32),
                ("thresholds", ctypes.c_float * 3),
                ("c0", ctypes.c_int32), ("c1", ctypes.c_int32), ("c2", ctypes.c_int32),
                ("k8", ctypes.c_float), ("k9", ctypes.c_float), ("k10", ctypes.c_float), ("k11", ctypes.c_float),
                ("gcr_pos", ctypes.c_float), ("gcr_neg", ctypes.c_float),
                ("gcb_pos", ctypes.c_float), ("gcb_neg", ctypes.c_float),
                ("area", ctypes.c_float * 16), ("area_flag", ctypes.c_int32),
                ("w9", ctypes.c_int32), ("w12", ctypes.c_int32), ("w8", ctypes.c_int32), ("w11", ctypes.c_int32)]


def _i32(v):
    v = int(v) & 0xffffffff
    return v - (1 << 32) if v & 0x80000000 else v


def front_args(look, thresholds=(0, 0, 0)):
    """RGB2YCC / AreaComp / ChromaSuppress constants of a sony_render.Look."""
    import sony_ycc as SY
    a = FrontArgs()
    for i in range(3):
        a.thresholds[i] = float(thresholds[i])
    a.c0, a.c1, a.c2 = (SY.i16(int(v) << 7 & 0xffff) for v in look.luma)
    p = [SY.i16(v) for v in look.ycc_params]
    a.k8, a.k9, a.k10, a.k11 = (SY._shear(p[i]) * 0.00390625 for i in (1, 3, 0, 2))
    gain = lambda v: ((v & 0xffff) >> 3 & 0xff) * 0.015625
    a.gcr_pos, a.gcr_neg, a.gcb_pos, a.gcb_neg = gain(p[5]), gain(p[7]), gain(p[4]), gain(p[6])
    area, flag = look.area_comp if look.area_comp is not None else ([0.0] * 16, 0)
    for i in range(16):
        a.area[i] = float(area[i])
    a.area_flag = int(flag)
    a.w9, a.w12, a.w8, a.w11 = (_i32(v) for v in look.cs)
    return a


def _planes(h, w):
    return tuple(metal_itp.empty((h, w)) for _ in range(3))


def front(rgb, look, atan, args=None):
    """LinearMatrix16 through ChromaSuppress on uint16 RGB; returns (Y, Cr, Cb) uint16 planes."""
    rgb = np.ascontiguousarray(rgb, dtype=np.uint16)
    table = np.ascontiguousarray(look.table, dtype=np.float32)
    gamma = np.ascontiguousarray(look.gamma, dtype=np.int16)
    atan = np.ascontiguousarray(atan, dtype=np.float32)
    if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.shape[1] < 5 or rgb.shape[0] == 0:
        raise ValueError("expected nonempty H x W x 3 RGB with width >= 5")
    if table.shape != (1024, 18) or gamma.shape != (65536,) or atan.shape != (512,):
        raise ValueError("invalid look table, gamma or atan shape")
    args = front_args(look) if args is None else args
    out = _planes(*rgb.shape[:2])
    lib = metal_itp._load()
    lib.sonylook_metal_front.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                                        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                        ctypes.POINTER(FrontArgs),
                                        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    rc = lib.sonylook_metal_front(rgb.ctypes.data, rgb.shape[1], rgb.shape[0], table.ctypes.data,
                                 gamma.ctypes.data, atan.ctypes.data, ctypes.byref(args),
                                 *(p.ctypes.data for p in out))
    if rc:
        raise RuntimeError(lib.sonylook_metal_error().decode())
    return out


def encoded_front(encoded, look, args=None):
    """RGB2YCC, AreaComp and ChromaSuppress on interleaved int16 MainGamma RGB."""
    encoded = np.ascontiguousarray(encoded, dtype=np.int16)
    if encoded.ndim != 3 or encoded.shape[2] != 3 or 0 in encoded.shape:
        raise ValueError("expected nonempty H x W x 3 encoded RGB")
    args = front_args(look) if args is None else args
    out = _planes(*encoded.shape[:2])
    lib = metal_itp._load()
    lib.sonylook_metal_encoded_front.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                                                ctypes.POINTER(FrontArgs),
                                                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    rc = lib.sonylook_metal_encoded_front(encoded.ctypes.data, encoded.shape[1], encoded.shape[0],
                                         ctypes.byref(args), *(p.ctypes.data for p in out))
    if rc:
        raise RuntimeError(lib.sonylook_metal_error().decode())
    return out


class SpatialArgs(ctypes.Structure):
    _fields_ = [("width", ctypes.c_uint32), ("height", ctypes.c_uint32),
                ("sharp_thr", ctypes.c_float), ("sharp_s0", ctypes.c_float), ("sharp_s1", ctypes.c_float),
                ("sharp_s9", ctypes.c_float), ("sharp_k", ctypes.c_float),
                ("yg_s0", ctypes.c_float), ("yg_s1", ctypes.c_float),
                ("yg_s2", ctypes.c_float), ("yg_s3", ctypes.c_float),
                ("spica_thr", ctypes.c_uint32), ("spica_full", ctypes.c_int32),
                ("spica_gain_on", ctypes.c_int32), ("spica_s", ctypes.c_float), ("spica_k", ctypes.c_float),
                ("s", ctypes.c_float * 25)]


class Spatial:
    """Sharpness / YGamma / Spica constants and tables for the Metal spatial kernels."""

    def __init__(self, look, detail):
        import fused_rust as FR
        import sony_ycc as SY
        cfg = FR.spatial_config_from_look(look, detail)
        p, f = cfg.params, np.float32
        self.ylut, self.patterns, self.coefs = cfg.keep
        a = SpatialArgs()
        for k in ("sharp_thr", "sharp_s0", "sharp_s1", "sharp_s9", "sharp_k", "spica_full", "spica_s"):
            setattr(a, k, getattr(p, k))
        a.spica_gain_on = p.spica_gain_on
        a.spica_thr = min(int(p.spica_thr), 0xffffffff)
        # Same float32 operation order as ygamma() / spica() in the Rust core.
        w13 = p.ygamma_ac + 3 if p.ygamma_ac < 0 else p.ygamma_ac
        nq = SY.i16(-(w13 >> 2))
        a.yg_s0 = f(SY.i16(p.ygamma_off))
        a.yg_s1 = p.ygamma_gain
        a.yg_s2 = f(nq) * f(63.998047)
        a.yg_s3 = f(1.0) / f(0x200 - p.ygamma_b0 - nq)
        a.spica_k = f(f(p.spica_k2) * f(0.0002)) * f(p.dev208 + 100) * f(100 - p.dev2c4)
        for i in range(25):
            a.s[i] = p.s[i]
        self.args = a


def spatial(y, cr, cb, sp: Spatial):
    """Sharpness -> YGamma -> Spica -> YCC2RGB on whole Y/Cr/Cb planes; returns (R, G, B)."""
    planes = [np.ascontiguousarray(v, dtype=np.uint16) for v in (y, cr, cb)]
    h, w = planes[0].shape
    if any(v.shape != (h, w) for v in planes) or h < 7 or w < 7:
        raise ValueError("expected three identically shaped planes of at least 7 x 7")
    out = _planes(h, w)
    lib = metal_itp._load()
    lib.sonylook_metal_spatial.argtypes = [ctypes.c_void_p] * 3 + [ctypes.c_uint32, ctypes.c_uint32,
                                          ctypes.POINTER(SpatialArgs)] + [ctypes.c_void_p] * 6
    rc = lib.sonylook_metal_spatial(*(v.ctypes.data for v in planes), w, h, ctypes.byref(sp.args),
                                   sp.ylut.ctypes.data, sp.patterns.ctypes.data, sp.coefs.ctypes.data,
                                   *(v.ctypes.data for v in out))
    if rc:
        raise RuntimeError(lib.sonylook_metal_error().decode())
    return out


def front_spatial(rgb, look, atan, sp: Spatial, args=None):
    """LinearMatrix16 through YCC2RGB on uint16 RGB in one GPU pass; returns (R, G, B)."""
    rgb = np.ascontiguousarray(rgb, dtype=np.uint16)
    table = np.ascontiguousarray(look.table, dtype=np.float32)
    gamma = np.ascontiguousarray(look.gamma, dtype=np.int16)
    atan = np.ascontiguousarray(atan, dtype=np.float32)
    if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.shape[0] < 7 or rgb.shape[1] < 7:
        raise ValueError("expected H x W x 3 RGB of at least 7 x 7")
    args = front_args(look) if args is None else args
    out = _planes(*rgb.shape[:2])
    lib = metal_itp._load()
    lib.sonylook_metal_front_spatial.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32] + \
        [ctypes.c_void_p] * 3 + [ctypes.POINTER(FrontArgs), ctypes.POINTER(SpatialArgs)] + [ctypes.c_void_p] * 6
    rc = lib.sonylook_metal_front_spatial(rgb.ctypes.data, rgb.shape[1], rgb.shape[0], table.ctypes.data,
                                         gamma.ctypes.data, atan.ctypes.data, ctypes.byref(args),
                                         ctypes.byref(sp.args), sp.ylut.ctypes.data, sp.patterns.ctypes.data,
                                         sp.coefs.ctypes.data, *(v.ctypes.data for v in out))
    if rc:
        raise RuntimeError(lib.sonylook_metal_error().decode())
    return out


class MarbleArgs(ctypes.Structure):
    _fields_ = [(k, ctypes.c_uint32) for k in ("width", "height", "w4", "h4", "n8w", "n8h")] + \
               [("m_fwd", ctypes.c_int32 * 9), ("m_inv", ctypes.c_int32 * 9)] + \
               [(k, ctypes.c_int32) for k in ("thr_y", "a_y", "g20", "g24", "lo_l", "hi_l", "gate",
                                              "g34", "g38", "g3c", "g40")] + \
               [("f", ctypes.c_float), ("inset", ctypes.c_int32)] + \
               [(k, ctypes.c_int32) for k in ("lum_on", "bnr", "blk", "nbw", "nbh")] + \
               [("d0", ctypes.c_uint32)] + \
               [(k, ctypes.c_int32) for k in ("cc", "c8", "c4", "c0", "bc", "b8", "b4", "b0", "ac", "a8",
                                              "l98", "l90", "l88", "t7c", "t80")] + \
               [("up_t", ctypes.c_int32 * 4)]


def marble_supported(look, dev):
    """Clarity 0..109; something to do (chroma NR on, or Clarity > 0)."""
    lum = int(dev["d2c0"])
    bnr = dev["d218"] == 1 and look.s16(0x109c) != 0
    return 0 <= lum <= 109 and (bnr or lum > 0)


def marble(r, g, b, look, dev, dec, mode=0, inset=True):
    """ZcTaskMarble (luma and chroma paths) on whole uint16 planes, as sony_marble.marble with no region.

    inset=True keeps the input values outside the 16-px valid region, as render's
    marble_inset does.  Returns (R, G, B), or None when marble_supported() is false."""
    import sony_effect as E
    import sony_marble as MB
    if not marble_supported(look, dev):
        return None
    planes = [np.ascontiguousarray(v, dtype=np.uint16) for v in (r, g, b)]
    h, w = planes[0].shape
    if any(v.shape != (h, w) for v in planes) or h < 10 or w < 10:
        raise ValueError("expected three identically shaped planes of at least 10 x 10")
    lum = int(dev["d2c0"])
    P, thr_y, a_y, G = MB.luma_params(look, dev, dec, lum)
    a = MarbleArgs()
    a.lum_on = 1 if lum else 0
    a.bnr = 1 if (dev["d218"] == 1 and look.s16(0x109c) != 0) else 0
    if a.bnr:
        a.blk = 8 if look.s16(0x109e) == 1 else 4
        a.d0 = int(P["d0"]) & 0xffffffff
        for k in ("cc", "c8", "c4", "c0", "bc", "b8", "b4", "b0", "ac", "a8", "l98", "l90", "l88"):
            setattr(a, k, _i32(P[k]))
        a.t7c = MB._recip_signed(P["l94"] - P["l98"])
        a.t80 = MB._recip_signed(P["l8c"] - P["l90"])
        for i, off in enumerate(MB.UP_TABLES[a.blk]):
            a.up_t[i] = (off - MB.UPW_BASE) // 4
    for i, v in enumerate(int(x) for row in E.M_FWD[mode] for x in row):
        a.m_fwd[i] = v
    for i, v in enumerate(int(x) for row in E.M_INV[mode] for x in row):
        a.m_inv[i] = v
    a.thr_y, a.a_y = int(thr_y), int(a_y)
    for k, src in (("g20", "g20"), ("g24", "g24"), ("lo_l", "lo"), ("hi_l", "hi"), ("gate", "gate"),
                   ("g34", "g34"), ("g38", "g38"), ("g3c", "g3c"), ("g40", "g40")):
        setattr(a, k, _i32(G[src]))
    a.f = float(MB.strength(dev["d224"], dec))
    a.inset = 1 if inset else 0
    T = E.tables()
    names = ("srgb_dec" if mode == 0 else "gamma_dec", "gamma_enc",
             "gamma_dec", "srgb_enc" if mode == 0 else "gamma_enc")
    tabs = [np.ascontiguousarray(T[k], dtype=np.int16) for k in names]
    if any(t.shape != (0x4000,) for t in tabs):
        raise ValueError("Marble conversion tables must have 0x4000 entries")
    upw = np.ascontiguousarray(MB.UPW, dtype=np.int32)
    out = _planes(h, w)
    lib = metal_itp._load()
    lib.sonylook_metal_marble.argtypes = [ctypes.c_void_p] * 3 + [ctypes.c_uint32, ctypes.c_uint32,
                                         ctypes.POINTER(MarbleArgs)] + [ctypes.c_void_p] * 5 + \
                                        [ctypes.c_uint32] + [ctypes.c_void_p] * 3
    rc = lib.sonylook_metal_marble(*(v.ctypes.data for v in planes), w, h, ctypes.byref(a),
                                  *(t.ctypes.data for t in tabs), upw.ctypes.data, upw.size,
                                  *(v.ctypes.data for v in out))
    if rc:
        raise RuntimeError(lib.sonylook_metal_error().decode())
    return out


class PostArgs(ctypes.Structure):
    _fields_ = [("width", ctypes.c_uint32), ("height", ctypes.c_uint32), ("capacity", ctypes.c_uint32),
                ("effect", ctypes.c_int32), ("conv", ctypes.c_int32),
                ("m_fwd", ctypes.c_int32 * 9), ("m_inv", ctypes.c_int32 * 9),
                ("t_r", ctypes.c_float), ("t_b", ctypes.c_float),
                ("c_hi", ctypes.c_float * 3), ("c_lo", ctypes.c_float * 3),
                ("tone", ctypes.c_int32), ("shade", ctypes.c_int32), ("cw", ctypes.c_int32), ("ch", ctypes.c_int32),
                ("g_hi", ctypes.c_float * 11), ("g_lo", ctypes.c_float * 11),
                ("d_hi", ctypes.c_float * 10), ("d_lo", ctypes.c_float * 10),
                ("diff_zero", ctypes.c_uint32), ("lo_one", ctypes.c_uint32), ("c10_one", ctypes.c_int32)]


def _split(v):
    hi = np.float32(v)
    return float(hi), float(np.float32(float(v) - float(hi)))


class Post:
    """Effect / ToneCurve / ShadeCorrection settings of a sony_render.Look for an image size."""

    def __init__(self, look, width, height):
        import sony_effect as E
        import sony_shade as SH
        self.look_id, self.tint, self.mode = look.look_id, look.tint, look.output_mode
        self.effect = self.look_id & ~1 == 0x10
        self.tone_luts = look.tone_luts
        self.shade = look.shade
        self.width, self.height = width, height
        a = PostArgs()
        if self.effect:
            a.effect = 1 if self.look_id == E.LOOK_BW else 2
            a.conv = 1 if self.mode in (0, 1) else 0
            if a.conv:
                for i, v in enumerate(int(x) for row in E.M_FWD[self.mode] for x in row):
                    a.m_fwd[i] = v
                for i, v in enumerate(int(x) for row in E.M_INV[self.mode] for x in row):
                    a.m_inv[i] = v
            if a.effect == 2:
                a.t_r, a.t_b = float(self.tint[0]), float(self.tint[1])
            for i, c in enumerate((0.2126, 0.7152, 0.0722)):
                a.c_hi[i], a.c_lo[i] = _split(c)
        a.tone = 1 if self.tone_luts is not None else 0
        if self.shade is not None:
            a.shade = 1
            self.centre = SH.centre(width, height, flag=self.shade["flag"], angle=self.shade["angle"],
                                    scale_w=width, scale_h=height)
            a.cw, a.ch = (int(v) for v in self.centre)
            c = [float(v) for v in self.shade["coeffs"]]
            for i in range(11):
                a.g_hi[i], a.g_lo[i] = _split(c[i])
            for i in range(10):
                d = float(np.float64(c[i + 1]) - np.float64(c[i]))
                a.d_hi[i], a.d_lo[i] = _split(d)
                a.diff_zero |= (d == 0.0) << i
                a.lo_one |= (c[i] == 1.0) << i
            a.c10_one = int(c[10] == 1.0)
        self.args = a
        mode = self.mode if self.mode in (0, 1) else 0
        T = E.tables()
        names = ("srgb_dec" if mode == 0 else "gamma_dec", "gamma_enc",
                 "gamma_dec", "srgb_enc" if mode == 0 else "gamma_enc")
        self.tables = [np.ascontiguousarray(T[k], dtype=np.int16) for k in names]
        luts = self.tone_luts if self.tone_luts is not None else [np.zeros(0x10000, np.uint16)] * 4
        self.luts = np.ascontiguousarray(np.stack([np.asarray(v, np.uint16) for v in luts]))

    @property
    def active(self):
        return self.effect or self.tone_luts is not None or self.shade is not None

    def reference(self, r, g, b, xs=None, ys=None):
        """The CPU chain (sony_effect / sony_tonecurve / sony_shade), on whole planes or, with
        xs / ys, on 1-D pixel lists."""
        import sony_effect as E
        import sony_shade as SH
        import sony_tonecurve as TC
        if self.effect:
            r, g, b = E.effect_apply(r, g, b, self.look_id, self.tint, mode=self.mode)
        if self.tone_luts is not None:
            r, g, b = TC.apply(r, g, b, self.tone_luts)
        if self.shade is not None:
            if xs is None:
                r, g, b = SH.apply(r, g, b, self.shade["coeffs"], self.width, self.height,
                                   flag=self.shade["flag"], angle=self.shade["angle"],
                                   scale_w=self.width, scale_h=self.height)
            else:
                gain = SH.gains_at(self.shade["coeffs"], *self.centre, xs, ys)
                r, g, b = SH.apply_gain(r, g, b, gain)
        return r, g, b


def post(r, g, b, pp: Post, capacity=None, stats=None):
    """Effect -> ToneCurve -> ShadeCorrection on whole uint16 planes; returns (R, G, B).

    Pixels whose float64 decision the GPU could not settle are recomputed with Post.reference;
    stats (a dict) receives their count."""
    planes = [np.ascontiguousarray(v, dtype=np.uint16) for v in (r, g, b)]
    h, w = planes[0].shape
    if any(v.shape != (h, w) for v in planes) or (w, h) != (pp.width, pp.height):
        raise ValueError("planes must match the Post image size")
    n = w * h
    cap = max(1, n // 64) if capacity is None else int(capacity)
    pp.args.capacity = cap
    fix = np.empty(cap, np.uint32)
    nfix = ctypes.c_uint32(0)
    out = _planes(h, w)
    lib = metal_itp._load()
    lib.sonylook_metal_post.argtypes = [ctypes.c_void_p] * 3 + [ctypes.c_uint32, ctypes.c_uint32,
                                       ctypes.POINTER(PostArgs)] + [ctypes.c_void_p] * 10
    rc = lib.sonylook_metal_post(*(v.ctypes.data for v in planes), w, h, ctypes.byref(pp.args),
                                *(t.ctypes.data for t in pp.tables), pp.luts.ctypes.data,
                                *(v.ctypes.data for v in out), fix.ctypes.data, ctypes.byref(nfix))
    if rc:
        raise RuntimeError(lib.sonylook_metal_error().decode())
    count = int(nfix.value)
    if stats is not None:
        stats["fixed"] = count
    if count > cap:                              # too many to patch: use the CPU chain
        return tuple(np.asarray(v, np.uint16) for v in pp.reference(*planes))
    if count:
        idx = np.sort(fix[:count]).astype(np.int64)
        flat = [v.reshape(-1) for v in planes]
        xs, ys = (idx % w).astype(np.float64), (idx // w).astype(np.float64)
        fixed = pp.reference(*(f[idx] for f in flat), xs=xs, ys=ys)
        for o, v in zip(out, fixed):
            o.reshape(-1)[idx] = v
    return out


def interleave(r, g, b):
    """(H, W, 3) uint16 in GPU-visible memory from three planes (resident planes are read in place)."""
    planes = [np.ascontiguousarray(v, dtype=np.uint16) for v in (r, g, b)]
    h, w = planes[0].shape
    if any(v.shape != (h, w) for v in planes) or not h or not w:
        raise ValueError("planes must be nonempty and the same size")
    out = metal_itp.empty((h, w, 3))
    lib = metal_itp._load()
    lib.sonylook_metal_interleave.argtypes = [ctypes.c_void_p] * 3 + [ctypes.c_uint32] * 2 + [ctypes.c_void_p]
    if lib.sonylook_metal_interleave(*(v.ctypes.data for v in planes), w, h, out.ctypes.data):
        raise RuntimeError(lib.sonylook_metal_error().decode())
    return out
