"""Build the pinned shared LUT language resources from locally held banks."""
from pathlib import Path
import argparse
import hashlib
import json
import struct
HERE = Path(__file__).resolve().parent

def records(data):
    if data[:4] != b'uxc\7':
        raise ValueError('Expected indexed UXC')
    count, rem = divmod(struct.unpack_from('<I', data, 12)[0], 0x1001)
    if rem:
        raise ValueError('Invalid UXC count')
    base = (16 + 2 * count + 3) & ~3
    first = 0x02000000 + (struct.unpack_from('<H', data, 10)[0] << 13)
    result = {}
    for i in range(count):
        rel = struct.unpack_from('<H', data, 16 + 2 * i)[0]
        if rel == 0xffff:
            continue
        pos = base + 4 * rel
        if struct.unpack_from('<I', data, pos)[0] != first + i + 0x1c000000:
            raise ValueError('Invalid UXC record')
        end = data.index(0, pos + 4)
        result[first + i] = data[pos + 4:end].decode('utf-8')
    return first, count, base, result


FIRST_ID = 0x0204E85E


def patch_bank(source, name, strings):
    first, count, base, old = records(source)
    if first + count != FIRST_ID:
        raise ValueError('Expected the pinned pre-LUT-localization bank range')
    family = 0 if 'simplifiedchinese' in name else 1 if 'traditionalchinese' in name else 2
    new_count = count + len(strings)
    new_base = (16 + 2 * new_count + 3) & ~3
    result = bytearray(source[:16 + 2 * count])
    result.extend(b'\xff\xff' * len(strings))
    result.extend(bytes(new_base - len(result)))
    result.extend(source[base:])
    struct.pack_into('<I', result, 12, new_count * 0x1001)
    for i, translations in enumerate(strings):
        result.extend(bytes(-len(result) % 4))
        rel = (len(result) - new_base) // 4
        if rel >= 0xffff:
            raise ValueError('UXC record offset exceeds the native index')
        struct.pack_into('<H', result, 16 + 2 * (count + i), rel)
        result.extend(struct.pack('<I', FIRST_ID + i + 0x1c000000))
        result.extend(translations[family].encode('utf-8') + b'\0')
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='Extracted share/app directory')
    parser.add_argument('--output', type=Path, required=True, help='New output share/app directory')
    args = parser.parse_args()
    reference = json.loads((HERE/'resources.json').read_text('utf-8'))
    strings = json.loads((HERE/'strings.json').read_text('utf-8'))
    if args.output.exists():
        raise ValueError('Use a new output directory')
    payloads = {}
    for row in reference['files']:
        name = Path(row['path']).name
        data = (args.input/name).read_bytes()
        if hashlib.sha256(data).hexdigest() != row['input_sha256']:
            raise ValueError('Unsupported language bank: '+name)
        result = patch_bank(data,name,strings)
        if hashlib.sha256(result).hexdigest() != row['output_sha256']:
            raise ValueError('Output differs from the reviewed resource set: '+name)
        old = records(data)[3]
        new = records(result)[3]
        if any(new[key] != value for key,value in old.items()):
            raise ValueError('Existing record changed: '+name)
        payloads[name] = result
    args.output.mkdir(parents=True)
    for name,data in payloads.items():
        (args.output/name).write_bytes(data)
    print('Built 34 language banks with 50 LUT labels; original records retained.')


if __name__ == '__main__':
    main()
