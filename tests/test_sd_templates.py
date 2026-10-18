"""Synthetic regression: SD defaults must retain colour and preserve LOOK/reset."""
import json
import struct
import zlib

import pytest

from a7m4.common import ToolError, digest
from a7m4 import sd_templates as sd
from a7m4.fl23 import SLOTS, bk4_rows
from a7m4.firmware import update_sum
from test_offline_methods import synthetic_bk4


def checksum(data, row):
    base, end = row["base"], row["base"] + row["extent"]
    struct.pack_into("<I", data, base + 32, (sum(data[base:base + 32]) + sum(data[base + 36:end])) & 0xffffffff)


@pytest.fixture
def colours(tmp_path, monkeypatch):
    cc, matrix = bytearray(8192), bytearray(28672)
    cc[0xefe] = 1
    for bank in sd.BANKS:
        struct.pack_into("<24h", cc, 0x1250 + bank * 64,
                         *([bank] * 8 + [bank + 3] * 8 + [bank - 2] * 8))
        base = 0x1e0 + bank * 0x300
        for endpoint in range(4):
            matrix[base + endpoint * 192:base + (endpoint + 1) * 192] = bytes([bank + endpoint]) * 192
    # Only synthetic identities are substituted; production has pinned FX2 hashes.
    (tmp_path / "cp-v7-recipe.json").write_text(json.dumps({"donors": {
        "fx2_cc1": digest(cc), "fx2_block13": digest(matrix)}}))
    monkeypatch.setattr(sd, "RECIPES", tmp_path)
    return bytes(cc), bytes(matrix)


@pytest.fixture
def template():
    data = bytearray(synthetic_bk4())
    rows = bk4_rows(data)
    for key, size in ((sd.CC1, 8192), (sd.MATRIX, 28672)):
        record = rows[0]["records"][key]
        data[record["offset"]:record["offset"] + size] = bytes(size)
        # Colour attributes 8, LOOK attributes 0x60. Independent index edit.
        groups, items = struct.unpack_from("<II", data, 0x10)
        first = struct.unpack_from("<I", data, 0x100 + 6 * (key >> 16) + 2)[0]
        struct.pack_into("<H", data, 0x100 + groups * 6 + (first + (key & 65535)) * 6, 8)
    for key in SLOTS:
        data[rows[0]["records"][key]["offset"]] = 7
    # Unrelated calibration and trailing reset-like bytes must survive exactly.
    data[0x40:0x50] = bytes(range(16))
    checksum(data, rows[0])
    return bytes(data)


@pytest.mark.parametrize("mode", ["fixed-a1", "dynamic"])
def test_colour_only_merge_preserves_every_other_byte(template, colours, mode):
    fields = sd.colour_fields(*colours, mode)
    output = sd.patch_template(template, fields)
    rows = bk4_rows(template)
    allowed = set(range(32, 36))
    for field in fields:
        at = rows[0]["records"][field.key]["offset"] + field.offset
        allowed.update(range(at, at + len(field.target)))
        assert output[at:at + len(field.target)] == field.target
    assert all(a == b or i in allowed for i, (a, b) in enumerate(zip(template, output)))
    assert output[-256:] == template[-256:]
    assert all(output[rows[0]["records"][key]["offset"]] == 7 for key in SLOTS)
    assert sd.patch_template(output, fields) == output
    cc = rows[0]["records"][sd.CC1]["offset"]
    mat = rows[0]["records"][sd.MATRIX]["offset"]
    assert output[cc + 0x1236:cc + 0x123a] == bytes([22, 24, 23, 25])
    for bank in sd.BANKS:
        assert struct.unpack_from("<24h", output, cc + 0x1250 + bank * 64) == tuple([bank] * 8 + [3] * 8 + [-2] * 8)
        at = mat + 0x1e0 + bank * 0x300
        expected = bytes([bank + 1]) * 576 if mode == "fixed-a1" else b"".join(bytes([bank + i]) * 192 for i in range(3))
        assert output[at:at + 576] == expected
        assert output[at + 576:at + 768] == bytes(192)


def test_known_dynamic_preimage_can_be_fixed(template, colours):
    dynamic = sd.patch_template(template, sd.colour_fields(*colours, "dynamic"))
    assert sd.patch_template(dynamic, sd.colour_fields(*colours)) == sd.patch_template(template, sd.colour_fields(*colours))


@pytest.mark.parametrize("index", range(10))
def test_unknown_field_refuses_whole_merge(template, colours, index):
    fields = sd.colour_fields(*colours)
    field = fields[index]
    rows = bk4_rows(template)
    bad = bytearray(template)
    bad[rows[0]["records"][field.key]["offset"] + field.offset] = 0xfe
    checksum(bad, rows[0])
    with pytest.raises(ToolError, match="Unknown colour preimage"):
        sd.patch_template(bytes(bad), fields)


def test_corrupt_bk4_and_wrong_donor_refused(template, colours):
    bad = bytearray(template)
    bad[-1] ^= 1
    with pytest.raises(ToolError, match="checksum"):
        sd.patch_template(bad, sd.colour_fields(*colours))
    with pytest.raises(ToolError, match="FX2"):
        sd.colour_fields(bytes(8192), colours[1])


@pytest.mark.parametrize("invalid", ["partial", "extra", "crc", "duplicate", "size"])
def test_template_set_and_manifest_fail_closed(template, colours, invalid):
    names = [sd.PREFIX + f"SYSIPSX-DSLR/{group}/REGION{i:02}.bin"
             for group in ("LS", "LS_GLEE") for i in range(16)]
    index = {name: (0, len(template)) for name in names}
    if invalid == "partial":
        index.pop(names[0])
    if invalid == "extra":
        index[sd.PREFIX + "other.bin"] = (0, len(template))
    if invalid in ("partial", "extra"):
        with pytest.raises(ToolError, match="32 official"):
            sd.template_changes(index, lambda _: template, *colours)
        return
    changes, evidence = sd.template_changes(index, lambda _: template, *colours)
    assert evidence["count"] == len(changes) == 32
    lines = [f"0,{zlib.crc32(old):08x},{len(old):08x},,,,,,,,{name.removeprefix(sd.PREFIX)},0\r\n"
             for name, (old, new) in changes.items()]
    subset = {name.removeprefix(sd.PREFIX): pair for name, pair in changes.items()}
    valid = "".join(lines).encode("ascii")
    result = update_sum(valid, subset)
    assert len(result) == len(valid)
    for line, (old, new) in zip(result.decode().splitlines(), changes.values()):
        assert int(line.split(",")[1], 16) == zlib.crc32(new)
    if invalid == "crc":
        lines[0] = lines[0].replace(lines[0].split(",")[1], "ffffffff", 1)
    elif invalid == "duplicate":
        lines.append(lines[0])
    elif invalid == "size":
        fields = lines[0].split(",")
        fields[2] = "00000001"
        lines[0] = ",".join(fields)
    with pytest.raises(ToolError, match="checksum row"):
        update_sum("".join(lines).encode("ascii"), subset)
