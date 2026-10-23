"""Regression checks for the exact-layout offline composer; no device access."""
import os
from pathlib import Path
import struct
import subprocess
import sys

import pytest

pytest.importorskip('numpy')
from a7m4 import combined662 as c


def bank(labels):
    count = 0xBE2
    data = bytearray(16 + 2 * count)
    data[:4] = b'uxc\x07'
    struct.pack_into('<H', data, 10, 5)
    struct.pack_into('<I', data, 12, count * 0x1001)
    data[16:] = b'\xff\xff' * count
    data.extend(bytes(-len(data) % 4))
    base = len(data)
    for rid, label in labels.items():
        struct.pack_into('<H', data, 16 + 2 * (rid - 0x200A000), (len(data) - base) // 4)
        data.extend(struct.pack('<I', rid + 0x1C000000) + label.encode() + b'\0')
        data.extend(bytes(-len(data) % 4))
    return bytes(data)


def test_aspect_resource_relocation_preserves_sound_labels():
    base = bank({0x200AB60: 'old'})
    main_labels = {0x200AB60: '', 0x200AB61: '确认导入快门声', 0x200AB62: '确认导入对焦声', 0x200AB63: '取消'}
    aspect_labels = dict(zip(range(0x200AB60, 0x200AB64), ('17:6', '65:24', '5:4', '7:6')))
    result, _ = c.merge_string(base, bank(main_labels), bank(aspect_labels))
    actual = c.parse(result)
    assert all(actual[key] == value for key, value in main_labels.items())
    assert [actual[key] for key in range(0x200AB4C, 0x200AB50)] == ['17:6', '65:24', '5:4', '7:6']


def test_unknown_resource_collision_rejected():
    base = bank({0x200AB60: 'old', 0x200AB10: 'base'})
    main = bank({0x200AB60: '', 0x200AB10: 'unrelated main change'})
    labels = dict(zip(range(0x200AB60, 0x200AB64), ('17:6', '65:24', '5:4', '7:6')))
    with pytest.raises(AssertionError):
        c.merge_string(base, main, bank(labels | {0x200AB10: 'conflicting aspect change'}))


def test_reserved_destination_collision_rejected():
    labels = dict(zip(range(0x200AB60, 0x200AB64), ('17:6', '65:24', '5:4', '7:6')))
    with pytest.raises(AssertionError):
        c.merge_string(bank({}), bank({0x200AB4C: 'occupied'}), bank(labels))


def test_long_record_last_avoids_16bit_offset_overflow():
    # Placing the long live record first would push later record starts outside
    # the u16-word range. The last record may safely end beyond that range.
    labels = {0x200AB10: 'x' * 262100, 0x200AB60: 'old'}
    aspect = dict(zip(range(0x200AB60, 0x200AB64), ('17:6', '65:24', '5:4', '7:6')))
    result, _ = c.merge_string(bank({0x200AB60: 'old'}), bank(labels), bank(aspect))
    assert c.parse(result)[0x200AB10] == labels[0x200AB10]
    assert c.parse(result)[0x200AB4D] == '65:24'


@pytest.mark.parametrize('call', [
    lambda: c.compose_ap(b'wrong', b'wrong', b'wrong'),
    lambda: c.compile_cp(b'wrong', Path('no-compiler.exe')),
    lambda: c.compose_string(next(iter(c.LAYOUT['resource_banks'])), b'wrong', b'wrong', b'wrong'),
])
def test_wrong_image_rejected_before_parsing_or_compiling(call):
    with pytest.raises(ValueError, match='SHA-256 mismatch'):
        call()


def test_write_never_overwrites(tmp_path):
    path = tmp_path/'existing.so'
    path.write_bytes(b'keep')
    with pytest.raises(FileExistsError):
        c.write_new(path, b'replace')
    assert path.read_bytes() == b'keep'


def test_sources_match_published_recipe():
    for row in c.LAYOUT['source_files']:
        c.check_hash((c.ROOT/row['path']).read_bytes(), row['sha256'], row['path'])


def test_optimized_python_is_rejected():
    result = subprocess.run([sys.executable, '-O', '-B', '-c', 'import a7m4.combined662'],
                            cwd=c.ROOT, env=os.environ.copy(), capture_output=True, text=True)
    assert result.returncode != 0
    assert 'binary invariant checks are required' in result.stderr
