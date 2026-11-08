"""Build the exact CP layer that preserves custom aspect ratios in task copies."""
from io import BytesIO
from pathlib import Path
import argparse
import hashlib
import json
import struct
import subprocess
import tempfile
import zlib

from elftools.elf.elffile import ELFFile

if not __debug__:
    raise RuntimeError('Run without Python -O: binary invariant checks are required')

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'native/aspect-capture-clone'
LAYOUT = json.loads((NATIVE / 'layout.json').read_text('utf8'))


def check_hash(data, expected, label):
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(label + ': SHA-256 mismatch')


def compose(data, compiler):
    identity = LAYOUT['identities'].get(hashlib.sha256(data).hexdigest())
    if len(data) != LAYOUT['file_bytes'] or identity is None:
        raise ValueError('Unsupported CP input; a listed complete SHA-256 is required')
    check_hash(Path(compiler).read_bytes(), LAYOUT['compiler_sha256'], 'compiler')
    for name, expected in LAYOUT['sources'].items():
        check_hash((NATIVE / name).read_bytes(), expected, name)
    with tempfile.TemporaryDirectory(prefix='a7m4-aspect-clone-') as tmp:
        module = Path(tmp) / 'clone.elf'
        subprocess.run([str(compiler), *LAYOUT['compiler_flags'], '-T', str(NATIVE / 'clone.ld'),
                        str(NATIVE / 'clone.c'), '-o', str(module)], check=True)
        elf = ELFFile(BytesIO(module.read_bytes()))
        section = elf.get_section_by_name('.text')
        assert section['sh_addr'] == int(LAYOUT['helper_VA'], 0)
        assert section['sh_size'] == LAYOUT['helper_bytes']
        assert not [s.name for s in elf.get_section_by_name('.symtab').iter_symbols()
                    if s.name and s['st_shndx'] == 'SHN_UNDEF']
        code = section.data()
    check_hash(code, LAYOUT['helper_sha256'], 'compiled clone helper')
    output = bytearray(data)
    base = int(LAYOUT['cp_base'], 0)
    at = int(LAYOUT['helper_VA'], 0) - base
    assert not any(data[at:at+len(code)])
    output[at:at+len(code)] = code
    for patch in LAYOUT['patches']:
        at = int(patch['VA'], 0) - base
        before, after = bytes.fromhex(patch['before']), bytes.fromhex(patch['after'])
        assert len(before) == len(after) and data[at:at+len(before)] == before
        output[at:at+len(after)] = after
    crc = LAYOUT['prefix_crc']
    start, end = int(crc['start_VA'], 0)-base, int(crc['end_VA'], 0)-base
    at = int(crc['literal_VA'], 0) - base
    assert struct.unpack_from('<I', data, at)[0] == zlib.crc32(data[start:end])
    struct.pack_into('<I', output, at, zlib.crc32(output[start:end]))
    result = bytes(output)
    check_hash(result, identity['output_sha256'], 'CP output')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Output exists; no file will be overwritten')
    result = compose(args.input.read_bytes(), args.compiler)
    with args.output.open('xb') as stream:
        stream.write(result)
    print(json.dumps(dict(bytes=len(result), sha256=hashlib.sha256(result).hexdigest())))


if __name__ == '__main__':
    main()
