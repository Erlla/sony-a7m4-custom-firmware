"""Compile the LUT input adapter and apply it to the exact reference AP."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile

from elftools.elf.elffile import ELFFile

HERE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build(source, zig):
    reference = json.loads((HERE / 'reference.json').read_text('utf-8'))
    if sha(source) != reference['input_AP_sha256']:
        raise ValueError('Unsupported AP: use the exact combined input in reference.json')
    with tempfile.TemporaryDirectory(prefix='lut-input-') as temporary:
        elf_path = Path(temporary) / 'input.elf'
        command = [str(zig), 'cc', '-target', 'aarch64-freestanding-none',
            '-mgeneral-regs-only', '-mno-outline-atomics', '-mstrict-align', '-fpie', '-Os', '-g',
            '-Wall', '-Wextra', '-Werror', '-ffreestanding', '-fno-builtin', '-fno-stack-protector',
            '-ffunction-sections', '-fdata-sections', '-nostdlib', '-static', '-Wl,-no-pie',
            '-Wl,--gc-sections', '-Wl,-u,lut_input_dispatch', '-Wl,-e,lut_input_dispatch',
            '-Wl,-T,' + str(HERE / 'input.ld'),
            str(HERE / 'lut_input.c'), '-o', str(elf_path)]
        subprocess.run(command, check=True)
        elf = ELFFile(io.BytesIO(elf_path.read_bytes()))
        segment, = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
        if segment['p_vaddr'] != int(reference['module_VA'], 16):
            raise ValueError('Unexpected adapter load address')
        code = segment.data()

    output = bytearray(source)
    for edit in reference['edits']:
        offset, size = edit['offset'], edit['bytes']
        payload = code if edit.get('payload') == 'linked_RX_segment' else bytes.fromhex(edit['after_hex'])
        if len(payload) != size or sha(payload) != edit['after_sha256']:
            raise ValueError('Compiled adapter or layout differs from the reviewed component')
        output[offset:offset + size] = payload
    if sha(output) != reference['output_AP_sha256']:
        raise ValueError('Output differs from the reviewed AP')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='Locally held matching appFw.so')
    parser.add_argument('--output', type=Path, required=True, help='New output AP file')
    parser.add_argument('--zig', type=Path, required=True, help='Zig 0.14.1 executable')
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a new output file')
    output = build(args.input.read_bytes(), args.zig.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('xb') as stream:
        stream.write(output)
    print(f'Built {len(output)} bytes; SHA-256 {sha(output)}')


if __name__ == '__main__':
    main()
