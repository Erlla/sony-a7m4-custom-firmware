"""Bounded FAT12/16 reader and in-chain writer; no filesystem reformatting."""
import math
import struct
from .common import require


class Fat:
    def __init__(self, data):
        self.data = bytearray(data)
        require(len(data) >= 512 and data[510:512] == b"\x55\xaa", "FAT", "Missing FAT boot signature")
        self.bps = struct.unpack_from("<H", data, 11)[0]
        self.spc = data[13]
        self.reserved = struct.unpack_from("<H", data, 14)[0]
        self.nfat = data[16]
        self.roots = struct.unpack_from("<H", data, 17)[0]
        sectors = struct.unpack_from("<H", data, 19)[0] or struct.unpack_from("<I", data, 32)[0]
        self.spf = struct.unpack_from("<H", data, 22)[0]
        require(self.bps in (512, 1024, 2048, 4096) and self.spc in (1, 2, 4, 8, 16, 32, 64, 128) and self.nfat in (1, 2) and self.spf and self.reserved and self.roots, "FAT", "Unsupported FAT geometry")
        self.cluster_size = self.bps * self.spc
        self.fat_start = self.reserved * self.bps
        self.fat_size = self.spf * self.bps
        self.root_start = self.fat_start + self.nfat * self.fat_size
        root_sectors = math.ceil(self.roots * 32 / self.bps)
        self.data_start = self.root_start + root_sectors * self.bps
        self.total = sectors * self.bps
        require(self.data_start < self.total <= len(data), "FAT", "FAT geometry outside partition")
        self.cluster_count = (self.total - self.data_start) // self.cluster_size
        self.bits = 12 if self.cluster_count < 4085 else 16
        require(self.cluster_count < 65525, "FAT", "FAT32 is not supported")
        require(math.ceil((self.cluster_count + 2) * self.bits / 8) <= self.fat_size, "FAT", "FAT allocation table too small")
        for i in range(1, self.nfat):
            require(data[self.fat_start:self.fat_start+self.fat_size] == data[self.fat_start+i*self.fat_size:self.fat_start+(i+1)*self.fat_size], "FAT", "FAT copies disagree")
        self.validate_ownership()

    def validate_ownership(self):
        owners = set()
        def walk(first, depth):
            require(depth < 64, "FAT", "Directory nesting is too deep")
            for name, (_, cluster, size, attr) in self.entries(first).items():
                if name in (".", ".."):
                    continue
                chain = self.chain(cluster)
                require(not owners.intersection(chain), "FAT", "Cross-linked files or directories")
                owners.update(chain)
                require(size <= len(chain)*self.cluster_size, "FAT", "File exceeds its allocation")
                if attr & 16:
                    require(cluster >= 2, "FAT", "Directory has no cluster")
                    walk(cluster, depth+1)
        walk(None, 0)

    def offset(self, cluster):
        require(2 <= cluster < self.cluster_count + 2, "FAT", "Cluster outside filesystem")
        return self.data_start + (cluster - 2) * self.cluster_size

    def chain(self, first):
        result, visited, c = [], set(), first
        while c >= 2:
            require(c not in visited and c < self.cluster_count+2, "FAT", "Cyclic or out-of-range cluster chain")
            visited.add(c)
            result.append(c)
            off = self.fat_start + (c * 3 // 2 if self.bits == 12 else c * 2)
            value = struct.unpack_from("<H", self.data, off)[0]
            if self.bits == 12:
                value = (value >> 4 if c & 1 else value) & 0xfff
            if value >= (0xff8 if self.bits == 12 else 0xfff8):
                return result
            require(2 <= value < (0xff0 if self.bits == 12 else 0xfff0), "FAT", "Free, bad or reserved cluster in file")
            c = value
        require(not result, "FAT", "Unterminated FAT chain")
        return result

    def entries(self, first=None):
        ranges = [(self.root_start, self.roots * 32)] if first is None else [(self.offset(c), self.cluster_size) for c in self.chain(first)]
        entries = {}
        for start, size in ranges:
            for off in range(start, start + size, 32):
                row = self.data[off:off+32]
                if row[0] == 0:
                    return entries
                if row[0] == 0xe5 or row[11] == 0x0f or row[11] & 8:
                    continue
                name = bytes(row[:8]).decode("ascii", "replace").rstrip()
                ext = bytes(row[8:11]).decode("ascii", "replace").rstrip()
                name += "." + ext if ext else ""
                require(name not in entries, "FAT", "Duplicate short filename")
                entries[name] = (off, struct.unpack_from("<H", row, 26)[0], struct.unpack_from("<I", row, 28)[0], row[11])
        return entries

    def locate(self, path):
        first = None
        parts = path.strip("/").upper().split("/")
        for idx, part in enumerate(parts):
            require(part not in ("", ".", ".."), "FAT", "Invalid filesystem path")
            entry = self.entries(first).get(part)
            require(entry is not None, "FAT_FILE", f"Missing FAT file: {path}")
            if idx < len(parts)-1:
                require(entry[3] & 16, "FAT", "Expected a directory")
                first = entry[1]
        require(not entry[3] & 16, "FAT", "Expected a regular file")
        return entry

    def read(self, path):
        _, first, size, _ = self.locate(path)
        chain = self.chain(first)
        require(size <= len(chain) * self.cluster_size, "FAT", "File exceeds cluster chain")
        return b"".join(self.data[self.offset(c):self.offset(c)+self.cluster_size] for c in chain)[:size]

    def replace(self, path, value):
        entry, first, _, _ = self.locate(path)
        chain = self.chain(first)
        require(len(value) <= len(chain) * self.cluster_size, "FAT_CAPACITY", f"Replacement exceeds existing allocation: {path}")
        # Retain allocation and unused tail bytes; only content and size may change.
        for idx, c in enumerate(chain):
            chunk = value[idx*self.cluster_size:(idx+1)*self.cluster_size]
            if not chunk:
                break
            off = self.offset(c)
            self.data[off:off+len(chunk)] = chunk
        struct.pack_into("<I", self.data, entry+28, len(value))
        require(self.read(path) == value, "FAT_VERIFY", "FAT replacement readback mismatch")

    def bytes(self):
        return bytes(self.data)
