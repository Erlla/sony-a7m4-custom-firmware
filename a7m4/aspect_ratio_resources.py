"""Extend supplied UXC/UXD banks with the two wide-ratio labels and icons."""
from pathlib import Path
import argparse
import hashlib
import json
import struct
from PIL import Image, ImageDraw, ImageFont
from .aspect_autoreview import LAYOUT, check_hash
from .menu_ui_fixes import records
from .icon_lz4k import encode, decode

sha=lambda data:hashlib.sha256(data).hexdigest()
LABELS = ("21:9", "2.35:1")


def pixels(label, selected, menu=False, font_path=None):
    font_size = 20
    font = ImageFont.truetype(str(font_path), font_size)
    while font.getbbox(label)[2] - font.getbbox(label)[0] > 60:
        font_size -= 1
        font = ImageFont.truetype(str(font_path), font_size)
    image = Image.new("RGBA", (70, 60), (221, 221, 221, 0))
    draw = ImageDraw.Draw(image)
    box = draw.textbbox((0, 0), label, font=font)
    width = box[2] - box[0]
    left = (70 - width - 10) // 2
    fill = (221, 85, 51, 255) if selected else (221, 221, 221, 255)
    draw.rectangle((left, 18, left + width + 9, 41), fill=fill, outline=(0, 0, 0, 255), width=2)
    draw.text(((70 - width) // 2 - box[0], 30 - (box[1] + box[3]) // 2), label, font=font, fill=(0, 0, 0, 255))
    if menu:
        compact = Image.new("RGBA", (76, 40), (221, 221, 221, 0))
        compact.paste(image.crop((0, 10, 70, 50)), (3, 0))
        image = compact
    data = bytearray()
    for y in range(image.height):
        for x in range(80):
            rgba = image.getpixel((x, y)) if x < image.width else (221, 221, 221, 0)
            r, g, b, a = [(value + 8) // 17 for value in rgba]
            data.extend(struct.pack("<H", (r << 12) | (g << 8) | (b << 4) | a))
    return image.width, image.height, bytes(data)


def image_bank(before, font_path):
    target_bytes = len(before)
    count, base, original = records(before)
    specs = [(0x1e9c + i, label, False, False) for i, label in enumerate(LABELS)]
    specs += [(0x1e9e + i, label, True, False) for i, label in enumerate(LABELS)]
    specs += [(0x1ea4 + i, label, False, True) for i, label in enumerate(LABELS)]
    needed = max(index for index, *_ in specs) + 1
    if needed > count:
        new_base = (16 + 2 * needed + 3) & ~3
        extended = bytearray(before[:16 + 2 * count])
        extended.extend(b"\xff\xff" * (needed - count))
        extended.extend(bytes(new_base - len(extended)))
        extended.extend(before[base:])
        struct.pack_into("<I", extended, 12, needed | (((needed + 1) // 2) << 13))
        before = bytes(extended)
        count, base, original = records(before)
    assert all(index < count and struct.unpack_from("<H", before, 16 + 2 * index)[0] == 0xffff for index, *_ in specs)
    insertion = min(row["payload"] for row in original)
    assert insertion == max(row["offset"] + row["descriptor_bytes"] for row in original)
    extra = 20 * len(specs)
    after = bytearray(before[:insertion] + bytes(extra) + before[insertion:])
    for row in original:
        struct.pack_into("<I", after, row["offset"] + row["relative_field"], row["relative"] + extra)
    cursor = (max(row["payload"] + row["bytes"] for row in original) + extra + 3) & ~3
    assert not any(after[cursor:])
    artwork = []
    for i, (index, label, selected, menu) in enumerate(specs):
        width, height, raw = pixels(label, selected, menu, font_path)
        compressed = encode(raw)
        assert decode(compressed)[0] == raw
        cursor = (cursor + 3) & ~3
        assert cursor + len(compressed) <= target_bytes and not any(after[cursor:cursor + len(compressed)])
        descriptor = insertion + 20 * i
        word = (descriptor - base) // 4
        assert word < 0xffff
        struct.pack_into("<H", after, 16 + 2 * index, word)
        struct.pack_into("<IIHHII", after, descriptor, 0x1a000000 + index, 0xc0000000,
                         width, height, len(compressed), cursor - descriptor - 4)
        after[cursor:cursor + len(compressed)] = compressed
        artwork.append(dict(index=index, label=label, selected=selected, width=width, height=height,
                            pixels_sha256=sha(raw)))
        cursor += len(compressed)
    assert not any(after[target_bytes:])
    del after[target_bytes:]
    updated = {row["index"]: row for row in records(after)[2]}
    for row in original:
        new = updated[row["index"]]
        assert all(new[key] == row[key] for key in ("flags", "width", "height", "bytes"))
        assert after[new["payload"]:new["payload"] + new["bytes"]] == before[row["payload"]:row["payload"] + row["bytes"]]
    return bytes(after), artwork


def string_bank(before):
    assert before[:4] == b"uxc\x07"
    packed = struct.unpack_from("<I", before, 12)[0]
    count, remainder = divmod(packed, 0x1001)
    assert not remainder
    base = (16 + 2 * count + 3) & ~3
    id_base = 0x1e000000 + (struct.unpack_from("<H", before, 10)[0] << 13)
    after = bytearray(before)
    if (len(before) - base + 24) // 4 >= 0xffff:
        # The native directory stores a 16-bit word offset. Prior edits can
        # leave obsolete payloads at the end. Repack live records, placing
        # the longest final record last so every start remains representable.
        entries = []
        for slot in range(count):
            word = struct.unpack_from("<H", before, 16 + 2 * slot)[0]
            if word == 0xffff:
                continue
            start = base + word * 4
            assert struct.unpack_from("<I", before, start)[0] == id_base + slot
            end = (before.index(b"\0", start + 4) + 4) & ~3
            entries.append((slot, before[start:end]))
        entries.sort(key=lambda entry: len(entry[1]))
        after = bytearray(before[:base])
        for slot, record in entries:
            word = (len(after) - base) // 4
            assert word < 0xffff
            struct.pack_into("<H", after, 16 + 2 * slot, word)
            after.extend(record)
        # Insert the new labels before the final, longest record.
        slot, record = entries[-1]
        after = after[:-len(record)]
        final = (slot, record)
    else:
        final = None
    for index, label in enumerate(LABELS):
        key = 0x1e00ab66 + index
        slot = key - id_base
        assert 0 <= slot < count and struct.unpack_from("<H", before, 16 + 2 * slot)[0] == 0xffff
        after.extend(bytes((-len(after)) % 4))
        word = (len(after) - base) // 4
        assert word < 0xffff
        struct.pack_into("<H", after, 16 + 2 * slot, word)
        after.extend(struct.pack("<I", key) + label.encode("ascii") + b"\0")
        after.extend(bytes((-len(after)) % 4))
    if final:
        slot, record = final
        word = (len(after) - base) // 4
        assert word < 0xffff
        struct.pack_into("<H", after, 16 + 2 * slot, word)
        after.extend(record)
    for slot in range(count):
        word = struct.unpack_from("<H", before, 16 + 2 * slot)[0]
        if word == 0xffff:
            continue
        old = base + 4 * word
        new = base + 4 * struct.unpack_from("<H", after, 16 + 2 * slot)[0]
        end = before.index(b"\0", old + 4) + 1
        assert after[new:new + end - old] == before[old:end]
    return bytes(after)


def compose(data, camera_path, font_path=None):
    spec=next(r for r in LAYOUT['resources'] if r['path']==camera_path)
    check_hash(data,spec['source_sha256'],camera_path+' input')
    if '/image_' in camera_path:
        if font_path is None:raise ValueError('Arial Bold font is required for image banks')
        check_hash(Path(font_path).read_bytes(),LAYOUT['font']['sha256'],'font')
        result=image_bank(data,font_path)[0]
    else:result=string_bank(data)
    check_hash(result,spec['sha256'],camera_path+' output')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-directory',type=Path,required=True)
    parser.add_argument('--output-directory',type=Path,required=True)
    parser.add_argument('--font',type=Path,required=True)
    args=parser.parse_args()
    args.output_directory.mkdir(parents=True,exist_ok=False)
    for spec in LAYOUT['resources']:
        name=Path(spec['path']).name
        result=compose((args.input_directory/name).read_bytes(),spec['path'],args.font)
        (args.output_directory/name).write_bytes(result)
    print(json.dumps(dict(resource_banks=len(LAYOUT['resources']),passed=True)))


if __name__=='__main__':main()
