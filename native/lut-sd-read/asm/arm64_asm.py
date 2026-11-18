"""Minimal AArch64 encoder for LUT SD page-flip caves (no external deps)."""
from __future__ import annotations

import struct

EQ, NE, CS, CC = 0, 1, 2, 3
NOP = bytes.fromhex("1f2003d5")


class Asm:
    def __init__(self, base: int):
        self.base = base
        self.words: list[int] = []
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple] = []

    def lab(self, n: str) -> None:
        self.labels[n] = len(self.words)

    def emit(self, w: int) -> None:
        self.words.append(w & 0xFFFFFFFF)

    def ret(self) -> None:
        self.emit(0xD65F03C0)

    def movz_w(self, rd: int, imm: int) -> None:
        self.emit(0x52800000 | ((imm & 0xFFFF) << 5) | rd)

    def mov_w(self, rd: int, rm: int) -> None:
        self.emit(0x2A0003E0 | (rm << 16) | rd)

    def mov_x(self, rd: int, rm: int) -> None:
        self.emit(0xAA0003E0 | (rm << 16) | rd)

    def add_imm_w(self, rd: int, rn: int, imm: int) -> None:
        self.emit(0x11000000 | ((imm & 0xFFF) << 10) | (rn << 5) | rd)

    def add_imm_x(self, rd: int, rn: int, imm: int, lsl12: bool = False) -> None:
        self.emit(
            0x91000000
            | ((1 if lsl12 else 0) << 22)
            | ((imm & 0xFFF) << 10)
            | (rn << 5)
            | rd
        )

    def sub_imm_x(self, rd: int, rn: int, imm: int) -> None:
        self.emit(0xD1000000 | ((imm & 0xFFF) << 10) | (rn << 5) | rd)

    def sub_imm_w(self, rd: int, rn: int, imm: int) -> None:
        self.emit(0x51000000 | ((imm & 0xFFF) << 10) | (rn << 5) | rd)

    def subs_imm_w(self, rd: int, rn: int, imm: int) -> None:
        self.emit(0x71000000 | ((imm & 0xFFF) << 10) | (rn << 5) | rd)

    def ldr_w(self, rt: int, rn: int, imm: int = 0) -> None:
        self.emit(0xB9400000 | ((imm // 4) << 10) | (rn << 5) | rt)

    def str_w(self, rt: int, rn: int, imm: int = 0) -> None:
        self.emit(0xB9000000 | ((imm // 4) << 10) | (rn << 5) | rt)

    def cmp_imm_w(self, rn: int, imm: int) -> None:
        self.emit(0x71000000 | ((imm & 0xFFF) << 10) | (rn << 5) | 31)

    def cmp_w(self, rn: int, rm: int) -> None:
        self.emit(0x6B00001F | (rm << 16) | (rn << 5))

    def add_w(self, rd: int, rn: int, rm: int) -> None:
        self.emit(0x0B000000 | (rm << 16) | (rn << 5) | rd)

    def csinc_w(self, rd: int, rn: int, rm: int, cond: int) -> None:
        self.emit(0x1A800400 | (rm << 16) | (cond << 12) | (rn << 5) | rd)

    def csel_w(self, rd: int, rn: int, rm: int, cond: int) -> None:
        self.emit(0x1A800000 | (rm << 16) | (cond << 12) | (rn << 5) | rd)

    def stp_x(self, a: int, b: int, rn: int, imm: int) -> None:
        self.emit(0xA9000000 | ((imm // 8) << 15) | (b << 10) | (rn << 5) | a)

    def ldp_x(self, a: int, b: int, rn: int, imm: int) -> None:
        self.emit(0xA9400000 | ((imm // 8) << 15) | (b << 10) | (rn << 5) | a)

    def _fix(self, kind: str, target, extra=None) -> None:
        i = len(self.words)
        self.words.append(0)
        self.fixups.append((i, kind, target, extra))

    def cbz_w(self, rt: int, t: str) -> None:
        self._fix("cbz", t, rt)

    def b(self, t) -> None:
        self._fix("b", t)

    def bcond(self, c: int, t) -> None:
        self._fix("bcond", t, c)

    def adrp(self, rd: int, page: int) -> None:
        self._fix("adrp", page, rd)

    def resolve(self) -> bytes:
        for idx, kind, target, extra in self.fixups:
            pc = self.base + idx * 4
            tgt = self.base + self.labels[target] * 4 if isinstance(target, str) else int(target)
            if kind == "b":
                imm = (tgt - pc) // 4
                self.words[idx] = 0x14000000 | (imm & 0x3FFFFFF)
            elif kind == "bcond":
                imm = (tgt - pc) // 4
                self.words[idx] = 0x54000000 | ((imm & 0x7FFFF) << 5) | int(extra)
            elif kind == "cbz":
                imm = (tgt - pc) // 4
                self.words[idx] = 0x34000000 | ((imm & 0x7FFFF) << 5) | int(extra)
            elif kind == "adrp":
                imm = ((int(target) & ~0xFFF) - (pc & ~0xFFF)) >> 12
                self.words[idx] = (
                    0x90000000
                    | ((imm & 3) << 29)
                    | (((imm >> 2) & 0x7FFFF) << 5)
                    | int(extra)
                )
            else:
                raise ValueError(kind)
        return b"".join(struct.pack("<I", w) for w in self.words)


def enc_bl(pc: int, tgt: int) -> bytes:
    return struct.pack("<I", 0x94000000 | (((tgt - pc) // 4) & 0x3FFFFFF))


def enc_b(pc: int, tgt: int) -> bytes:
    return struct.pack("<I", 0x14000000 | (((tgt - pc) // 4) & 0x3FFFFFF))
