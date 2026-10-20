"""Offline-only tests. No real USB, serial, fastboot subprocess or camera access."""
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from a7m4 import sd_recovery as core, recover_sd
from a7m4.transport import Partition, Fastboot


def entry(image, offset, name, attr=0x20, cluster=0, size=0):
    image[offset:offset + 32] = bytes(32)
    image[offset:offset + 11] = name.encode('ascii').ljust(11, b' ')
    image[offset + 11] = attr
    struct.pack_into('<H', image, offset + 26, cluster)
    struct.pack_into('<I', image, offset + 28, size)


def settings_image():
    # Synthetic fixture adapted from the frozen toolkit's demo.py, no camera data.
    image = bytearray(128 * 512)
    image[:3], image[3:11] = b'\xeb\x3c\x90', b'DEMO    '
    struct.pack_into('<HBHBHHBHH', image, 11, 512, 1, 1, 2, 64, 128, 0xf8, 1, 32)
    image[510:512] = b'\x55\xaa'
    fat = bytearray(512)
    fat[:3] = b'\xf8\xff\xff'
    for cluster in (2, 3, 4):
        off = cluster * 3 // 2
        value = int.from_bytes(fat[off:off + 2], 'little')
        value = (value & 0xf) | 0xfff0 if cluster & 1 else (value & 0xf000) | 0xfff
        fat[off:off + 2] = value.to_bytes(2, 'little')
    image[512:1024] = image[1024:1536] = fat
    entry(image, 1536, 'BACKUP  BIN', cluster=2, size=128)
    entry(image, 1568, 'UPDATER', attr=0x10, cluster=3)
    image[3584:3712] = b'synthetic-personalization'.ljust(128, b'\0')
    entry(image, 4096, 'DAT4', cluster=4, size=2)
    entry(image, 4128, 'COMP')
    entry(image, 4160, 'MEDIAU~1')
    image[4608:4610] = b'\x37\x06'
    return bytes(image).ljust(core.SETTINGS_SIZE, b'\0')


class FakeTransport:
    """A memory-backed device; the test never constructs a real transport."""
    def __init__(self, settings, fault=None):
        self.data = {name: b'x' * 512 for name in core.BACKUP_NAMES}
        self.data['nflasha2'] = settings
        self.fault, self.calls, self.selections, self.tables = fault, [], 0, 0

    def select(self):
        self.selections += 1
        return dict(product='ILCE-7M4' if self.fault != 'model' else 'OTHER',
                    transport_serial='fake-changed' if self.selections == 2 and self.fault == 'identity' else 'FAKE',
                    serial_is_unique=False)

    def partitions(self):
        self.tables += 1
        return [Partition(n, i * 100000 + (1 if self.fault == 'layout_changed' and self.tables == 2 else 0),
                          len(b) // 512, 'TEST') for i, (n, b) in enumerate(self.data.items())]

    def dump(self, part, target):
        target = Path(target)
        self.calls.append(('dump', part.name, target.name))
        if self.fault == 'backup' and part.name == 'nflasha8':
            raise core.ToolError('INJECTED', 'backup fault')
        data = self.data[part.name]
        if self.fault == 'short_backup' and part.name == 'nflashaB0':
            data = data[:-1]
        if target.parent.name == 'prewrite' and self.fault == 'stale' and part.name == 'nflashaB1':
            data = b'changed'.ljust(len(data), b'\0')
        if target.name == 'nflasha2.after.bin' and self.fault == 'readback':
            data = b'!' + data[1:]
        target.write_bytes(data)
        folder = target.parent if target.name.endswith('.before.bin') else target.parent.parent
        if self.fault == 'backup_changed' and part.name == 'nflasha13' and target.name.endswith('.before.bin'):
            (folder / 'nflashaB0.before.bin').write_bytes(b'y' * 512)
        if target.parent.name == 'prewrite' and part.name == 'nflasha2' and self.fault == 'candidate_changed':
            (folder / 'nflasha2.MODE5.candidate.bin').write_bytes(b'z' * core.SETTINGS_SIZE)

    def write_settings(self, part, image, expected_hash):
        self.calls.append(('flash', part.name))
        if self.fault == 'flash':
            raise core.ToolError('INJECTED', 'write may be partial')
        assert part.name == 'nflasha2' and core.sha256(image) == expected_hash
        self.data[part.name] = Path(image).read_bytes()

    def reboot(self):
        self.calls.append(('reboot',))
        if self.fault == 'reboot':
            raise core.ToolError('TIMEOUT', 'reboot outcome unknown')


class Versions(unittest.TestCase):
    def test_bcd_not_decimal_minor(self):
        self.assertEqual(core.decode_version(bytes.fromhex('3306')), 633)
        self.assertEqual(core.encode_version(637), bytes.fromhex('3706'))

    def test_roundtrip(self):
        for value in (0, 1, 602, 636, 637, 699, 1234, 9999):
            self.assertEqual(core.decode_version(core.encode_version(value)), value)

    def test_invalid(self):
        for raw in (b'', b'\x37', b'\x3a\x06', b'\x37\xf6', b'000'):
            with self.assertRaises(core.ToolError):
                core.decode_version(raw)
        for value in (-1, 10000, True, '637'):
            with self.assertRaises(core.ToolError):
                core.encode_version(value)


class Trigger(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = settings_image()

    def test_only_allowed_bytes_and_preserve_personalization(self):
        candidate, plan = core.make_trigger(self.original)
        old, new = core.Fat(self.original), core.Fat(candidate)
        self.assertEqual(new.read('UPDATER/DAT4'), b'\0\0')
        self.assertEqual(set(core.all_files(new)) - set(core.all_files(old)), {'UPDATER/MODE', 'UPDATER/MODE5'})
        for path, value in core.all_files(old).items():
            if path != 'UPDATER/DAT4':
                self.assertEqual(new.read(path), value)
        self.assertEqual(candidate[:old.data_start], self.original[:old.data_start])
        self.assertEqual(plan['target'], '卡槽1:/BODYDATA.DAT')
        self.assertFalse(plan['target_version_known_to_host'])
        self.assertEqual(plan['allowed_ranges'], [(4608, 2), (4192, 32), (4224, 32)])
        self.assertEqual(new.read('UPDATER/COMP'), b'')
        self.assertEqual(new.read('UPDATER/MEDIAU~1'), b'')

    def test_idempotent_trigger(self):
        one, _ = core.make_trigger(self.original)
        two, plan = core.make_trigger(one)
        self.assertEqual(one, two)
        self.assertEqual(plan['changed_bytes'], 0)

    def test_existing_flags_only_dat4_changes(self):
        image = bytearray(self.original)
        entry(image, 4192, 'MODE')
        entry(image, 4224, 'MODE5')
        _, plan = core.make_trigger(bytes(image))
        self.assertEqual(plan['created_flags'], [])
        self.assertEqual(plan['changed_offsets'], [4608, 4609])

    def test_only_one_missing_flag(self):
        image = bytearray(self.original)
        entry(image, 4192, 'MODE')
        _, plan = core.make_trigger(bytes(image))
        self.assertEqual(plan['created_flags'], ['MODE5'])

    def test_conflicting_modes(self):
        for flag in ('MODE1', 'MODE2', 'MODE3', 'MODE4', 'MODE6', 'MODE7', 'UINCOMP'):
            image = bytearray(self.original)
            entry(image, 4192, flag)
            with self.assertRaises(core.ToolError) as caught:
                core.make_trigger(bytes(image))
            self.assertEqual(caught.exception.code, 'OTHER_UPDATE_MODE')

    def test_flag_with_allocation_rejected(self):
        image = bytearray(self.original)
        entry(image, 4192, 'MODE', cluster=2)
        with self.assertRaises(core.ToolError):
            core.make_trigger(bytes(image))  # Also rejects cross-link with Backup.bin.

    def test_flag_directory_rejected(self):
        image = bytearray(self.original)
        entry(image, 4192, 'MODE', attr=0x10)
        with self.assertRaises(core.ToolError):
            core.make_trigger(bytes(image))

    def test_no_directory_space(self):
        image = bytearray(self.original)
        for i, off in enumerate(range(4192, 4608, 32)):
            entry(image, off, 'F' + str(i))
        with self.assertRaises(core.ToolError) as caught:
            core.make_trigger(bytes(image))
        self.assertEqual(caught.exception.code, 'NO_DIRECTORY_ROOM')

    def test_hidden_directory_tail(self):
        image = bytearray(self.original)
        image[4225] = 1
        with self.assertRaises(core.ToolError) as caught:
            core.make_trigger(bytes(image))
        self.assertEqual(caught.exception.code, 'DIR_TAIL_NOT_EMPTY')

    def test_malformed_size_fat_and_version(self):
        with self.assertRaises(core.ToolError):
            core.make_trigger(self.original[:-1])
        for offset, value in ((510, 0), (1024, 0), (4608, 0xff), (4609, 0x07)):
            image = bytearray(self.original)
            image[offset] = value
            with self.assertRaises(core.ToolError):
                core.make_trigger(bytes(image))


class Workflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = settings_image()

    def run_case(self, fault=None, ready=False):
        settings = core.make_trigger(self.original)[0] if ready else self.original
        fake = FakeTransport(settings, fault)
        with tempfile.TemporaryDirectory(prefix='sd-recovery-test-') as tmp:
            folder = Path(tmp)
            def inspect(image, config):
                if fault == 'updater':
                    raise core.ToolError('UPDATER_PROFILE', 'unknown initrd')
                return dict(mock=True)
            if fault:
                with self.assertRaises(core.ToolError):
                    core.recover(fake, folder, {}, inspect, disk_free=0 if fault == 'disk' else 1 << 32, notify=lambda x: None)
            else:
                core.recover(fake, folder, {}, inspect, disk_free=1 << 32, notify=lambda x: None)
            result = json.loads((folder / 'result.json').read_text('utf8'))
            if result.get('readback_verified'):
                self.assertEqual(core.sha256(folder / 'nflasha2.after.bin'), result['candidate_sha256'])
            return fake.calls, result

    def test_success_one_write_then_readback_then_one_reboot(self):
        calls, result = self.run_case()
        self.assertEqual([c for c in calls if c[0] == 'flash'], [('flash', 'nflasha2')])
        self.assertEqual(calls[-2:], [('dump', 'nflasha2', 'nflasha2.after.bin'), ('reboot',)])
        self.assertEqual(result['status'], 'SD_UPDATE_TRIGGERED_PENDING_CAMERA')
        self.assertTrue(result['readback_verified'])
        self.assertFalse(result['update_completed'])
        self.assertFalse(result['full_eMMC_backup'])
        self.assertFalse(result['NOR_direct_write'])

    def test_already_ready_does_not_flash(self):
        calls, result = self.run_case(ready=True)
        self.assertFalse(result['flash_attempted'])
        self.assertFalse(any(c[0] == 'flash' for c in calls))
        self.assertEqual(calls[-1], ('reboot',))

    def test_all_prewrite_failures_block_flash_and_reboot(self):
        for fault in ('model', 'disk', 'backup', 'short_backup', 'backup_changed', 'updater',
                      'identity', 'layout_changed', 'stale', 'candidate_changed'):
            with self.subTest(fault=fault):
                calls, result = self.run_case(fault)
                self.assertEqual(result['status'], 'STOPPED_KEEP_FASTBOOT')
                self.assertFalse(any(c[0] in ('flash', 'reboot') for c in calls))

    def test_uncertain_flash_not_retried_or_rebooted(self):
        calls, result = self.run_case('flash')
        self.assertEqual(sum(c[0] == 'flash' for c in calls), 1)
        self.assertFalse(any(c[0] == 'reboot' for c in calls))
        self.assertTrue(result['flash_attempted'])
        self.assertFalse(result['readback_verified'])

    def test_readback_failure_no_reboot(self):
        calls, result = self.run_case('readback')
        self.assertFalse(any(c[0] == 'reboot' for c in calls))
        self.assertFalse(result['readback_verified'])

    def test_reboot_timeout_records_uncertain_no_retry(self):
        calls, result = self.run_case('reboot')
        self.assertEqual(sum(c[0] == 'reboot' for c in calls), 1)
        self.assertTrue(result['readback_verified'])
        self.assertEqual(result['status'], 'REBOOT_OUTCOME_UNCERTAIN')


class CommandScope(unittest.TestCase):
    def test_forbidden_commands_never_reach_backend(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(Fastboot, 'command') as backend:
            transport = core.RecoveryTransport(tmp)
            for args in (('erase', 'nflasha2'), ('flash', 'nflasha15', 'x'),
                         ('oem', 'program'), ('reboot-bootloader',), ('flash', 'nflashaB0', 'x'),
                         ('flash', 'nflasha2', 'x')):
                with self.assertRaises(core.ToolError):
                    transport.command(*args)
            backend.assert_not_called()

    def test_arm_consumed_on_backend_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'image.bin'
            path.write_bytes(b'\0' * core.SETTINGS_SIZE)
            transport = core.RecoveryTransport(tmp)
            part = Partition('nflasha2', 1, core.SETTINGS_SIZE // 512, 'TEST')
            with patch.object(Fastboot, 'command', side_effect=core.ToolError('FAIL', 'uncertain')) as backend:
                with self.assertRaises(core.ToolError):
                    transport.write_settings(part, path, core.sha256(path))
                with self.assertRaises(core.ToolError) as caught:
                    transport.command('flash', 'nflasha2', path)
                self.assertEqual(caught.exception.code, 'WRITE_NOT_ARMED')
                self.assertEqual(backend.call_count, 1)

    def test_only_registered_fastboot_resources_are_required(self):
        from a7m4.common import Assets
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / 'local/bin').mkdir(parents=True)
            files = {}
            for name in ('fastboot.exe', 'AdbWinApi.dll', 'AdbWinUsbApi.dll'):
                path = base / 'local/bin' / name
                path.write_bytes(b'synthetic, never executed')
                files['bin/' + name] = {'sha256': core.sha256(path)}
            (base / 'manifest.local.json').write_text(json.dumps({'files': files}), 'utf8')
            self.assertEqual(len(core.check_resources(Assets(base))['files']), 3)
            (base / 'local/bin/AdbWinApi.dll').write_bytes(b'modified')
            with self.assertRaises(core.ToolError) as caught:
                core.check_resources(Assets(base))
            self.assertEqual(caught.exception.code, 'ASSET_INTEGRITY')

    def test_frontend_no_input_or_host_firmware(self):
        source = Path(recover_sd.__file__).read_text('utf8')
        self.assertNotIn('input(', source)
        self.assertNotIn('firmware_check', source)
        with patch.object(recover_sd, 'hardware_lock') as device:
            with self.assertRaises(SystemExit) as caught:
                recover_sd.main(['--help'])
            self.assertEqual(caught.exception.code, 0)
            device.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
