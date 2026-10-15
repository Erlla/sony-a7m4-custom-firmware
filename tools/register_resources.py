"""Register a user-supplied local resource tree; never download or operate devices."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Directory with bin/, driver/, squashfs/")
    parser.add_argument("--destination", type=Path, default=Path(__file__).resolve().parents[1] / "vendor")
    args = parser.parse_args()
    source, destination = args.directory.resolve(), args.destination.resolve()
    required = ("bin/fastboot.exe", "bin/fastboot.bin", "bin/uart_boot.ino.uf2",
                "driver/android_winusb.inf", "squashfs/sqfs2tar.exe", "squashfs/tar2sqfs.exe")
    if any(not (source / name).is_file() for name in required):
        raise SystemExit("Incomplete resource tree. See docs/setup.md")
    if (destination / "manifest.local.json").exists():
        raise SystemExit("Manifest exists; use a new destination or deliberately manage your local pack")
    selected = []
    for folder, suffixes in (("bin", {".exe", ".dll", ".bin", ".uf2", ".txt", ".md"}),
                             ("driver", {".inf", ".cat", ".dll", ".properties", ".txt", ".md"}),
                             ("squashfs", {".exe", ".dll", ".txt", ".md"})):
        for path in (source / folder).rglob("*"):
            if path.is_file() and path.suffix.lower() in suffixes:
                relative = path.relative_to(source)
                if not path.resolve().is_relative_to(source):
                    raise SystemExit("Linked resource escapes input directory")
                selected.append((path, relative))
    files = {}
    for path, relative in selected:
        target = destination / "local" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.resolve() != target.resolve():
            shutil.copyfile(path, target)
        files[relative.as_posix()] = {"size": target.stat().st_size, "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                                      "source": "user-supplied; record exact upstream revisions separately"}
    manifest = {"schema": 1, "distribution": "LOCAL-ONLY; external component redistribution not cleared", "files": files}
    (destination / "manifest.local.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"resources_registered": len(files), "camera_io": False, "destination": str(destination)}))


if __name__ == "__main__":
    main()
