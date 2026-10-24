from product_integrity import pinned, state_path
from pathlib import Path
import argparse
import copy
import hashlib
import importlib.util
import io
import json
import secrets
import struct
import subprocess
import sys
from byte_diff import count_differences
CASE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
LEGACY = CASE.parent / 'writer'
RAM = CASE.parent / 'native'
SCHEMA = 'm4-reviewed-full-p1-writer/1'
PATCH_SET = 'sd-signature-success0-version-true1-core/1'
SOURCE_STATES = ('stock_key_gate', 'stock_key_version_true')
GOOD_STATE = 'stock_key_version_true'
FROZEN_PINS = {p: pinned(p) for p in ['app/writer/writer.c', 'app/writer/sha256.h', 'app/native/linux_a64.h', 'app/native/lifecycle_worker.c', 'app/native/bootstrap.c', 'app/native/elf_tools.py', 'app/native/toolchain.json', 'app/container/common.py', 'app/protocol/identity.py', 'app/protocol/auth.py', 'app/usb/usb_session.py', 'app/usb/senser_wire.py', 'app/usb/transport.py', 'app/usb/draft_policy.py']}
_THIS_SHA = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

def check_frozen():
    for relative, expected in FROZEN_PINS.items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT.resolve()) or not path.is_file():
            raise ValueError('Frozen dependency is not a workspace regular file')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Frozen dependency changed: ' + relative)

def load_private(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
check_frozen()
sys.path[:0] = [str(CASE), str(ROOT / 'vendor/python')]
_helpers = load_private('_m4_boolfix_writer_common', CASE.parent / 'container/common.py')
file_sha = _helpers.file_sha
local_path = _helpers.local_path
locked = _helpers.locked
new_dir = _helpers.new_dir
require = _helpers.require
save_json = _helpers.save_json
sha = _helpers.sha
_adapter_path = CASE / 'receiver.py'
_ADAPTER_SHA = file_sha(_adapter_path)
adapter = load_private('_m4_receiver_gates_writer_adapter_v2', _adapter_path)
require((adapter.SCHEMA, adapter.PATCH_SET, tuple(adapter.SOURCE_STATES), adapter.GOOD_STATE) == ('m4-reviewed-full-p1-bundle/1', PATCH_SET, SOURCE_STATES, GOOD_STATE), 'Receiver v2 adapter contract changed')
from elftools.elf.elffile import ELFFile
inspection = load_private('_m4_boolfix_writer_elf', RAM / 'elf_tools.py')
ROW = struct.Struct('<QQ32s32s')
RESULT = struct.Struct('<8s16s15q32s32s')
FIELDS = ('version', 'phase', 'error', 'euid', 'pid', 'ppid', 'loader_pid', 'cleanup', 'mode', 'rows', 'write_calls', 'write_bytes', 'rollback', 'flags', 'io_status')
P1_BYTES = 25100288
MAX_WINDOW = 16384
MODE = {'apply': 1, 'restore': 2}

def decode(raw, meta):
    require(len(raw) == RESULT.size, 'Incomplete native writer record')
    magic, nonce, *values = RESULT.unpack(raw)
    require(magic == b'M4P1WR01' and nonce.hex() == meta['nonce'], 'Writer record identity mismatch')
    r = dict(zip(FIELDS, values[:15]))
    r['before_sha256'] = values[15].hex()
    r['after_sha256'] = values[16].hex()
    require(r['version'] == 1 and r['phase'] in (1, 2, 3, 5, 6, 90) and (r['mode'] == MODE[meta['direction']]) and (r['rows'] == len(meta['windows'])), 'Writer record contract changed')
    require(-4095 <= r['error'] <= 0 and r['rollback'] in (0, 1, 2) and (0 <= r['flags'] <= 255) and (r['write_calls'] >= 0) and (r['write_bytes'] >= 0), 'Invalid native writer counters')
    return r

def token(meta, commit=False):
    return (b'M4COMMIT' if commit else b'M4PREP01') + bytes.fromhex(meta['nonce']) + bytes.fromhex(meta['table_sha256']) + struct.pack('<Q', MODE[meta['direction']])

def source_files():
    check_frozen()
    require(file_sha(Path(__file__)) == _THIS_SHA and file_sha(_adapter_path) == _ADAPTER_SHA, 'Loaded source changed')
    result = dict(FROZEN_PINS)
    result.update(adapter.source_pins())
    for path in (Path(__file__), ROOT / 'app/workflow/receiver_usb_writer_user.py'):
        result[path.relative_to(ROOT).as_posix()] = file_sha(path)
    return result

def verify_patch_semantics(old, new):
    """Recompute full-container and bool1 semantics; no old updater verdict."""
    return adapter.verify_patch_semantics(old, new)

def prepare(bundle, direction, output, current=None, expected_current=None, nonce=None):
    require(direction in MODE, 'Unknown direction')
    pins = source_files()
    m, old, new = adapter.load_bundle(bundle)
    require(m['schema'] == adapter.SCHEMA and m['patch_set'] == PATCH_SET, 'Wrong receiver bundle/patch set')
    require(len(old) == len(new) == P1_BYTES, 'USB writer requires a full 25100288-byte p1, never a packaged FAT volume')
    require(m['before']['trust_state'] in SOURCE_STATES and m['after']['trust_state'] == GOOD_STATE, 'Bundle must start at a reviewed receiver state')
    origin_state = m['before']['trust_state']
    origin_version = m['before']['version_boolean_return']
    origin_kind = m['before']['version_predicate_mode']
    require(not m['already_adapted'], 'Already correct: no writer job is necessary')
    verify_patch_semantics(old, new)
    if current is None:
        current = Path(bundle) / ('p1_original.bin' if direction == 'apply' else 'p1_candidate.bin')
        expected_current = m['source_sha256'] if direction == 'apply' else m['candidate_sha256']
    require(expected_current is not None, 'Current source needs an explicit SHA-256')
    current = locked(current, expected_current)
    before = current.read_bytes()
    require(len(before) == P1_BYTES, 'Wrong current p1 length')
    require(local_path(output).is_relative_to((ROOT / 'state/receiver_stock').resolve()), 'Receiver job output must stay in this case state')
    out = new_dir(output)
    replay = adapter.replay(bundle, current, expected_current, direction, out / 'image')
    after = (out / 'image' / ('p1_' + direction + '.bin')).read_bytes()
    windows = []
    table = bytearray()
    assets = out / 'assets'
    assets.mkdir()
    for item in m['spans']:
        start, length = (item['offset'], item['length'])
        for off in range(start, start + length, MAX_WINDOW):
            n = min(MAX_WINDOW, start + length - off)
            a, b = (before[off:off + n], after[off:off + n])
            if a == b:
                continue
            index = len(windows)
            require(index < 768 and sum((2 * w['length'] for w in windows)) + 2 * n <= 24 * 1024 * 1024, 'Fixed window count/staging bound exceeded')
            name = f'w{index:04d}'
            table.extend(ROW.pack(off, n, hashlib.sha256(a).digest(), hashlib.sha256(b).digest()))
            (assets / name).write_bytes(a + b)
            windows.append(dict(name=name, offset=off, length=n, before_sha256=sha(a), after_sha256=sha(b), packet_sha256=sha(a + b)))
    require(windows, 'Already at requested state; no USB writer job is necessary')
    require(len(windows) <= 768 and len(table) <= 61440, 'Too many fixed windows')
    stage_bytes = sum((2 * w['length'] for w in windows))
    require(stage_bytes <= 24 * 1024 * 1024, 'Staging limit exceeded')
    (assets / 'table').write_bytes(table)
    (out / 'source_p1.bin').write_bytes(before)
    nonce = secrets.token_bytes(16) if nonce is None else nonce
    require(len(nonce) == 16 and any(nonce), 'Invalid job nonce')
    directory = '/tmp_wbshd/m4p1_' + nonce.hex()

    def array(name, data):
        return 'static const unsigned char ' + name + '[]={' + ','.join(map(str, data)) + '};\n'
    job = '#define JOB_DIR "' + directory + '"\n#define JOB_MODE ' + str(MODE[direction]) + '\n' + '#define NROWS ' + str(len(windows)) + '\n#define STAGE_BYTES ' + str(stage_bytes) + '\n' + '#define REQUIRED_TMPFS ' + str(stage_bytes * 2 + stage_bytes // 2 + 4 * 1024 * 1024) + 'UL\n' + array('job_nonce', nonce) + array('expected_table_digest', hashlib.sha256(table).digest()) + array('expected_before_digest', hashlib.sha256(before).digest()) + array('expected_after_digest', hashlib.sha256(after).digest())
    (out / 'job.h').write_text(job, 'ascii', newline='\n')
    compiler = ROOT / 'tools/zig/zig.exe'
    toolchain = json.loads((RAM / 'toolchain.json').read_text('utf-8'))
    locked(compiler, toolchain['executable_sha256'])
    flags = ['-target', 'aarch64-linux-gnu', '-mcpu=generic', '-Os', '-g', '-ffreestanding', '-fno-builtin', '-fno-stack-protector', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables', '-nostdlib', '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections', '-Wl,--no-undefined', '-Wl,--build-id=none', '-Wl,-z,noexecstack', '-Wl,-z,max-page-size=4096', '-Wl,-z,common-page-size=4096', '-I', str(out), '-I', str(RAM)]

    def compile(source, name, extra):
        command = [str(compiler), 'cc', *flags, *extra, str(source), '-o', str(out / name)]
        run = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
        (out / (name + '.compile.log')).write_text(run.stdout + run.stderr, 'utf-8', newline='\n')
        require(run.returncode == 0, 'Native compilation failed: ' + run.stderr[-1500:])
    compile(LEGACY / 'writer.c', 'worker.debug.elf', ['-static', '-fno-pic', '-Wl,-e,_start'])
    debug_raw = (out / 'worker.debug.elf').read_bytes()
    debug_elf = ELFFile(io.BytesIO(debug_raw))
    inspection.inspect(out / 'worker.debug.elf', True)
    limit = max((s['p_offset'] + s['p_filesz'] for s in debug_elf.iter_segments() if s['p_type'] == 'PT_LOAD'))
    compact = bytearray(debug_raw[:limit])
    struct.pack_into('<Q', compact, 40, 0)
    struct.pack_into('<3H', compact, 58, 0, 0, 0)
    require(compact[:40] == debug_raw[:40] and compact[48:58] == debug_raw[48:58] and (compact[64:] == debug_raw[64:limit]), 'Compact ELF changed loadable instructions/data')
    (out / 'worker.elf').write_bytes(compact)
    symbols = {s.name: s['st_value'] for s in debug_elf.get_section_by_name('.symtab').iter_symbols() if s.name}
    save_json(out / 'symbols.json', symbols)
    worker = (out / 'worker.elf').read_bytes()
    (out / 'worker_blob.h').write_text(array('worker_blob', worker), 'ascii', newline='\n')
    compile(RAM / 'bootstrap.c', 'libJit.so', ['-shared', '-fPIC', '-Wl,-Bsymbolic', '-s'])
    require((out / 'libJit.so').stat().st_size <= 65520, 'Bootstrap exceeds bounded Jiritsu upload')
    require(source_files() == pins, 'Receiver dependencies changed during job preparation')
    meta = dict(schema=SCHEMA, patch_set=PATCH_SET, nonce=nonce.hex(), job_dir=directory, direction=direction, origin_gate_state=origin_state, source_gate_state=origin_state if direction == 'apply' else GOOD_STATE, target_gate_state=GOOD_STATE if direction == 'apply' else origin_state, origin_version_return_value=origin_version, origin_version_predicate_mode=origin_kind, target_version_return_value=1 if direction == 'apply' else origin_version, target_version_gate_kind='constant_true' if direction == 'apply' else origin_kind, goal='INSTALL_REVIEWED_RECEIVER_GATES' if direction == 'apply' else 'ROLLBACK_TO_THIS_SAVED_SOURCE', source_sha256=sha(before), target_sha256=sha(after), table_sha256=sha(table), bytes=P1_BYTES, windows=windows, stage_bytes=stage_bytes, changed_bytes=count_differences(before, after), worker=inspection.inspect(out / 'worker.elf', True), bootstrap=inspection.inspect(out / 'libJit.so', False), symbols_sha256=file_sha(out / 'symbols.json'), debug_sha256=sha(debug_raw), loaded_code_and_data_unchanged=True, compiler=toolchain, sources=pins, bundle_sha256=file_sha(Path(bundle) / 'bundle.json'), bundle_manifest=str(local_path(Path(bundle) / 'bundle.json', existing=True)), target=dict(path='/dev/cnflasha1', device_id='252:129', bytes=P1_BYTES, exclusive_required=True), protocol='prepare_then_commit_v1', automatic_retry=False, offline_built=True, camera_tested=False, firmware_target='M4 SD signature success0, version true1 and reviewed core gates; key entries preserved', public_key_changed=False, DAT_signature_changed=False, hardware_operations=0)
    save_json(out / 'job.json', meta)
    return meta

def validate(folder):
    folder = local_path(folder)
    meta = json.loads(local_path(folder / 'job.json', existing=True).read_text('utf-8'))
    require(meta['schema'] == SCHEMA and meta['patch_set'] == PATCH_SET, 'Wrong receiver writer schema/patch set')
    require(meta['sources'] == source_files(), 'Receiver writer source/profile changed')
    require(meta['direction'] in MODE, 'Unknown receiver job direction')
    require(meta['origin_gate_state'] in SOURCE_STATES and meta['origin_gate_state'] != GOOD_STATE, 'Wrong receiver original source state')
    wanted = (meta['origin_gate_state'], GOOD_STATE, 1, 'constant_true', 'INSTALL_REVIEWED_RECEIVER_GATES') if meta['direction'] == 'apply' else (GOOD_STATE, meta['origin_gate_state'], meta['origin_version_return_value'], meta['origin_version_predicate_mode'], 'ROLLBACK_TO_THIS_SAVED_SOURCE')
    require(tuple((meta[k] for k in ('source_gate_state', 'target_gate_state', 'target_version_return_value', 'target_version_gate_kind', 'goal'))) == wanted, 'Wrong receiver source/target Boolean state')
    require(meta['bytes'] == P1_BYTES and meta['target'] == dict(path='/dev/cnflasha1', device_id='252:129', bytes=P1_BYTES, exclusive_required=True), 'Wrong receiver fixed target')
    locked(meta['bundle_manifest'], meta['bundle_sha256'])
    bundle, original, candidate = adapter.load_bundle(Path(meta['bundle_manifest']).parent)
    require(not bundle['already_adapted'] and bundle['before']['trust_state'] == meta['origin_gate_state'] and (bundle['before']['version_boolean_return'] == meta['origin_version_return_value']) and (bundle['before']['version_predicate_mode'] == meta['origin_version_predicate_mode']), 'Saved origin predicate differs')
    require(meta['job_dir'] == '/tmp_wbshd/m4p1_' + meta['nonce'] and len(bytes.fromhex(meta['nonce'])) == 16, 'Wrong fixed job directory')
    for name, kind, executable in (('worker.elf', 'worker', True), ('libJit.so', 'bootstrap', False)):
        require(inspection.inspect(folder / name, executable) == meta[kind], 'Prepared ELF changed')
    source = locked(folder / 'source_p1.bin', meta['source_sha256']).read_bytes()
    locked(folder / 'symbols.json', meta['symbols_sha256'])
    target = locked(folder / 'image' / ('p1_' + meta['direction'] + '.bin'), meta['target_sha256']).read_bytes()
    require(len(source) == len(target) == P1_BYTES, 'Receiver image length differs')
    if meta['direction'] == 'apply':
        require(source == original and target == candidate, 'Apply source/target differ from saved full bundle')
    else:
        expected = bytearray(source)
        for row in bundle['spans']:
            a, n = (row['offset'], row['length'])
            require(source[a:a + n] == candidate[a:a + n], 'Restore source region changed')
            expected[a:a + n] = original[a:a + n]
        require(target == bytes(expected), 'Restore changed bytes outside exact saved regions')
    semantics = verify_patch_semantics(source, target) if meta['direction'] == 'apply' else verify_patch_semantics(target, source)
    require(semantics['before']['trust_state'] == meta['origin_gate_state'] and semantics['after']['trust_state'] == GOOD_STATE, 'Receiver actual image state differs')
    expected_windows = []
    for span in bundle['spans']:
        start, length = (span['offset'], span['length'])
        for off in range(start, start + length, MAX_WINDOW):
            n = min(MAX_WINDOW, start + length - off)
            a, b = (source[off:off + n], target[off:off + n])
            if a != b:
                expected_windows.append(dict(name=f'w{len(expected_windows):04d}', offset=off, length=n, before_sha256=sha(a), after_sha256=sha(b), packet_sha256=sha(a + b)))
    require(meta['windows'] == expected_windows, 'Writer window set differs from exact saved-region differences')
    require(meta['changed_bytes'] == count_differences(source, target), 'Writer changed-byte count differs')
    table = (folder / 'assets/table').read_bytes()
    require(sha(table) == meta['table_sha256'], 'Staged table changed')
    require(len(table) == len(meta['windows']) * ROW.size, 'Table row count differs')
    require(0 < len(meta['windows']) <= 768 and len(table) <= 61440, 'Receiver window count differs')
    cursor = 0
    for i, row in enumerate(meta['windows']):
        require(row['name'] == f'w{i:04d}' and 0 < row['length'] <= MAX_WINDOW, 'Invalid window packet')
        packet = locked(folder / 'assets' / row['name'], row['packet_sha256']).read_bytes()
        off, n = (row['offset'], row['length'])
        require(isinstance(off, int) and cursor <= off < off + n <= P1_BYTES, 'Receiver windows overlap/out of range')
        require(source[cursor:off] == target[cursor:off], 'Unlisted receiver image change')
        require(packet == source[off:off + n] + target[off:off + n], 'Receiver packet/image bytes differ')
        require(sha(packet[:n]) == row['before_sha256'] and sha(packet[n:]) == row['after_sha256'], 'Receiver packet window digest differs')
        cursor = off + n
        require(table[i * ROW.size:(i + 1) * ROW.size] == ROW.pack(row['offset'], row['length'], bytes.fromhex(row['before_sha256']), bytes.fromhex(row['after_sha256'])), 'Window table differs')
    require(source[cursor:] == target[cursor:], 'Unlisted receiver image tail change')
    require(meta['stage_bytes'] == sum((2 * w['length'] for w in meta['windows'])) <= 24 * 1024 * 1024, 'Receiver staging bytes differ')
    return meta
