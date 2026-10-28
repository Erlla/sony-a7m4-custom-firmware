import copy
import hashlib
import json
from pathlib import Path

import pytest

from a7m4.custom_sound_handoff import digest, load_profile, patch_cp


def sample():
    before = b"a locally generated CP fixture"
    after = before[:2] + b"ZZ" + before[4:]
    profile = dict(input_bytes=len(before), source_sha256=digest(before), output_sha256=digest(after),
                   cp_base=0x1000, patches=[dict(va="0x1002", before=before[2:4].hex(), after=b"ZZ".hex())])
    return before, after, profile


def test_exact_component_patch_and_untouched_complement():
    before, after, profile = sample()
    assert patch_cp(before, profile) == after
    assert patch_cp(before, profile)[:2] == before[:2]
    assert patch_cp(before, profile)[4:] == before[4:]


def test_reject_unknown_or_already_patched_component():
    before, after, profile = sample()
    for raw in [before + b"x", after, bytes(len(before))]:
        with pytest.raises(ValueError, match="Unsupported CP"):
            patch_cp(raw, profile)


@pytest.mark.parametrize("failure", ["preimage", "overlap", "outside", "size", "output"])
def test_reject_inconsistent_recipe(failure):
    before, _, profile = sample()
    row = profile["patches"][0]
    if failure == "preimage": row["before"] = "0000"
    elif failure == "overlap": profile["patches"].append(copy.deepcopy(row))
    elif failure == "outside": row["va"] = "0x2000"
    elif failure == "size": row["after"] = "00"
    else: profile["output_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        patch_cp(before, profile)


def test_published_native_sources_and_lut_component_chain_agree():
    root = Path(__file__).resolve().parents[1]
    profile = load_profile()
    for name, expected in profile["sources"].items():
        assert hashlib.sha256((root / "native/custom-sounds/handoff" / name).read_bytes()).hexdigest() == expected
    layout = json.loads((root / "methods/08-custom-lut/reference-layout.json").read_text("utf8"))
    assert next(r["sha256"] for r in layout["components"] if r["component"] == "CP") == profile["output_sha256"]
    chain = layout["CP_component_patches"][-1]
    assert chain["source_sha256"] == profile["source_sha256"]
    assert chain["output_sha256"] == profile["output_sha256"]
    assert {r["va"] for r in profile["patches"] if r["purpose"].endswith("_gate")} == {"0x5ddc24", "0x5ddd08", "0x5dec74"}
