"""Rebuild the exact six-ratio and normal automatic-review component layer."""
from io import BytesIO
from pathlib import Path
import argparse
import hashlib
import json
import struct
import subprocess
import tempfile

from elftools.elf.elffile import ELFFile

if not __debug__:
    raise RuntimeError('Run without Python -O: binary invariant checks are required')

NATIVE = Path(__file__).resolve().parents[1] / 'native/aspect-autoreview'
LAYOUT = json.loads((NATIVE / 'layout.json').read_text('utf8'))


def check_hash(data, expected, label):
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(label + ': SHA-256 mismatch')


def compose(data, component, compiler):
    profile = LAYOUT['components'][component]
    check_hash(data, profile['input_sha256'], component + ' input')
    assert len(data) == profile['file_bytes']
    roles = {m['compiler'] for m in profile['modules']}
    assert len(roles) == 1
    role = next(iter(roles))
    compiler = Path(compiler).resolve()
    check_hash(compiler.read_bytes(), LAYOUT['compilers'][role]['sha256'], role)
    for name, digest in LAYOUT['sources'].items():
        check_hash((NATIVE / name).read_bytes(), digest, name)
    output = bytearray(data)
    with tempfile.TemporaryDirectory(prefix='a7m4-aspect-review-') as tmp:
        for module in profile['modules']:
            target = Path(tmp) / (module['name'] + '.elf')
            command = [str(compiler)] + (['cc'] if role == 'zig' else [])
            command += module['flags']
            command += ['-Wl,-T,' + str(NATIVE / module['linker']), '-Wa,-I' + str(NATIVE)]
            command += [str(NATIVE / s) for s in module['sources']]
            subprocess.run(command + ['-o', str(target)], cwd=NATIVE, check=True)
            elf = ELFFile(BytesIO(target.read_bytes()))
            for spec in module['sections']:
                section = elf.get_section_by_name(spec['name'])
                assert section['sh_addr'] == int(spec['VA'], 0)
                code = bytearray(section.data())
                patch = module.get('explicit_mode_patch')
                if patch:
                    at = patch['offset']
                    assert code[at:at+4] == bytes.fromhex(patch['before'])
                    code[at:at+4] = bytes.fromhex(patch['after'])
                assert len(code) == spec['bytes']
                check_hash(code, spec['sha256'], module['name'])
                at = spec['offset']
                check_hash(data[at:at+len(code)], spec['input_sha256'], 'module preimage')
                output[at:at+len(code)] = code
    if component == 'ap':
        table = profile['menu_table']
        start = table['source_offset']
        rows = bytearray(data[start:start + 8*128])
        for i in range(2):
            row = bytearray(rows[:128])
            for offset, value in ((0, 5636+i), (4, 5636+i), (8, 0x200ab66+i),
                                  (12, 0x2001ea4+i), (32, 0x2001e9c+i),
                                  (36, 0x2001e9e+i), (52, 8+i)):
                struct.pack_into('<I', row, offset, value)
            rows.extend(row)
        at = table['output_offset']
        assert not any(data[at:at+len(rows)])
        output[at:at+len(rows)] = rows
    for patch in profile['small_patches']:
        at = patch['offset']
        before, after = bytes.fromhex(patch['before']), bytes.fromhex(patch['after'])
        assert len(before) == len(after) and output[at:at+len(before)] == before
        output[at:at+len(after)] = after
    assert len(output) == len(data)
    check_hash(output, profile['output_sha256'], component + ' output')
    return bytes(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component', choices=sorted(LAYOUT['components']), required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Output exists; no file will be overwritten')
    result = compose(args.input.read_bytes(), args.component, args.compiler)
    with args.output.open('xb') as stream:
        stream.write(result)
    print(json.dumps(dict(component=args.component, bytes=len(result),
                          sha256=hashlib.sha256(result).hexdigest())))


if __name__ == '__main__':
    main()
