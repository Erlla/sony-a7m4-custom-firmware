"""Offline builders only. No device, driver, reset or flash operations."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import zlib

from .common import Assets, digest, require, sha256
from .fat import Fat
from .patching import Updater, new_keypair, set_version, version


def save_new(path, data, evidence):
    path = Path(path)
    require(not path.exists() and not path.with_suffix(path.suffix + ".json").exists(),
            "EXISTS", "Choose a new output path")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
    report = path.with_suffix(path.suffix + ".json")
    report.write_text(json.dumps(evidence | {"output_sha256": digest(data),
                        "size": len(data), "camera_io": False}, indent=2) + "\n", encoding="utf-8")


def ufu_layout(path):
    """Bounded UFU chunk parser; this signer supports a final RSA-2048 FDAT."""
    total = Path(path).stat().st_size
    chunks = []
    with Path(path).open("rb") as stream:
        require(stream.read(8) == b"\x89UFU\r\n\x1a\n", "UFU", "Invalid UFU magic")
        pos = 8
        while pos < total:
            stream.seek(pos)
            header = stream.read(8)
            require(len(header) == 8, "UFU", "Truncated chunk header")
            size, tag = struct.unpack(">I4s", header)
            require(pos + 8 + size <= total, "UFU", "Chunk exceeds file")
            chunks.append((tag, pos + 8, size))
            pos += 8 + size
    require(len(chunks) >= 2 and chunks[-1][0] == b"DEND" and chunks[-1][2] == 4,
            "UFU", "Expected a final DEND CRC")
    fdat = [row for row in chunks if row[0] == b"FDAT"]
    require(len(fdat) == 1 and chunks[-2] == fdat[0] and fdat[0][2] >= 512 + 16 + 256,
            "UFU", "Expected exactly one FDAT immediately before DEND")
    require([r[0] for r in chunks].count(b"DEND") == 1, "UFU", "Duplicate DEND")
    return fdat[0][1], fdat[0][1] + fdat[0][2] - 256, total - 12


def range_hash(stream, start, end):
    stream.seek(start)
    result = hashlib.sha256()
    while start < end:
        data = stream.read(min(4 << 20, end - start))
        require(data, "UFU", "Truncated input")
        result.update(data)
        start += len(data)
    return result.digest()


def prefix_crc(stream, end):
    stream.seek(0)
    crc = 0
    for start in range(0, end, 4 << 20):
        data = stream.read(min(4 << 20, end - start))
        require(data, "UFU", "Truncated input")
        crc = zlib.crc32(data, crc)
    return crc & 0xffffffff


def resign(source, private_path, output):
    """Sign existing FDAT ciphertext + IV, then recompute outer DEND CRC.

    This does not rebuild/encrypt firmware or validate its internal checksums.
    A successful signature is not an assertion that a package is safe to flash.
    """
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding, utils
    source, output = Path(source), Path(output)
    require(not output.exists(), "EXISTS", "Output already exists")
    key = serialization.load_pem_private_key(Path(private_path).read_bytes(), password=None)
    require(isinstance(key, rsa.RSAPrivateKey) and key.key_size == 2048
            and key.public_key().public_numbers().e == 65537, "KEY", "Expected RSA-2048, e=65537")
    start, signature, dend = ufu_layout(source)
    with source.open("rb") as stream:
        old_crc = prefix_crc(stream, dend)
        stream.seek(dend + 8)
        require(struct.unpack(">I", stream.read(4))[0] == old_crc, "UFU", "Input DEND CRC mismatch")
        signed_hash = range_hash(stream, start, signature)
    sig = key.sign(signed_hash, padding.PKCS1v15(), utils.Prehashed(hashes.SHA256()))
    output.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as src, output.open("xb+") as dst:
        shutil.copyfileobj(src, dst, 4 << 20)
        dst.seek(signature)
        dst.write(sig)
        dst.flush()
        crc = prefix_crc(dst, dend)
        dst.seek(dend + 8)
        dst.write(struct.pack(">I", crc))
        dst.flush()
        check = range_hash(dst, start, signature)
        dst.seek(signature)
        key.public_key().verify(dst.read(256), check, padding.PKCS1v15(), utils.Prehashed(hashes.SHA256()))
        require(check == signed_hash, "SIGNATURE", "Signed bytes changed")
    return {"source_sha256": sha256(source), "output_sha256": sha256(output),
            "signed_range": [start, signature], "signature_verified": True,
            "dend_crc32": f"{crc:08x}", "internal_firmware_validated": False, "camera_io": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("keygen")
    gen.add_argument("directory", type=Path)
    ver = sub.add_parser("version")
    ver.add_argument("image", type=Path)
    ver.add_argument("--set", dest="value")
    ver.add_argument("--output", type=Path)
    unlock = sub.add_parser("unlock")
    unlock.add_argument("image", type=Path)
    unlock.add_argument("--public-key", type=Path, required=True)
    unlock.add_argument("--output", type=Path, required=True)
    unlock.add_argument("--resources", type=Path)
    fat = sub.add_parser("fat-replace")
    fat.add_argument("image", type=Path)
    fat.add_argument("--path", required=True)
    fat.add_argument("--file", type=Path, required=True)
    fat.add_argument("--output", type=Path, required=True)
    sign = sub.add_parser("resign")
    sign.add_argument("source", type=Path)
    sign.add_argument("--private-key", type=Path, required=True)
    sign.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "keygen":
        result = new_keypair(args.directory)
    elif args.command == "resign":
        result = resign(args.source, args.private_key, args.output)
    else:
        source = args.image.read_bytes()
        evidence = {"source_sha256": digest(source), "camera_io": False}
        if args.command == "version":
            result = evidence | {"version": version(source)}
            if args.value is not None:
                require(args.output, "OUTPUT", "--set requires --output")
                image, detail = set_version(source, args.value)
                save_new(args.output, image, evidence | detail)
                result |= detail
        elif args.command == "unlock":
            image, detail = Updater(Assets(args.resources)).unlock(source, args.public_key.read_bytes())
            save_new(args.output, image, evidence | detail)
            result = evidence | detail
        else:
            fs = Fat(source)
            before = fs.read(args.path)
            fs.replace(args.path, args.file.read_bytes())
            result = evidence | {"file": args.path, "old_file_sha256": digest(before),
                                 "new_file_sha256": digest(fs.read(args.path))}
            save_new(args.output, fs.bytes(), result)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
