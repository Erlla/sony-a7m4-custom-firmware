"""Build clear / total / wrap caves for LUT SD edge page-flip."""
from __future__ import annotations

from .arm64_asm import EQ, NE, CS, CC, Asm


def build_clear(*, cave: int, bss: int, continue_va: int) -> bytes:
    a = Asm(cave)
    a.adrp(10, bss)
    a.str_w(31, 10, bss & 0xFFF)
    a.b(continue_va)
    return a.resolve()


def build_total(*, cave: int, bss: int) -> bytes:
    a = Asm(cave)
    a.str_w(8, 21, 0xC)
    a.adrp(10, bss)
    a.str_w(8, 10, (bss + 4) & 0xFFF)
    a.str_w(1, 10, bss & 0xFFF)
    a.add_imm_x(8, 19, 0x3F, lsl12=True)
    a.ret()
    return a.resolve()


def build_wrap(*, cave: int, bss: int, msg_page: int, msg_off: int) -> bytes:
    """Edge page-flip without sync producer/refresh (those hung the UI thread).

    Entry: w8=row, w1=dir, x19=list. Exit: w8=new row, x0=x19 (required).
    """
    a = Asm(cave)
    a.sub_imm_x(31, 31, 0x30)
    a.stp_x(30, 19, 31, 0x20)
    a.stp_x(20, 21, 31, 0x10)
    a.stp_x(22, 23, 31, 0x0)

    a.mov_w(20, 8)
    a.mov_w(21, 1)

    a.adrp(22, bss)
    a.ldr_w(23, 22, bss & 0xFFF)
    a.ldr_w(10, 22, (bss + 4) & 0xFFF)

    a.cmp_imm_w(21, 2)
    a.bcond(NE, "check_prev")
    a.cmp_imm_w(20, 0x10)
    a.bcond(NE, "check_prev")
    a.add_imm_w(9, 23, 0x10)
    a.cmp_w(9, 10)
    a.bcond(CS, "gray")
    a.str_w(9, 22, bss & 0xFFF)
    a.mov_w(11, 9)
    a.movz_w(12, 0)
    a.b("do_page")

    a.lab("check_prev")
    a.cmp_imm_w(21, 1)
    a.bcond(NE, "do_wrap")
    a.cmp_imm_w(20, 0)
    a.bcond(NE, "do_wrap")
    a.cbz_w(23, "gray")
    a.sub_imm_w(9, 23, 0x10)
    a.str_w(9, 22, bss & 0xFFF)
    a.mov_w(11, 9)
    a.movz_w(12, 0x10)
    a.b("do_page")

    a.lab("gray")
    a.mov_w(8, 20)
    a.b("epilogue")

    a.lab("do_wrap")
    a.mov_w(8, 20)
    a.cmp_imm_w(8, 0x10)
    a.movz_w(9, 0x10)
    a.csinc_w(8, 31, 8, EQ)
    a.cmp_imm_w(21, 2)
    a.csinc_w(10, 9, 31, NE)
    a.add_w(8, 8, 10)
    a.subs_imm_w(10, 8, 0x11)
    a.csel_w(8, 8, 10, CC)
    a.sub_imm_w(10, 8, 1)
    a.cmp_imm_w(8, 0)
    a.csel_w(8, 9, 10, EQ)
    a.b("epilogue")

    a.lab("do_page")
    a.adrp(9, msg_page)
    a.add_imm_x(9, 9, msg_off)
    a.ldr_w(8, 9, 0)
    a.add_imm_w(8, 8, 1)
    a.str_w(8, 9, 0)
    a.movz_w(8, 2)
    a.str_w(8, 9, 8)
    a.str_w(31, 9, 0x68)
    a.str_w(11, 9, 0x18)
    a.mov_w(8, 12)

    a.lab("epilogue")
    a.mov_x(0, 19)
    a.ldp_x(22, 23, 31, 0x0)
    a.ldp_x(20, 21, 31, 0x10)
    a.ldp_x(30, 19, 31, 0x20)
    a.add_imm_x(31, 31, 0x30)
    a.ret()
    return a.resolve()
