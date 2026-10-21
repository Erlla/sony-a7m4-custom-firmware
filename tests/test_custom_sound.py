import base64
import copy
import json
import subprocess
from pathlib import Path

import pytest

from a7m4.custom_sound import apply_delta, apply_file, digest, load_profile, prepare, validate_profile


def specification(kind="ap", path="lib/appFw.so", source=b"old-image", target=b"old-sound"):
    return {"kind": kind, "path": path, "input_bytes": len(source), "input_sha256": digest(source),
            "output_bytes": len(target), "output_sha256": digest(target),
            "ops": [{"data": base64.b64encode(target).decode("ascii")}]}


def profile(rows):
    return {"schema": 1, "id": "synthetic", "firmware_metadata_changed": False,
            "automatic_diagnostic_export": False, "files": rows}


def test_copy_add_reconstruction():
    assert apply_delta(b"012345", [{"copy": [0, 2]}, {"data": "YWI="}, {"copy": [4, 2]}], 6) == b"01ab45"


@pytest.mark.parametrize("operations,size", [
    ([{"copy": [-1, 1]}], 1), ([{"copy": [True, 1]}], 1),
    ([{"copy": [0, 0]}], 0), ([{"copy": [0, 3]}], 3),
    ([{"copy": [0, 2]}], 1), ([{"copy": [0]}], 1),
    ([{"data": "!!"}], 1), ([{"data": ""}], 0),
    ([{"data": "YWI="}], 1), ([{"unknown": 1}], 1),
    ([{"copy": [0, 1], "data": "YQ=="}], 1), ([], 1),
])
def test_bad_delta_is_rejected(operations, size):
    with pytest.raises(ValueError):
        apply_delta(b"01", operations, size)


def test_wrong_baseline_and_corrupt_output_rejected():
    row = specification()
    with pytest.raises(ValueError, match="Unsupported input"):
        apply_file(b"bad-image", row)
    row["output_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="output SHA"):
        apply_file(b"old-image", row)


@pytest.mark.parametrize("kind,path", [
    ("fs", "../outside.uxc"), ("fs", "/share/app/string.uxc"),
    ("fs", "C:/outside.uxc"), ("fs", "share\\app\\string.uxc"),
    ("fs", "share/app/../string.uxc"), ("fs", "share//app/string.uxc"),
    ("fs", "updater/dat4"), ("ap", "lib/other.so"), ("driver", "cpapp-b.bin"),
])
def test_no_path_escape_or_version_metadata(kind, path):
    with pytest.raises(ValueError):
        validate_profile(profile([specification(kind, path)]))


def test_duplicate_output_rejected():
    row = specification()
    with pytest.raises(ValueError, match="duplicate"):
        validate_profile(profile([row, copy.deepcopy(row)]))


def test_all_inputs_checked_before_output_write(tmp_path):
    ap = tmp_path / "ap"
    cp = tmp_path / "cp"
    ap.write_bytes(b"old-image")
    cp.write_bytes(b"bad-image")
    p = profile([specification(), specification("cp", "cpapp-b.bin")])
    output = tmp_path / "result"
    with pytest.raises(ValueError):
        prepare(ap, cp, tmp_path, output, p)
    assert not output.exists()
    assert ap.read_bytes() == b"old-image"


def test_output_and_input_preserved(tmp_path):
    ap = tmp_path / "ap"
    ap.write_bytes(b"old-image")
    output = tmp_path / "result"
    evidence = prepare(ap, tmp_path / "unused-cp", tmp_path, output, profile([specification()]))
    assert (output / "fs/lib/appFw.so").read_bytes() == b"old-sound"
    assert ap.read_bytes() == b"old-image"
    assert evidence["firmware_metadata_changed"] is False
    assert evidence["automatic_diagnostic_export"] is False
    assert evidence["camera_io"] is False
    assert not (output / "updater/dat4").exists()
    with pytest.raises(ValueError, match="new output"):
        prepare(ap, tmp_path / "unused-cp", tmp_path, output, profile([specification()]))


def test_reference_recipe_and_native_source_manifest():
    p = load_profile()
    assert len(p["files"]) == 71
    assert sum(row["kind"] == "fs" and row["path"].endswith(".uxc") for row in p["files"]) == 68
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "native/custom-sounds/source-manifest.json").read_text("utf-8"))
    assert manifest["firmware_version_required"] is False
    published = set(p.decode("utf-8") for p in subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root).split(b"\0") if p)
    for row in manifest["files"]:
        assert row["path"] in published
        assert digest((root / row["path"]).read_bytes()) == row["sha256"]
