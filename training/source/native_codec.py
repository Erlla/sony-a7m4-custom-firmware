"""A7M4 native parameter codecs. Offline data tools; never patch/deploy firmware.

Lossless decoding is separate from the restricted photo-generation validator.
Integer units are Sony record units, not normalized RGB matrix units.
"""
from bisect import bisect_right
from pathlib import Path
import argparse
import json
import math
import struct
import sys

HERE = Path(__file__).resolve().parent
WIDTHS = (32, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768)
STARTS = (0, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768)
ADJUSTMENT_RANGES = ((-9, 9), (-9, 9), (-9, 9), (0, 9), (-9, 9), (0, 9), (1, 5), (0, 9))


class CodecError(ValueError):
    pass


def integer(v, low, high):
    if type(v) is not int or not low <= v <= high:
        raise CodecError(f'Expected integer {low}..{high}')
    return v


def vector(v, size, low=-32768, high=32767):
    if not isinstance(v, (list, tuple)) or len(v) != size:
        raise CodecError(f'Expected {size} integers')
    return [integer(x, low, high) for x in v]


def _record(raw, active, stride):
    if not isinstance(raw, bytes) or len(raw) not in (active, stride):
        raise CodecError(f'Expected {active} or {stride} bytes')
    return raw[:active], raw[active:]


def _padding(raw, size):
    if not isinstance(raw, bytes) or len(raw) not in (0, size):
        raise CodecError('Invalid reserved bytes')
    return raw


def decode_coefficients(raw):
    active, padding = _record(raw, 48, 64)
    values = list(struct.unpack('<24h', active))
    return [values[n:n+8] for n in (0, 8, 16)], padding


def encode_coefficients(storage, padding=b''):
    if not isinstance(storage, (list, tuple)) or len(storage) != 3:
        raise CodecError('Expected B, delta-A1, delta-A2')
    values = [v for row in storage for v in vector(row, 8)]
    return struct.pack('<24h', *values) + _padding(padding, 16)


def coefficient_endpoints(storage, wrap=False):
    decode_coefficients(encode_coefficients(storage))
    out = [list(storage[0])] + [[storage[0][i] + row[i] for i in range(8)] for row in storage[1:]]
    if wrap:
        return [[((x + 32768) % 65536) - 32768 for x in row] for row in out]
    for row in out:
        vector(row, 8)
    return out


def coefficients_from_endpoints(absolute, padding=b''):
    if not isinstance(absolute, (list, tuple)) or len(absolute) != 3:
        raise CodecError('Expected three absolute endpoints')
    rows = [vector(row, 8) for row in absolute]
    storage = [rows[0]] + [[x - b for x, b in zip(row, rows[0])] for row in rows[1:]]
    return encode_coefficients(storage, padding)


def quantize_coefficients(values, scale_flag):
    """0x6AFC5A: first four signed11, last four unsigned10, factor1/4."""
    vector(values, 8)
    integer(scale_flag, 0, 1)
    factor = 1 if scale_flag else 4
    return [(max(-1024, min(1023, x * factor)) & 2047) if i < 4
            else max(0, min(1023, x * factor)) for i, x in enumerate(values)]


def decode_matrices(raw):
    active, padding = _record(raw, 576, 768)
    values = list(struct.unpack('<288h', active))
    return [[values[e*96+g*6:e*96+g*6+6] for g in range(16)] for e in range(3)], padding


def encode_matrices(family, padding=b''):
    if not isinstance(family, (list, tuple)) or len(family) != 3:
        raise CodecError('Expected three matrix endpoints')
    values = []
    for endpoint in family:
        if not isinstance(endpoint, (list, tuple)) or len(endpoint) != 16:
            raise CodecError('Expected sixteen matrix groups')
        for group in endpoint:
            values.extend(vector(group, 6))
    return struct.pack('<288h', *values) + _padding(padding, 192)


def expand_matrix(terms, diagonal, wrap=False):
    p, q, r, s, t, u = vector(terms, 6)
    a, b, c = vector(diagonal, 3, 0, 65535)
    values = [a+p+q, -p, -q, -r, b+r+s, -s, -t, -u, c+t+u]
    if wrap:
        return [((x + 32768) % 65536) - 32768 for x in values]
    return vector(values, 9)


def compress_matrix(matrix, diagonal):
    m = vector(matrix, 9)
    d = vector(diagonal, 3, 0, 65535)
    if [sum(m[n:n+3]) for n in (0, 3, 6)] != d:
        raise CodecError('Matrix row sums must equal the caller diagonal')
    terms = vector([-m[i] for i in (1, 2, 3, 5, 6, 7)], 6)
    if expand_matrix(terms, diagonal) != m:
        raise CodecError('Nonrepresentable native matrix')
    return terms


def decode_gamma(raw):
    active, padding = _record(raw, 572, 576)
    return dict(y=list(struct.unpack_from('<129I', active)),
                divisions=list(active[0x204:0x210]),
                metadata_hex=active[0x210:].hex(), padding_hex=padding.hex())


def encode_gamma(value):
    if type(value) is not dict or set(value) != {'y', 'divisions', 'metadata_hex', 'padding_hex'}:
        raise CodecError('Incorrect decoded Gamma fields')
    y = vector(value['y'], 129, 0, 0xffffffff)
    divisions = vector(value['divisions'], 12, 0, 255)
    try:
        if type(value['metadata_hex']) is not str or type(value['padding_hex']) is not str:
            raise ValueError('Hex text required')
        metadata = bytes.fromhex(value['metadata_hex'])
        padding = bytes.fromhex(value['padding_hex'])
    except ValueError as exc:
        raise CodecError('Invalid Gamma metadata hex') from exc
    if len(metadata) != 44:
        raise CodecError('Gamma metadata must preserve exactly44 bytes')
    return struct.pack('<129I', *y) + bytes(divisions) + metadata + _padding(padding, 4)


def gamma_x(divisions):
    """Restricted complete129-point grid, as generated by0x3D09E2..0x3D0A6C."""
    ds = vector(divisions, 12, 0, 15)
    counts = [1 << n for n in ds]
    if sum(counts) != 128 or any(width >> n == 0 for width, n in zip(WIDTHS, ds)):
        raise CodecError('Gamma grid must cover twelve segments with exactly128 intervals')
    result = [0]
    for start, width, n, count in zip(STARTS, WIDTHS, ds, counts):
        step = width >> n
        result.extend(min(65535, start + step*k) for k in range(1, count+1))
    if len(result) != 129 or result[-1] != 65535 or any(a >= b for a, b in zip(result, result[1:])):
        raise CodecError('Incomplete or nonincreasing native Gamma grid')
    return result


def photo_profiles():
    return json.loads((HERE/'photo_profiles.json').read_text('utf-8'))['profiles']


def validate_gamma(raw, context, profiles=None):
    """Fail closed to approved FL2/FL3 metadata; no arbitrary flags/pointers."""
    integer(context, 0, 6)
    g = decode_gamma(raw)
    gamma_x(g['divisions'])
    if g['padding_hex'] not in ('', '00000000'):
        raise CodecError('Custom Gamma reserved stride bytes must be zero')
    matches = [p for p in (photo_profiles() if profiles is None else profiles)
               if p['metadata_hex'] == g['metadata_hex'] and context in p['contexts']]
    if not matches:
        raise CodecError('Unsupported Gamma flags/metadata/context')
    y = g['y']
    if any(x > 0x3ffff for x in y) or any(a > b for a, b in zip(y, y[1:])):
        raise CodecError('Gamma must be monotone unsigned18-bit')
    matches = [p for p in matches if y[0] == p['y_first'] and y[-1] == p['y_last']]
    if not matches:
        raise CodecError('Gamma endpoint outside approved photo profile')
    return dict(profile=matches[0]['name'], x=gamma_x(g['divisions']), y=y)


def gamma_from_curve(template, points, context=0):
    """Encode monotone normalized knots onto the verified native integer grid.

    Retains approved template controls/endpoints. Not a LUT-to-camera colour fit.
    """
    validated = validate_gamma(template, context)
    if not isinstance(points, (list, tuple)) or not 2 <= len(points) <= 4096:
        raise CodecError('Expected2..4096 curve knots')
    knots = []
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise CodecError('Expected(x,y) curve knots')
        for v in point:
            if type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 1:
                raise CodecError('Curve values must be finite normalized numbers')
        knots.append(tuple(point))
    if knots[0] != (0, 0) or knots[-1] != (1, 1):
        raise CodecError('Curve endpoints must be(0,0) and(1,1)')
    if any(a[0] >= b[0] or a[1] > b[1] for a, b in zip(knots, knots[1:])):
        raise CodecError('Curve x must increase and y must not decrease')
    xs = [p[0] for p in knots]
    first, last = validated['y'][0], validated['y'][-1]
    values = []
    for x in validated['x']:
        q = x / 65535
        k = min(len(knots)-2, max(0, bisect_right(xs, q)-1))
        (x0, y0), (x1, y1) = knots[k:k+2]
        v = y0 + (y1-y0) * (q-x0)/(x1-x0)
        values.append(math.floor(first + (last-first)*v + .5))
    g = decode_gamma(template)
    g['y'] = values
    encoded = encode_gamma(g)
    validate_gamma(encoded, context)
    return encoded
