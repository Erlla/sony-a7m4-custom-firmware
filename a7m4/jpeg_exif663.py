"""Offline JPEG EXIF correction for the exact combined-6.62 sound libmpr.

Builds one component from original assembly. No device or signing operations.
"""
from pathlib import Path
from io import BytesIO
import argparse
import hashlib
import json
import struct
import subprocess
import tempfile
from elftools.elf.elffile import ELFFile

if not __debug__:
    raise RuntimeError('Run without Python -O: binary invariant checks are required')

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'native/jpeg-exif-663'
LAYOUT = json.loads((NATIVE / 'layout.json').read_text('utf8'))


def check_hash(data, expected, label):
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise ValueError(f'{label}: SHA-256 mismatch: {actual} != {expected}')


def compose(data, zig):
    check_hash(data, LAYOUT['input_sha256'], 'libmpr input')
    check_hash(Path(zig).read_bytes(), LAYOUT['compiler_sha256'], 'Zig compiler')
    source, ld = NATIVE / 'jpeg_exif.S', NATIVE / 'jpeg_exif.ld'
    for file in (source, ld):
        check_hash(file.read_bytes(), LAYOUT['sources'][file.name], file.name)
    elf = ELFFile(BytesIO(data))
    ph = elf['e_phoff']
    assert ph == 0x370000 and elf['e_phnum'] == 7 and elf['e_phentsize'] == 56
    assert elf['e_machine'] == 'EM_AARCH64' and elf['e_type'] == 'ET_DYN'
    rx = elf.get_segment(0)
    assert rx['p_type'] == 'PT_LOAD' and rx['p_flags'] == 5
    assert rx['p_offset'] == rx['p_vaddr'] == 0
    assert rx['p_filesz'] == rx['p_memsz'] == 0x2e9e44
    assert not any(data[0x2e9e44:0x2ea448])
    assert data[0x2732f0:0x2732f4].hex() == 'ff4338d1'
    with tempfile.TemporaryDirectory(prefix='a7m4-jpeg-exif-') as tmp:
        module = Path(tmp) / 'jpeg_exif.elf'
        subprocess.run([str(zig), 'cc', '-target', 'aarch64-freestanding-none',
                        '-mcpu=generic-neon-fp_armv8', '-g', '-nostdlib',
                        '-Wl,--build-id=none', '-Wl,-e,aspect_jpeg_exif_header',
                        '-Wl,-T,' + str(ld), str(source), '-o', str(module)], check=True)
        linked = ELFFile(BytesIO(module.read_bytes()))
        text = linked.get_section_by_name('.text')
        assert text['sh_addr'] == 0x2e9e50 and text['sh_size'] == 448
        assert not [s for s in linked.iter_sections() if s['sh_type'] in ('SHT_REL', 'SHT_RELA') and s['sh_size']]
        assert not [s.name for s in linked.get_section_by_name('.symtab').iter_symbols() if s.name and s['st_shndx'] == 'SHN_UNDEF']
        code = text.data()
    check_hash(code, LAYOUT['code_sha256'], 'compiled prelude')
    output = bytearray(data)
    edits = [(ph + 32, struct.pack('<Q', 0x2ea010)),
             (ph + 40, struct.pack('<Q', 0x2ea010)),
             (0x2732f0, struct.pack('<I', 0x14000000 | ((0x2e9e50 - 0x2732f0) // 4))),
             (0x2e9e50, code)]
    cursor = 0
    for offset, value in sorted(edits):
        assert output[cursor:offset] == data[cursor:offset]
        output[offset:offset + len(value)] = value
        cursor = offset + len(value)
    assert output[cursor:] == data[cursor:] and len(output) == len(data)
    assert output[0x370038:] == data[0x370038:]
    assert output[0xa9348:0xa934c] == data[0xa9348:0xa934c]
    check_hash(output, LAYOUT['output_sha256'], 'libmpr output')
    return bytes(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--zig', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Output exists; no file will be overwritten')
    result = compose(args.input.read_bytes(), args.zig)
    with args.output.open('xb') as f:
        f.write(result)
    print(json.dumps(dict(result='PASS_EXACT_SOUND_MPR_JPEG_EXIF', bytes=len(result),
                          sha256=hashlib.sha256(result).hexdigest())))


if __name__ == '__main__':
    main()
