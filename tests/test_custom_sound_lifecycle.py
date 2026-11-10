import copy
import hashlib
import json
from pathlib import Path

import pytest

from a7m4.custom_sound_lifecycle import digest, load_profile, patch_component


def fixture():
    original = b"local AP fixture with preserved bytes"
    patched = original[:6] + b"CP" + original[8:]
    recipe = dict(input_bytes=len(original), identities={digest(original): dict(output_sha256=digest(patched))},
                  patches=[dict(offset=6, before=original[6:8].hex(), after=b"CP".hex())])
    return original, patched, {"components": {"ap": recipe, "cp": copy.deepcopy(recipe)}}


@pytest.mark.parametrize("component", ["ap", "cp"])
def test_exact_identity_and_untouched_complement(component):
    original, expected, profile = fixture()
    assert patch_component(original, component, profile) == expected
    for bad in (expected, original + b"x", bytes(len(original))):
        with pytest.raises(ValueError, match="Unsupported"):
            patch_component(bad, component, profile)


@pytest.mark.parametrize("error", ["preimage", "overlap", "size", "outside", "output"])
def test_invalid_recipe_is_rejected(error):
    original, _, profile = fixture()
    recipe = profile["components"]["ap"]
    row = recipe["patches"][0]
    if error == "preimage": row["before"] = "0000"
    elif error == "overlap": recipe["patches"].append(copy.deepcopy(row))
    elif error == "size": row["after"] = "00"
    elif error == "outside": row["offset"] = 1000
    else: recipe["identities"][digest(original)]["output_sha256"] = "0" * 64
    with pytest.raises(ValueError): patch_component(original, "ap", profile)


def test_current_component_chains_and_awb_composition():
    root = Path(__file__).resolve().parents[1]
    profile = load_profile()
    layout = json.loads((root / "methods/08-custom-lut/reference-layout.json").read_text("utf-8"))
    awb = json.loads((root / "a7m4/profiles/awb-priority.json").read_text("utf-8"))
    for component in ("AP", "CP"):
        chain = layout[component + "_component_patches"]
        assert all(a["output_sha256"] == b["source_sha256"] for a, b in zip(chain, chain[1:]))
        lifecycle = next(row for row in chain if row.get("profile") == "a7m4/profiles/custom-sound-lifecycle.json")
        identity = profile["components"][component.lower()]["identities"][lifecycle["source_sha256"]]
        assert identity["output_sha256"] == lifecycle["output_sha256"]
        current = chain[-1]["output_sha256"]
        if component == "AP":
            playback = layout["aspect_playback"]["components"]["ap"]
            assert playback["input_sha256"] == current
            current = playback["output_sha256"]
            for name in layout["menu_ui_fixes"]["AP_order"]:
                stage = layout["menu_ui_fixes"]["components"][name]
                assert stage["input_sha256"] == current
                current = stage["output_sha256"]
        else:
            clone = layout["aspect_capture_clone"]
            assert clone["source_sha256"] == lifecycle["output_sha256"]
            assert current == clone["output_sha256"]
        assert next(r["sha256"] for r in layout["components"] if r["component"] == component) == current
    assert layout["CP_component_patches"][-1]["output_sha256"] in awb["identities"]
    assert not profile["sound_conversion_cache_enabled"] and profile["LUT_compilation_cache_preserved"]
    for name, expected in profile["source_hashes"].items():
        assert hashlib.sha256((root / "native/custom-sounds/lifecycle" / name).read_bytes()).hexdigest() == expected
