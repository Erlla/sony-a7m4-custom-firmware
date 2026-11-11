"""Build the exact CP component for camera-written FL2/FL3 RAW choices."""
from io import BytesIO
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import tempfile

from elftools.elf.elffile import ELFFile

if not __debug__:
    raise RuntimeError('Run without Python -O: binary invariant checks are required')

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'native/raw-alternative-looks'
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
    with tempfile.TemporaryDirectory(prefix='a7m4-raw-looks-') as tmp:
        module = Path(tmp) / 'raw_list.elf'
        subprocess.run([str(compiler), *LAYOUT['compiler_flags'], '-T', str(NATIVE / 'raw_list.ld'),
                        str(NATIVE / 'raw_list.c'), '-o', str(module)], check=True)
        elf = ELFFile(BytesIO(module.read_bytes()))
        assert not [s.name for s in elf.get_section_by_name('.symtab').iter_symbols()
                    if s.name and s['st_shndx'] == 'SHN_UNDEF']
        compiled = {}
        for row in LAYOUT['compiled_sections']:
            section = elf.get_section_by_name(row['section'])
            assert section['sh_addr'] == int(row['VA'], 0) and section['sh_size'] == row['bytes']
            compiled[row['section']] = section.data()
            check_hash(section.data(), row['sha256'], row['section'])
    output = bytearray(data)
    base = int(LAYOUT['cp_base'], 0)
    for patch in LAYOUT['patches']:
        at = int(patch['VA'], 0) - base
        before = bytes.fromhex(patch['before'])
        after = compiled[patch['section']] if 'section' in patch else bytes.fromhex(patch['after'])
        assert len(before) == len(after) and data[at:at+len(before)] == before
        output[at:at+len(after)] = after
    for start, end in LAYOUT['preserved_VA_ranges']:
        start, end = int(start, 0)-base, int(end, 0)-base
        assert output[start:end] == data[start:end]
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
