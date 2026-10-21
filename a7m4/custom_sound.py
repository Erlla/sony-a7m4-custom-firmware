"""Version-neutral, offline custom shutter/focus sound file patches.

This module never imports hardware transports or reads/writes updater/dat4.
The built-in recipe requires the exact shared-menu reference layout, not stock AP.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from importlib.resources import files
from pathlib import Path, PurePosixPath

MAX_FILE_BYTES = 128 * 1024 * 1024


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def integer(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("Expected a non-negative integer")
    return value


def apply_delta(source: bytes, operations: list, output_bytes: int) -> bytes:
    """Reconstruct from bounded original-file COPYs and new-byte ADDs."""
    size = integer(output_bytes)
    if size > MAX_FILE_BYTES or not isinstance(operations, list):
        raise ValueError("Invalid output size or delta")
    result = bytearray()
    for operation in operations:
        if not isinstance(operation, dict):
            raise ValueError("Invalid delta operation")
        if set(operation) == {"copy"}:
            pair = operation["copy"]
            if not isinstance(pair, list) or len(pair) != 2:
                raise ValueError("Invalid COPY")
            start, count = map(integer, pair)
            if not count or start + count > len(source) or len(result) + count > size:
                raise ValueError("COPY exceeds a bound")
            result.extend(source[start:start + count])
        elif set(operation) == {"data"}:
            encoded = operation["data"]
            if not isinstance(encoded, str) or len(encoded) > (size + 2) // 3 * 4:
                raise ValueError("Invalid ADD length")
            try:
                payload = base64.b64decode(encoded, validate=True)
            except (ValueError, TypeError) as error:
                raise ValueError("Invalid ADD encoding") from error
            if not payload or len(result) + len(payload) > size:
                raise ValueError("ADD exceeds output bound")
            result.extend(payload)
        else:
            raise ValueError("Unknown delta operation")
    if len(result) != size:
        raise ValueError("Delta output length mismatch")
    return bytes(result)


def apply_file(source: bytes, specification: dict) -> bytes:
    if len(source) != specification["input_bytes"] or digest(source) != specification["input_sha256"]:
        raise ValueError("Unsupported input SHA-256; firmware display labels do not establish compatibility")
    result = apply_delta(source, specification["ops"], specification["output_bytes"])
    if digest(result) != specification["output_sha256"]:
        raise ValueError("Patched output SHA-256 mismatch")
    return result


def validate_profile(profile: dict) -> None:
    if (profile.get("schema") != 1 or profile.get("firmware_metadata_changed") is not False
            or profile.get("automatic_diagnostic_export") is not False):
        raise ValueError("Expected the metadata-preserving, no-export sound profile")
    rows = profile.get("files")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Missing sound files")
    names = set()
    for row in rows:
        path = row.get("path", "")
        if (not isinstance(path, str) or "\\" in path or ":" in path
                or PurePosixPath(path).as_posix() != path
                or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts):
            raise ValueError("Unsafe profile path")
        kind = row.get("kind")
        supported = ((kind == "ap" and path == "lib/appFw.so")
                     or (kind == "cp" and path == "cpapp-b.bin")
                     or (kind == "fs" and (path == "lib/libmpr.so"
                         or (path.startswith("share/app/") and len(PurePosixPath(path).parts) == 3
                             and path.endswith(".uxc")))))
        destination = ("cp/" if kind == "cp" else "fs/") + path
        if not supported or destination in names:
            raise ValueError("Unsupported or duplicate sound destination")
        names.add(destination)
        for key in ("input_bytes", "output_bytes"):
            if integer(row.get(key)) > MAX_FILE_BYTES:
                raise ValueError("Image exceeds size limit")
        for key in ("input_sha256", "output_sha256"):
            value = row.get(key, "")
            if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError("Invalid image SHA-256")


def load_profile() -> dict:
    profile = json.loads(files("a7m4").joinpath("profiles/custom-sounds-reference.json").read_text("utf-8"))
    validate_profile(profile)
    return profile


def prepare(ap: Path, cp: Path, fs_root: Path, output: Path, profile: dict | None = None) -> dict:
    """Validate ALL inputs/outputs before creating a new output directory."""
    profile = load_profile() if profile is None else profile
    validate_profile(profile)
    if output.exists() or output.is_symlink():
        raise ValueError("Choose a new output directory")
    outputs, evidence = [], []
    for row in profile["files"]:
        source_path = ap if row["kind"] == "ap" else cp if row["kind"] == "cp" else fs_root / row["path"]
        if source_path.stat().st_size != row["input_bytes"]:
            raise ValueError("Unsupported input size: " + row["path"])
        source = source_path.read_bytes()
        try:
            patched = apply_file(source, row)
        except ValueError as error:
            raise ValueError(row["path"] + ": " + str(error)) from error
        relative = ("cp/" if row["kind"] == "cp" else "fs/") + row["path"]
        outputs.append((relative, patched))
        evidence.append({key: row[key] for key in ("kind", "path", "input_sha256", "output_sha256", "output_bytes")})
    manifest = {"schema": 1, "profile": profile["id"], "files": evidence,
                "firmware_metadata_changed": False, "automatic_diagnostic_export": False,
                "camera_io": False, "installable_package_created": False}
    # Parent symlinks are resolved once, before any output writes.
    destination = output.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()
    for relative, payload in outputs:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(payload)
    with (destination / "manifest.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect", help="List supported file hashes; do not access camera")
    apply = sub.add_parser("apply", help="Create patched files from exact local reference inputs")
    apply.add_argument("--ap", type=Path, required=True)
    apply.add_argument("--cp", type=Path, required=True)
    apply.add_argument("--fs-root", type=Path, required=True)
    apply.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        profile = load_profile()
        result = ({key: value for key, value in profile.items() if key != "files"}
                  | {"files": [{k: v for k, v in row.items() if k != "ops"} for row in profile["files"]]}
                  if args.command == "inspect" else prepare(args.ap, args.cp, args.fs_root, args.output, profile))
    except (ValueError, OSError) as error:
        parser.exit(2, str(error) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
