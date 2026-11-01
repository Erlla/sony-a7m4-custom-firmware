"""Apply the fixed -1/0/97 AWB-priority recipe to a supported local CP file."""
from __future__ import annotations

import argparse
import hashlib
from importlib.resources import files
import json
from pathlib import Path


def load_profile() -> dict:
    return json.loads(files("a7m4").joinpath("profiles/awb-priority.json").read_text("utf-8"))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def patch_cp(data: bytes, profile: dict | None = None) -> bytes:
    profile = load_profile() if profile is None else profile
    identity = profile["identities"].get(digest(data))
    if len(data) != profile["input_bytes"] or identity is None:
        raise ValueError("Unsupported CP input; a listed complete SHA-256 is required")
    result = bytearray(data)
    previous_end = 0
    for row in sorted(profile["patches"], key=lambda r: int(r["file_offset"], 16)):
        at = int(row["file_offset"], 16)
        before, after = bytes.fromhex(row["before"]), bytes.fromhex(row["after"])
        end = at + len(before)
        if at < previous_end or not before or len(before) != len(after) or end > len(data) or data[at:end] != before:
            raise ValueError("CP range/preimage mismatch: " + row["file_offset"])
        result[at:end] = after
        previous_end = end
    result = bytes(result)
    if digest(result) != identity["output_sha256"]:
        raise ValueError("CP output SHA-256 mismatch")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = patch_cp(args.input.read_bytes())
    with args.output.open("xb") as stream:
        stream.write(result)
    print(digest(result))


if __name__ == "__main__":
    main()
