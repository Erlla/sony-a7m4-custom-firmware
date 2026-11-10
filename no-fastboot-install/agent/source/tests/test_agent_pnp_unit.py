"""Run the production probe in PowerShell with an inert Get-PnpDevice fixture."""
from pathlib import Path
from unittest.mock import patch
import os
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'app'))
from agent_platform import WindowsHost


@unittest.skipUnless(os.name == 'nt', 'Windows PowerShell fixture')
class PnpProbeTests(unittest.TestCase):
    def probe(self, fixture):
        run = subprocess.run
        def evaluate(arguments, **kwargs):
            command = list(arguments)
            command[-1] = fixture + '\n' + command[-1]
            return run(command, **kwargs)
        with patch('agent_platform.subprocess.run', side_effect=evaluate):
            return WindowsHost().probe()

    def test_usb_paths_are_matched_by_real_powershell(self):
        result = self.probe(r'''
function Get-PnpDevice {
    param([switch]$PresentOnly)
    @('USB\VID_054C&PID_0DA5\NORMAL', 'USB\VID_054C&PID_0336\SERVICE',
      'USB\VID_054C&PID_0DA5&MI_00\INTERFACE', 'USB\VID_054C&PID_0DA50\OTHER',
      'USBSTOR\DISK&VEN_SONY\CHILD', 'USB\VID_1234&PID_0DA5\OTHER') |
        ForEach-Object { [pscustomobject]@{InstanceId=$_} }
}
''')
        self.assertEqual((result['normal_count'], result['service_count']), (1, 1))
        self.assertEqual(result['device_operations'], 0)

    def test_no_present_device_is_a_valid_result(self):
        result = self.probe('function Get-PnpDevice { param([switch]$PresentOnly) @() }')
        self.assertEqual((result['normal_count'], result['service_count']), (0, 0))

    def test_original_chinese_failure_remains_readable(self):
        with self.assertRaises(RuntimeError) as caught:
            self.probe("function Get-PnpDevice { param([switch]$PresentOnly) throw '模拟枚举失败' }")
        self.assertIn('模拟枚举失败', str(caught.exception))


if __name__ == '__main__': unittest.main(verbosity=2)
