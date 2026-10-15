"""Synthetic camera used by the GUI demo and safety integration tests."""
from pathlib import Path
import struct
import time
from .common import require, ToolError
from .transport import Partition


def settings_image():
    image = bytearray(128*512)
    image[:3] = b"\xeb\x3c\x90"
    image[3:11] = b"DEMO    "
    struct.pack_into("<HBHBHHBHH", image, 11, 512, 1, 1, 2, 64, 128, 0xf8, 1, 32)
    image[510:512] = b"\x55\xaa"
    fat = bytearray(512)
    fat[:3] = b"\xf8\xff\xff"
    for c in (2, 3, 4):
        off = c*3//2
        value = int.from_bytes(fat[off:off+2], "little")
        value = (value & 0xf) | 0xfff0 if c & 1 else (value & 0xf000) | 0xfff
        fat[off:off+2] = value.to_bytes(2, "little")
    image[512:1024] = image[1024:1536] = fat
    def entry(offset, name, attr, cluster, size):
        image[offset:offset+11] = name
        image[offset+11] = attr
        struct.pack_into("<H", image, offset+26, cluster)
        struct.pack_into("<I", image, offset+28, size)
    entry(1536, b"BACKUP  BIN", 0x20, 2, 128)
    entry(1568, b"UPDATER    ", 0x10, 3, 0)
    image[3584:3712] = b"synthetic-personalization".ljust(128, b"\0")
    entry(4096, b"DAT4       ", 0x20, 4, 2)
    image[4608:4610] = b"\x02\x06"
    return bytes(image)


class DemoTransport:
    def __init__(self, slow=False):
        names = ["nflasha"+str(n) for n in (1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 15, 18, 23)] + ["nflashaB0", "nflashaB1"]
        self.images = {n: bytes([i])*65536 for i, n in enumerate(names)}
        self.images["nflasha2"] = settings_image()
        self.rows = sorted([Partition(n, 128*i if "B" not in n else 0, 128, "raw" if "B" in n else "fat") for i, n in enumerate(names)], key=lambda p:p.name)
        self.slow, self.writes = slow, []
        self.fail_partition, self.bad_readback = None, False

    def select(self):
        return {"product": "ILCE-7M4", "transport_serial": "SYNTHETIC-DEMO", "serial_is_unique": False}

    def partitions(self):
        return self.rows

    def dump(self, partition, target, progress=None, cancelled=None):
        require(partition.name != self.fail_partition, "DEMO_READ_FAIL", "Injected read failure")
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = self.images[partition.name]
        with target.open("xb") as f:
            for off in range(0, len(data), 16384):
                if cancelled and cancelled():
                    raise ToolError("CANCELLED", "Cancelled")
                f.write(data[off:off+16384])
                if progress:
                    progress(min(off+16384, len(data)), len(data))
                if self.slow:
                    time.sleep(0.025)

    def flash(self, partition, image):
        self.writes.append(partition.name)
        self.images[partition.name] = Path(image).read_bytes()
        if self.bad_readback:
            self.images[partition.name] = b"\xff" + self.images[partition.name][1:]

    def reboot(self):
        return None
