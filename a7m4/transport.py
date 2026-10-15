"""Strict subprocess fastboot transport; all commands target one selected device."""
from dataclasses import dataclass, asdict
import os
from pathlib import Path
import re
import tempfile
from .common import ToolError, require, run, event

BOOT = {"nflashaB0", "nflashaB1"}
MINIMUM = {*("nflasha"+str(n) for n in (1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 15, 18, 23)), *BOOT}


@dataclass(frozen=True)
class Partition:
    name: str
    start: int
    sectors: int
    kind: str

    @property
    def size(self):
        return self.sectors * 512

    def json(self):
        return asdict(self)


def parse_partitions(text):
    rows = []
    for line in text.splitlines():
        line = re.sub(r"^\s*\(bootloader\)\s*", "", line).strip()
        match = re.fullmatch(r"(nflasha(?:[0-9]+|B[01]))\s+([0-9a-fA-F]{8})\s+([0-9a-fA-F]{8})\s+(\S+)", line)
        if match:
            name, start, size, kind = match.groups()
            rows.append(Partition(name, int(start, 16), int(size, 16), kind))
        elif re.match(r"nflasha(?:[0-9]+|B[01])\b", line):
            raise ToolError("PARTITION_TABLE", f"Unrecognized partition row: {line}")
    require(len(rows) == len({p.name for p in rows}) and MINIMUM.issubset(p.name for p in rows), "PARTITION_TABLE", "Incomplete or duplicate partition table")
    require(all(0 < p.size <= 8*1024**3 and p.start+p.sectors <= 0xffffffff for p in rows), "PARTITION_TABLE", "Invalid partition size")
    normal = sorted((p for p in rows if p.name not in BOOT), key=lambda p: p.start)
    require(all(a.start+a.sectors <= b.start for a, b in zip(normal, normal[1:])), "PARTITION_TABLE", "Overlapping partitions")
    return sorted(rows, key=lambda p: p.name)


class Fastboot:
    chunk_sectors = 8 * 1024 * 1024 // 512

    def __init__(self, assets):
        self.assets, self.serial = assets, None

    def devices(self):
        out = run([self.assets.get("bin/fastboot.exe"), "devices"], timeout=15).decode("utf-8", "replace")
        return [line.split()[0] for line in out.splitlines() if re.fullmatch(r"\S+\s+fastboot\s*", line)]

    def select(self):
        devices = self.devices()
        require(len(devices) == 1, "DEVICE_COUNT", f"Expected one fastboot device; found {len(devices)}", "Connect one A7M4 only; check the camera USB cable and driver.")
        if self.serial:
            require(self.serial == devices[0], "DEVICE_CHANGED", "Device changed; reconnect and back up again")
        self.serial = devices[0]
        out = self.command("getvar", "product").decode("utf-8", "replace")
        require(re.search(r"product:\s*ILCE-7M4\s*(?:\r?\n|$)", out), "MODEL", "Device does not report ILCE-7M4")
        return {"product": "ILCE-7M4", "transport_serial": self.serial,
                "serial_is_unique": False}

    def command(self, *args, timeout=300):
        require(self.serial, "NOT_CONNECTED", "Select a device first")
        return run([self.assets.get("bin/fastboot.exe"), "-s", self.serial, *args], timeout=timeout)

    def partitions(self):
        return parse_partitions(self.command("oem", "partition").decode("utf-8", "replace"))

    def dump(self, partition, target, progress=None, cancelled=None):
        target = Path(target)
        partial = target.with_suffix(target.suffix + ".partial")
        require(not target.exists() and not partial.exists(), "EXISTS", "Backup destination already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with partial.open("xb") as dest, tempfile.TemporaryDirectory(prefix="a7m4-read-") as temp:
                chunk_path = Path(temp) / "chunk.bin"
                for off in range(0, partition.sectors, self.chunk_sectors):
                    if cancelled and cancelled():
                        raise ToolError("CANCELLED", "Backup cancelled; writes remain locked")
                    count = min(self.chunk_sectors, partition.sectors-off)
                    self.command("oem", "partition", "dump", partition.name, f"{off:x}", f"{count:x}")
                    chunk_path.unlink(missing_ok=True)
                    self.command("get_staged", chunk_path)
                    require(chunk_path.is_file() and chunk_path.stat().st_size == count*512, "SHORT_READ", f"Incomplete read: {partition.name}")
                    dest.write(chunk_path.read_bytes())
                    if progress:
                        progress((off+count)*512, partition.size)
                dest.flush()
                os.fsync(dest.fileno())
            require(partial.stat().st_size == partition.size, "SIZE", "Backup size mismatch")
            os.replace(partial, target)
        except Exception:
            # A partial file is deliberately never accepted as a backup.
            raise

    def flash(self, partition, image):
        require(partition.name not in BOOT, "BOOT_READ_ONLY", "eMMC boot hardware partitions are backup-only")
        require(Path(image).stat().st_size == partition.size, "SIZE", "Image must match the entire partition size")
        self.command("flash", partition.name, image, timeout=1800)

    def reboot(self):
        self.command("reboot")
