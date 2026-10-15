"""Replay two AF mechanisms in one SHA-256-bound stock CP using Unicorn.

Firmware must be supplied locally. This tool creates synthetic emulator memory;
it does not patch firmware, communicate with a camera, or measure performance.
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct

import unicorn
from unicorn import Uc, UC_ARCH_ARM, UC_HOOK_CODE, UC_MODE_THUMB
from unicorn.arm_const import (
    UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1,
    UC_ARM_REG_R2, UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_SP,
)

SOURCE_SHA256 = "7b9b137d696e5972d20db7f9119076172ed8e0730805d7f0b4c31b87689e2c2b"
SOURCE_SIZE = 16_236_816
BASE = 0x108000
STOP = 0x2E00000
STACK = 0x2F00000
P = 0x2000000
POINTS = {
    0x3B3C88, 0x98ED0E, 0x9975D6, 0x997618, 0x997624,
    0x3AD130, 0x3B31EC, 0x3B3762, 0x3B321E, 0x997940,
    0x98F0F4, 0x585FB8, 0x5866AC, 0x394978, 0x9579D0, 0x9579FE,
    0x47B9FC, 0xA3FFBC, 0x47E12C, 0xA40048, 0x941DD6,
    0x91D12A, 0xA3D66A,
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def need(condition, message):
    if not condition:
        raise ValueError(message)


def word(value):
    return struct.pack("<I", value)


def short(value):
    return struct.pack("<H", value)


class Replay:
    def __init__(self, data):
        self.u = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        self.u.mem_map(0x100000, 0x3000000)
        self.u.mem_write(BASE, data)
        self.trace = []
        self.calls = []
        self.stubs = {}
        self.stop = STOP
        self.u.hook_add(UC_HOOK_CODE, self.hook)

    def hook(self, u, pc, size, context):
        if pc == self.stop:
            u.emu_stop()
            return
        need(len(self.trace) < 10_000, "Instruction budget exceeded")
        self.trace.append(pc)
        if pc in self.stubs:
            self.calls.append(pc)
            self.stubs[pc](u)
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))

    def execute(self, entry, stop=STOP, *, regs=None, memory=None, stubs=None):
        self.stop = stop
        self.trace = []
        self.calls = []
        self.stubs = stubs or {}
        self.u.reg_write(UC_ARM_REG_SP, STACK)
        self.u.reg_write(UC_ARM_REG_LR, STOP | 1)
        for register, value in (regs or {}).items():
            self.u.reg_write(register, value)
        for address, data in (memory or {}).items():
            self.u.mem_write(address, data)
        self.u.emu_start(entry | 1, stop + 2, count=10_100)
        need(self.u.reg_read(UC_ARM_REG_PC) == stop, "Expected stop was not reached")
        return {
            "entry": hex(entry), "stop": hex(stop),
            "return_r0": self.u.reg_read(UC_ARM_REG_R0),
            "instructions": len(self.trace),
            "trace_sha256": sha(b"".join(word(pc) for pc in self.trace)),
            "visited_points": [hex(pc) for pc in sorted(set(self.trace) & POINTS)],
            "stubbed_calls": [hex(pc) for pc in self.calls],
        }

    def classify(self, lens_id, config):
        return self.execute(
            0x9975D6, regs={UC_ARM_REG_R0: lens_id},
            memory={0x104C747: bytes([config]), 0x14F3774: b"\xff"},
        )


def info7_reader(u):
    need(u.reg_read(UC_ARM_REG_R2) == 7, "Expected info7 reader")
    output = u.reg_read(UC_ARM_REG_R0)
    need(STACK - 0x100 <= output < STACK, "Unexpected reader output address")
    u.mem_write(output, word(1) + word(P))
    u.reg_write(UC_ARM_REG_R0, 1)


def logging_stub(u):
    u.reg_write(UC_ARM_REG_R0, 0)


def verify(data):
    need(len(data) == SOURCE_SIZE and sha(data) == SOURCE_SHA256,
         "Unsupported CP: exact stock evidence hash and size are required")
    cases = []
    for lens_id, config in [(0xC530, 0), (0x8050, 0), (0xFFFF, 0),
                            (0xC530, 1), (0xC530, 2)]:
        vm = Replay(data)
        packet = bytearray([255]) * 64
        packet[0xA:0xC] = short(lens_id)
        execution = vm.execute(
            0x3B3C88, 0x3B3CC2, regs={UC_ARM_REG_R0: 0},
            memory={P: bytes(packet), 0x104C747: bytes([config])},
            stubs={0x98ED0E: info7_reader},
        )
        flag = vm.u.mem_read(0x14F3774, 1)[0]
        expected = int(config == 1 or (config == 0 and lens_id >> 14 == 3
                                      and lens_id & 0xFFF != 0xFFF))
        after = bytes(vm.u.mem_read(P, 64))
        need(flag == expected, "info7 classifier result")
        need(after[0xA:0xC] == short(lens_id), "info7 changed lens ID")
        need((0x997624 in vm.trace) == bool(flag), "info7 filter branch")
        need(after != packet if flag else after == packet, "info7 packet effect")
        cases.append({
            "result": "PASS", "stage": "info7_ID_classification_and_filter",
            "lens_id": hex(lens_id), "config": config,
            "fixture": "64-byte all-FF stress response with explicit ID",
            "raw_packet_hex": bytes(packet).hex(), "stored_packet_hex": after.hex(),
            "compatibility_flag": flag, "lens_id_preserved": True,
            "executions": [execution],
        })

    record_va, table_va, speed_va, output_va = (P + i for i in (0x9000, 0xA000, 0xB000, 0xC000))
    for lens_id, config, capabilities in [
        (0xC530, 0, True), (0xD123, 0, True), (0x8050, 0, True),
        (0xFFFF, 0, True), (0xC530, 1, True), (0xC530, 0, False),
    ]:
        vm = Replay(data)
        executions = [vm.classify(lens_id, config)]
        packet = bytearray(64)
        struct.pack_into("<I", packet, 0x21, 0x30209000 if capabilities else 0)
        packet[0x32] = 0x30 if capabilities else 0
        record = bytearray(0x400)
        record[8] = 0x10  # Only command 3D is reported; command 1 is mandatory.
        record[0x2B:0x2D] = short(lens_id)
        record[0x4E] = 4
        memory = {
            P: bytes(packet), record_va: bytes(record), 0x1407744: word(record_va),
            0x14F3209: b"\0", 0x1407538: word(4), 0x14AC250: b"\x60\0",
            0xFBA20C: word(table_va),
            table_va + 0x3D * 6: struct.pack("<3H", 0x3D, 0x3D, 64),
            0xF4F6A4: word(speed_va),
            speed_va: struct.pack("<6H", 7000, 6000, 5000, 9000, 8000, 7000),
        }
        supported = vm.execute(0x3AD130, regs={UC_ARM_REG_R0: 0x3D}, memory=memory)
        need(supported["return_r0"] == 1, "Reported command 3D must be supported")
        executions.append(supported)
        vm.u.mem_write(0x11BCC90 + 0x3D, b"\1")
        vm.u.mem_write(0x11BCC90 + 0x5A, b"\0")
        executions.append(vm.execute(0x3B31EC, 0x3B3762))
        execution = vm.execute(
            0x3B321E, 0x3B324C,
            regs={UC_ARM_REG_R4: P, UC_ARM_REG_R5: 0, UC_ARM_REG_R6: 0},
        )
        need({0x98F0F4, 0x585FB8}.issubset(vm.trace), "Native size reader/copy missing")
        executions.append(execution)
        after = bytes(vm.u.mem_read(record_va + 0x139, 64))
        need(after == bytes(vm.u.mem_read(P, 64)), "Native 64-byte copy mismatch")
        filtered = config == 1 or (config == 0 and lens_id >> 14 == 3
                                   and lens_id & 0xFFF != 0xFFF)
        caps = struct.unpack_from("<I", after, 0x21)[0]
        flags = after[0x32]
        retained = capabilities and not filtered
        need(caps == (0x30209000 if retained else 0), "Stored AF capabilities")
        need(flags == (0x30 if retained else 0), "Stored speed-profile flags")
        executions.append(vm.execute(
            0x394978, regs={UC_ARM_REG_R0: output_va, UC_ARM_REG_R1: output_va + 2},
        ))
        speeds = list(struct.unpack("<2H", vm.u.mem_read(output_va, 4)))
        need(speeds == ([7000, 9000] if retained else [0, 0]), "Speed selection")
        cases.append({
            "result": "PASS", "stage": "info3D_request_filter_copy_speed",
            "lens_id": hex(lens_id), "config": config,
            "physical_capabilities_fixture": capabilities,
            "raw_packet_hex": bytes(packet).hex(), "stored_packet_hex": after.hex(),
            "stored_capabilities": hex(caps), "stored_speed_flags": hex(flags),
            "calibration_fixture": [7000, 6000, 5000, 9000, 8000, 7000],
            "selected_fixture_MaxFcSpeed": speeds, "cached_command3D": 1,
            "cached_command5A": 0, "body_mode_fixture": 4,
            "frequency_fixture": [96, 0], "executions": executions,
        })

    for lens_id, prohibit in [(0xC530, None), (0xC530, 0x14),
                              (0xC530, 0x17), (0x8010, None)]:
        vm = Replay(data)
        context, param_va, result_va = P + 0x1000, P + 0x2000, P + 0x3000
        param = bytearray(0x40)
        struct.pack_into("<I", param, 0, 1)
        struct.pack_into("<I", param, 0xC, lens_id)
        if prohibit is not None:
            param[prohibit] = 1
        executions = [vm.execute(
            0x47B9FC, regs={UC_ARM_REG_R0: context, UC_ARM_REG_R1: param_va,
                            UC_ARM_REG_R2: result_va},
            memory={param_va: bytes(param), context: bytes(0x40), result_va: bytes(0x40)},
        )]
        flags = list(vm.u.mem_read(result_va + 0x10, 4))
        expected = [1, 0, 1, 1] if prohibit is None and lens_id != 0x8010 else [
            0, int(prohibit == 0x14), 0, 0,
        ]
        need(flags == expected, "AF range descriptor flags")
        # Explicit callback handoff: execute the original setter with its two fields.
        executions.append(vm.execute(
            0x941DD6, regs={UC_ARM_REG_R0: flags[0], UC_ARM_REG_R1: flags[2]},
            stubs={0xA3D66A: logging_stub},
        ))
        consumer = vm.execute(0x91D12A)
        need(consumer["return_r0"] == int(bool(flags[0])), "AF range consumer")
        executions.append(consumer)
        cases.append({
            "result": "PASS", "stage": "descriptor_fallback_AF_range_consumer",
            "lens_id": hex(lens_id), "input_category_fixture": 1,
            "input_descriptor_hex": bytes(param).hex(),
            "prohibit_offset": hex(prohibit) if prohibit is not None else None,
            "output_flags_10_to_13": flags,
            "AF_range_consumer_return": consumer["return_r0"],
            "callback_handoff": "Explicit +0x10/+0x12 arguments to original setter",
            "executions": executions,
        })

    vm = Replay(data)
    execution = vm.execute(0x47E12C, regs={UC_ARM_REG_R0: 1, UC_ARM_REG_R1: 0x8011})
    need(execution["return_r0"] == 0xD46734, "Internal profile name pointer")
    name = bytes(vm.u.mem_read(0xD46734, 16)).split(b"\0")[0].decode("ascii")
    need(name == "VX9101", "Internal profile name")
    cases.append({
        "result": "PASS", "stage": "ID_to_internal_profile_name",
        "input_category_fixture": 1, "lens_id": "0x8011",
        "profile_name_pointer": "0xd46734", "profile_name": name,
        "name_source": "Stock CP table, not a hardware string read",
        "executions": [execution],
    })
    return {
        "result": "PASS", "verification_kind": "bounded_original_CP_instruction_replay",
        "source": {"role": "stock CP evidence input", "bytes": len(data), "sha256": sha(data)},
        "script_sha256": sha(Path(__file__).read_bytes()),
        "engine": {"name": "Unicorn", "version": unicorn.__version__},
        "case_count": len(cases), "cases": cases,
        "external_stubs": {
            "0x98ed0e": "info7 response descriptor fixture, in info7 cases only",
            "0xa3d66a": "logging no-op, in range setter cases only",
        },
        "limitations": [
            "Synthetic protocol records, cached support, metadata, mode, frequency and calibration.",
            "Wire-level handshake, serial framing and CRC checks before the selected windows are outside scope.",
            "Range category 1 is supplied as a fixture; its upstream producer and brand meaning are unbound.",
            "Range callback argument handoff is explicit, not a full callback registration/dispatch replay.",
            "The profile-name case does not execute lensfile.bin lookup or transfer.",
            "This replays stock CP only, not the patch helper or every supported patch baseline.",
            "No camera or physical lens ID, AF speed, tracking accuracy or burst FPS was measured.",
            "Values 7000/9000 are calibration fixtures; zero is no speed result at this interface, not total AF failure.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cp", type=Path, required=True, help="Locally supplied stock CP evidence input")
    parser.add_argument("--report", type=Path, help="New JSON output; existing files are refused")
    args = parser.parse_args()
    if args.report is not None:
        need(not args.report.exists(), "Report already exists; choose a new path")
    report = verify(args.cp.read_bytes())
    if args.report is not None:
        with args.report.open("x", encoding="utf-8", newline="\n") as output:
            output.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("result", "source", "engine", "case_count")}, indent=2))


if __name__ == "__main__":
    main()
