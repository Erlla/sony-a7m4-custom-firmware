"""Compose sound startup, replay and gain changes into listed AP/CP files."""
from __future__ import annotations

import argparse
import hashlib
from importlib.resources import files
import json
from pathlib import Path


def load_profile() -> dict:
    return json.loads(files("a7m4").joinpath("profiles/custom-sound-lifecycle.json").read_text("utf-8"))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def patch_component(data: bytes, component: str, profile: dict | None = None) -> bytes:
    profile = load_profile() if profile is None else profile
    recipe = profile["components"][component]
    identity = recipe["identities"].get(digest(data))
    if len(data) != recipe["input_bytes"] or identity is None:
        raise ValueError("Unsupported " + component.upper() + " input; a listed complete SHA-256 is required")
    result = bytearray(data)
    previous_end = 0
    for row in sorted(recipe["patches"], key=lambda r: r["offset"]):
        at = row["offset"]
        before, after = bytes.fromhex(row["before"]), bytes.fromhex(row["after"])
        end = at + len(before)
        if at < previous_end or not before or len(before) != len(after) or end > len(data) or data[at:end] != before:
            raise ValueError("Component range/preimage mismatch: " + hex(at))
        result[at:end] = after
        previous_end = end
    result = bytes(result)
    if digest(result) != identity["output_sha256"]:
        raise ValueError("Component output SHA-256 mismatch")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", choices=("ap", "cp"), required=True)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = patch_component(args.input.read_bytes(), args.component)
    with args.output.open("xb") as stream:
        stream.write(result)
    print(digest(result))


if __name__ == "__main__":
    main()
