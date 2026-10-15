"""Independent synthetic wire/filesystem fixtures; no camera or proprietary bytes."""
import hashlib
from pathlib import Path
import struct
import zlib

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from a7m4.common import ToolError
from a7m4.demo import settings_image
from a7m4.fat import Fat
from a7m4.fl23 import SLOTS, bk4_rows, color_records, delta_coefficients, patch_backup, patch_program
from a7m4.offline import resign, ufu_layout
from a7m4.patching import set_version, version

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("text,raw", [("0.00", "0000"), ("6.09", "0906"), ("6.10", "1006"),
                                     ("6.15", "1506"), ("6.20", "2006"), ("9.99", "9909")])
def test_bcd_known_camera_vectors(text, raw):
    source = settings_image()
    output, _ = set_version(source, text)
    assert Fat(output).read("updater/dat4") == bytes.fromhex(raw)
    assert Fat(output).read("Backup.bin") == Fat(source).read("Backup.bin")
    assert version(output) == text


@pytest.mark.parametrize("raw", [b"\x1a\x06", b"\xa0\x06", b"\x15\xfa", b"\x15"])
def test_unknown_existing_bcd_refuses_write(raw):
    fs = Fat(settings_image())
    fs.replace("updater/dat4", raw)
    with pytest.raises(ToolError):
        set_version(fs.bytes(), "6.20")


def sample_color(flag):
    cc, matrix = bytearray([0x31] * 0x2000), bytes([0x5b] * 0x7000)
    cc[0xefe] = flag
    for bank in (22, 23, 24, 25):
        values = list(range(8)) + list(range(20, 28)) + list(range(-10, -2))
        struct.pack_into("<24h", cc, 0x1250 + bank * 64, *values)
    return bytes(cc), matrix


def test_color_conversion_retains_other_calibration():
    source, matrix = sample_color(0)
    donor, dm = sample_color(1)
    cc, mat = color_records(source, matrix, donor, dm)
    allowed = set(range(0x1236, 0x123a))
    for bank in (22, 23, 24, 25):
        off = 0x1250 + bank * 64
        allowed.update(range(off, off + 48))
        assert struct.unpack_from("<24h", cc, off) == tuple(list(range(8)) + [20] * 8 + [-10] * 8)
    assert cc[0xefe] == 0
    assert all(a == b or i in allowed for i, (a, b) in enumerate(zip(source, cc)))
    assert mat[:0x1cc] == matrix[:0x1cc] and mat[0x1d0:] == matrix[0x1d0:]
    with pytest.raises(ToolError):
        color_records(donor, matrix, donor, dm)


def test_coefficient_delta_overflow_rejected():
    raw = struct.pack("<24h", *([-32768] * 8 + [32767] * 16))
    with pytest.raises(ToolError, match="int16"):
        delta_coefficients(raw, 0)


def synthetic_bk4():
    """Independent serializer for groups/index records, including long records."""
    cc, matrix = sample_color(0)
    values = {0x02a40001: cc, 0x02a4000d: matrix, **{k: b"\0" for k in SLOTS}}
    groups = 0x2d0
    counts = [0] * groups
    for key in values:
        counts[key >> 16] = max(counts[key >> 16], (key & 65535) + 1)
    count = sum(counts)
    body = 0x100 + 6 * groups + 6 * count
    output = bytearray(body)
    output[4:8] = b"\xaa" * 4
    output[12:16] = b"BK4\0"
    struct.pack_into("<III", output, 0x10, groups, count, body)
    first = 0
    for group, amount in enumerate(counts):
        struct.pack_into("<HI", output, 0x100 + 6 * group, amount, first)
        for slot in range(amount):
            entry = 0x100 + 6 * groups + (first + slot) * 6
            value = values.get((group << 16) | slot)
            if value is None:
                struct.pack_into("<HI", output, entry, 0, 0xffffffff)
                continue
            offset = len(output)
            if len(value) >= 255:
                output.extend(struct.pack("<H", len(value)))
                packed = offset | 0xff000000
            else:
                packed = offset | (len(value) << 24)
            output.extend(value)
            struct.pack_into("<HI", output, entry, 0x60, packed)
        first += amount
    struct.pack_into("<I", output, 0x1c, len(output) - body)
    struct.pack_into("<I", output, 0x20, sum(output[:0x20]) + sum(output[0x24:]))
    second = bytearray(0x100)
    second[4:8] = b"\xaa" * 4
    second[12:16] = b"BK4\0"
    struct.pack_into("<III", second, 0x18, 0x100, 0, 0)
    struct.pack_into("<I", second, 0x20, sum(second))
    return bytes(output + second)


def test_bk4_fixture_slots_checksums_and_other_segment():
    source = synthetic_bk4()
    donor, matrix = sample_color(1)
    output = patch_backup(source, donor, matrix)
    rows = bk4_rows(output)
    for key, expected in SLOTS.items():
        record = rows[0]["records"][key]
        assert output[record["offset"]:record["offset"] + record["size"]] == bytes([expected])
    assert output[-0x100:] == source[-0x100:]
    assert len(output) == len(source)
    for row in rows:
        base = row["base"]
        assert struct.unpack_from("<I", output, base + 32)[0] == sum(output[base:base + 32]) + sum(output[base + 36:base + row["extent"]])


def test_bk4_corrupt_source_refused():
    raw = bytearray(synthetic_bk4())
    raw[-1] ^= 1
    with pytest.raises(ToolError, match="checksum"):
        bk4_rows(raw)


def test_recipe_requires_whole_file_and_final_identity():
    before = b"abcdef"
    recipe = {"size": 6, "source_sha256": hashlib.sha256(before).hexdigest(),
              "target_sha256": hashlib.sha256(b"abXYef").hexdigest(),
              "patches": [{"offset": 2, "old_sha256": hashlib.sha256(b"cd").hexdigest(), "new_hex": "5859"}]}
    assert patch_program(before, recipe) == b"abXYef"
    with pytest.raises(ToolError):
        patch_program(b"abcdeg", recipe)
    recipe["target_sha256"] = "0" * 64
    with pytest.raises(ToolError, match="Final"):
        patch_program(before, recipe)


def synthetic_ufu(*, bad_block_sum=False):
    # Construct independently with struct, not the NumPy implementation under test.
    from a7m4.firmware import KEY_HEADER, KEY_K8
    header = bytearray(512)
    header[:8] = b"UDTRFIRM"
    header[32:34] = bytes([0x15, 6])
    payload = bytes(header) + b"test-payload-" * 63
    struct.pack_into("<III", header, 48, 512, len(payload) - 512, 0)
    struct.pack_into("<I", header, 8, zlib.crc32(header[12:]))
    payload = bytes(header) + payload[512:]
    frames = bytearray()
    for start in range(0, len(payload), 1020):
        chunk = payload[start:start + 1020]
        flags = len(chunk) | (0x8000 if start + 1020 >= len(payload) else 0)
        body = struct.pack("<H", flags) + chunk + b"\xff" * (1020 - len(chunk))
        checksum = sum(struct.unpack("<511H", body)) & 65535
        frames.extend(struct.pack("<H", checksum ^ int(bad_block_sum)) + body)
    iv = bytes(range(16))
    ecb = Cipher(algorithms.AES(KEY_HEADER), modes.ECB()).encryptor()
    cbc = Cipher(algorithms.AES(KEY_K8), modes.CBC(iv)).encryptor()
    ciphertext = ecb.update(frames[:512]) + cbc.update(frames[512:])
    fdat = ciphertext + iv + bytes(256)
    prefix = b"\x89UFU\r\n\x1a\n" + struct.pack(">I4sI", 4, b"DATV", 1) + struct.pack(">I4s", len(fdat), b"FDAT")
    raw = prefix + fdat
    return raw + struct.pack(">I4sI", 4, b"DEND", zlib.crc32(raw)), payload


def test_ufu_full_noop_reencode_and_modified_roundtrip(tmp_path):
    pytest.importorskip("numpy")
    from a7m4.firmware import decode, encode
    raw, payload = synthetic_ufu()
    source, plain, rebuilt = [tmp_path / s for s in ("source.DAT", "plain.bin", "rebuilt.DAT")]
    source.write_bytes(raw)
    report = decode(source, output=plain)
    assert report["blocks_verified"] == 2 and plain.read_bytes() == payload
    encode(source, plain, rebuilt)
    assert rebuilt.read_bytes() == raw
    changed = bytearray(payload)
    changed[600] ^= 0x41
    plain.write_bytes(changed)
    modified = tmp_path / "modified.DAT"
    encode(source, plain, modified)
    assert decode(modified, compare=plain)["compared_byte_for_byte"]


def test_inner_checksum_rejected_even_when_outer_crc_valid(tmp_path):
    pytest.importorskip("numpy")
    from a7m4.firmware import decode
    raw, _ = synthetic_ufu(bad_block_sum=True)
    path = tmp_path / "corrupt.DAT"
    path.write_bytes(raw)
    with pytest.raises(ToolError, match="Block checksum"):
        decode(path)


def test_re_sign_changes_only_signature_and_dend(tmp_path):
    source, target = tmp_path / "source.DAT", tmp_path / "signed.DAT"
    raw, _ = synthetic_ufu()
    source.write_bytes(raw)
    result = resign(source, ROOT / "keys/published/A7M4_updater_private.pem", target)
    start, sig, dend = ufu_layout(target)
    final = target.read_bytes()
    assert result["signature_verified"] and result["internal_firmware_validated"] is False
    assert final[:sig] == raw[:sig] and final[dend:dend + 8] == raw[dend:dend + 8]
    assert start != 124  # The signer parses the layout instead of hardcoding 124.
    with pytest.raises(ToolError, match="already exists"):
        resign(source, ROOT / "keys/published/A7M4_updater_private.pem", target)


@pytest.mark.parametrize("firmware", [b"uart_boot 1", b"uart_boot 2", b"unknown"])
def test_boot_bridge_protocol_versions_without_uart_console(tmp_path, monkeypatch, firmware):
    from a7m4 import hardware
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"synthetic-boot-payload")
    class Assets:
        def get(self, name):
            assert name == "bin/fastboot.bin"
            return payload
    class Link:
        calls, closed = [], False
        def __init__(self, *args):
            pass
        def command(self, command, payload=b""):
            self.calls.append(command)
            return firmware if command == 1 else b""
        def packet(self, deadline):
            return 0x83, b"[mira] fastboot ready"
        def close(self):
            Link.closed = True
    monkeypatch.setattr(hardware, "bootsel_drives", lambda: [])
    monkeypatch.setattr(hardware, "rp_ports", lambda: ["synthetic-port"])
    monkeypatch.setattr(hardware, "RpLink", Link)
    monkeypatch.setattr(hardware.time, "sleep", lambda _: None)
    if firmware == b"unknown":
        with pytest.raises(ToolError, match="Unexpected RP2040"):
            hardware.prepare_rp(Assets(), None)
        assert Link.calls == [1]
    else:
        hardware.prepare_rp(Assets(), None)
        assert set(Link.calls) == {1, 2, 3, 4, 5} and 6 not in Link.calls
    assert Link.closed
