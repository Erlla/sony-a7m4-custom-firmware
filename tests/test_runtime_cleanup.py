import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native/custom-lut/runtime-cleanup"


def read(path):
    return json.loads(path.read_text("utf-8"))


def test_cleanup_follows_title_and_raw_components():
    layout = read(NATIVE / "layout.json")
    reference = read(ROOT / "methods/08-custom-lut/reference-layout.json")
    icons = read(ROOT / "native/menu-ui-fixes/title-icons.json")
    previous_ap = read(ROOT / "native/menu-ui-fixes/layout.json")["components"]["aspect-ap"]
    assert icons["input_AP_sha256"] == previous_ap["output_sha256"]
    assert layout["input_AP_sha256"] == icons["output_AP_sha256"]
    assert layout["input_CP_sha256"] == reference["raw_alternative_looks"]["output_sha256"]
    for component in ("AP", "CP"):
        current = reference["runtime_cleanup"]["components"][component]
        assert current["input_sha256"] == layout["input_" + component + "_sha256"]
        assert current["output_sha256"] == layout["output_" + component + "_sha256"]


def test_source_diff_and_linker_identity():
    layout = read(NATIVE / "layout.json")
    patch = NATIVE / layout["source_patch"]["file"]
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == layout["source_patch"]["sha256"]
    assert len(layout["source_patch"]["files"]) == 5
    for name, module in layout["modules"].items():
        assert hashlib.sha256((NATIVE / (name + ".ld")).read_bytes()).hexdigest() == module["linker_sha256"]
        assert set(module["source_order"]).isdisjoint(layout["removed_translation_units"])
    assert len(layout["native_bindings"]) == 13
    assert len(layout["factories"]) == 6
    assert len(layout["cache_calls"]) == 3


def test_lut_only_cache_uses_existing_sources():
    profile = read(NATIVE / "cache-build.json")
    for name, expected in profile["source_hashes"].items():
        path = ROOT / "native/persistent-cache" / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    assert "sound_cache.c" not in profile["source_hashes"]
    assert set(profile["original_functions"]) == {"lut_read_original", "lut_verify_original"}
    assert profile["module"]["bytes"] == 1694


def test_title_resource_set_is_complete():
    icons = read(ROOT / "native/menu-ui-fixes/title-icons.json")
    names = {row["path"] for row in icons["strings"]}
    assert len(names) == len(icons["strings"]) == 68
    for row in icons["strings"]:
        assert row["bytes"] - row["source_bytes"] == row["added_bytes"] == 4
        counterpart = row["path"].replace("_horizontal", "_vertical")
        assert counterpart in names
