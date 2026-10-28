"""Derive current sound policy sources without changing the fixed-layout inputs.

These sources are useful for host policy checks and a separately relinked port.
The fixed-address native builder uses explicit post-link edits in build-plan.json.
"""
from pathlib import Path
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
CHANGES = {
    "sound_core.c": (
        ("    if (slot==SS_ELECTRONIC && enabled && shutter!=SS_SHUTTER_ELECTRONIC) return SS_INCOMPATIBLE;\n", ""),
        ("    if (shutter==SS_SHUTTER_ELECTRONIC) return SS_OK;\n    return ss_set_enabled(s,SS_ELECTRONIC,0,shutter,commit,context);",
         "    (void)commit; (void)context; return SS_OK;"),
        ("        if (n->shutter!=SS_SHUTTER_ELECTRONIC) return SS_OK;\n", ""),
    ),
    "ap_runtime.c": (
        ("__atomic_store_n(&runtime->mechanical_off_pending,1,__ATOMIC_RELEASE);\n        return SS_OK;",
         "__atomic_store_n(&runtime->mechanical_off_pending,0,__ATOMIC_RELEASE);\n        return SS_OK;"),
    ),
    "menu_callbacks.c": (("if(raw!=1 || csnd_ap_mechanical_pending())", "if(raw>1 || csnd_ap_mechanical_pending())"),),
    "ap_sd_backend.c": (("/PRIVATE/SONY/PRO/SOUNDS/", "/PRIVATE/M4ROOT/GENERAL/SOUNDS/"),),
}


def prepare(output: Path) -> None:
    if output.exists():
        raise ValueError("Choose a new output directory")
    manifest = json.loads((ROOT/"native/custom-sounds/source-manifest.json").read_text("utf-8"))
    pins = {r["path"]:r["sha256"] for r in manifest["files"]}
    payloads = {}
    for name, changes in CHANGES.items():
        source = ROOT/"native/custom-sounds/runtime/src"/name
        raw = source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != pins[source.relative_to(ROOT).as_posix()]:
            raise ValueError("Reference source changed: " + name)
        text = raw.decode("utf-8")
        for before, after in changes:
            if text.count(before) != 1:
                raise ValueError("Source anchor changed: " + name)
            text = text.replace(before, after)
        payloads[name] = text.encode("utf-8")
    output.mkdir(parents=True)
    for name, raw in payloads.items():
        with (output/name).open("xb") as stream:
            stream.write(raw)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    prepare(parser.parse_args().output)
