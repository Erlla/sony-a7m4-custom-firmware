"""FL2/FL3 colour-only merge into generic SD-update BK4 defaults.

No camera I/O or personalized partitions. Keep LOOK/reset/calibration bytes.
The caller must first verify the complete official plaintext identity.
"""
from dataclasses import dataclass
import json

from .common import digest, require
from .fl23 import RECIPES, bk4_rows, delta_coefficients

CC1, MATRIX = 0x02a40001, 0x02a4000d
BANKS = (22, 23, 24, 25)
PREFIX = "0110_backup/"


@dataclass(frozen=True)
class ColourField:
    key: int
    offset: int
    target: bytes
    legacy: bytes = b""


def colour_fields(donor_cc1, donor_matrix, matrix_mode="fixed-a1"):
    identities = json.loads((RECIPES / "cp-v7-recipe.json").read_text("utf-8"))["donors"]
    require(len(donor_cc1) == 8192 and len(donor_matrix) == 28672
            and digest(donor_cc1) == identities["fx2_cc1"]
            and digest(donor_matrix) == identities["fx2_block13"],
            "DONOR", "Exact FX2 1.01 CC1 and block13 are required")
    require(donor_cc1[0xefe] == 1, "COLOR", "Expected FX2 absolute coefficients")
    require(matrix_mode in ("fixed-a1", "dynamic"), "COLOR", "Unknown matrix mode")
    mapping = bytes([22, 24, 23, 25])
    fields = [ColourField(CC1, 0x1236, mapping), ColourField(MATRIX, 0x1cc, mapping)]
    for bank in BANKS:
        offset = 0x1250 + bank * 64
        fields.append(ColourField(CC1, offset, delta_coefficients(donor_cc1, offset)))
        base = 0x1e0 + bank * 0x300
        dynamic = donor_matrix[base:base + 0x240]
        a1 = donor_matrix[base + 0xc0:base + 0x180] * 3
        target, legacy = (a1, dynamic) if matrix_mode == "fixed-a1" else (dynamic, a1)
        fields.append(ColourField(MATRIX, base, target, legacy))
    require(len(fields) == 10 and sum(len(f.target) for f in fields) == 2504,
            "COLOR", "Unexpected colour field contract")
    return tuple(fields)


def patch_template(payload, fields):
    """Validate every preimage before changing ten fields and affected sums."""
    import struct
    rows = bk4_rows(payload)
    records = {}
    for key, size in ((CC1, 8192), (MATRIX, 28672)):
        matches = [(i, row["records"][key]) for i, row in enumerate(rows) if key in row["records"]]
        require(len(matches) == 1, "BK4", "Missing or ambiguous colour record")
        segment, record = matches[0]
        require(record["size"] == size and record["attrs"] == 8,
                "BK4", "Unexpected colour record size/attributes")
        records[key] = (segment, record)
    cc_at = records[CC1][1]["offset"]
    require(payload[cc_at + 0xefe] == 0, "COLOR", "Expected M4 base/delta format")
    edits, allowed, affected = [], set(), set()
    for field in fields:
        require(field.key in records, "COLOR", "Unexpected field record")
        segment, record = records[field.key]
        require(0 <= field.offset <= record["size"] - len(field.target), "COLOR", "Field outside record")
        offset = record["offset"] + field.offset
        positions = set(range(offset, offset + len(field.target)))
        require(not allowed.intersection(positions), "COLOR", "Overlapping colour fields")
        old = payload[offset:offset + len(field.target)]
        accepted = (bytes(len(field.target)), field.target)
        if field.legacy:
            accepted += (field.legacy,)
        require(old in accepted, "COLOR", f"Unknown colour preimage {field.key:08x}+{field.offset:x}")
        edits.append((offset, field.target))
        allowed.update(positions)
        affected.add(segment)
    require(len(fields) == 10 and len(allowed) == 2504, "COLOR", "Expected ten fields / 2504 bytes")
    output = bytearray(payload)
    for offset, value in edits:
        output[offset:offset + len(value)] = value
    for segment in affected:
        row = rows[segment]
        base, end = row["base"], row["base"] + row["extent"]
        checksum = (sum(output[base:base + 32]) + sum(output[base + 36:end])) & 0xffffffff
        struct.pack_into("<I", output, base + 32, checksum)
        allowed.update(range(base + 32, base + 36))
    require(len(output) == len(payload) and bk4_rows(output) == rows, "BK4", "Index/attribute drift")
    require(all(a == b or i in allowed for i, (a, b) in enumerate(zip(payload, output))),
            "BK4", "Non-colour bytes changed")
    return bytes(output)


def template_changes(index, read, donor_cc1, donor_matrix, matrix_mode="fixed-a1"):
    """Prepare all templates before any package write; reject partial sets."""
    fields = colour_fields(donor_cc1, donor_matrix, matrix_mode)
    names = sorted(name for name in index if name.startswith(PREFIX) and name.endswith(".bin"))
    require(len(names) == 32
            and all(name.startswith(PREFIX + "SYSIPSX-DSLR/LS/")
                    or name.startswith(PREFIX + "SYSIPSX-DSLR/LS_GLEE/") for name in names)
            and sum(name.startswith(PREFIX + "SYSIPSX-DSLR/LS/") for name in names) == 16,
            "TEMPLATES", "Expected all 32 official LS/LS_GLEE colour templates")
    changes, evidence = {}, []
    for name in names:
        before = read(name)
        require(len(before) == index[name][1], "SIZE", "Truncated template")
        after = patch_template(before, fields)
        changes[name] = (before, after)
        evidence.append({"member": name, "bytes": len(before), "source_sha256": digest(before),
                         "target_sha256": digest(after), "changed_bytes": sum(a != b for a, b in zip(before, after))})
    return changes, {"count": 32, "fields_each": 10, "field_bytes_each": 2504,
                     "matrix_mode": matrix_mode, "LOOK_defaults_changed": False,
                     "reset_attributes_calibration_preserved": True,
                     "personalized_partition_embedded": False, "templates": evidence}
