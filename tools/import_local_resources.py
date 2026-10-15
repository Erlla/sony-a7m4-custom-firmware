"""Copy explicitly selected existing host resources, never camera images or keys.

This creates an ignored, LOCAL-ONLY resource pack, not a redistributable release.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-tool", type=Path, required=True)
    parser.add_argument("--squashfs", type=Path, required=True)
    parser.add_argument("--destination", type=Path, default=Path(__file__).resolve().parents[1]/"vendor")
    args = parser.parse_args()
    dest = args.destination.resolve()
    files = {}

    def copy(source, relative, upstream, license_status):
        source = source.resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        target = dest/"local"/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        files[relative] = {"sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "size": target.stat().st_size, "upstream": upstream, "license_status": license_status}

    for name in ("fastboot.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll"):
        copy(args.legacy_tool/"bin"/name, "bin/"+name, "https://android.googlesource.com/platform/system/core/+/refs/heads/main/fastboot/", "local-sdk-binary-review-required")
    for name in ("fastboot.bin", "uart_boot.ino.uf2"):
        copy(args.legacy_tool/"bin"/name, "bin/"+name, "https://github.com/DavidBuchanan314/ILCE-7M4-RE", "upstream-license-not-found")
    for source in (args.legacy_tool/"driver").rglob("*"):
        if source.is_file() and source.suffix.lower() in (".inf", ".cat", ".dll", ".properties"):
            copy(source, "driver/"+source.relative_to(args.legacy_tool/"driver").as_posix(), "https://developer.android.com/studio/run/win-usb", "google-sdk-terms-no-public-redistribution-clearance")
    for source in (args.squashfs/"bin").glob("*"):
        if source.suffix.lower() == ".dll" or source.name in ("sqfs2tar.exe", "tar2sqfs.exe", "rdsquashfs.exe"):
            copy(source, "squashfs/"+source.name, "https://github.com/AgentD/squashfs-tools-ng", "GPL-3.0-or-later-tools-LGPL-3.0-or-later-library-see-notices")
    for source in [args.squashfs/"COPYING.md", *(args.squashfs/"licenses").glob("*")]:
        if source.is_file():
            copy(source, "squashfs/licenses/"+source.name, "https://github.com/AgentD/squashfs-tools-ng", "license-text")
    manifest = {"schema": 1, "distribution": "LOCAL-ONLY; upstream payload and Google driver redistribution not cleared", "files": files}
    (dest/"manifest.local.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"copied": len(files), "destination": str(dest), "distribution": manifest["distribution"]}))


if __name__ == "__main__":
    main()
