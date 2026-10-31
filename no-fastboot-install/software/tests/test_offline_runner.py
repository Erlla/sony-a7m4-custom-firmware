"""Runner error/timeout/isolation tests. Package dispatch is mocked, not built."""
from pathlib import Path
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch, MagicMock
import xml.etree.ElementTree as ET

spec = importlib.util.spec_from_file_location('source_offline_runner', Path(__file__).with_name('run_offline.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def completed(exit_code=0):
    return dict(exit_code=exit_code, timed_out=False, output='', output_truncated=False, seconds=0)


class RunnerTests(unittest.TestCase):
    def assert_windows_process_stopped(self, pid):
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD,wintypes.BOOL,wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE,wintypes.DWORD)
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel.OpenProcess(0x100000, False, pid)
        if handle:
            try: self.assertEqual(kernel.WaitForSingleObject(handle,0), 0)
            finally: kernel.CloseHandle(handle)

    def test_catalogue_includes_both_new_package_regressions_and_lineages(self):
        specs = {name:(script,extra) for name,script,extra in runner.PACKAGE_CASES}
        self.assertEqual(len(specs), len(runner.PACKAGE_CASES))
        self.assertEqual(specs['startup-session'][0], 'test_startup_session.py')
        self.assertEqual(specs['usb-identity'][0], 'test_usb_identity.py')
        self.assertEqual(specs['menu-stock'][1], ('--lineage','stock'))
        self.assertEqual(specs['menu-user'][1], ('--lineage','user'))

    def test_blocked_checks_are_partial_and_failure_takes_precedence(self):
        self.assertEqual(runner.overall_status([{'status':'PASS'}]), 'PASS')
        self.assertEqual(runner.overall_status([{'status':'PASS'},{'status':'BLOCKED'}]), 'PARTIAL')
        self.assertEqual(runner.overall_status([{'status':'FAIL'},{'status':'BLOCKED'}]), 'FAIL')

    def test_successful_exit_without_worker_record_is_failure(self):
        with patch.object(runner, 'run_process', return_value=completed()):
            self.assertEqual(runner.run_source_case('build-assets', 10)['status'], 'FAIL')

    def test_malformed_worker_record_is_reported_without_aborting(self):
        def invalid(command, timeout):
            Path(command[-1]).write_text('{bad json', 'utf-8')
            return completed()
        with patch.object(runner, 'run_process', side_effect=invalid):
            self.assertEqual(runner.run_source_case('build-assets', 10)['status'], 'FAIL')

    def test_nonzero_worker_exit_cannot_be_overridden_by_pass_record(self):
        def failing(command, timeout):
            Path(command[-1]).write_text(json.dumps({'passed':True,'tests_run':1,'tests':[]}), 'utf-8')
            return completed(1)
        with patch.object(runner, 'run_process', side_effect=failing):
            self.assertEqual(runner.run_source_case('build-assets', 10)['status'], 'FAIL')

    def test_real_unit_failures_and_subtest_failures_are_recorded(self):
        module = ModuleType('controlled_failing_fixture')
        class FailingFixture(unittest.TestCase):
            def test_failure(self): self.fail('intentional fixture failure')
            def test_subtest(self):
                with self.subTest(boundary='fixture'): self.assertEqual(1, 2)
        module.FailingFixture = FailingFixture
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)/'worker.json'
            with patch.object(runner, 'load_module', return_value=module), \
                 patch.object(sys, 'stderr', io.StringIO()):
                code = runner.unit_worker('build-assets', destination)
            result = json.loads(destination.read_text('utf-8'))
        self.assertEqual(code, 1)
        self.assertFalse(result['passed'])
        self.assertEqual(result['tests_run'], 2)
        self.assertEqual(len(result['tests']), 2)
        self.assertTrue(all(t['status']=='FAIL' for t in result['tests']))

    def test_missing_package_is_blocked_without_copy_or_process(self):
        with patch.object(runner, 'package_preflight', return_value={'status':'BLOCKED','reason':'missing'}), \
             patch.object(runner, 'copy_package') as copy, patch.object(runner, 'run_process') as process:
            rows = runner.run_package_cases(Path('not-a-package'), 10)
        self.assertEqual(len(rows), len(runner.PACKAGE_CASES))
        self.assertTrue(all(row['status']=='BLOCKED' for row in rows))
        copy.assert_not_called(); process.assert_not_called()

    def test_invalid_package_is_failure_and_does_not_execute(self):
        with patch.object(runner, 'package_preflight', side_effect=ValueError('hash mismatch')), \
             patch.object(runner, 'run_process') as process:
            rows = runner.run_package_cases(Path('not-a-package'), 10)
        self.assertEqual(runner.overall_status(rows), 'FAIL')
        self.assertEqual(rows[0]['id'], 'package.preflight')
        process.assert_not_called()

    def test_package_cases_receive_distinct_copies_and_continue_after_failure(self):
        # This checks dispatch only. No runtime, EXE or release.json is made.
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory)
            marker = original/'user-record.txt'; marker.write_bytes(b'preserve')
            with patch.object(runner, 'package_preflight', return_value={'status':'PASS'}), \
                 patch.object(runner, 'copy_package') as copy, \
                 patch.object(runner, 'run_process', side_effect=[completed(1)]+[completed()]*(len(runner.PACKAGE_CASES)-1)) as process:
                rows = runner.run_package_cases(original, 10)
            destinations = [call.args[1] for call in copy.call_args_list]
            self.assertEqual(len(set(destinations)), len(runner.PACKAGE_CASES))
            self.assertTrue(all(not dest.is_relative_to(original) for dest in destinations))
            self.assertTrue(all(not dest.exists() for dest in destinations))
            self.assertEqual(process.call_count, len(runner.PACKAGE_CASES))
            self.assertEqual(rows[0]['status'], 'FAIL')
            self.assertTrue(all(row['status']=='PASS' for row in rows[1:]))
            self.assertEqual(marker.read_bytes(), b'preserve')

    def test_reports_cannot_overwrite_package_or_source_tests(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            with self.assertRaises(ValueError): runner.validate_outputs([package/'state/report.json'], package)
        with self.assertRaises(ValueError): runner.validate_outputs([runner.HERE/'report.json'])
        with self.assertRaises(ValueError): runner.validate_outputs([Path('same'),Path('same')])

    def test_junit_preserves_failures_blocks_and_platform_skips(self):
        report = {'checks':[
            {'id':'source.example','status':'PASS','details':{'tests':[
                {'id':'ok','status':'PASS'},{'id':'windows','status':'SKIP','reason':'platform'}]}},
            {'id':'package.example','status':'BLOCKED','reason':'missing assets'},
            {'id':'source.broken','status':'FAIL','reason':'worker failed'}]}
        root = ET.fromstring(runner.junit(report))
        self.assertEqual(root.attrib['tests'], '4')
        self.assertEqual(root.attrib['failures'], '1')
        self.assertEqual(root.attrib['skipped'], '2')

    def test_junit_cannot_hide_worker_failure_behind_passed_unit_rows(self):
        root = ET.fromstring(runner.junit({'checks':[{'id':'source.x','status':'FAIL',
            'details':{'tests':[{'id':'unit','status':'PASS'}]},'reason':'timed out'}]}))
        self.assertEqual(root.attrib['failures'], '1')

    def test_process_uses_isolation_and_clears_camera_session_environment(self):
        with patch.dict(os.environ, {'M4_TOOL_SESSION':'inherited-not-for-tests'}):
            result = runner.run_process([sys.executable, '-I', '-B', '-c',
                'import os; print(os.environ.get("M4_TOOL_SESSION", "absent"))'], 15)
        self.assertEqual(result['exit_code'], 0)
        self.assertEqual(result['output'].strip(), 'absent')

    def test_interrupt_also_cleans_up_the_owned_process_tree(self):
        child = MagicMock()
        child.wait.side_effect = KeyboardInterrupt
        child.poll.return_value = None
        with patch.object(runner.subprocess, 'Popen', return_value=child), \
             patch.object(runner, 'stop_process_tree') as stop:
            with self.assertRaises(KeyboardInterrupt): runner.run_process(['unused'], 1)
        stop.assert_called_once_with(child)

    def test_process_timeout_stops_the_owned_process(self):
        with tempfile.TemporaryDirectory() as directory:
            pid_file = Path(directory)/'pid.txt'
            command = ('import os,sys,time; from pathlib import Path; '
                       'Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(60)')
            result = runner.run_process([sys.executable,'-I','-B','-c',command,str(pid_file)], 1)
            self.assertTrue(result['timed_out'])
            self.assertNotEqual(result['exit_code'], 0)
            self.assertTrue(pid_file.is_file(), 'interpreter did not start before timeout')
            pid = int(pid_file.read_text())
            if os.name == 'nt':
                self.assert_windows_process_stopped(pid)
            else:
                with self.assertRaises(ProcessLookupError): os.kill(pid,0)

    @unittest.skipUnless(os.name == 'nt', 'checks Windows taskkill tree semantics')
    def test_timeout_stops_owned_descendant_as_well_as_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            pid_file = Path(directory)/'tree.json'
            command = ('import json,os,subprocess,sys,time; from pathlib import Path; '
                       'child=subprocess.Popen([sys.executable,"-I","-B","-c",'
                       '"import time; time.sleep(60)"]); '
                       'Path(sys.argv[1]).write_text(json.dumps([os.getpid(),child.pid])); time.sleep(60)')
            result = runner.run_process([sys.executable,'-I','-B','-c',command,str(pid_file)], 1)
            self.assertTrue(result['timed_out'])
            self.assertTrue(pid_file.exists(), 'parent did not start before timeout')
            pids = json.loads(pid_file.read_text())
            try:
                for pid in pids: self.assert_windows_process_stopped(pid)
            finally:
                # Clean up only these explicitly owned test processes if a regression occurs.
                for pid in pids:
                    subprocess.run([str(Path(os.environ['SystemRoot'])/'System32/taskkill.exe'),
                                    '/PID', str(pid), '/T', '/F'], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, timeout=10,
                                   creationflags=subprocess.CREATE_NO_WINDOW)


if __name__ == '__main__': unittest.main(verbosity=2)
