"""Synthetic plaintext-container gate checks; no firmware or camera bytes."""
import io
import struct
import tarfile
import zlib

import pytest
from a7m4.common import ToolError
from a7m4.firmware import tar_index, update_sum, verify_plain_header


def plain_header(offset, length, number, members=(), bcd=b"\x02\x06"):
    header = bytearray(512)
    header[:8] = b"UDTRFIRM"
    header[0x20:0x22] = bcd
    struct.pack_into("<III", header, 48, offset, length, number)
    for index, (tag, off, count) in enumerate(members):
        struct.pack_into("<4sIII", header, 64 + 16 * index, tag, off, count, 0)
    struct.pack_into("<I", header, 8, zlib.crc32(header[12:]))
    return bytes(header)


def checksum_manifest(rows):
    return "".join(f"0,{crc:08x},{size:08x},x,y,z,a,b,c,d,{name},pad\n"
                   for name, crc, size in rows).encode("ascii")


def tar_image(path, offset, members):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, data in members:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    payload = buffer.getvalue()
    image = bytearray(offset + len(payload) + 64)
    image[:512] = plain_header(offset, len(payload), 0)
    image[offset:offset + len(payload)] = payload
    path.write_bytes(image)
    return bytes(image)


def rejects(tool_error, function, *args):
    with pytest.raises(ToolError) as raised:
        function(*args)
    assert raised.value.code == tool_error


def test_header_accepts_the_documented_minimum_bounds():
    assert verify_plain_header(plain_header(512, 512, 0), 1024) == (512, 512)


def test_header_rejects_a_broken_crc_or_magic():
    corrupt = bytearray(plain_header(512, 512, 0))
    corrupt[8] ^= 0xFF
    rejects("HEADER", verify_plain_header, bytes(corrupt), 1024)
    corrupt = bytearray(plain_header(512, 512, 0))
    corrupt[3] ^= 0xFF
    rejects("HEADER", verify_plain_header, bytes(corrupt), 1024)


@pytest.mark.parametrize("bcd", [b"\xa6\x06", b"\x6a\x06", b"\xaa\x0a", b"\x0a\x9a"])
def test_header_rejects_non_bcd_versions(bcd):
    rejects("HEADER", verify_plain_header, plain_header(512, 512, 0, bcd=bcd), 1024)


@pytest.mark.parametrize("offset,length", [(0, 512), (1024, 512), (512, 1024)])
def test_header_rejects_a_region_outside_the_plaintext(offset, length):
    rejects("HEADER", verify_plain_header, plain_header(offset, length, 0), 1024)


def test_header_rejects_29_members_and_accepts_28():
    members = [(b"PART", 600 + 8 * i, 8) for i in range(28)]
    assert verify_plain_header(plain_header(512, 3000, 28, members), 4096) == (512, 3000)
    rejects("HEADER", verify_plain_header, plain_header(512, 3000, 29, members), 4096)


def test_header_rejects_a_member_outside_the_plaintext():
    rejects("HEADER", verify_plain_header, plain_header(512, 1024, 1, [(b"PART", 5000, 100)]), 4096)


def test_update_sum_rewrites_only_the_matched_rows():
    old, new, other = b"A" * 128, b"B" * 128, b"C" * 64
    content = checksum_manifest([("SYS1.bin", zlib.crc32(old), len(old)),
                                 ("SYS2.bin", zlib.crc32(other), len(other))])
    updated = update_sum(content, {"SYS1.bin": (old, new)})
    lines = updated.decode("ascii").splitlines()
    assert lines[0].split(",")[1] == f"{zlib.crc32(new):08x}"
    assert lines[1] == content.decode("ascii").splitlines()[1]
    assert len(updated) == len(content)


def test_update_sum_rejects_an_unexpected_checksum_row():
    old, new = b"A" * 128, b"B" * 128
    content = checksum_manifest([("SYS1.bin", 0x12345678, len(old))])
    rejects("MANIFEST", update_sum, content, {"SYS1.bin": (old, new)})


def test_update_sum_rejects_a_resized_partition():
    old, new = b"A" * 128, b"B" * 64
    content = checksum_manifest([("SYS1.bin", zlib.crc32(old), len(old))])
    rejects("MANIFEST", update_sum, content, {"SYS1.bin": (old, new)})


def test_update_sum_rejects_missing_and_duplicate_rows():
    old, new, other = b"A" * 128, b"B" * 128, b"C" * 64
    row = ("SYS1.bin", zlib.crc32(old), len(old))
    rejects("MANIFEST", update_sum, checksum_manifest([row]),
            {"SYS1.bin": (old, new), "SYS2.bin": (other, other)})
    rejects("MANIFEST", update_sum, checksum_manifest([row]) + checksum_manifest([row]),
            {"SYS1.bin": (old, new)})


def test_tar_index_maps_members_inside_the_firmware_region(tmp_path):
    plain = tmp_path / "plain.bin"
    tar_image(plain, 512, [("./fs/file1.bin", b"0123456789abcdef")])
    assert tar_index(plain) == {"fs/file1.bin": (1024, 16)}


def test_tar_index_rejects_a_broken_header_crc(tmp_path):
    image = bytearray(tar_image(tmp_path / "plain.bin", 512, [("./fs/file1.bin", b"data")]))
    image[8] ^= 0xFF
    broken = tmp_path / "broken.bin"
    broken.write_bytes(bytes(image))
    rejects("HEADER", tar_index, broken)


def test_tar_index_rejects_a_member_outside_the_firmware_region(tmp_path):
    plain = tmp_path / "plain.bin"
    image = bytearray(tar_image(plain, 512, [("./fs/file1.bin", b"data")]))
    struct.pack_into("<I", image, 52, 64)
    struct.pack_into("<I", image, 8, zlib.crc32(image[12:512]))
    shrunk = tmp_path / "shrunk.bin"
    shrunk.write_bytes(bytes(image))
    rejects("TAR", tar_index, shrunk)


@pytest.mark.parametrize("name", ["../escape.bin", "fs/../escape.bin"])
def test_tar_index_rejects_unsafe_or_duplicate_members(tmp_path, name):
    unsafe = tmp_path / "unsafe.bin"
    tar_image(unsafe, 512, [(name, b"data")])
    rejects("TAR", tar_index, unsafe)
    duplicate = tmp_path / "duplicate.bin"
    tar_image(duplicate, 512, [("./fs/file1.bin", b"data"), ("fs/file1.bin", b"data2")])
    rejects("TAR", tar_index, duplicate)
