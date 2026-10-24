from product_integrity import pinned, state_path
from pathlib import Path
import argparse, hashlib, importlib.util, io, json, secrets, struct, subprocess, sys
CASE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
RAM = CASE.parent / 'native'
WRITER = CASE.parent / 'writer'
sys.path[:0] = [str(ROOT / 'vendor/python'), str(CASE.parent / 'container')]
from common import require, save_json, file_sha, locked
from elftools.elf.elffile import ELFFile
spec = importlib.util.spec_from_file_location('reader_inspection', RAM / 'elf_tools.py')
inspection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspection)
RESULT = struct.Struct('<8s16s11q32s32s')
FIELDS = ('version', 'phase', 'error', 'euid', 'pid', 'ppid', 'loader_pid', 'cleanup', 'bytes', 'chunks', 'flags')
P1_BYTES = 25100288
CHUNK = 32768
COUNT = (P1_BYTES + CHUNK - 1) // CHUNK

def decode(raw, meta):
    require(len(raw) == RESULT.size, 'Incomplete reader publication')
    magic, nonce, *values = RESULT.unpack(raw)
    require(magic == b'M4P1RD01' and nonce.hex() == meta['nonce'], 'Reader nonce differs')
    r = dict(zip(FIELDS, values[:11]))
    r.update(first_sha256=values[11].hex(), second_sha256=values[12].hex())
    require(r['version'] == 1 and r['phase'] in (1, 2, 3, 4, 5, 90), 'Reader version/phase differs')
    return r

def sources():
    return {p: file_sha(ROOT / p) for p in ['app/reader/reader.c', 'app/reader/reader_job.py', 'app/reader/live_reader.py', 'app/native/linux_a64.h', 'app/native/lifecycle_worker.c', 'app/native/bootstrap.c', 'app/native/elf_tools.py', 'app/native/toolchain.json', 'app/writer/sha256.h']}

def prepare():
    nonce = secrets.token_bytes(16)
    out = ROOT / 'state/reader' / ('job_' + nonce.hex())
    out.mkdir(parents=True, exist_ok=False)
    directory = '/tmp_wbshd/m4rd_' + nonce.hex()

    def array(name, data):
        return 'static const unsigned char ' + name + '[]={' + ','.join(map(str, data)) + '};\n'
    (out / 'job.h').write_text('#define JOB_DIR "' + directory + '"\n' + array('job_nonce', nonce), 'ascii')
    compiler = ROOT / 'tools/zig/zig.exe'
    toolchain = json.loads((RAM / 'toolchain.json').read_text('utf-8'))
    locked(compiler, toolchain['executable_sha256'])
    flags = ['-target', 'aarch64-linux-gnu', '-mcpu=generic', '-Os', '-g', '-ffreestanding', '-fno-builtin', '-fno-stack-protector', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables', '-nostdlib', '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections', '-Wl,--no-undefined', '-Wl,--build-id=none', '-Wl,-z,noexecstack', '-Wl,-z,max-page-size=4096', '-Wl,-z,common-page-size=4096', '-I', str(out), '-I', str(RAM)]

    def compile(source, name, extra):
        run = subprocess.run([str(compiler), 'cc', *flags, *extra, str(source), '-o', str(out / name)], capture_output=True, text=True, timeout=120)
        (out / (name + '.compile.log')).write_text(run.stdout + run.stderr, 'utf-8')
        require(run.returncode == 0, run.stderr[-2000:])
    compile(CASE / 'reader.c', 'worker.debug.elf', ['-static', '-fno-pic', '-Wl,-e,_start'])
    raw = (out / 'worker.debug.elf').read_bytes()
    elf = ELFFile(io.BytesIO(raw))
    inspection.inspect(out / 'worker.debug.elf', True)
    limit = max((s['p_offset'] + s['p_filesz'] for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD'))
    compact = bytearray(raw[:limit])
    struct.pack_into('<Q', compact, 40, 0)
    struct.pack_into('<3H', compact, 58, 0, 0, 0)
    require(compact[:40] == raw[:40] and compact[48:58] == raw[48:58] and (compact[64:] == raw[64:limit]), 'Changed loadable bytes')
    (out / 'worker.elf').write_bytes(compact)
    save_json(out / 'symbols.json', {s.name: s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name})
    (out / 'worker_blob.h').write_text(array('worker_blob', compact), 'ascii')
    compile(RAM / 'bootstrap.c', 'libJit.so', ['-shared', '-fPIC', '-Wl,-Bsymbolic', '-s'])
    require((out / 'libJit.so').stat().st_size <= 65520, 'Module exceeds USB upload limit')
    meta = dict(schema='m4-fixed-p1-reader/1', nonce=nonce.hex(), job_dir=directory, bytes=P1_BYTES, chunk=CHUNK, count=COUNT, worker=inspection.inspect(out / 'worker.elf', True), bootstrap=inspection.inspect(out / 'libJit.so', False), symbols_sha256=file_sha(out / 'symbols.json'), compiler=toolchain, sources=sources(), block_open_flags='O_RDONLY|O_CLOEXEC|O_NOFOLLOW', target='/dev/cnflasha1', device_id='252:129', block_writes=False, automatic_retry=False)
    save_json(out / 'job.json', meta)
    return out

def validate(folder):
    folder = Path(folder).resolve()
    require(folder.is_relative_to(ROOT / 'state/reader'), 'Job outside private case')
    meta = json.loads((folder / 'job.json').read_text('utf-8'))
    require(meta['schema'] == 'm4-fixed-p1-reader/1' and meta['sources'] == sources(), 'Reader source changed')
    require(len(bytes.fromhex(meta['nonce'])) == 16 and meta['job_dir'] == '/tmp_wbshd/m4rd_' + meta['nonce'], 'Job scope changed')
    for name, key, exe in [('worker.elf', 'worker', True), ('libJit.so', 'bootstrap', False)]:
        require(inspection.inspect(folder / name, exe) == meta[key], 'Reader binary changed')
    locked(folder / 'symbols.json', meta['symbols_sha256'])
    return meta
