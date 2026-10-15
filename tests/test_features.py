"""Bounded patching, reversal and explicit feature opt-in; synthetic bytes only."""
import copy
from pathlib import Path
import struct
import subprocess
import sys

import pytest

from a7m4 import features
from a7m4.common import ToolError, digest
from a7m4.firmware import optional_features


@pytest.fixture
def recipe(monkeypatch):
    before, after = b"0123456789abcdef", b"0123XY6789abcdef"
    data = {"feature": "battery", "scope": "synthetic fixture", "profiles": [
        {"baseline": "synthetic", "size": len(before), "source_sha256": digest(before),
         "target_sha256": digest(after), "changed_bytes": 2,
         "patches": [{"offset": 4, "old_hex": b"45".hex(), "new_hex": b"XY".hex()}]}]}
    monkeypatch.setattr(features, "catalog", lambda feature: data)
    return before, after, data


def test_patch_then_exact_reversal_and_reapply_refusal(recipe):
    source, expected, _ = recipe
    output, report = features.apply_feature(source, "battery")
    assert output == expected and output[:4] == source[:4] and output[6:] == source[6:]
    assert report["hardware_tested"] is False and report["camera_io"] is False
    with pytest.raises(ToolError, match="Unsupported"):
        features.apply_feature(output, "battery")
    restored, evidence = features.apply_feature(output, "battery", undo=True)
    assert restored == source and evidence["undo"]


@pytest.mark.parametrize("source", [b"wrong", b"0123456789abcdeg", b"0123456789abcde"])
def test_unknown_full_file_identity_refused(recipe, source):
    with pytest.raises(ToolError, match="Unsupported"):
        features.apply_feature(source, "battery")


@pytest.mark.parametrize("fault", ["empty", "overlap", "negative", "outside", "resize", "preimage", "final_hash", "change_count"])
def test_invalid_or_tampered_recipe_is_refused(recipe, fault):
    source, _, data = recipe
    profile = data["profiles"][0]
    patch = profile["patches"][0]
    if fault == "empty":
        profile["patches"] = []
    elif fault == "overlap":
        profile["patches"].append(copy.deepcopy(patch))
    elif fault == "negative":
        patch["offset"] = -1
    elif fault == "outside":
        patch["offset"] = len(source)
    elif fault == "resize":
        patch["new_hex"] = "000000"
    elif fault == "preimage":
        patch["old_hex"] = "ffff"
    elif fault == "final_hash":
        profile["target_sha256"] = "0" * 64
    else:
        profile["changed_bytes"] = 3
    with pytest.raises(ToolError):
        features.apply_feature(source, "battery")


def test_missing_execute_mapping_refuses_even_recognized_input(recipe):
    source, _, data = recipe
    data["binding_checks"] = [{"offset": 0, "old_hex": "ff"}]
    with pytest.raises(ToolError, match="mapping"):
        features.apply_feature(source, "lens-af")


def test_default_package_feature_selection_is_unchanged(monkeypatch):
    monkeypatch.setattr(features, "apply_feature", lambda *a, **k: pytest.fail("Unrequested feature applied"))
    assert optional_features(b"ap", b"cp") == (b"ap", b"cp", {})


@pytest.mark.parametrize("battery,lens", [(True, False), (False, True), (True, True)])
def test_package_only_applies_explicitly_selected_features(monkeypatch, battery, lens):
    calls = []
    def apply(source, feature):
        calls.append((source, feature))
        return source + b"!", {"feature": feature, "hardware_tested": False}
    monkeypatch.setattr(features, "apply_feature", apply)
    ap, cp, evidence = optional_features(b"ap", b"cp", battery=battery, lens_af=lens)
    assert ap == b"ap" + (b"!" if battery else b"")
    assert cp == b"cp" + (b"!" if lens else b"")
    assert {name for _, name in calls} == set(evidence) == ({"battery"} if battery else set()) | ({"lens-af"} if lens else set())


def thumb_bl_target(raw, address):
    """Decode the signed Thumb-2 BL immediate independently of the patch tool."""
    first, second = struct.unpack("<HH", raw)
    assert first & 0xf800 == 0xf000 and second & 0xd000 == 0xd000
    sign, j1, j2 = (first >> 10) & 1, (second >> 13) & 1, (second >> 11) & 1
    immediate = ((sign << 24) | ((1 ^ j1 ^ sign) << 23) | ((1 ^ j2 ^ sign) << 22)
                 | ((first & 1023) << 12) | ((second & 2047) << 1))
    if sign:
        immediate -= 1 << 25
    return address + 4 + immediate


def test_published_thumb_calls_resolve_to_helper_and_original_getter():
    recipe = features.catalog("lens-af")
    for profile in recipe["profiles"]:
        helper = profile["patches"][-1]
        target = int(helper["va"], 16)
        for patch in profile["patches"][:-1]:
            address = int(patch["va"], 16)
            assert thumb_bl_target(bytes.fromhex(patch["new_hex"]), address) == target
            assert thumb_bl_target(bytes.fromhex(patch["old_hex"]), address) == 0x997618


def test_lens_cli_discloses_untested_status_and_never_writes_unknown_source(tmp_path):
    source, output = tmp_path / "unknown.bin", tmp_path / "output.bin"
    source.write_bytes(b"unsupported camera program")
    result = subprocess.run([sys.executable, "-m", "a7m4.features", "lens-af", str(source), "--output", str(output)],
                            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, encoding="utf-8", timeout=15)
    assert result.returncode != 0 and not output.exists()
    assert "UNTESTED: no physical focus-speed" in result.stderr
