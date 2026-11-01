import copy
import hashlib
import json
from pathlib import Path

import pytest

from a7m4.persistent_cache import digest, load_profile, patch_ap


def fixture():
    before = b"locally generated AP fixture bytes"
    after = before[:3] + b"ABCD" + before[7:]
    return before, after, dict(input_bytes=len(before), source_sha256=digest(before),
                              output_sha256=digest(after), patches=[dict(offset=3, before=before[3:7].hex(), after=b"ABCD".hex())])


def test_exact_component_and_complement():
    before, after, profile = fixture()
    assert patch_ap(before, profile) == after
    assert before[:3] == after[:3] and before[7:] == after[7:]


@pytest.mark.parametrize("bad", [b"unknown", b"", b"x" * 33])
def test_unknown_ap_is_rejected(bad):
    _, _, profile = fixture()
    with pytest.raises(ValueError, match="Unsupported AP"):
        patch_ap(bad, profile)


@pytest.mark.parametrize("error", ["overlap", "preimage", "size", "outside", "output"])
def test_inconsistent_recipe_is_rejected(error):
    before, _, profile = fixture()
    row = profile["patches"][0]
    if error == "overlap": profile["patches"].append(copy.deepcopy(row))
    elif error == "preimage": row["before"] = "00000000"
    elif error == "size": row["after"] = "00"
    elif error == "outside": row["offset"] = 9999
    else: profile["output_sha256"] = "0" * 64
    with pytest.raises(ValueError): patch_ap(before, profile)


def test_sources_and_lut_component_chain_match():
    root = Path(__file__).resolve().parents[1]
    profile = load_profile()
    for name, expected in profile["source_hashes"].items():
        assert hashlib.sha256((root / "native/persistent-cache" / name).read_bytes()).hexdigest() == expected
    for name, expected in profile["source_header_dependencies"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected
    layout = json.loads((root / "methods/08-custom-lut/reference-layout.json").read_text("utf-8"))
    assert next(row["sha256"] for row in layout["components"] if row["component"] == "AP") == profile["output_sha256"]
    chain = layout["AP_component_patches"][-1]
    assert (chain["source_sha256"], chain["output_sha256"]) == (profile["source_sha256"], profile["output_sha256"])
