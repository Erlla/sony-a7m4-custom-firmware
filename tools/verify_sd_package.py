"""Independent struct-based UFU decode/compare, RSA and embedded-image audit.

Does not import the builder's codec and never operates a camera.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import tarfile
import zlib

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, utils
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def need(condition, message):
    if not condition:
        raise ValueError(message)


def exact(stream, count):
    data = stream.read(count)
    need(len(data) == count, "Truncated file")
    return data


def crc_region(stream, start, count):
    stream.seek(start)
    crc = 0
    while count:
        data = exact(stream, min(count, 4 << 20))
        count -= len(data)
        crc = zlib.crc32(data, crc)
    return crc


def verify(dat, plain, public_pem, warm_boot_marker=b"WBI3"):
    need(warm_boot_marker in (b"WBI3", b"WBI4"), "Unsupported expected warm-boot marker")
    public = serialization.load_pem_public_key(public_pem)
    need(public.key_size == 2048, "RSA-2048 required")
    with Path(dat).open("rb") as source, Path(plain).open("rb") as reference:
        total = Path(dat).stat().st_size
        need(exact(source, 8) == b"\x89UFU\r\n\x1a\n", "UFU magic")
        chunks = []
        while source.tell() < total:
            count, tag = struct.unpack(">I4s", exact(source, 8))
            offset = source.tell()
            need(offset + count <= total, "UFU chunk outside file")
            chunks.append((tag, offset, count))
            source.seek(count, 1)
        need(len([r for r in chunks if r[0] == b"FDAT"]) == 1
             and len([r for r in chunks if r[0] == b"DEND"]) == 1, "Ambiguous FDAT/DEND")
        need(chunks[-1][0] == b"DEND" and chunks[-1][2] == 4 and chunks[-2][0] == b"FDAT", "Final chunk layout")
        dend = chunks[-1][1] - 8
        crc = crc_region(source, 0, dend)
        source.seek(dend + 8)
        need(struct.unpack(">I", exact(source, 4))[0] == crc, "DEND CRC")
        _, start, size = chunks[-2]
        encrypted_size = size - 272
        need(encrypted_size > 0 and encrypted_size % 1024 == 0, "FDAT alignment")
        source.seek(start)
        signed_hash = hashlib.sha256()
        left = size - 256
        while left:
            data = exact(source, min(left, 4 << 20))
            left -= len(data)
            signed_hash.update(data)
        public.verify(exact(source, 256), signed_hash.digest(), padding.PKCS1v15(), utils.Prehashed(hashes.SHA256()))
        source.seek(start + encrypted_size)
        iv = exact(source, 16)
        ecb = Cipher(algorithms.AES(bytes.fromhex("e3b0c44298fc1c149afbf4c8996fb924")), modes.ECB()).decryptor()
        cbc = Cipher(algorithms.AES(bytes.fromhex("434589432d319010f1132727353286ce4d7ede8b9c4f7217a0e0226e0f0edc69")), modes.CBC(iv)).decryptor()
        source.seek(start)
        block_count, index, plain_hash, plain_size = encrypted_size // 1024, 0, hashlib.sha256(), 0
        while index < block_count:
            number = min(4096, block_count - index)
            ct = exact(source, number * 1024)
            raw = ecb.update(ct[:512]) + cbc.update(ct[512:]) if index == 0 else cbc.update(ct)
            for local in range(number):
                block = raw[local * 1024:(local + 1) * 1024]
                checksum, flags = struct.unpack_from("<HH", block)
                length = flags & 0x7fff
                final = index + local == block_count - 1
                need(0 < length <= 1020 and bool(flags & 0x8000) == final and (final or length == 1020), "Frame layout")
                need(sum(struct.unpack_from("<511H", block, 2)) & 65535 == checksum, "Frame checksum")
                payload = block[4:4 + length]
                need(exact(reference, length) == payload, "Plaintext comparison")
                plain_hash.update(payload)
                plain_size += length
            index += number
        need(not reference.read(1), "Extra reference plaintext")
        need(ecb.finalize() == b"" and cbc.finalize() == b"", "Cipher tail")
        reference.seek(0)
        header = exact(reference, 512)
        need(header[:8] == b"UDTRFIRM" and struct.unpack_from("<I", header, 8)[0] == zlib.crc32(header[12:]), "Firmware header/CRC")
        offset, size = struct.unpack_from("<II", header, 48)
        need(512 <= offset <= offset + size <= plain_size, "Firmware bounds")
        reference.seek(offset)
        members = {}
        with tarfile.open(fileobj=reference, mode="r|") as archive:
            for item in archive:
                name = item.name.removeprefix("./")
                need(name not in members, "Duplicate TAR member")
                if item.isfile():
                    need(item.offset_data + item.size <= size, "TAR bounds")
                    members[name] = (offset + item.offset_data, item.size)
        checked, backup_checked = [], []
        for manifest, prefix in (("0701_part_image_sum/part_image.sum", "0700_part_image/"),
                                 ("0401_updater_sum/updater.sum", "0400_updater/"),
                                 ("0111_backup_sum/backup.sum", "0110_backup/")):
            position, size = members[manifest]
            reference.seek(position)
            lines = exact(reference, size).decode("ascii").splitlines()
            for line in lines:
                fields = line.split(",")
                if fields[0] != "0":
                    continue
                name = prefix + fields[10]
                position, size = members[name]
                need(size == int(fields[2], 16) and crc_region(reference, position, size) == int(fields[1], 16), "Image CRC: " + name)
                destination = backup_checked if prefix == "0110_backup/" else checked
                need(name not in destination, "Duplicate checksum row: " + name)
                destination.append(name)
        templates = {name for name in members if name.startswith("0110_backup/") and name.endswith(".bin")}
        need(len(templates) == 32 and set(backup_checked) == templates, "Incomplete backup template CRC manifest")
        position, _ = members["0700_part_image/dev/nflasha5"]
        reference.seek(position)
        need(exact(reference, 4) == warm_boot_marker, "Warm-boot marker")
    return {"blocks_verified": block_count, "plaintext_sha256": plain_hash.hexdigest(),
            "plaintext_size": plain_size, "compared_byte_for_byte": True, "rsa_signature_verified": True,
            "dend_crc_verified": True, "header_crc_verified": True, "images_crc_verified": checked,
            "backup_templates_crc_verified": backup_checked,
            "warm_boot_marker": warm_boot_marker.decode("ascii"), "camera_io": False, "hardware_acceptance": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dat", type=Path)
    parser.add_argument("--plain", type=Path, required=True)
    parser.add_argument("--public-key", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--warm-boot-marker", choices=("WBI3", "WBI4"), default="WBI3",
                        help="Explicit expected cold-boot marker; default remains WBI3 for the documented SD package recipe")
    args = parser.parse_args()
    result = verify(args.dat, args.plain, args.public_key.read_bytes(), args.warm_boot_marker.encode("ascii"))
    if args.report:
        args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
