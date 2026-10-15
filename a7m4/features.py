"""Independent offline battery and lens-AF patch recipes. Never operate hardware.

Lens speed/AF tracking improvements have NOT undergone physical testing.
"""
import argparse
from pathlib import Path
import sys

from .common import digest, read_json, require
from .offline import save_new

FEATURES = ("battery", "lens-af")


def catalog(feature):
    require(feature in FEATURES, "FEATURE", "Unknown feature")
    return read_json(Path(__file__).parent / "profiles" / (feature + ".json"))


def apply_feature(source, feature, *, undo=False):
    recipe = catalog(feature)
    key = "target_sha256" if undo else "source_sha256"
    source_hash = digest(source)
    profiles = [p for p in recipe["profiles"] if p["size"] == len(source) and p[key] == source_hash]
    require(len(profiles) == 1, "BASELINE", "Unsupported source or already patched file; select an exact documented baseline")
    profile = profiles[0]
    for check in recipe.get("binding_checks", []):
        off, raw = check["offset"], bytes.fromhex(check["old_hex"])
        require(0 <= off <= len(source) - len(raw) and source[off:off + len(raw)] == raw,
                "MAPPING", "Required CP mapping is absent; do not patch an unreviewed executable layout")
    output, occupied = bytearray(source), set()
    patches = profile["patches"]
    require(patches, "PATCH", "Empty patch recipe")
    for item in patches:
        off = item["offset"]
        old, new = bytes.fromhex(item["old_hex"]), bytes.fromhex(item["new_hex"])
        if undo:
            old, new = new, old
        require(old and len(old) == len(new) and 0 <= off <= len(source) - len(old), "PATCH", "Invalid patch bounds/size")
        positions = set(range(off, off + len(old)))
        require(not positions.intersection(occupied), "PATCH", "Overlapping patches")
        require(source[off:off + len(old)] == old, "PREIMAGE", "Instruction preimage differs")
        occupied.update(positions)
        output[off:off + len(new)] = new
    expected = profile["source_sha256"] if undo else profile["target_sha256"]
    changed = sum(a != b for a, b in zip(source, output))
    require(len(output) == len(source) and digest(output) == expected and changed == profile["changed_bytes"],
            "VERIFY", "Final patch identity/count mismatch")
    return bytes(output), {"feature": feature, "baseline": profile["baseline"], "undo": undo,
                           "source_sha256": source_hash, "output_sha256": expected,
                           "changed_bytes": changed, "patch_regions": len(patches),
                           "hardware_tested": False, "camera_io": False,
                           "status": recipe.get("status", "Offline recipe; see documented hardware limits"),
                           "scope": recipe["scope"]}


def patch_partition(source, feature, *, undo=False):
    """Edit a complete user-supplied partition without resizing its filesystem."""
    require(feature in FEATURES, "FEATURE", "Unknown feature")
    if feature == "battery":
        import io
        from dissect.extfs import ExtFS
        from .firmware import ext_replace
        program = ExtFS(io.BytesIO(source)).get("lib/appFw.so").open().read()
        patched, evidence = apply_feature(program, feature, undo=undo)
        output = ext_replace(source, "lib/appFw.so", patched, digest(program))
    else:
        from .fat import Fat
        fs = Fat(source)
        patched, evidence = apply_feature(fs.read("CPAPP-B.BIN"), feature, undo=undo)
        fs.replace("CPAPP-B.BIN", patched)
        output = fs.bytes()
    require(len(output) == len(source), "SIZE", "Partition size changed")
    return output, evidence | {"program_source_sha256": evidence["source_sha256"],
                               "program_output_sha256": evidence["output_sha256"],
                               "source_sha256": digest(source), "output_sha256": digest(output),
                               "partition_size": len(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feature", choices=FEATURES)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--undo", action="store_true", help="Restore the exact source bytes from a recognized patched file")
    parser.add_argument("--partition", action="store_true", help="Input/output are complete personal nflasha15 (battery) or nflasha8 (lens) images")
    args = parser.parse_args()
    if args.feature == "lens-af":
        print("UNTESTED: no physical focus-speed, AF-tracking or burst-performance testing.", file=sys.stderr)
    patcher = patch_partition if args.partition else apply_feature
    output, evidence = patcher(args.source.read_bytes(), args.feature, undo=args.undo)
    save_new(args.output, output, evidence)
    import json
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
