import base64
import struct

import pytest

from a7m4.custom_sound import (
    REQUIRED_RESOURCE_PATHS, SOUND_TEXT_IDS, digest, load_menu_profile, load_profile,
    menu_text, prepare, repair_menu_resources, validate_profile, verify_menu_resources,
)


def bank(path, *, missing=None, bad_volume=False):
    labels = {rid: "sound" for rid in SOUND_TEXT_IDS}
    labels[0x200AB60] = ""
    labels.update({rid: f"{(rid - 0x200ABD8 + 1) * 10}%" for rid in range(0x200ABD8, 0x200ABE2)})
    if "simplifiedchinese" in path:
        labels.update(zip((0x200AB5C, 0x200AB5D, 0x200AB5E, 0x200AB5F, 0x200AB65),
                          ("自定义电子快门声", "自定义对焦声音", "从SD卡内导入", "开关", "音量")))
    if missing:
        del labels[missing]
    if bad_volume:
        labels[0x200ABD8] = "999%"
    count = 0xBE2
    data = bytearray(16 + 2 * count)
    data[:4] = b"uxc\x07"
    struct.pack_into("<H", data, 10, 5)
    struct.pack_into("<I", data, 12, count * 0x1001)
    data[16:] = b"\xff\xff" * count
    data.extend(bytes(-len(data) % 4))
    base = len(data)
    for rid, label in sorted(labels.items()):
        struct.pack_into("<H", data, 16 + 2 * (rid - 0x200A000), (len(data) - base) // 4)
        data.extend(struct.pack("<I", rid + 0x1C000000) + label.encode() + b"\0")
        data.extend(bytes(-len(data) % 4))
    return bytes(data)


def fixture_profile(root, *, missing=None, bad_volume=False):
    rows = []
    for path in sorted(REQUIRED_RESOURCE_PATHS):
        source, target = b"old-resource", bank(path, missing=missing, bad_volume=bad_volume)
        p = root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(source)
        rows.append({"kind": "fs", "path": path, "input_bytes": len(source), "input_sha256": digest(source),
                     "output_bytes": len(target), "output_sha256": digest(target),
                     "ops": [{"data": base64.b64encode(target).decode()}]})
    return {"schema": 1, "id": "synthetic-menu", "firmware_metadata_changed": False,
            "automatic_diagnostic_export": False, "resources_only": True,
            "required_menu_resources": 68, "files": rows}


def test_bundled_repair_targets_equal_existing_full_recipe():
    full = load_profile()
    repair = load_menu_profile()
    expected = {r["path"]: r["output_sha256"] for r in full["files"] if r["path"] in REQUIRED_RESOURCE_PATHS}
    assert len(expected) == 68
    assert {r["path"]: r["output_sha256"] for r in repair["files"]} == expected


@pytest.mark.parametrize("path", ["share/app/string_english_horizontal.uxc", "share/app/string_english_vertical.uxc", "cpapp-b.bin"])
def test_full_sound_contract_rejects_missing_required_files(path):
    profile = load_profile()
    profile["files"] = [r for r in profile["files"] if r["path"] != path]
    with pytest.raises(ValueError):
        validate_profile(profile)


def test_repair_only_resources_and_repeat_is_idempotent(tmp_path):
    root = tmp_path / "input"
    profile = fixture_profile(root)
    for name in ("lib/appFw.so", "lib/libmpr.so", "cpapp-b.bin", "updater/dat4", "setting/csnd/settings.bin"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"preserve-code-and-settings")
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    output = tmp_path / "repair"
    result = repair_menu_resources(root, output, profile)
    assert result["program_code_changed"] is False
    assert result["menu_verification"]["banks_verified"] == 68
    assert result["menu_verification"]["text_checks"] == 1360
    assert {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()} == {
        "manifest.json", *("fs/" + p for p in REQUIRED_RESOURCE_PATHS)}
    assert before == {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert verify_menu_resources(output / "fs", profile)["banks_verified"] == 68
    again = repair_menu_resources(output / "fs", tmp_path / "again", profile)
    assert all(r["already_repaired"] for r in again["files"])
    with pytest.raises(ValueError, match="new output"):
        repair_menu_resources(root, output, profile)


def test_late_bad_input_never_creates_partial_output(tmp_path):
    root = tmp_path / "input"
    profile = fixture_profile(root)
    (root / profile["files"][-1]["path"]).write_bytes(b"unknown-resource")
    with pytest.raises(ValueError, match="Unsupported input"):
        repair_menu_resources(root, tmp_path / "result", profile)
    assert not (tmp_path / "result").exists()


@pytest.mark.parametrize("missing,bad_volume", [(0x200AB5D, False), (None, True)])
def test_semantic_missing_labels_and_bad_volume_fail_before_write(tmp_path, missing, bad_volume):
    profile = fixture_profile(tmp_path / "input", missing=missing, bad_volume=bad_volume)
    with pytest.raises(ValueError, match="menu text|volume labels"):
        repair_menu_resources(tmp_path / "input", tmp_path / "result", profile)
    assert not (tmp_path / "result").exists()


def test_final_filesystem_verification_rejects_missing_and_changed_bank(tmp_path):
    profile = fixture_profile(tmp_path / "input")
    repair_menu_resources(tmp_path / "input", tmp_path / "result", profile)
    fs = tmp_path / "result/fs"
    path = fs / profile["files"][-1]["path"]
    saved = path.read_bytes()
    path.unlink()
    with pytest.raises(FileNotFoundError):
        verify_menu_resources(fs, profile)
    path.write_bytes(saved[:-1] + bytes([saved[-1] ^ 1]))
    with pytest.raises(ValueError, match="hash/size"):
        verify_menu_resources(fs, profile)


def test_full_prepare_checks_menu_payloads_before_any_output(tmp_path):
    root = tmp_path / "input"
    profile = fixture_profile(root, missing=0x200AB5D)
    profile["resources_only"] = False
    for kind, path in (("ap", "lib/appFw.so"), ("cp", "cpapp-b.bin"), ("fs", "lib/libmpr.so")):
        source = root / path
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"code")
        profile["files"].append({"kind": kind, "path": path, "input_bytes": 4, "input_sha256": digest(b"code"),
                                 "output_bytes": 4, "output_sha256": digest(b"code"), "ops": [{"copy": [0, 4]}]})
    with pytest.raises(ValueError, match="menu text"):
        prepare(root / "lib/appFw.so", root / "cpapp-b.bin", root, tmp_path / "result", profile)
    assert not (tmp_path / "result").exists()


@pytest.mark.parametrize("value", [b"", b"uxc\x07" + bytes(12), b"not-uxc" + bytes(20)])
def test_malformed_uxc_is_rejected(value):
    with pytest.raises(ValueError):
        menu_text(value, 0x200AB5C)


def test_uxc_id_validation_and_retired_empty_caption():
    data = bank("english")
    assert menu_text(data, 0x200AB60) == ""
    assert menu_text(data, 0x200C001) is None
    bad = bytearray(data)
    struct.pack_into("<H", bad, 16 + 2 * 0xB5C, 0xFFFE)
    with pytest.raises(ValueError, match="offset"):
        menu_text(bytes(bad), 0x200AB5C)
