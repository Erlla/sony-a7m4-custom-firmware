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
import struct

MAX_FILE_BYTES = 128 * 1024 * 1024
RESOURCE_LANGUAGES = (
    "arabic", "brazilianportuguese", "bulgarian", "canadianfrench", "croatian", "czech",
    "danish", "dutch", "english", "finnish", "french", "german", "greek", "hindi",
    "hungarian", "indonesia", "italian",
    "japanese", "korean", "malay", "norwegian", "persian", "polish", "portuguese",
    "romanian", "russian", "simplifiedchinese", "spanish", "swedish",
    "thai", "traditionalchinese", "turkish", "ukrainian", "vietnamese",
)
# Checked against the reference recipe below; language names are firmware paths.
REQUIRED_RESOURCE_PATHS = frozenset(
    f"share/app/string_{language}_{orientation}.uxc"
    for language in RESOURCE_LANGUAGES for orientation in ("horizontal", "vertical")
)
SOUND_TEXT_IDS = (*range(0x200AB5C, 0x200AB66), *range(0x200ABD8, 0x200ABE2))


def menu_resource_rows(profile: dict) -> list[dict]:
    rows = [r for r in profile["files"] if r["kind"] == "fs" and r["path"].startswith("share/app/")]
    if len(rows) != 68 or {r["path"] for r in rows} != REQUIRED_RESOURCE_PATHS:
        raise ValueError("Require all 68 sound menu resources, including both orientations")
    return rows


def menu_text(data: bytes, resource_id: int) -> str | None:
    """Read the indexed UXC layout; not a hardware/rendering acceptance test."""
    if len(data) < 16 or data[:4] != b"uxc\x07":
        raise ValueError("Invalid indexed UXC header")
    count, remainder = divmod(struct.unpack_from("<I", data, 12)[0], 0x1001)
    if remainder or not 0 < count <= 8192 or 16 + 2 * count > len(data):
        raise ValueError("Invalid UXC index bounds")
    base = (16 + 2 * count + 3) & ~3
    stored_id = resource_id + 0x1C000000
    first_id = 0x1E000000 + (struct.unpack_from("<H", data, 10)[0] << 13)
    index = stored_id - first_id
    if not 0 <= index < count:
        return None
    offset = struct.unpack_from("<H", data, 16 + 2 * index)[0]
    if offset == 0xFFFF:
        return None
    position = base + 4 * offset
    if position + 4 > len(data) or struct.unpack_from("<I", data, position)[0] != stored_id:
        raise ValueError("Invalid UXC record offset or identifier")
    try:
        end = data.index(0, position + 4)
        return data[position + 4:end].decode("utf-8")
    except (ValueError, UnicodeError) as error:
        raise ValueError("Invalid UXC text") from error


def verify_menu_payloads(profile: dict, payloads: dict[str, bytes]) -> dict:
    rows = menu_resource_rows(profile)
    for row in rows:
        data = payloads[row["path"]]
        if len(data) != row["output_bytes"] or digest(data) != row["output_sha256"]:
            raise ValueError("Sound menu output hash/size mismatch: " + row["path"])
        labels = {rid: menu_text(data, rid) for rid in SOUND_TEXT_IDS}
        if any(value is None or (not value and rid != 0x200AB60) for rid, value in labels.items()):
            raise ValueError("Missing sound menu text: " + row["path"])
        if labels[0x200AB60] != "":
            raise ValueError("Retired duration caption must remain empty")
        if [labels[rid] for rid in range(0x200ABD8, 0x200ABE2)] != [f"{i * 10}%" for i in range(1, 11)]:
            raise ValueError("Invalid sound volume labels")
        if "simplifiedchinese" in row["path"] and [labels[rid] for rid in (
                0x200AB5C, 0x200AB5D, 0x200AB5E, 0x200AB5F, 0x200AB65)] != [
                "自定义快门声", "自定义对焦声音", "从SD卡内导入", "开关", "音量"]:
            raise ValueError("Invalid Simplified Chinese sound labels")
    return {"banks_verified": len(rows), "text_checks": len(rows) * len(SOUND_TEXT_IDS),
            "glyph_rendering_tested": False, "camera_io": False}


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
    if "required_menu_resources" in profile:
        if type(profile["required_menu_resources"]) is not int or profile["required_menu_resources"] != 68:
            raise ValueError("Expected 68 required menu resources")
        menu_resource_rows(profile)
        components = {(r["kind"], r["path"]) for r in rows if not r["path"].startswith("share/app/")}
        expected = set() if profile.get("resources_only") is True else {
            ("ap", "lib/appFw.so"), ("cp", "cpapp-b.bin"), ("fs", "lib/libmpr.so")}
        if components != expected:
            raise ValueError("Incomplete sound component/resource set")


def load_profile() -> dict:
    profile = json.loads(files("a7m4").joinpath("profiles/custom-sounds-reference.json").read_text("utf-8"))
    validate_profile(profile)
    if profile.get("required_menu_resources") != 68 or profile.get("resources_only"):
        raise ValueError("Missing full sound menu resource contract")
    return profile


def load_menu_profile() -> dict:
    profile = json.loads(files("a7m4").joinpath("profiles/custom-sound-menu-repair.json").read_text("utf-8"))
    validate_profile(profile)
    if profile.get("resources_only") is not True or profile.get("required_menu_resources") != 68:
        raise ValueError("Expected the resource-only sound menu repair profile")
    return profile


def verify_menu_resources(fs_root: Path, profile: dict | None = None) -> dict:
    """Check every required bank in an extracted final filesystem, without writes."""
    profile = load_menu_profile() if profile is None else profile
    validate_profile(profile)
    payloads = {r["path"]: (fs_root / r["path"]).read_bytes() for r in menu_resource_rows(profile)}
    return verify_menu_payloads(profile, payloads)


def repair_menu_resources(fs_root: Path, output: Path, profile: dict | None = None) -> dict:
    """Emit only 68 resource files. Never read or replace AP, CP, MPR or settings."""
    profile = load_menu_profile() if profile is None else profile
    validate_profile(profile)
    if profile.get("resources_only") is not True or len(profile["files"]) != 68:
        raise ValueError("Only the complete resource repair profile is supported")
    if output.exists() or output.is_symlink():
        raise ValueError("Choose a new output directory")
    payloads, evidence = {}, []
    for row in menu_resource_rows(profile):
        source = (fs_root / row["path"]).read_bytes()
        already = len(source) == row["output_bytes"] and digest(source) == row["output_sha256"]
        target = source if already else apply_file(source, row)
        payloads[row["path"]] = target
        evidence.append({"kind": "fs", "path": row["path"], "input_sha256": digest(source),
                         "output_sha256": digest(target), "output_bytes": len(target), "already_repaired": already})
    checks = verify_menu_payloads(profile, payloads)
    manifest = {"schema": 1, "profile": profile["id"], "files": evidence,
                "required_menu_resources": 68, "menu_verification": checks, "resources_only": True,
                "firmware_metadata_changed": False, "program_code_changed": False,
                "camera_io": False, "installable_package_created": False}
    # Preflight ALL banks before creating any output; all input files remain intact.
    destination = output.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()
    for path, payload in payloads.items():
        target = destination / "fs" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(payload)
    with (destination / "manifest.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return manifest


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
    if profile.get("required_menu_resources") == 68:
        payloads = {relative.removeprefix("fs/"): payload for relative, payload in outputs if relative.startswith("fs/share/app/")}
        manifest["required_menu_resources"] = 68
        manifest["menu_verification"] = verify_menu_payloads(profile, payloads)
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
    repair = sub.add_parser("repair-resources", help="Repair only missing sound labels in an exact merged filesystem")
    repair.add_argument("--fs-root", type=Path, required=True)
    repair.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify-resources", help="Check all 68 banks in the extracted final filesystem; no writes")
    verify.add_argument("--fs-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "repair-resources":
            result = repair_menu_resources(args.fs_root, args.output)
        elif args.command == "verify-resources":
            result = verify_menu_resources(args.fs_root)
        else:
            profile = load_profile()
            result = ({key: value for key, value in profile.items() if key != "files"}
                  | {"files": [{k: v for k, v in row.items() if k != "ops"} for row in profile["files"]]}
                  if args.command == "inspect" else prepare(args.ap, args.cp, args.fs_root, args.output, profile))
    except (ValueError, OSError) as error:
        parser.exit(2, str(error) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
