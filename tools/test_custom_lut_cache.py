"""Compile and exercise the published cache core on Windows; no camera I/O."""
from pathlib import Path
import argparse
import concurrent.futures
import ctypes as C
import json
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

class Bank(C.Structure):
    _fields_ = [('generation', C.c_uint64), ('state', C.c_uint32), ('reserved', C.c_uint32)]

class Cache(C.Structure):
    _fields_ = [('bank', Bank * 63), ('cursor', C.c_uint32)]

class Lease(C.Structure):
    _fields_ = [('generation', C.c_uint64), ('slot', C.c_uint32), ('held', C.c_uint32)]

def exercise(lib):
    lib.p6c_init.argtypes = [C.POINTER(Cache)]
    lib.p6c_init.restype = None
    for name in ('reserve', 'publish', 'abort', 'release'):
        fn = getattr(lib, 'p6c_' + name)
        fn.argtypes = [C.POINTER(Cache), C.POINTER(Lease)]
        fn.restype = C.c_int
    lib.p6c_acquire.argtypes = [C.POINTER(Cache), C.c_uint32, C.c_uint64, C.POINTER(Lease)]
    lib.p6c_acquire.restype = C.c_int
    lib.p6c_clone.argtypes = [C.POINTER(Cache), C.POINTER(Lease), C.POINTER(Lease)]
    lib.p6c_clone.restype = C.c_int
    cache = Cache()
    lib.p6c_init(C.byref(cache))
    held = [Lease() for _ in range(63)]
    for lease in held:
        assert lib.p6c_reserve(C.byref(cache), C.byref(lease)) == 0
        assert lib.p6c_publish(C.byref(cache), C.byref(lease)) == 0
    extra, child = Lease(), Lease()
    assert lib.p6c_reserve(C.byref(cache), C.byref(extra)) == -1
    old_slot, old_generation = held[0].slot, held[0].generation
    assert lib.p6c_clone(C.byref(cache), C.byref(held[0]), C.byref(child)) == 0
    assert lib.p6c_release(C.byref(cache), C.byref(held[0])) == 0
    assert lib.p6c_reserve(C.byref(cache), C.byref(extra)) == -1
    assert lib.p6c_release(C.byref(cache), C.byref(child)) == 0
    assert lib.p6c_reserve(C.byref(cache), C.byref(extra)) == 0
    assert extra.slot == old_slot and extra.generation != old_generation
    assert lib.p6c_publish(C.byref(cache), C.byref(extra)) == 0
    stale = Lease()
    assert lib.p6c_acquire(C.byref(cache), old_slot, old_generation, C.byref(stale)) == -2
    assert lib.p6c_release(C.byref(cache), C.byref(extra)) == 0
    for lease in held[1:]:
        assert lib.p6c_release(C.byref(cache), C.byref(lease)) == 0
    for _ in range(10000):
        lease = Lease()
        assert lib.p6c_reserve(C.byref(cache), C.byref(lease)) == 0
        assert lib.p6c_publish(C.byref(cache), C.byref(lease)) == 0
        assert lib.p6c_release(C.byref(cache), C.byref(lease)) == 0
    lib.fixture_init.argtypes = []
    lib.fixture_init.restype = None
    lib.fixture_writer.argtypes = [C.c_uint32]
    lib.fixture_writer.restype = None
    lib.fixture_reader.argtypes = [C.c_uint32, C.c_uint32]
    lib.fixture_reader.restype = None
    lib.fixture_stat.argtypes = [C.c_uint32]
    lib.fixture_stat.restype = C.c_uint32
    lib.fixture_init()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        jobs = [pool.submit(lib.fixture_writer, 20000)]
        jobs += [pool.submit(lib.fixture_reader, seed, 30000) for seed in (1, 91, 12345)]
        for job in jobs:
            job.result()
    stats = [lib.fixture_stat(i) for i in range(5)]
    assert stats[0] == 0 and stats[1] > 0 and stats[2] == 20000 and stats[4] == 0, stats
    return dict(result='PASS',sequential_reuses=10000,concurrent_writes=stats[2],
                successful_reads=stats[1],stale_or_busy_reads=stats[3],errors=stats[0],remaining_refs=stats[4],camera_io=False)

def main():
    if not __debug__:
        raise RuntimeError('Run without -O so verification assertions execute')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zig', type=Path, required=True)
    args = parser.parse_args()
    native = ROOT / 'native/custom-lut'
    # A subprocess owns the DLL so Windows releases its file handle before cleanup.
    with tempfile.TemporaryDirectory(prefix='a7m4-lut-cache-') as temporary:
        dll = Path(temporary) / 'cache.dll'
        subprocess.run([str(args.zig.resolve()), 'cc', '-target', 'x86_64-windows-gnu',
            '-shared', '-Wl,--export-all-symbols', '-O2', '-std=c11', '-Wall', '-Wextra', '-Werror',
            str(native/'cache_core.c'), str(native/'cache_thread_fixture.c'), '-o', str(dll)], check=True)
        import sys
        code = 'import ctypes,json;from tools.test_custom_lut_cache import exercise;print(json.dumps(exercise(ctypes.CDLL(__import__("sys").argv[1]))))'
        subprocess.run([sys.executable, '-c', code, str(dll)], cwd=ROOT, check=True)

if __name__ == '__main__':
    main()
