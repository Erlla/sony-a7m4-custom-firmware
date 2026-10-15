import io
import json
from pathlib import Path
import struct
import pytest

from a7m4.common import ToolError, sha256, read_json, atomic_json
from a7m4.demo import DemoTransport, settings_image
from a7m4.engine import Engine, validate_backup
from a7m4.fat import Fat
from a7m4.patching import set_version, version, new_keypair, public_key, patch_library
from a7m4.transport import parse_partitions, Fastboot
from a7m4.hardware import boot_records, uf2_check
from a7m4.cli import serve, dispatch


@pytest.fixture
def setup(tmp_path):
    transport = DemoTransport()
    engine = Engine(transport=transport, home=tmp_path/"home")
    return engine, transport


def ready(setup):
    engine, device = setup
    engine.connect_backup(enter=False)
    return engine, device


def test_full_backup_required(setup):
    engine, device = setup
    with pytest.raises(ToolError, match="fresh full backup"):
        engine.prepare("set_version", value="2.01")
    assert device.writes == []


def test_complete_manifest_and_all_partitions(setup):
    engine, device = ready(setup)
    manifest = validate_backup(engine.backup)
    assert manifest["complete"] and len(manifest["partitions"]) == 17
    assert engine.status()["write_enabled"]
    assert {r["name"] for r in manifest["partitions"]} == set(device.images)


def test_backup_failure_never_unlocks(setup):
    engine, device = setup
    device.fail_partition = "nflasha8"
    with pytest.raises(ToolError):
        engine.connect_backup(enter=False)
    assert not engine.status()["write_enabled"]
    assert not read_json(engine.backup/"manifest.json")["complete"]
    with pytest.raises(ToolError):
        engine.prepare("set_version", value="0.00")


def test_cancel_backup(setup):
    engine, device = setup
    engine.callback = lambda e: engine.cancel.set() if e["phase"] == "backup" else None
    with pytest.raises(ToolError, match="Cancelled"):
        engine.connect_backup(enter=False)
    assert engine.state == "locked" and not device.writes


def test_each_connection_creates_fresh_backup(setup):
    engine, device = ready(setup)
    original = engine.backup
    engine.connect_backup(enter=False)
    assert engine.backup != original
    assert validate_backup(original)


@pytest.mark.parametrize("value,changes", [("6.02", 0), ("6.03", 1), ("2.01", 2), ("0.00", 2), ("9.99", 2)])
def test_version_changes_only_zero_one_or_two_bytes(value, changes):
    source = settings_image()
    output, evidence = set_version(source, value)
    assert version(output) == value
    assert evidence["changed_bytes"] == changes
    assert Fat(output).read("Backup.bin") == Fat(source).read("Backup.bin")
    assert len(source) == len(output)


@pytest.mark.parametrize("value", ["6.2", "256.01", "-1.00", "6.100", "6.02;whoami", "06.02", "", None])
def test_bad_version_rejected(value):
    with pytest.raises(ToolError):
        set_version(settings_image(), value)


def test_corrupt_fat_copies_rejected():
    image = bytearray(settings_image())
    image[1024] ^= 1
    with pytest.raises(ToolError, match="FAT copies"):
        Fat(image)


def test_cyclic_chain_rejected():
    image = bytearray(settings_image())
    # FAT12 entry 2 points to itself in both FAT copies.
    for start in (512, 1024):
        image[start+3] = 2
        image[start+4] &= 0xf0
    with pytest.raises(ToolError, match="Cyclic"):
        Fat(image).read("Backup.bin")


def test_fat_allocation_does_not_expand():
    with pytest.raises(ToolError, match="allocation"):
        Fat(settings_image()).replace("updater/dat4", b"x"*513)


def test_crosslinked_fat_rejected():
    image = bytearray(settings_image())
    struct.pack_into("<H", image, 4096+26, 2)  # dat4 aliases Backup.bin
    with pytest.raises(ToolError, match="Cross-linked"):
        Fat(image)


def test_confirm_and_readback(setup):
    engine, device = ready(setup)
    source = (engine.backup/"nflasha2.bin").read_bytes()
    plan = engine.prepare("set_version", value="2.01")
    with pytest.raises(ToolError, match="Confirmation"):
        engine.apply(plan["plan_id"], "YES")
    assert not device.writes
    result = engine.apply(plan["plan_id"], plan["confirmation"])
    assert result["status"] == "verified" and device.writes == ["nflasha2"]
    assert version(device.images["nflasha2"]) == "2.01"
    assert (engine.backup/"nflasha2.bin").read_bytes() == source
    with pytest.raises(ToolError):
        engine.apply(plan["plan_id"], plan["confirmation"])


def test_second_change_uses_verified_current_snapshot(setup):
    engine, device = ready(setup)
    p1 = engine.prepare("set_version", value="2.01")
    engine.apply(p1["plan_id"], p1["confirmation"])
    p2 = engine.prepare("set_version", value="3.05")
    assert p2["source_sha256"] == p1["image_sha256"]
    engine.apply(p2["plan_id"], p2["confirmation"])
    assert version(device.images["nflasha2"]) == "3.05"


def test_no_change_does_not_flash(setup):
    engine, device = ready(setup)
    plan = engine.prepare("set_version", value="6.02")
    assert engine.apply(plan["plan_id"], plan["confirmation"])["status"] == "no_change"
    assert not device.writes


def test_readback_disk_reservation_precedes_flash(setup, monkeypatch):
    from collections import namedtuple
    import a7m4.engine as module
    engine, device = ready(setup)
    plan = engine.prepare("set_version", value="2.01")
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(module.shutil, "disk_usage", lambda _:usage(100, 99, 1))
    with pytest.raises(ToolError, match="post-write readback"):
        engine.apply(plan["plan_id"], plan["confirmation"])
    assert not device.writes


def test_readback_failure_locks_reboot_and_next_write(setup):
    engine, device = ready(setup)
    plan = engine.prepare("set_version", value="2.01")
    device.bad_readback = True
    with pytest.raises(ToolError, match="readback"):
        engine.apply(plan["plan_id"], plan["confirmation"])
    assert engine.state == "recovery_required"
    assert read_json(Path(plan["image"]).parent/"receipt.json")["status"] == "failed"
    with pytest.raises(ToolError):
        engine.reboot()


def test_artifact_tamper_rejected(setup):
    engine, device = ready(setup)
    plan = engine.prepare("set_version", value="2.01")
    Path(plan["image"]).write_bytes(b"tamper")
    with pytest.raises(ToolError, match="Prepared image changed"):
        engine.apply(plan["plan_id"], plan["confirmation"])
    assert not device.writes


def test_returned_plan_mutation_does_not_change_authority(setup):
    engine, device = ready(setup)
    plan = engine.prepare("set_version", value="2.01")
    plan["partition"] = "nflashaB0"
    plan["confirmation"] = "YES"
    with pytest.raises(ToolError):
        engine.apply(plan["plan_id"], "YES")
    assert not device.writes


def test_backup_tamper_rejected(setup):
    engine, device = ready(setup)
    with (engine.backup/"nflasha15.bin").open("r+b") as stream:
        stream.write(b"changed")
    with pytest.raises(ToolError, match="Backup damaged"):
        engine.prepare("set_version", value="2.01")
    assert not device.writes


def test_changed_target_rejected(setup):
    engine, device = ready(setup)
    plan = engine.prepare("set_version", value="2.01")
    device.images["nflasha2"], _ = set_version(device.images["nflasha2"], "3.00")
    with pytest.raises(ToolError, match="Target changed"):
        engine.apply(plan["plan_id"], plan["confirmation"])
    assert not device.writes


def test_camera_swap_rejected_despite_same_serial(setup):
    engine, device = ready(setup)
    plan = engine.prepare("set_version", value="2.01")
    device.images["nflashaB0"] = b"other-camera".ljust(65536, b"\0")
    with pytest.raises(ToolError, match="binding changed"):
        engine.apply(plan["plan_id"], plan["confirmation"])
    assert not device.writes


@pytest.mark.parametrize("name", ["nflashaB0", "nflashaB1", "../../escape", "nflasha999"])
def test_boot_and_unknown_restore_blocked(setup, name):
    engine, device = ready(setup)
    with pytest.raises(ToolError):
        engine.prepare("restore", partition=name)
    assert not device.writes


def test_restore_own_backup(setup):
    engine, device = ready(setup)
    plan = engine.prepare("set_version", value="2.01")
    engine.apply(plan["plan_id"], plan["confirmation"])
    restore = engine.prepare("restore", partition="nflasha2")
    engine.apply(restore["plan_id"], restore["confirmation"])
    assert version(device.images["nflasha2"]) == "6.02"


def test_restore_other_camera_backup_rejected(setup, tmp_path):
    engine, _ = ready(setup)
    other = DemoTransport()
    other.images["nflashaB0"] = b"different".ljust(65536, b"\0")
    e2 = Engine(transport=other, home=tmp_path/"other")
    e2.connect_backup(enter=False)
    with pytest.raises(ToolError, match="does not match"):
        engine.prepare("restore", partition="nflasha2", source_backup=e2.backup)


def test_unknown_official_base_rejected(setup):
    engine, _ = ready(setup)
    with pytest.raises(ToolError):
        engine.prepare("restore_official")


def test_unknown_elf_rejected():
    with pytest.raises(ToolError):
        patch_library(b"not an ELF", "libupdaterapi.so")


def test_key_pair_is_local_and_no_overwrite(tmp_path):
    result = new_keypair(tmp_path)
    assert public_key(Path(result["public_key"]).read_bytes())[1] == result["fingerprint"]
    with pytest.raises(ToolError):
        new_keypair(tmp_path)
    with pytest.raises(ToolError, match="public key only"):
        public_key(Path(result["private_key"]).read_bytes())


def test_partition_table_dynamic_and_duplicate_failure():
    table = "\n".join(f"(bootloader) {p.name} {p.start:08x} {p.sectors:08x} {p.kind}" for p in DemoTransport().partitions())
    assert len(parse_partitions(table)) == 17
    with pytest.raises(ToolError):
        parse_partitions(table+"\n(bootloader) nflasha2 0000c000 0000a000 fat")


def test_incomplete_device_table_rejected():
    rows = DemoTransport().partitions()[:-1]
    with pytest.raises(ToolError, match="Incomplete"):
        parse_partitions("\n".join(f"{p.name} {p.start:08x} {p.sectors:08x} {p.kind}" for p in rows))


def test_changed_manifest_cannot_shrink_backup_gate(setup):
    engine, device = ready(setup)
    manifest = read_json(engine.backup/"manifest.json")
    manifest["partitions"] = [p for p in manifest["partitions"] if p["name"] != "nflasha15"]
    atomic_json(engine.backup/"manifest.json", manifest)
    with pytest.raises(ToolError):
        engine.prepare("set_version", value="2.01")
    assert not device.writes


def test_global_lock_excludes_another_engine(setup, tmp_path):
    from a7m4.engine import hardware_lock
    import threading
    results = []
    def attempt():
        try:
            with hardware_lock():
                results.append("entered")
        except ToolError as e:
            results.append(e.code)
    with hardware_lock():
        thread = threading.Thread(target=attempt)
        thread.start()
        thread.join(timeout=3)
    assert results == ["BUSY"]


def test_rpc_no_write_bypass_and_continues_after_bad_json(setup):
    engine, device = setup
    source = io.StringIO('broken\n'+json.dumps({"jsonrpc":"2.0","id":1,"method":"apply","params":{"plan_id":"fake","confirmation":"YES"}})+'\n'+json.dumps({"jsonrpc":"2.0","id":2,"method":"capabilities"})+'\n')
    sink = io.StringIO()
    serve(engine, source, sink)
    results = [json.loads(l) for l in sink.getvalue().splitlines()]
    assert "error" in results[0]
    assert results[1]["error"]["data"]["code"] == "BACKUP_REQUIRED"
    assert results[2]["result"]["arbitrary_commands"] is False
    assert device.writes == []


def test_rpc_rejects_extra_params(setup):
    engine, _ = setup
    with pytest.raises(ToolError):
        dispatch(engine, "apply", {"shell": "anything"})


def test_boot_records_crc():
    import zlib
    records = list(boot_records(b"X"*1025))
    assert len(records) == 8
    for data in records:
        assert struct.unpack_from("<I", data, len(data)-4)[0] == zlib.crc32(data[:-4])


def test_bad_uf2_rejected():
    with pytest.raises(ToolError):
        uf2_check(bytes(512))
