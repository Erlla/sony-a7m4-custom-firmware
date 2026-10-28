import json
from pathlib import Path

import pytest

from a7m4.custom_sound_policy import EDITS, SOUND_DIRECTORY, edits_in_section, patch_ap


def test_section_policy_and_path_edits_preserve_size_and_other_bytes():
    start, end = 0x8F92000, 0x8F9A3DC
    raw = bytearray(end - start)
    allowed = set()
    for va, before, after, _ in EDITS:
        raw[va-start:va-start+len(bytes.fromhex(before))] = bytes.fromhex(before)
        allowed.update(range(va-start,va-start+len(bytes.fromhex(after))))
    result = edits_in_section(bytes(raw), start)
    assert len(result) == len(raw)
    for va, _, after, _ in EDITS:
        assert result[va-start:va-start+len(bytes.fromhex(after))] == bytes.fromhex(after)
    assert all(a == b or i in allowed for i,(a,b) in enumerate(zip(raw,result)))
    assert SOUND_DIRECTORY + b"\0" in result


def test_wrong_instruction_rejected_before_emitting_a_section():
    with pytest.raises(ValueError, match="preimage"):
        edits_in_section(bytes(0x100), 0x8F990CC)


def test_complete_unknown_ap_rejected():
    root = Path(__file__).resolve().parents[1]
    identities = json.loads((root/"a7m4/profiles/custom-sound-policy.json").read_text("utf-8"))["AP_identities"]
    with pytest.raises(ValueError, match="SHA-256"):
        patch_ap(b"unrelated-image", identities)
