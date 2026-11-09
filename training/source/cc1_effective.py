"""M4 CC1 storage -> selected SR2 effective coefficients for fixed WB only.

The custom photo path stores B, delta-A1 and delta-A2 in JSON. SR2 reorders
those fields and doubles the last four values. Interpolation happens before
that doubling: doing it on eight unscaled RAW shorts gives one-code errors.

The simple folded-weight formula matches the measured fixed-context RAWs. Three AWB RAWs
do not match: the camera has intermediate rounding before weight projection.
``effective_from_storage`` therefore requires ``validate_fixed_context``.
The unrestricted arithmetic helper is a candidate model, not an AWB solution.

Weights are measured SR2 0x7848 Q10 integers. They may exceed 1024 and are never
normalized or clipped. WB-to-weight generation and the full ISP are not modeled.
"""
from dataclasses import dataclass
from numbers import Integral
import struct


JSON_TO_RAW = (3, 0, 1, 2, 7, 4, 5, 6)
RAW_SCALES = (1, 1, 1, 1, 2, 2, 2, 2)


@dataclass(frozen=True)
class FixedContext:
    """Admission result for the measured single-active-delta fixed-WB path."""
    weights: tuple
    extra_deltas: tuple
    reference_effective: tuple


def _vector(value, size, name):
    result = list(value)
    if len(result) != size or any(isinstance(v, bool) or not isinstance(v, Integral)
                                  or not -32768 <= v <= 32767 for v in result):
        raise ValueError(f'{name}: expected {size} signed 16-bit integers')
    return [int(v) for v in result]


def decode_sr2_fields(sr):
    """Read the required signed-SHORT fields from ``a['sr']``.

    The list/dict entries are those returned by the existing ARW parser.
    Returned lists are ordinary Python integers; this function performs no IO.
    7843/44/45/46 are four RAW delta rows; 7847 and 7848 are distinct weights.
    """
    def read(tag, count):
        entries = [entry for entry in sr if entry['tag'] == tag]
        if len(entries) != 1:
            raise ValueError(f'Expected one SR2 {tag:04x} entry')
        entry = entries[0]
        if entry['type'] != 8 or entry['count'] != count or len(entry['data']) != count * 2:
            raise ValueError(f'SR2 {tag:04x} is not {count} signed SHORT values')
        return list(struct.unpack('<' + str(count) + 'h', entry['data']))
    return dict(effective=read(0x7841, 8), base=read(0x7842, 8),
                deltas=[read(tag, 8) for tag in (0x7843, 0x7844, 0x7845, 0x7846)],
                weights_7847=read(0x7847, 4), weights_7848=read(0x7848, 4),
                luma_7801=read(0x7801, 3))


def _native_units(raw, name):
    values = _vector(raw, 8, name)
    if any(value % scale for value, scale in zip(values, RAW_SCALES)):
        raise ValueError(f'{name}: last four RAW fields must have integral half-scale units')
    return [value // scale for value, scale in zip(values, RAW_SCALES)]


def interpolate_folded_raw_fields(base, deltas, weights):
    """Candidate B + ASR10(sum(delta_j * weight_j)), then encode 8 shorts.

    ``base``/four ``deltas`` use SR2 order and scaling. ``weights`` are four
    measured Q10 signed SHORTs. ASR10 floors negative sums, unlike int(x/1024).
    No convex-weight, gamut, coefficient-register or output clipping is added.
    AWB generally has additional intermediate rounding; this helper alone is
    not an assertion that these values are the camera's effective coefficients.
    """
    b = _native_units(base, 'base')
    rows = [_native_units(row, 'delta') for row in deltas]
    if len(rows) != 4:
        raise ValueError('Expected four RAW delta rows')
    q = _vector(weights, 4, 'weights')
    native = [b[i] + (sum(row[i] * weight for row, weight in zip(rows, q)) >> 10)
              for i in range(8)]
    result = [value * scale for value, scale in zip(native, RAW_SCALES)]
    return _vector(result, 8, 'effective result')


def raw_storage_from_json(storage, extra_deltas=None):
    """Map JSON [B, delta-A1, delta-A2] into the selected SR2 storage layout.

    The measured custom path has zero 7843/7846 rows. A caller retaining a
    different measured context can supply those two rows in RAW order/units.
    """
    rows = [_vector(row, 8, 'JSON coefficient row') for row in storage]
    if len(rows) != 3:
        raise ValueError('Expected JSON B, delta-A1 and delta-A2')
    packed = [_vector([row[index] * scale for index, scale in zip(JSON_TO_RAW, RAW_SCALES)],
                      8, 'RAW coefficient row') for row in rows]
    extra = [[0] * 8, [0] * 8] if extra_deltas is None else list(extra_deltas)
    if len(extra) != 2:
        raise ValueError('Expected optional 7843 and 7846 rows')
    return dict(base=packed[0], deltas=[_vector(extra[0], 8, '7843'), packed[1], packed[2],
                                      _vector(extra[1], 8, '7846')])


def validate_fixed_context(fields, *, white_balance_mode):
    """Admit a measured fixed-WB single-delta context after exact baseline check.

    WB mode is an explicit shooting-state fact supplied by the caller; folded
    weights cannot identify it. Current evidence covers fixed WB, active 7844,
    zero 7843/7846, and no 7845 contribution. A weight on an exactly zero extra
    row has no contribution (observed at5000K). AWB is deliberately not admitted.
    """
    if white_balance_mode != 'fixed':
        raise ValueError('Only measured fixed-WB contexts are supported; AWB has intermediate rounding')
    weights = _vector(fields['weights_7848'], 4, '7848 weights')
    rows = [_vector(row, 8, 'delta') for row in fields['deltas']]
    if len(rows) != 4 or weights[2] != 0 or weights[1] == 0:
        raise ValueError('Fixed-WB admission requires only the measured 7844 delta to contribute')
    if any(rows[i] != [0] * 8 for i in (0, 3)):
        raise ValueError('Nonzero 7843/7846 are outside the measured fixed-WB path')
    actual = _vector(fields['effective'], 8, '7841 effective')
    predicted = interpolate_folded_raw_fields(fields['base'], rows, weights)
    if predicted != actual:
        raise ValueError('Folded-weight baseline differs from measured effective 7841')
    return FixedContext(tuple(weights), (tuple(rows[0]), tuple(rows[3])), tuple(actual))


def effective_from_storage(storage, context):
    """JSON storage + admitted measured fixed context -> candidate 8 RAW shorts.

    JSON values remain in camera storage units. The result can be packed with
    ``struct.pack('<8h', ...)``. This is a parameter-mapping candidate; changing
    CC1 still needs an independent Sony/camera response check before claiming
    hardware equivalence. Passing a bare AWB/folded weight vector is rejected.
    """
    if not isinstance(context, FixedContext):
        raise TypeError('Call validate_fixed_context with measured fields and fixed WB first')
    packed = raw_storage_from_json(storage, context.extra_deltas)
    return interpolate_folded_raw_fields(packed['base'], packed['deltas'], context.weights)
