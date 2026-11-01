"""Test Windows restart classification and the non-writing recovery entry."""
from pathlib import Path
from unittest.mock import patch
import argparse
import json
import os
import queue
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, required=True)
    root = parser.parse_args().package.resolve(strict=True)
    for name in ('app', 'vendor/python', 'vendor/squashfs', 'vendor/usb', 'app/container',
                 'app/provider', 'app/reader', 'app/workflow', 'app/ui'):
        sys.path.insert(0, str(root / name))
    from product_integrity import verify_release
    verify_release()
    import driver_restart, user_provider, standalone_usb_restore as direct, simple_app, gui_model
    ps = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    env = os.environ.copy(); env.pop('PSModulePath', None)
    command = [str(ps), '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
               str(Path(__file__).with_suffix('.ps1').with_name('test_driver_restart.ps1')), '-Package', str(root)]
    result = subprocess.run(command, capture_output=True, encoding='utf-8-sig', errors='replace', timeout=60,
                            creationflags=subprocess.CREATE_NO_WINDOW, env=env)
    if result.returncode: raise RuntimeError(result.stdout + result.stderr)
    native = json.loads(result.stdout)
    assert native['passed'] and native['cases'] == 7
    rows = ['powershell_3010_boot_boundary_and_fixture_confirmation']
    folder = root / 'state/source_tests/restore_deadlock'; folder.mkdir(parents=True, exist_ok=True)
    provider = user_provider.Provider()
    waiting = dict(phase='WINDOWS_RESTART_REQUIRED', source_run='offline')
    with patch.object(driver_restart, 'check', side_effect=[dict(phase='CLEAR'), waiting]), \
         patch.object(user_provider.old.Provider, 'restore', side_effect=ValueError('legacy 3010 classification')) as parent:
        assert provider.restore(folder) == 'WINDOWS_RESTART_REQUIRED' and parent.call_count == 1
    rows.append('legacy_restore_failure_is_recognized_as_windows_restart_without_repeat')
    with patch.object(driver_restart, 'check', return_value=dict(phase='CLEAR')), \
         patch.object(user_provider.old.Provider, 'restore', side_effect=ValueError('unknown failure')):
        try: provider.restore(folder)
        except ValueError as error: assert str(error) == 'unknown failure'
        else: raise AssertionError('Unrelated driver failure was hidden')
    rows.append('unknown_restore_failure_is_preserved')
    with patch.object(driver_restart, 'check', return_value=dict(phase='DRIVER_RESTART_RECOVERY_VERIFIED')), \
         patch.object(user_provider.old.Provider, 'restore', side_effect=AssertionError('no new dispatch')):
        assert provider.restore(folder) == 'VERIFIED'
    rows.append('fresh_post_reboot_confirmation_does_not_dispatch_another_restore')
    class Windows:
        def restart_state(self): return waiting
        def probe(self): raise AssertionError('No driver work during Windows restart wait')
        launch = probe
    reply = direct.recover(Windows(), wait_seconds=0)
    assert reply['phase'] == 'USB_RESTORE_WINDOWS_RESTART' and reply['passed'] is False
    assert gui_model.classify('simple-recover-usb', 0, reply)[0] == 'waiting'
    rows.append('restart_wait_is_not_reported_as_complete_or_unknown_write')
    import tkinter as tk
    class Jobs:
        busy = False
        events = queue.Queue()
    top = tk.Tk(); top.withdraw()
    app = simple_app.App(top, jobs=Jobs(), flow_reader=lambda: dict(phase='NO_FLOW'))
    Jobs.events.put(('finished', dict(phase='WAITING', action='simple-recover-usb', result=reply)))
    app.poll(); top.update_idletasks()
    assert app.title.get() == '请重启电脑' and app.primary.cget('state') == 'disabled'
    assert app.restore.cget('state') == 'normal' and '重启电脑' in app.detail.get()
    app.close()
    rows.append('ui_distinguishes_computer_restart_from_usb_replug')
    record = dict(passed=True, cases=7 + len(rows) - 1, tests=rows, powershell=native,
                  device_operations=0, driver_tasks_dispatched=0, firmware_operations=0)
    (root / 'state/source_tests/restore_deadlock.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(record))


if __name__ == '__main__': main()
