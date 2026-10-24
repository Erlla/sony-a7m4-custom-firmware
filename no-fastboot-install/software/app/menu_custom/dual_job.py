from product_integrity import pinned, state_path
from pathlib import Path
import argparse
import hashlib
import importlib.util
import io
import json
import secrets
import struct
import subprocess
import sys
CASE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
RAM = CASE.parent / 'native'
ADAPTER = CASE.parent / 'container'
sys.path[:0] = [str(ROOT / 'vendor/python'), str(ADAPTER)]
from common import file_sha, local_path, locked, new_dir, require, save_json
from elftools.elf.elffile import ELFFile
spec = importlib.util.spec_from_file_location('dual_elf_inspection', RAM / 'elf_tools.py')
inspection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspection)
BASE_FIELDS = ('version', 'phase', 'error', 'euid', 'pid', 'ppid', 'loader_pid', 'cleanup', 'maps_bytes', 'polls', 'target_addr', 'base_addr', 'machine_version', 'patched', 'restored', 'hold_seconds', 'flags', 'mem_status', 'restore_status')
APP_FIELDS = ('app_pid', 'app_target_addr', 'app_base_addr', 'app_machine_version', 'app_patched', 'app_restored', 'app_mem_status', 'app_restore_status', 'app_write_attempted')
STATUS_FIELDS = ('app_maps_bytes', 'proc_candidates', 'identity_checks', 'lib_identity_status', 'app_identity_status', 'snapshot_before_status', 'snapshot_end_status')
OBSERVATIONS = ('usb_stream', 'network_stream', 'slot1_mount', 'media_error', 'target_version', 'query_error', 'inhibited', 'debug_exclusion')
FIELDS = BASE_FIELDS + APP_FIELDS + STATUS_FIELDS + tuple((f'{phase}_{name}' for phase in ('before', 'end') for name in OBSERVATIONS))
RESULT = struct.Struct('<8s16s51q')
assert len(FIELDS) == 51 and RESULT.size == 432
MAGIC = b'M4DWL002'
START_MAGIC = b'M4DSTART'
SCHEMA = 'm4-content-window-job/1'
MODULE_SHA = 'f2e7d27602e3f7b236fc41dd93fccf53ba24f0793fd454e7fec171ae378beca7'
APP_SHA = 'fcb052ef4c33040036db72eba21495441ab1019b968a625b9bc69f9f0bab6a97'
ANCHOR_OFFSET, PATCH_OFFSET, GLOBAL_OFFSET = (8004, 8016, 152164)
APP_ANCHOR_OFFSET, APP_PATCH_OFFSET, APP_GLOBAL_OFFSET = (40219316, 40219336, 134012192 + 249016)
ORIGINAL4, PATCH4 = (bytes.fromhex('00c84479'), bytes.fromhex('00c08052'))
APP_ORIGINAL4, APP_PATCH4 = (bytes.fromhex('e3050054'), bytes.fromhex('2f000014'))
OBSERVATION_OFFSETS = (134605304, 134152080, 134223368, 134012192 + 51336, 134012192 + 621008, 134012192 + 621168, 139210037, 134109776)
OBSERVATION_SIZES = (4, 4, 4, 4, 4, 4, 1, 1)
START_TIMEOUT, MAPS_WAIT_SECONDS, HOLD_SECONDS = (120, 300, 600)
PATCHED_FLAGS, RESTORED_FLAGS = (765, 1021)

def decode(raw, meta):
    require(len(raw) == RESULT.size, 'Incomplete dual-window result')
    magic, nonce, *values = RESULT.unpack(raw)
    require(magic == MAGIC and nonce.hex() == meta['nonce'], 'Dual-window identity mismatch')
    row = dict(zip(FIELDS, values))
    require(row['version'] == 1 and row['phase'] in (1, 2, 3, 4, 5, 6, 90), 'Dual-window contract changed')
    require(-4095 <= row['error'] <= 0, 'Invalid dual-window error code')
    return row

def sources():
    return {p: file_sha(ROOT / p) for p in ['app/menu_custom/dual_job.py', 'app/menu_custom/dual_worker.c', 'app/workflow/version_labels.h', 'app/native/linux_a64.h', 'app/native/bootstrap.c', 'app/native/elf_tools.py', 'app/native/toolchain.json', 'app/container/common.py', 'app/menu_custom/layout.json']}

def _elf(data, expected_size):
    require(len(data) == expected_size, 'Pinned ELF size changed')
    elf = ELFFile(io.BytesIO(data))
    require(elf.elfclass == 64 and elf.little_endian and (elf['e_machine'] == 'EM_AARCH64'), 'Pinned ELF architecture changed')
    return elf

def prepare(output=None, nonce=None):
    layout_path = CASE / 'layout.json'
    locked(layout_path, pinned(layout_path.relative_to(ROOT).as_posix()))
    layout = json.loads(layout_path.read_text('utf-8'))
    require(layout['schema'] == 'm4-menu-layout/1', 'Menu layout schema changed')
    module_layout = layout['modules']['libupdaterufp.so']
    app_layout = layout['modules']['appFw.so']
    require(module_layout['sha256'] == MODULE_SHA and app_layout['sha256'] == APP_SHA, 'Menu layout identity changed')
    require(module_layout['anchor_offset'] == ANCHOR_OFFSET and app_layout['anchor_offset'] == APP_ANCHOR_OFFSET, 'Menu anchor location changed')
    anchor = bytes.fromhex(module_layout['anchor_hex'])
    app_anchor = bytes.fromhex(app_layout['anchor_hex'])
    require(len(anchor) == 20 and len(app_anchor) == 32, 'Menu anchor size changed')
    require(anchor[PATCH_OFFSET - ANCHOR_OFFSET:PATCH_OFFSET - ANCHOR_OFFSET + 4] == ORIGINAL4, 'Updater instruction changed')
    require(app_anchor[APP_PATCH_OFFSET - APP_ANCHOR_OFFSET:APP_PATCH_OFFSET - APP_ANCHOR_OFFSET + 4] == APP_ORIGINAL4, 'App instruction changed')
    data = range(module_layout['bytes'])
    appdata = range(app_layout['bytes'])
    out = new_dir(Path(output) if output else ROOT / 'state/menu_custom' / ('job_' + secrets.token_hex(16)))
    nonce = secrets.token_bytes(16) if nonce is None else bytes.fromhex(nonce)
    require(len(nonce) == 16 and any(nonce), 'Invalid job nonce')
    directory = '/tmp_wbshd/m4dual_' + nonce.hex()

    def array(name, blob, ctype='unsigned char'):
        return f'static const {ctype} {name}[]={{' + ','.join(map(str, blob)) + '};\n'
    defs = dict(START_TIMEOUT=START_TIMEOUT, MAPS_WAIT_SECONDS=MAPS_WAIT_SECONDS, HOLD_SECONDS=HOLD_SECONDS, PATCH_OFFSET=PATCH_OFFSET, ANCHOR_OFFSET=ANCHOR_OFFSET, GLOBAL_OFFSET=GLOBAL_OFFSET, APP_PATCH_OFFSET=APP_PATCH_OFFSET, APP_ANCHOR_OFFSET=APP_ANCHOR_OFFSET, APP_GLOBAL_OFFSET=APP_GLOBAL_OFFSET)
    header = f'#define JOB_DIR "{directory}"\n' + ''.join((f'#define {k} {v}\n' for k, v in defs.items()))
    for name, blob in (('job_nonce', nonce), ('anchor', anchor), ('original4', ORIGINAL4), ('patch4', PATCH4), ('app_anchor', app_anchor), ('app_original4', APP_ORIGINAL4), ('app_patch4', APP_PATCH4)):
        header += array(name, blob)
    header += array('observation_offsets', OBSERVATION_OFFSETS, 'unsigned long')
    header += array('observation_sizes', OBSERVATION_SIZES, 'unsigned long')
    (out / 'job.h').write_text(header, 'ascii', newline='\n')
    compiler = ROOT / 'tools/zig/zig.exe'
    toolchain = json.loads((RAM / 'toolchain.json').read_text('utf-8'))
    locked(compiler, toolchain['executable_sha256'])
    flags = ['-target', 'aarch64-linux-gnu', '-mcpu=generic', '-Os', '-g', '-ffreestanding', '-fno-builtin', '-fno-stack-protector', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables', '-nostdlib', '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections', '-Wl,--no-undefined', '-Wl,--build-id=none', '-Wl,-z,noexecstack', '-Wl,-z,max-page-size=4096', '-Wl,-z,common-page-size=4096', '-I', str(out), '-I', str(RAM)]

    def compile(source, name, extra):
        run = subprocess.run([str(compiler), 'cc', *flags, *extra, str(source), '-o', str(out / name)], capture_output=True, text=True, timeout=120)
        (out / (name + '.compile.log')).write_text(run.stdout + run.stderr, 'utf-8', newline='\n')
        require(run.returncode == 0, 'Native compilation failed: ' + run.stderr[-2000:])
    compile(CASE / 'dual_worker.c', 'worker.debug.elf', ['-static', '-fno-pic', '-Wl,-e,_start'])
    debug = (out / 'worker.debug.elf').read_bytes()
    elf = ELFFile(io.BytesIO(debug))
    inspection.inspect(out / 'worker.debug.elf', True)
    limit = max((s['p_offset'] + s['p_filesz'] for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD'))
    compact = bytearray(debug[:limit])
    struct.pack_into('<Q', compact, 40, 0)
    struct.pack_into('<3H', compact, 58, 0, 0, 0)
    require(compact[:40] == debug[:40] and compact[48:58] == debug[48:58] and (compact[64:] == debug[64:limit]), 'Compact ELF changed loadable instructions/data')
    (out / 'worker.elf').write_bytes(compact)
    symbols = {s.name: s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name}
    save_json(out / 'symbols.json', symbols)
    (out / 'worker_blob.h').write_text(array('worker_blob', compact), 'ascii', newline='\n')
    compile(RAM / 'bootstrap.c', 'libJit.so', ['-shared', '-fPIC', '-Wl,-Bsymbolic', '-s'])
    require((out / 'libJit.so').stat().st_size <= 65520, 'Bootstrap exceeds bounded Jiritsu upload')
    meta = dict(schema=SCHEMA, nonce=nonce.hex(), job_dir=directory, result_magic=MAGIC.decode(), start_magic=START_MAGIC.decode(), result_bytes=RESULT.size, result_fields=list(FIELDS), module_sha256=MODULE_SHA, module_bytes=len(data), app_sha256=APP_SHA, app_bytes=len(appdata), anchor_offset=ANCHOR_OFFSET, anchor_hex=anchor.hex(), patch_offset=PATCH_OFFSET, original_hex=ORIGINAL4.hex(), patch_hex=PATCH4.hex(), global_version_offset=GLOBAL_OFFSET, version_policy='consistent_runtime_encodings', app_anchor_offset=APP_ANCHOR_OFFSET, app_anchor_hex=app_anchor.hex(), app_patch_offset=APP_PATCH_OFFSET, app_original_hex=APP_ORIGINAL4.hex(), app_patch_hex=APP_PATCH4.hex(), app_global_version_offset=APP_GLOBAL_OFFSET, observations=[dict(name=name, offset=offset, bytes=size) for name, offset, size in zip(OBSERVATIONS, OBSERVATION_OFFSETS, OBSERVATION_SIZES)], start_timeout=START_TIMEOUT, maps_wait_seconds=MAPS_WAIT_SECONDS, hold_seconds=HOLD_SECONDS, worker=inspection.inspect(out / 'worker.elf', True), bootstrap=inspection.inspect(out / 'libJit.so', False), symbols_sha256=file_sha(out / 'symbols.json'), debug_sha256=hashlib.sha256(debug).hexdigest(), compiler=toolchain, sources=sources(), persistence='none; retained /proc mem descriptors, fixed 600-second RAM window', patch_order=['app', 'lib'], restore_order=['lib', 'app'], automatic_retry=False, offline_built=True, camera_tested=False, hardware_operations=0, deployment_state='OFFLINE_ONLY_NOT_BODY_BOUND', live_controller_sealed=False, target_package_sha256=None)
    save_json(out / 'job.json', meta)
    return (out, meta)

def validate(folder):
    folder = local_path(folder)
    meta = json.loads(local_path(folder / 'job.json', existing=True).read_text('utf-8'))
    require(meta['schema'] == SCHEMA and meta['sources'] == sources(), 'Dual-window job source changed')
    require(meta.get('deployment_state') == 'OFFLINE_ONLY_NOT_BODY_BOUND' and meta.get('live_controller_sealed') is False and (meta.get('target_package_sha256') is None), 'Content preparation context changed')
    require(meta['job_dir'] == '/tmp_wbshd/m4dual_' + meta['nonce'], 'Wrong fixed dual-window directory')
    require(meta['result_magic'] == MAGIC.decode() and meta['result_fields'] == list(FIELDS) and (meta['result_bytes'] == RESULT.size) and (meta['start_magic'] == START_MAGIC.decode()), 'Result protocol changed')
    require(meta['module_sha256'] == MODULE_SHA and meta['app_sha256'] == APP_SHA and (meta['hold_seconds'] == HOLD_SECONDS) and (meta.get('version_policy') == 'consistent_runtime_encodings') and ('expected_machine_version' not in meta) and ('expected_app_machine_version' not in meta), 'Pinned target/timing changed')
    expected = dict(module_bytes=22768, app_bytes=99026944, anchor_offset=ANCHOR_OFFSET, patch_offset=PATCH_OFFSET, original_hex=ORIGINAL4.hex(), patch_hex=PATCH4.hex(), global_version_offset=GLOBAL_OFFSET, app_anchor_offset=APP_ANCHOR_OFFSET, app_patch_offset=APP_PATCH_OFFSET, app_original_hex=APP_ORIGINAL4.hex(), app_patch_hex=APP_PATCH4.hex(), app_global_version_offset=APP_GLOBAL_OFFSET, start_timeout=START_TIMEOUT, maps_wait_seconds=MAPS_WAIT_SECONDS, patch_order=['app', 'lib'], restore_order=['lib', 'app'], observations=[dict(name=name, offset=offset, bytes=size) for name, offset, size in zip(OBSERVATIONS, OBSERVATION_OFFSETS, OBSERVATION_SIZES)])
    require(all((meta.get(k) == v for k, v in expected.items())), 'Pinned target metadata changed')
    for name, kind, executable in (('worker.elf', 'worker', True), ('libJit.so', 'bootstrap', False)):
        require(inspection.inspect(folder / name, executable) == meta[kind], 'Prepared ELF changed')
    locked(folder / 'symbols.json', meta['symbols_sha256'])
    return meta
