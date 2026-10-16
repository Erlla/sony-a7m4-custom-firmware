"""Reproduce the 6.02 / FX2 1.01 FL2/FL3 artifacts offline. Never flash devices."""
import argparse
import json
from pathlib import Path
import struct

from .common import digest, require, read_json
from .fat import Fat
from .offline import save_new

RECIPES = Path(__file__).resolve().parent / "profiles/fl23"
SLOTS = {0x02cf12c8: 10, 0x02cf12ca: 11, 0x02cf13b0: 10,
         0x02cf13d0: 11, 0x02cf143e: 10, 0x02cf1440: 11}


def delta_coefficients(cc1, offset):
    require(0 <= offset <= len(cc1) - 48, "COEFFICIENT", "Coefficient outside CC1")
    values = struct.unpack_from("<24h", cc1, offset)
    converted = list(values[:8]) + [values[i + 8] - values[i] for i in range(8)] + [values[i + 16] - values[i] for i in range(8)]
    require(all(-32768 <= v <= 32767 for v in converted), "COEFFICIENT", "Delta exceeds int16")
    return struct.pack("<24h", *converted)


def patch_program(source, recipe, donors=None):
    require(len(source) == recipe["size"] and digest(source) == recipe["source_sha256"],
            "BASELINE", "Unsupported source. This recipe requires the exact official 6.02 file")
    output = bytearray(source)
    donors = donors or {}
    for name, data in donors.items():
        require(digest(data) == recipe["donors"][name], "DONOR", "Wrong FX2 donor: " + name)
    for op in recipe.get("donor_operations", []):
        offset, size, src = op["offset"], op["size"], op["source_offset"]
        if op["source"] == "fx2_cp":
            raw = donors["fx2_cp"][src:src + size]
        else:
            raw = delta_coefficients(donors["fx2_cc1"], src)
        require(len(raw) == size and digest(raw) == op["sha256"], "DONOR", "Donor record mismatch")
        require(0 <= offset <= len(source) - size, "PATCH", "Record outside output")
        output[offset:offset + size] = raw
    for patch in recipe["patches"]:
        offset, raw = patch["offset"], bytes.fromhex(patch["new_hex"])
        require(0 <= offset <= len(source) - len(raw), "PATCH", "Patch outside file")
        require(digest(source[offset:offset + len(raw)]) == patch["old_sha256"], "PATCH", "Patch preimage mismatch")
        output[offset:offset + len(raw)] = raw
    require(len(output) == len(source) and digest(output) == recipe["target_sha256"], "PATCH", "Final artifact hash mismatch")
    return bytes(output)


def bk4_rows(data):
    """Parse two bounded BK4 containers and validate all records and sums."""
    starts, pos = [], 0
    while True:
        pos = data.find(b"BK4\0", pos)
        if pos < 0:
            break
        if pos >= 12 and data[pos - 8:pos - 4] == b"\xaa" * 4:
            starts.append(pos - 12)
        pos += 4
    require(len(starts) == 2, "BK4", "Expected two BK4 segments")
    rows = []
    for number, base in enumerate(starts):
        end = starts[number + 1] if number + 1 < len(starts) else len(data)
        require(base + 0x100 <= end, "BK4", "Truncated header")
        groups, items, body = struct.unpack_from("<III", data, base + 0x10)
        extent = sum(struct.unpack_from("<II", data, base + 0x18))
        index = base + 0x100 + 6 * groups
        require(index + 6 * items <= base + body <= base + extent <= end, "BK4", "Invalid index or extent")
        checksum = sum(data[base:base + 0x20]) + sum(data[base + 0x24:base + extent])
        require(checksum == struct.unpack_from("<I", data, base + 0x20)[0], "BK4", "Original checksum mismatch")
        records, expected = {}, 0
        intervals = []
        for group in range(groups):
            count, first = struct.unpack_from("<HI", data, base + 0x100 + group * 6)
            require(first == expected and first + count <= items, "BK4", "Invalid group index")
            expected += count
            for slot in range(count):
                attrs, packed = struct.unpack_from("<HI", data, index + 6 * (first + slot))
                if packed == 0xffffffff:
                    continue
                offset, size = base + (packed & 0xffffff), packed >> 24
                start = offset
                if size == 255:
                    require(base + body <= offset <= base + extent - 2, "BK4", "Invalid extended record")
                    size = struct.unpack_from("<H", data, offset)[0]
                    offset += 2
                require(base + body <= start <= offset <= offset + size <= base + extent, "BK4", "Record outside body")
                records[(group << 16) | slot] = {"offset": offset, "size": size, "attrs": attrs}
                if offset + size > start:
                    intervals.append((start, offset + size))
        require(expected == items, "BK4", "Incomplete index")
        intervals.sort()
        require(all(a[1] <= b[0] for a, b in zip(intervals, intervals[1:])), "BK4", "Overlapping records")
        rows.append({"base": base, "extent": extent, "records": records})
    return rows


def color_records(cc1, matrix, donor_cc1, donor_matrix, matrix_mode="fixed-a1"):
    require(len(cc1) == 0x2000 and len(matrix) == 0x7000, "COLOR", "Unexpected target color record size")
    require(len(donor_cc1) == 0x2000 and len(donor_matrix) == 0x7000, "COLOR", "Unexpected donor size")
    require(cc1[0xefe] == 0 and donor_cc1[0xefe] == 1, "COLOR", "Expected M4 delta / FX2 absolute encoding")
    require(matrix_mode in ("fixed-a1", "dynamic"), "COLOR", "Unknown matrix mode")
    new_cc, new_matrix = bytearray(cc1), bytearray(matrix)
    new_cc[0x1236:0x123a] = bytes([22, 24, 23, 25])
    for bank in (22, 23, 24, 25):
        offset = 0x1250 + bank * 64
        new_cc[offset:offset + 48] = delta_coefficients(donor_cc1, offset)
    new_matrix[0x1cc:0x1d0] = bytes([22, 24, 23, 25])
    new_matrix[0x43e0:0x4fe0] = donor_matrix[0x43e0:0x4fe0]
    if matrix_mode == "fixed-a1":
        for bank in (22, 23, 24, 25):
            base = 0x1e0 + bank * 0x300
            a1 = donor_matrix[base + 0xc0:base + 0x180]
            # Three 192-byte endpoints, followed by the unchanged bank tail.
            new_matrix[base:base + 0x240] = a1 * 3
    return bytes(new_cc), bytes(new_matrix)


def patch_backup(payload, donor_cc1, donor_matrix, matrix_mode="fixed-a1"):
    rows = bk4_rows(payload)
    result = bytearray(payload)
    all_records = {}
    for row in rows:
        for key, record in row["records"].items():
            all_records.setdefault(key, []).append(record)
    def locate(key):
        values = all_records.get(key, [])
        require(len(values) == 1, "BK4", f"Expected exactly one record {key:08x}")
        return values[0]
    def read(key):
        rec = locate(key)
        return payload[rec["offset"]:rec["offset"] + rec["size"]]
    allowed = set()
    def write(key, value):
        rec = locate(key)
        require(len(value) == rec["size"], "BK4", "Record size must be retained")
        start = rec["offset"]
        result[start:start + len(value)] = value
        allowed.update(range(start, start + len(value)))
    cc, matrix = color_records(read(0x02a40001), read(0x02a4000d), donor_cc1, donor_matrix, matrix_mode)
    write(0x02a40001, cc)
    write(0x02a4000d, matrix)
    for key, value in SLOTS.items():
        rec = locate(key)
        require(rec["attrs"] == 0x60 and rec["size"] == 1, "BK4", "Unknown look-slot format")
        write(key, bytes([value]))
    for row in rows:
        base, extent = row["base"], row["extent"]
        checksum = sum(result[base:base + 0x20]) + sum(result[base + 0x24:base + extent])
        struct.pack_into("<I", result, base + 0x20, checksum)
        allowed.update(range(base + 0x20, base + 0x24))
    require(all(a == b or i in allowed for i, (a, b) in enumerate(zip(payload, result))), "BK4", "Unexpected backup changes")
    bk4_rows(result)
    return bytes(result)


def personal_images(nfa2, nfa6, donor_cc1, donor_matrix, matrix_mode="fixed-a1"):
    require(len(nfa2) == 20971520, "BASELINE", "Expected 20 MiB settings partition")
    require(len(nfa6) >= 0x1a7c00, "BASELINE", "Truncated color partition")
    fs = Fat(nfa2)
    for filename in ("BACKUP.BIN", "BACKUP.BAK"):
        fs.replace(filename, patch_backup(fs.read(filename), donor_cc1, donor_matrix, matrix_mode))
    cc, matrix = color_records(nfa6[0x19cc00:0x19ec00], nfa6[0x1a0c00:0x1a7c00], donor_cc1, donor_matrix, matrix_mode)
    result = bytearray(nfa6)
    result[0x19cc00:0x19ec00] = cc
    result[0x1a0c00:0x1a7c00] = matrix
    return fs.bytes(), bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    for name in ("ap", "cp", "fx2-cp", "fx2-cc1", "fx2-block13", "nflasha2", "nflasha6"):
        build.add_argument("--" + name, type=Path, required=True)
    build.add_argument("--nflasha8", type=Path, help="Optionally replace CPAPP-B.BIN inside your FAT partition")
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--matrix-mode", choices=("fixed-a1", "dynamic"), default="fixed-a1",
                       help="fixed-a1 targets Imaging Edge re-selection; dynamic retains donor endpoints")
    extract = sub.add_parser("extract-donor", help="Extract and hash-check FX2 CC1/block13 from an unpacked BK4 defaults file")
    extract.add_argument("--backup", type=Path, required=True)
    extract.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify-nor")
    verify.add_argument("--nor", type=Path, required=True)
    verify.add_argument("--cp", type=Path, required=True)
    verify.add_argument("--offset", type=lambda x: int(x, 0), required=True)
    verify.add_argument("--swap16", action="store_true")
    args = parser.parse_args()
    if args.command == "extract-donor":
        require(not args.output.exists(), "EXISTS", "Choose a new donor directory")
        data = args.backup.read_bytes()
        rows = bk4_rows(data)
        cr = read_json(RECIPES / "cp-v7-recipe.json")
        products = {}
        for key, name, identity in ((0x02a40001, "cc1.bin", "fx2_cc1"), (0x02a4000d, "block13.bin", "fx2_block13")):
            records = [row["records"][key] for row in rows if key in row["records"]]
            require(len(records) == 1, "DONOR", "Ambiguous donor record")
            rec = records[0]
            payload = data[rec["offset"]:rec["offset"] + rec["size"]]
            require(digest(payload) == cr["donors"][identity], "DONOR", "Wrong FX2 1.01 color record")
            products[name] = payload
        args.output.mkdir(parents=True)
        for name, payload in products.items():
            (args.output / name).write_bytes(payload)
        print(json.dumps({"camera_io": False, "extracted": {name: digest(data) for name, data in products.items()}}, indent=2))
        return
    if args.command == "verify-nor":
        nor, cp = args.nor.read_bytes(), args.cp.read_bytes()
        require(0 <= args.offset <= len(nor) - len(cp), "NOR", "CP range outside NOR dump")
        raw = bytearray(nor[args.offset:args.offset + len(cp)])
        if args.swap16:
            require(len(raw) % 2 == 0, "NOR", "Odd word-swapped length")
            raw[0::2], raw[1::2] = raw[1::2], raw[0::2]
        require(bytes(raw) == cp, "NOR", "Physical NOR CP differs from target")
        print(json.dumps({"nor_cp_matches": True, "cp_sha256": digest(cp), "camera_io": False}))
        return
    require(not args.output.exists(), "EXISTS", "Choose a new output directory")
    ar, cr = read_json(RECIPES / "ap-recipe.json"), read_json(RECIPES / "cp-v7-recipe.json")
    donors = {"fx2_cp": args.fx2_cp.read_bytes(), "fx2_cc1": args.fx2_cc1.read_bytes(), "fx2_block13": args.fx2_block13.read_bytes()}
    for key, value in donors.items():
        require(digest(value) == cr["donors"][key], "DONOR", "Wrong donor: " + key)
    ap = patch_program(args.ap.read_bytes(), ar)
    cp = patch_program(args.cp.read_bytes(), cr, donors)
    source2, source6 = args.nflasha2.read_bytes(), args.nflasha6.read_bytes()
    nfa2, nfa6 = personal_images(source2, source6, donors["fx2_cc1"], donors["fx2_block13"], args.matrix_mode)
    products = {"appFw.so": (ap, ar["source_sha256"]), "CPAPP-B.BIN": (cp, cr["source_sha256"]),
                "nflasha2.bin": (nfa2, digest(source2)), "nflasha6.bin": (nfa6, digest(source6))}
    if args.nflasha8:
        original = args.nflasha8.read_bytes()
        fs = Fat(original)
        require(digest(fs.read("CPAPP-B.BIN")) == cr["source_sha256"], "BASELINE", "nflasha8 is not the stock 6.02 CP")
        fs.replace("CPAPP-B.BIN", cp)
        products["nflasha8.bin"] = (fs.bytes(), digest(original))
    args.output.mkdir(parents=True)
    report = {"baseline": "ILCE-7M4 official 6.02 / FX2 1.01", "camera_io": False,
              "matrix_mode": args.matrix_mode,
              "fl23_color_matches_official": None,
              "color_validation": "Fixed A1 samples are close to Imaging Edge re-selection; not pixel-identical or an all-scene FX2 equivalence claim",
              "installable_dat": False, "nor_updated": False, "outputs": {}}
    for name, (data, source_hash) in products.items():
        evidence = {"source_sha256": source_hash, "method": "FL2/FL3 v7"}
        save_new(args.output / name, data, evidence)
        report["outputs"][name] = evidence | {"output_sha256": digest(data), "size": len(data)}
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
