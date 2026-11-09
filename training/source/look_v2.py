"""Bounded camera-look JSON v2 and M4 native arrays; no device or filesystem writes."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import uuid

import native_codec as native

FORMAT, VERSION, MODEL, ABI = 'camera-look', 2, 'ILCE-7M4', 0x00020000
MAX_BYTES, MAX_DEPTH, MAX_PROVENANCE_BYTES = 128 * 1024, 16, 8192
ADJUSTMENTS = ('contrast', 'highlights', 'shadows', 'fade', 'saturation',
               'sharpness', 'sharpness_range', 'clarity')
ENCODINGS = dict(coefficients='a7m4-b-delta-int16-v1',
                 matrices='a7m4-3x16x6-int16-v1',
                 gamma='a7m4-native-record-572-v1')
GRID_ENCODING = 'a7m4-grid405-native-s7-v1'
BASE_CAPS = ('native-coeff-matrix-v1', 'native-photo7-live1-gamma-v1',
             'whole-generation-v1')
GRID_CAP = 'native-grid405-separate-v1'
RUNTIME_KEYS = ('format', 'version', 'model', 'engine_abi', 'required_capabilities',
                'id', 'revision', 'draft', 'mode', 'name', 'parameters', 'defaults')
ROOT_KEYS = set(RUNTIME_KEYS) | {'author', 'description', 'payload_sha256'}
LIVE_PROFILE = {
    'name': 'FL2_live_ctx6',
    'contexts': [6],
    'metadata_hex': '00000000000000001000013206000000dcdf0100000000000000000000000000000000000000000000000000',
    'y_first': 0, 'y_last': 122844,
}


class FormatError(ValueError):
    pass


def keys(value, required, optional=()):
    if type(value) is not dict or not set(required) <= value.keys() or value.keys() - set(required) - set(optional):
        raise FormatError('Missing or unknown fields')


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise FormatError('Expected integer in %d..%d' % (low, high))


def text(value, limit, multiline=False):
    if type(value) is not str:
        raise FormatError('Expected UTF-8 string')
    try:
        raw = value.encode('utf-8')
    except UnicodeError as exc:
        raise FormatError('Invalid UTF-8 string') from exc
    if len(raw) > limit or any(
            (ord(c) < 32 and not (multiline and c in '\n\t')) or 127 <= ord(c) <= 159
            for c in value):
        raise FormatError('Text exceeds byte limit or contains control characters')


def array(value, shape, low, high):
    if not shape:
        integer(value, low, high)
        return
    if type(value) is not list or len(value) != shape[0]:
        raise FormatError('Native array shape mismatch')
    for child in value:
        array(child, shape[1:], low, high)


def canonical(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise FormatError('Cannot encode finite UTF-8 JSON') from exc


def runtime_hash(value):
    """Runtime identity includes name/draft/UUID/revision as well as pixel data."""
    keys(value, ROOT_KEYS, {'provenance'})
    return hashlib.sha256(b'CAMLOOK2\0' + canonical({k: value[k] for k in RUNTIME_KEYS})).hexdigest()


def matrix_domain(family):
    limits = [[0, 65535] for _ in range(3)]
    for endpoint in family:
        for row in endpoint:
            for k in range(3):
                a, b = row[2*k:2*k+2]
                if a == -32768 or b == -32768:
                    raise FormatError('Matrix negation overflow')
                limits[k][0] = max(limits[k][0], -32768-a-b)
                limits[k][1] = min(limits[k][1], 32767-a-b)
                if limits[k][0] > limits[k][1]:
                    raise FormatError('Empty runtime diagonal domain')
    return limits


def validate_branch(branch, contexts, live=False):
    keys(branch, ENCODINGS)
    for key, encoding in ENCODINGS.items():
        field = 'records' if key == 'gamma' else 'values'
        keys(branch[key], {'encoding', field})
        if branch[key]['encoding'] != encoding:
            raise FormatError('Unsupported native encoding')
    array(branch['coefficients']['values'], (3, 8), -32768, 32767)
    array(branch['matrices']['values'], (3, 16, 6), -32768, 32767)
    array(branch['gamma']['records'], (len(contexts), 572), 0, 255)
    try:
        native.coefficient_endpoints(branch['coefficients']['values'])
        profiles = [
            native.validate_gamma(bytes(record), context, [LIVE_PROFILE] if live else None)['profile']
            for record, context in zip(branch['gamma']['records'], contexts)]
    except ValueError as exc:
        raise FormatError(str(exc)) from exc
    return dict(diagonal_domain=matrix_domain(branch['matrices']['values']),
                gamma_profiles=profiles)


def validate(value):
    keys(value, ROOT_KEYS, {'provenance'})
    if (value['format'] != FORMAT or type(value['version']) is not int or value['version'] != VERSION
            or value['model'] != MODEL or type(value['engine_abi']) is not int or value['engine_abi'] != ABI):
        raise FormatError('Unsupported format/model/version/ABI')
    if value['mode'] != 'photo' or type(value['draft']) is not bool:
        raise FormatError('Explicit photo mode and boolean draft state required')
    try:
        ident = uuid.UUID(value['id']) if type(value['id']) is str else None
        if ident is None or not ident.int or str(ident) != value['id']:
            raise ValueError('UUID')
    except (ValueError, AttributeError) as exc:
        raise FormatError('Canonical nonzero UUID required') from exc
    integer(value['revision'], 1, 0xffffffff)
    text(value['name'], 63)
    if not value['name'].strip():
        raise FormatError('Name is empty')
    text(value['author'], 63)
    text(value['description'], 1024, True)
    if 'provenance' in value:
        if type(value['provenance']) is not dict or len(canonical(value['provenance'])) > MAX_PROVENANCE_BYTES:
            raise FormatError('Invalid or oversized provenance')
    keys(value['defaults'], ADJUSTMENTS)
    for name, limits in zip(ADJUSTMENTS, native.ADJUSTMENT_RANGES):
        integer(value['defaults'][name], *limits)
    parameters = value['parameters']
    keys(parameters, {'photo', 'live', 'grid'})
    photo = validate_branch(parameters['photo'], range(7))
    live = validate_branch(parameters['live'], [6], live=True)
    grid = parameters['grid']
    if type(grid) is not dict:
        raise FormatError('Grid must be an object')
    if grid.get('mode') == 'disabled':
        keys(grid, {'mode'})
        required = sorted(BASE_CAPS)
    elif grid.get('mode') == 'custom':
        keys(grid, {'mode', 'encoding', 'photo', 'live'})
        if grid['encoding'] != GRID_ENCODING:
            raise FormatError('Unsupported grid encoding')
        for branch in ('photo', 'live'):
            array(grid[branch], (3, 5, 9, 9), -64, 63)
        required = sorted((*BASE_CAPS, GRID_CAP))
    else:
        raise FormatError('Unknown grid mode')
    if type(value['required_capabilities']) is not list or value['required_capabilities'] != required:
        raise FormatError('Required capabilities must be sorted, exact, supported and complete')
    digest = value['payload_sha256']
    if (type(digest) is not str or len(digest) != 64
            or any(c not in '0123456789abcdef' for c in digest) or runtime_hash(value) != digest):
        raise FormatError('Runtime content hash mismatch')
    return dict(photo=photo, live=live, grid_mode=grid['mode'],
                draft=value['draft'], required_capabilities=required)


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise FormatError('Duplicate JSON key')
        value[key] = item
    return value


def _nonfinite(value):
    raise FormatError('Non-finite JSON constant: ' + value)


def _depth(raw_text):
    depth = 0
    quoted = escaped = False
    for c in raw_text:
        if quoted:
            if escaped:
                escaped = False
            elif c == '\\':
                escaped = True
            elif c == '"':
                quoted = False
        elif c == '"':
            quoted = True
        elif c in '[{':
            depth += 1
            if depth > MAX_DEPTH:
                raise FormatError('JSON nesting exceeds 16')
        elif c in ']}':
            depth -= 1
            if depth < 0:
                raise FormatError('Unbalanced JSON containers')


def parse(raw):
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_BYTES:
        raise FormatError('JSON file outside 1..131072 bytes')
    try:
        value_text = raw.decode('utf-8-sig')
        _depth(value_text)
        value = json.loads(value_text, object_pairs_hook=_pairs, parse_constant=_nonfinite)
        validate(value)
        return value
    except FormatError:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise FormatError('Invalid UTF-8 JSON') from exc


def encode(value, pretty=False):
    validate(value)
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      indent=2, separators=None) if pretty else canonical(value).decode('utf-8'))
    raw = (raw + '\n').encode('utf-8')
    if len(raw) > MAX_BYTES:
        raise FormatError('Encoded file exceeds byte limit')
    # Also enforce depth for directly supplied provenance objects.
    parse(raw)
    return raw


def seal(value):
    """Recompute integrity only; this is not a signature or production approval."""
    result = deepcopy(value)
    result['payload_sha256'] = '0' * 64
    result['payload_sha256'] = runtime_hash(result)
    validate(result)
    return result


def flatten(value):
    for child in value:
        if type(child) is list:
            yield from flatten(child)
        else:
            yield child


def native_branch(branch):
    return (native.encode_coefficients(branch['coefficients']['values'])
            + native.encode_matrices(branch['matrices']['values'])
            + b''.join(bytes(row) for row in branch['gamma']['records']))


def compile_native(value, *, actual_diagonals=None):
    """Validated internal byte views. No on-card binary format, pointers or IO."""
    result = validate(value)
    if actual_diagonals is not None:
        keys(actual_diagonals, {'photo', 'live'})
        for branch in ('photo', 'live'):
            array(actual_diagonals[branch], (3,), 0, 65535)
            if any(not lo <= d <= hi for d, (lo, hi) in
                   zip(actual_diagonals[branch], result[branch]['diagonal_domain'])):
                raise FormatError('Actual runtime diagonal outside ' + branch + ' domain')
    photo = native_branch(value['parameters']['photo'])
    photo += struct.pack('<8h', *(value['defaults'][k] for k in ADJUSTMENTS))
    live = native_branch(value['parameters']['live'])
    grid = value['parameters']['grid']
    grids = {k: struct.pack('<1215b', *flatten(grid[k])) if grid['mode'] == 'custom' else b''
             for k in ('photo', 'live')}
    assert len(photo) == 4644 and len(live) == 1196
    return dict(photo=photo, live=live, grids=grids, semantics=result,
                runtime_diagonal_checked=actual_diagonals is not None,
                content_sha256=value['payload_sha256'])


def check_engine_compatibility(value, engine_abi, capabilities, *, allow_development=False):
    """Engine negotiation is separate from content validation and real application."""
    validate(value)
    if type(engine_abi) is not int or engine_abi != ABI or not set(value['required_capabilities']) <= set(capabilities):
        raise FormatError('Engine lacks required ABI or capability')
    if value['draft'] and not allow_development:
        raise FormatError('Draft cannot be imported as a production filter')
    return True
