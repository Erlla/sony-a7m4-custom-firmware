"""Build exact-layout AP/MPR components for custom-ratio camera playback."""
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

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'native/aspect-playback'
LAYOUT = json.loads((NATIVE / 'layout.json').read_text('utf8'))


def check_hash(data, expected, label):
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise ValueError(f'{label}: SHA-256 mismatch: {actual} != {expected}')


def compose(data, zig, component):
    profile = LAYOUT['components'][component]
    check_hash(data, profile['input_sha256'], component + ' input')
    check_hash(Path(zig).read_bytes(), LAYOUT['compiler_sha256'], 'Zig compiler')
    for name, expected in profile['sources'].items():
        check_hash((NATIVE / name).read_bytes(), expected, name)

    elf = ELFFile(BytesIO(data))
    assert elf['e_machine'] == 'EM_AARCH64' and elf['e_type'] == 'ET_DYN'
    index, rx = next((i, s) for i, s in enumerate(elf.iter_segments())
                     if s['p_type'] == 'PT_LOAD' and s['p_vaddr'] == int(profile['rx_VA'], 0))
    assert rx['p_flags'] == 5 and rx['p_filesz'] == rx['p_memsz'] == profile['input_rx_bytes']
    helper = int(profile['helper_VA'], 0)
    at = rx['p_offset'] + helper - rx['p_vaddr']
    assert not any(data[at:at + profile['reserved_helper_bytes']])

    with tempfile.TemporaryDirectory(prefix='a7m4-aspect-playback-') as tmp:
        module = Path(tmp) / 'playback.elf'
        subprocess.run([str(zig), 'cc', '-target', 'aarch64-freestanding-none',
                        '-mcpu=generic-neon-fp_armv8', '-nostdlib', '-g',
                        '-Wl,--build-id=none', '-Wl,-e,' + profile['entry_symbol'],
                        '-Wl,-T,' + str(NATIVE / profile['linker_script']),
                        '-Wa,-I' + str(NATIVE), str(NATIVE / profile['source']),
                        '-o', str(module)], check=True)
        linked = ELFFile(BytesIO(module.read_bytes()))
        section = linked.get_section_by_name('.text')
        assert section['sh_addr'] == helper and section['sh_size'] == profile['code_bytes']
        assert not [s for s in linked.iter_sections()
                    if s['sh_type'] in ('SHT_REL', 'SHT_RELA') and s['sh_size']]
        assert not [s.name for s in linked.get_section_by_name('.symtab').iter_symbols()
                    if s.name and s['st_shndx'] == 'SHN_UNDEF']
        code = section.data()
    check_hash(code, profile['code_sha256'], 'compiled playback helper')

    entry = int(profile['native_entry'], 0)
    source_load = next(s for s in elf.iter_segments()
                       if s['p_type'] == 'PT_LOAD' and
                       s['p_vaddr'] <= entry < s['p_vaddr'] + s['p_filesz'])
    entry_offset = source_load['p_offset'] + entry - source_load['p_vaddr']
    delta = helper - entry
    assert delta % 4 == 0 and -(1 << 27) <= delta < (1 << 27)
    output = bytearray(data)
    output[entry_offset:entry_offset + 4] = struct.pack('<I', 0x14000000 | ((delta // 4) & 0x3ffffff))
    output[at:at + len(code)] = code
    header = elf['e_phoff'] + index * elf['e_phentsize'] + 32
    output[header:header + 16] = struct.pack('<QQ', profile['output_rx_bytes'], profile['output_rx_bytes'])
    assert len(output) == len(data) == profile['file_bytes']
    check_hash(output, profile['output_sha256'], component + ' output')
    return bytes(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component', choices=sorted(LAYOUT['components']), required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--zig', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Output exists; no file will be overwritten')
    result = compose(args.input.read_bytes(), args.zig, args.component)
    with args.output.open('xb') as stream:
        stream.write(result)
    print(json.dumps(dict(component=args.component, bytes=len(result),
                          sha256=hashlib.sha256(result).hexdigest())))


if __name__ == '__main__':
    main()
