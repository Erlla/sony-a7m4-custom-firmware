"""Regression tests using recorded output and mocked transports; no hardware."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from a7m4 import sd_recovery as core, recover_sd
from a7m4.transport import Partition, Fastboot

FAILURE = ('getvar:product                                     FAILED '
           '(AdbWriteEndpointSync failed: 信号灯超时时间已到 (121))\r\n'
           'Finished. Total time: 5.002s\r\n').encode('utf8')
PRODUCT = b'product: ILCE-7M4\r\nFinished. Total time: 0.000s\r\n'


class ConnectionErrors(unittest.TestCase):
    def test_failed_product_stops_before_partition_backup_and_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = core.RecoveryTransport(tmp)
            with patch.object(t, 'devices', return_value=['ILCE7M4-fastboot']), patch.object(Fastboot, 'command', return_value=FAILURE) as backend:
                with self.assertRaises(core.ToolError) as caught:
                    core.recover(t, tmp, {}, disk_free=1 << 32, notify=lambda x: None)
                self.assertEqual(caught.exception.code, 'USB_TIMEOUT')
                self.assertEqual(backend.call_args_list, [unittest.mock.call('getvar', 'product', timeout=300)])
            row = json.loads((Path(tmp) / 'result.json').read_text('utf8'))
            self.assertEqual(row['status'], 'STOPPED_KEEP_FASTBOOT')
            self.assertEqual(row['error_code'], 'USB_TIMEOUT')
            self.assertFalse(row['flash_attempted'] or row['reboot_attempted'])
            self.assertFalse(list(Path(tmp).glob('*.bin')))

    def test_zero_exit_failed_output_is_usb_timeout_not_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = core.RecoveryTransport(tmp)
            with patch.object(t, 'devices', return_value=['ILCE7M4-fastboot']), patch.object(Fastboot, 'command', return_value=FAILURE):
                with self.assertRaises(core.ToolError) as caught:
                    t.select()
            self.assertEqual(caught.exception.code, 'USB_TIMEOUT')
            rows = [json.loads(x) for x in (Path(tmp) / 'commands.jsonl').read_text('utf8').splitlines()]
            self.assertEqual(rows[-1]['error_code'], 'USB_TIMEOUT')
            self.assertIn('AdbWriteEndpointSync', rows[-1]['output'])

    def test_valid_product_is_still_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = core.RecoveryTransport(tmp)
            with patch.object(t, 'devices', return_value=['ILCE7M4-fastboot']), patch.object(Fastboot, 'command', return_value=PRODUCT):
                self.assertEqual(t.select()['product'], 'ILCE-7M4')

    def test_genuine_other_model_is_still_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = core.RecoveryTransport(tmp)
            with patch.object(t, 'devices', return_value=['OTHER']), patch.object(Fastboot, 'command', return_value=b'product: ILCE-7M5\n'):
                with self.assertRaises(core.ToolError) as caught:
                    t.select()
            self.assertEqual(caught.exception.code, 'MODEL')

    def test_nonzero_process_error_retains_usb_classification(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = core.RecoveryTransport(tmp)
            t.serial = 'FAKE'
            with patch.object(Fastboot, 'command', side_effect=core.ToolError('COMMAND_FAILED', FAILURE.decode('utf8'))):
                with self.assertRaises(core.ToolError) as caught:
                    t.command('getvar', 'product')
            self.assertEqual(caught.exception.code, 'USB_TIMEOUT')

    def test_remote_failure_is_not_reported_as_usb(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = core.RecoveryTransport(tmp)
            t.serial = 'FAKE'
            with patch.object(Fastboot, 'command', return_value=b"FAILED (remote: unsupported command)\n"):
                with self.assertRaises(core.ToolError) as caught:
                    t.command('getvar', 'product')
            self.assertEqual(caught.exception.code, 'FASTBOOT_FAILED')

    def test_innocent_failed_counter_is_not_a_protocol_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = core.RecoveryTransport(tmp)
            t.serial = 'FAKE'
            data = b'failed_count: 0\nOKAY\n'
            with patch.object(Fastboot, 'command', return_value=data):
                self.assertEqual(t.command('oem', 'partition'), data)

    def test_failed_text_write_is_consumed_without_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'candidate.bin'
            path.write_bytes(bytes(core.SETTINGS_SIZE))
            t = core.RecoveryTransport(tmp)
            t.serial = 'FAKE'
            p = Partition('nflasha2', 0, core.SETTINGS_SIZE // 512, 'TEST')
            with patch.object(Fastboot, 'command', return_value=b'FAILED (remote: write failed)\n') as command:
                with self.assertRaises(core.ToolError):
                    t.write_settings(p, path, core.sha256(path))
                with self.assertRaises(core.ToolError) as caught:
                    t.command('flash', 'nflasha2', path)
                self.assertEqual(caught.exception.code, 'WRITE_NOT_ARMED')
                self.assertEqual(command.call_count, 1)

    def test_read_only_check_never_calls_partition_or_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(recover_sd, 'root_dir', return_value=Path(tmp)), patch.object(recover_sd, 'check_resources'), \
                 patch.object(recover_sd, 'read_config', return_value={}), patch.object(recover_sd, 'hardware_lock'), \
                 patch.object(recover_sd, 'RecoveryTransport') as cls, patch.object(recover_sd, 'recover') as write_flow:
                cls.return_value.select.return_value = {'product': 'ILCE-7M4'}
                self.assertEqual(recover_sd.main(['--check-connection']), 0)
                write_flow.assert_not_called()
                self.assertEqual([x[0] for x in cls.return_value.method_calls], ['select'])
                files = list(Path(tmp).glob('local/sd-recovery/sessions/*/result.json'))
                row = json.loads(files[0].read_text('utf8'))
                self.assertEqual(row['status'], 'CONNECTION_OK')
                self.assertFalse(row['flash_attempted'] or row['reboot_attempted'])

    def test_read_only_check_logs_failure_without_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = core.RecoveryTransport(tmp)
            with patch.object(t, 'select', side_effect=core.ToolError('USB_TIMEOUT', 'timeout', 'check cable')) as select:
                with self.assertRaises(core.ToolError):
                    core.check_connection(t, tmp)
                self.assertEqual(select.call_count, 1)
            row = json.loads((Path(tmp) / 'result.json').read_text('utf8'))
            self.assertEqual(row['error_code'], 'USB_TIMEOUT')
            self.assertFalse(row['flash_attempted'] or row['reboot_attempted'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
