"""Offline A7M4 6.02 container decoding and FL2/FL3 SD-package construction.

No camera I/O. Sony firmware and donor data must be supplied separately.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import struct
import tarfile
import zlib

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from .common import Assets, digest, require, sha256
from .fat import Fat
from .fl23 import RECIPES, patch_program
from .offline import prefix_crc, resign, ufu_layout
from .patching import Updater

OFFICIAL_SHA256 = "ad6df47a0a93a46336b9920a0d8891d0c766f8c96fa68ebda8685f6c21621188"
PLAIN_SHA256 = "4fd810b8d20ea239e0df01aded90687baef1ca2c8df208a7f58c4989f85799c3"
# Publicly researched CXD90057 container-format constants, not signing keys.
KEY_HEADER = bytes.fromhex("e3b0c44298fc1c149afbf4c8996fb924")
KEY_K8 = bytes.fromhex("434589432d319010f1132727353286ce4d7ede8b9c4f7217a0e0226e0f0edc69")


def exact(stream, count):
    data = stream.read(count)
    require(len(data) == count, "TRUNCATED", "Unexpected end of file")
    return data


def contexts(iv, encrypt=False):
    contexts = [Cipher(algorithms.AES(KEY_HEADER), modes.ECB()), Cipher(algorithms.AES(KEY_K8), modes.CBC(iv))]
    return [c.encryptor() if encrypt else c.decryptor() for c in contexts]


def frame_batches(source):
    """Validate DEND and every UFU block; CBC spans all but the first 512 B."""
    import numpy as np
    start, signature, dend = ufu_layout(source)
    encrypted_size = signature - start - 16
    require(encrypted_size > 0 and encrypted_size % 1024 == 0, "UFU", "Invalid FDAT block length")
    count = encrypted_size // 1024
    with Path(source).open("rb") as stream:
        crc = prefix_crc(stream, dend)
        stream.seek(dend + 8)
        require(struct.unpack(">I", exact(stream, 4))[0] == crc, "UFU", "DEND CRC mismatch")
        stream.seek(signature - 16)
        iv = exact(stream, 16)
        ecb, cbc = contexts(iv)
        stream.seek(start)
        for base in range(0, count, 4096):
            number = min(4096, count - base)
            ct = exact(stream, number * 1024)
            plain = ecb.update(ct[:512]) + cbc.update(ct[512:]) if base == 0 else cbc.update(ct)
            array = np.frombuffer(plain, dtype=np.uint8).reshape(number, 1024)
            words = array.view("<u2").reshape(number, 512)
            flags = words[:, 1]
            sizes = flags & 0x7fff
            full = number - 1 if base + number == count else number
            require(bool(np.all(sizes[:full] == 1020) and np.all(flags[:full] < 0x8000)), "UFU", "Nonfinal block layout mismatch")
            if full != number:
                require(int(flags[-1]) & 0x8000 and 0 < int(sizes[-1]) <= 1020, "UFU", "Invalid final block")
            require(bool(np.all((words[:, 1:].sum(axis=1, dtype=np.uint64) & 0xffff) == words[:, 0])), "UFU", "Block checksum mismatch")
            payload = array[:full, 4:].tobytes()
            if full != number:
                payload += array[-1, 4:4 + int(sizes[-1])].tobytes()
            yield base, count, array, payload, iv
        require(ecb.finalize() == b"" and cbc.finalize() == b"", "UFU", "Unexpected cipher tail")


def verify_plain_header(header, size):
    require(len(header) == 512 and header[:8] == b"UDTRFIRM", "HEADER", "Invalid UDTRFIRM header")
    require(struct.unpack_from("<I", header, 8)[0] == zlib.crc32(header[12:]), "HEADER", "Header CRC mismatch")
    require(all((v & 15) <= 9 and (v >> 4) <= 9 for v in header[0x20:0x22]), "HEADER", "Invalid BCD version")
    offset, length, number = struct.unpack_from("<III", header, 48)
    require(512 <= offset <= offset + length <= size and number <= 28, "HEADER", "Invalid firmware bounds")
    for index in range(number):
        _, off, count, _ = struct.unpack_from("<4sIII", header, 64 + 16 * index)
        require(off + count <= size, "HEADER", "Filesystem outside plaintext")
    return offset, length


def decode(source, *, output=None, compare=None):
    require(output is None or not Path(output).exists(), "EXISTS", "Plaintext output exists")
    target = Path(output).open("xb") if output else None
    reference = Path(compare).open("rb") if compare else None
    hasher, total, header, blocks = hashlib.sha256(), 0, bytearray(), 0
    try:
        for base, count, array, payload, _ in frame_batches(source):
            if reference:
                require(exact(reference, len(payload)) == payload, "COMPARE", "Decoded plaintext differs")
            if target:
                target.write(payload)
            if len(header) < 512:
                header.extend(payload[:512 - len(header)])
            hasher.update(payload)
            total += len(payload)
            blocks = count
        if reference:
            require(not reference.read(1), "COMPARE", "Reference has extra data")
        offset, length = verify_plain_header(header, total)
        return {"plaintext_sha256": hasher.hexdigest(), "plaintext_size": total, "blocks_verified": blocks,
                "firmware_offset": offset, "firmware_size": length, "compared_byte_for_byte": bool(compare),
                "camera_io": False, "rsa_verified": False}
    finally:
        if target:
            target.close()
        if reference:
            reference.close()


def encode(template, plain, output):
    """Preserve template framing/padding, recalculate sums, emit an unsigned intermediate."""
    import numpy as np
    require(not Path(output).exists(), "EXISTS", "Encoded output exists")
    start, signature, dend = ufu_layout(template)
    with Path(template).open("rb") as source, Path(plain).open("rb") as replacement, Path(output).open("xb") as target:
        prefix = exact(source, start)
        source.seek(signature - 16)
        iv, old_signature = exact(source, 16), exact(source, 256)
        ecb, cbc = contexts(iv, True)
        target.write(prefix)
        crc = zlib.crc32(prefix)
        for base, count, original, old_payload, _ in frame_batches(template):
            new_payload = exact(replacement, len(old_payload))
            array = original.copy()
            number = len(array)
            words = array.view("<u2").reshape(number, 512)
            full = number - 1 if base + number == count else number
            if full:
                array[:full, 4:] = np.frombuffer(new_payload[:full * 1020], dtype=np.uint8).reshape(full, 1020)
            if full != number:
                array[-1, 4:4 + len(new_payload) - full * 1020] = np.frombuffer(new_payload[full * 1020:], dtype=np.uint8)
            words[:, 0] = words[:, 1:].sum(axis=1, dtype=np.uint64) & 0xffff
            raw = array.tobytes()
            ct = ecb.update(raw[:512]) + cbc.update(raw[512:]) if base == 0 else cbc.update(raw)
            target.write(ct)
            crc = zlib.crc32(ct, crc)
        require(not replacement.read(1), "SIZE", "Replacement plaintext is too long")
        require(ecb.finalize() == b"" and cbc.finalize() == b"", "UFU", "Unexpected encryption tail")
        target.write(iv + old_signature)
        crc = zlib.crc32(iv + old_signature, crc)
        target.write(struct.pack(">I4sI", 4, b"DEND", crc))
    require(Path(output).stat().st_size == Path(template).stat().st_size, "SIZE", "Container size changed")
    return decode(output, compare=plain)


def tar_index(path):
    with Path(path).open("rb") as stream:
        offset, length = verify_plain_header(exact(stream, 512), Path(path).stat().st_size)
        stream.seek(offset)
        result = {}
        with tarfile.open(fileobj=stream, mode="r|") as archive:
            for member in archive:
                name = member.name.removeprefix("./")
                require(name not in result and not name.startswith("/") and ".." not in Path(name).parts, "TAR", "Invalid or duplicate member")
                if member.isfile():
                    require(member.offset_data + member.size <= length, "TAR", "Member outside firmware region")
                    result[name] = (offset + member.offset_data, member.size)
        return result


def ext_replace(image, path, replacement, expected_source):
    """Same-length in-place replacement through pinned Dissect 3.15 run mappings."""
    from dissect.extfs import ExtFS
    require(len(image) >= 2048, "EXTFS", "Truncated ext image")
    fs = ExtFS(io.BytesIO(image))
    stream = fs.get(path).open()
    original = stream.read()
    require(digest(original) == expected_source and len(original) == len(replacement), "BASELINE", "Unexpected ext file identity/size")
    output, logical, written = bytearray(image), 0, 0
    for disk, count in stream._runlist:
        require(disk is not None, "EXTFS", "Sparse/uninitialized extents need separate review")
        amount = min(count * stream.block_size, len(replacement) - logical)
        if amount <= 0:
            break
        offset = disk * stream.block_size
        require(0 <= offset <= len(image) - amount and image[offset:offset + amount] == original[logical:logical + amount], "EXTFS", "Unexpected extent mapping")
        output[offset:offset + amount] = replacement[logical:logical + amount]
        written += amount
        logical += amount
    require(written == len(replacement), "EXTFS", "Incomplete extent mapping")
    require(ExtFS(io.BytesIO(output)).get(path).open().read() == replacement, "EXTFS", "Reopened file differs")
    return bytes(output)


def update_sum(content, changes):
    lines, matched = content.decode("ascii").splitlines(keepends=True), set()
    for index, line in enumerate(lines):
        fields = line.split(",")
        if len(fields) <= 10 or fields[10] not in changes:
            continue
        name = fields[10]
        old, new = changes[name]
        require(name not in matched and len(fields[1]) == 8 and int(fields[1], 16) == zlib.crc32(old)
                and int(fields[2], 16) == len(old) == len(new), "MANIFEST", "Unexpected partition checksum row")
        fields[1] = f"{zlib.crc32(new):08x}"
        lines[index] = ",".join(fields)
        matched.add(name)
    result = "".join(lines).encode("ascii")
    require(matched == set(changes) and len(result) == len(content), "MANIFEST", "Missing or resized checksum entries")
    return result


def build(args):
    require(not args.output.exists(), "EXISTS", "Choose a new output directory")
    require(sha256(args.official) == OFFICIAL_SHA256, "BASELINE", "Only the exact official A7M4 6.02 DAT is supported")
    require(re.fullmatch(r"[0-9]\.[0-9]{2}", args.version), "VERSION", "Expected X.YY")
    from cryptography.hazmat.primitives import serialization
    private = serialization.load_pem_private_key(args.private_key.read_bytes(), None)
    public = serialization.load_pem_public_key(args.public_key.read_bytes())
    require(private.public_key().public_numbers() == public.public_numbers(), "KEY", "Package key differs from updater key")
    args.output.mkdir(parents=True)
    plain = args.output / "work/plain.bin"
    plain.parent.mkdir()
    initial = decode(args.official, output=plain)
    require(initial["plaintext_sha256"] == PLAIN_SHA256, "BASELINE", "Official plaintext identity mismatch")
    index = tar_index(plain)
    products = args.components
    ar = json.loads((RECIPES / "ap-recipe.json").read_text("utf-8"))
    cr = json.loads((RECIPES / "cp-v7-recipe.json").read_text("utf-8"))
    ap, cp = (products / "appFw.so").read_bytes(), (products / "CPAPP-B.BIN").read_bytes()
    require(digest(ap) == ar["target_sha256"] and digest(cp) == cr["target_sha256"], "COMPONENT", "Components differ from the reviewed FL2/FL3 recipe")
    ap, cp, feature_evidence = optional_features(ap, cp, battery=args.battery, lens_af=args.lens_af)
    changes, details = {}, {}
    with plain.open("r+b") as stream:
        def read(name):
            offset, size = index[name]
            stream.seek(offset)
            return exact(stream, size)
        def write(name, before, after):
            offset, size = index[name]
            require(len(before) == len(after) == size, "SIZE", "TAR member must retain its size")
            stream.seek(offset)
            stream.write(after)
            changes[name] = (before, after)
        name = "0700_part_image/dev/nflasha15"
        old = read(name)
        new = ext_replace(old, "lib/appFw.so", ap, ar["source_sha256"])
        # DAT member length need not equal the physical partition length.
        # Keep it inside the SD package, never advertise it as a raw flash image.
        write(name, old, new)
        old = read("0700_part_image/dev/nflasha8")
        fs = Fat(old)
        require(digest(fs.read("CPAPP-B.BIN")) == cr["source_sha256"], "BASELINE", "Wrong stock CP")
        fs.replace("CPAPP-B.BIN", cp)
        write("0700_part_image/dev/nflasha8", old, fs.bytes())
        old = read("0700_part_image/dev/nflasha5")
        require(old[:4] == b"WBI2", "BASELINE", "Unexpected warm-boot marker")
        write("0700_part_image/dev/nflasha5", old, b"WBI3" + old[4:])
        old = read("0400_updater/dev/nflasha1")
        new, details = Updater(Assets(args.resources)).unlock(old, args.public_key.read_bytes())
        write("0400_updater/dev/nflasha1", old, new)
        for manifest, prefix in [("0701_part_image_sum/part_image.sum", "0700_part_image/"), ("0401_updater_sum/updater.sum", "0400_updater/")]:
            old = read(manifest)
            subset = {key.removeprefix(prefix): value for key, value in changes.items() if key.startswith(prefix)}
            write(manifest, old, update_sum(old, subset))
        stream.seek(0)
        header = bytearray(exact(stream, 512))
        major, minor = map(int, args.version.split("."))
        header[0x20:0x22] = bytes([((minor // 10) << 4) | (minor % 10), major])
        struct.pack_into("<I", header, 8, zlib.crc32(header[12:]))
        stream.seek(0)
        stream.write(header)
    require(tar_index(plain) == index, "TAR", "TAR layout changed")
    # Compare every member to a fresh independent decoding of the official DAT.
    baseline = args.output / "work/original.bin"
    decode(args.official, output=baseline)
    with baseline.open("rb") as old, plain.open("rb") as new:
        for name, (offset, size) in index.items():
            old.seek(offset)
            new.seek(offset)
            different = False
            for start in range(0, size, 4 << 20):
                amount = min(4 << 20, size - start)
                different |= exact(old, amount) != exact(new, amount)
            require(different == (name in changes), "DIFF", "Unexpected changed/unchanged TAR member: " + name)
    unsigned = args.output / "work/UNSIGNED_DO_NOT_INSTALL.DAT"
    encoding = encode(args.official, plain, unsigned)
    final = args.output / "BODYDATA.DAT"
    signing = resign(unsigned, args.private_key, final)
    final_decoding = decode(final, compare=plain)
    # The key installed into the updater must match the signing private key.
    require(private.public_key().public_numbers() == public.public_numbers(), "KEY", "Package key differs from updater key; do not install")
    report = {"official_sha256": OFFICIAL_SHA256, "ap_sha256": digest(ap), "cp_sha256": digest(cp),
              "version": args.version, "changed_members": list(changes), "updater": details,
              "encoding": encoding, "signing": signing, "final_decoding": final_decoding,
              "camera_io": False, "camera_tested": False, "optional_features": feature_evidence,
              "fl23_color_matches_official": False,
              "personalization_embedded": False, "nor_updated": False,
              "prerequisites": ["Install/recheck this camera's nfa2/nfa6 color and slot changes separately", "Installed updater must already trust the signing public key", "Physical NOR synchronization occurs during matching official SD update scripts, not during this build", "Read back NOR/eMMC and check settings after installation"]}
    (args.output / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


def optional_features(ap, cp, *, battery=False, lens_af=False):
    """Explicit opt-in only; ordinary FL2/FL3 builds retain their original scope."""
    from .features import apply_feature
    evidence = {}
    if battery:
        ap, evidence["battery"] = apply_feature(ap, "battery")
    if lens_af:
        cp, evidence["lens-af"] = apply_feature(cp, "lens-af")
    return ap, cp, evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    dec = sub.add_parser("decode")
    dec.add_argument("source", type=Path)
    dec.add_argument("--output", type=Path)
    dec.add_argument("--compare", type=Path)
    extract = sub.add_parser("extract-target", help="Extract AP/CP components from exact official 6.02 plaintext")
    extract.add_argument("plain", type=Path)
    extract.add_argument("--output", type=Path, required=True)
    package = sub.add_parser("build-fl23")
    for name in ("official", "components", "public-key", "private-key", "output"):
        package.add_argument("--" + name, type=Path, required=True)
    package.add_argument("--resources", type=Path)
    package.add_argument("--version", default="6.05")
    package.add_argument("--battery", action="store_true", help="Opt into the independent battery display/caution patch")
    package.add_argument("--lens-af", action="store_true", help="UNTESTED: opt into the independent scoped lens capability filter patch; no physical speed testing")
    args = parser.parse_args()
    if args.command == "decode":
        print(json.dumps(decode(args.source, output=args.output, compare=args.compare), indent=2))
    elif args.command == "extract-target":
        from dissect.extfs import ExtFS
        require(not args.output.exists() and sha256(args.plain) == PLAIN_SHA256, "BASELINE", "Require exact official 6.02 plaintext and a new output directory")
        index = tar_index(args.plain)
        with args.plain.open("rb") as stream:
            off, size = index["0700_part_image/dev/nflasha15"]
            stream.seek(off)
            ap = ExtFS(io.BytesIO(exact(stream, size))).get("lib/appFw.so").open().read()
            off, size = index["0700_part_image/dev/nflasha8"]
            stream.seek(off)
            cp = Fat(exact(stream, size)).read("CPAPP-B.BIN")
        require(digest(ap) == json.loads((RECIPES / "ap-recipe.json").read_text("utf-8"))["source_sha256"]
                and digest(cp) == json.loads((RECIPES / "cp-v7-recipe.json").read_text("utf-8"))["source_sha256"], "BASELINE", "Extracted AP/CP mismatch")
        args.output.mkdir(parents=True)
        (args.output / "appFw.so").write_bytes(ap)
        (args.output / "CPAPP-B.BIN").write_bytes(cp)
        print(json.dumps({"camera_io": False, "ap_sha256": digest(ap), "cp_sha256": digest(cp)}, indent=2))
    else:
        if args.lens_af:
            print("UNTESTED: lens focus-speed, AF-tracking and burst-performance improvements have not undergone physical testing.", flush=True)
        build(args)


if __name__ == "__main__":
    main()
