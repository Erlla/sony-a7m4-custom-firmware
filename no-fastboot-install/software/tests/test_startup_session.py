"""Process-level startup isolation and Tk checks. No camera or driver actions."""
from pathlib import Path
from unittest.mock import patch
from types import ModuleType
import argparse
import hashlib
import json
import os
import queue
import runpy
import subprocess
import sys
import uuid


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(root, mode):
    # Run the real GUI entry path, replacing only the Tk main entry with checks.
    replacement = ModuleType('simple_app')
    rows = {}
    def gui_main():
        import operation_session as scope
        import wizard as flow
        import integrity_backend as backend
        import install_view
        import backend_bridge as bridge
        import standalone_usb_restore as usb
        from state_io import atomic_json
        session = os.environ[scope.ENVIRONMENT]
        expected = root / 'state/sessions' / session
        assert scope.operation_path() == expected
        assert flow.PRIVATE == install_view.PRIVATE == expected / 'workflow'
        assert backend.STATE == expected / 'workflow/patch'
        assert usb.PRIVATE == expected / 'usb_restore'
        assert bridge.Jobs().private == expected / 'ui'
        assert flow.load()['phase'] == install_view.snapshot()['phase'] == 'NO_FLOW'
        assert bridge.state_snapshot()['phase'] == 'NO_RUN' and usb.pending() is None
        import install_controller, install_controller_custom
        assert install_controller.PRIVATE == install_controller_custom.PRIVATE == flow.PRIVATE
        rows.update(session=session, fresh=True)
        if mode == 'old':
            value = dict(schema='m4-user-flow/1', flow=uuid.uuid4().hex)
            flow.save(value, 'REVIEW_REQUIRED', error='offline unresolved write fixture')
            atomic_json(flow.POINTER, {'flow': value['flow']})
            journal = backend.frozen.Journal(backend.STATE)
            journal.create(backend.LOADED_SHA)
            journal.update('REVIEW_REQUIRED', firmware_write_attempted=True)
            name = uuid.uuid4().hex
            atomic_json(usb.PRIVATE / name / 'recovery.json', dict(schema='m4-driver-only-recovery/1',
                        recovery=name, phase='DISPATCH_UNKNOWN'))
            atomic_json(usb.POINTER, {'recovery': name})
            return
        # A real child CLI receives the current GUI session; status has no device path.
        child = subprocess.run([sys.executable, '-I', '-B', '-X', 'utf8', str(root / 'app/entry.py'), 'simple-status'],
                               check=True, capture_output=True, text=True, encoding='utf-8')
        assert json.loads(child.stdout)['phase'] == 'NO_FLOW'
        rows['child_status'] = 'NO_FLOW'
        import simple_workflow as workflow
        with patch.object(workflow, 'binding_path', return_value=root / 'app/release.json'), \
             patch.object(workflow, 'Provider') as provider, \
             patch.object(workflow, 'patch_receiver', side_effect=lambda v: v) as boundary:
            value = workflow.begin(True)
            assert value['phase'] == 'PATCH_PREPARED' and boundary.call_count == 1
            provider.return_value.check.assert_called_once()
        rows['new_begin'] = 'PATCH_PREPARED'
        flow.save(value, 'REVIEW_REQUIRED')
        try: workflow.begin(True)
        except ValueError: pass
        else: raise AssertionError('In-session unresolved action was replayed')
        rows['same_session_blocked'] = True
        # The process lock remains global, including across different GUI sessions.
        from engine import single_instance
        from product_integrity import state_path
        with single_instance(state_path(backend.frozen.OLD_TOOL)):
            blocked = subprocess.run([sys.executable, '-I', '-B', '-X', 'utf8', str(root / 'app/entry.py'), 'simple-status'],
                                     capture_output=True, text=True, encoding='utf-8')
            assert blocked.returncode == 1 and '正在运行' in blocked.stderr
        rows['live_backend_lock'] = True
        # Restore the real Tk module, render initial session and check button behavior.
        del sys.modules['simple_app']
        import simple_app
        import tkinter as tk
        class Jobs:
            busy = False
            events = queue.Queue()
        ui = tk.Tk(); ui.withdraw()
        app = simple_app.App(ui, jobs=Jobs(), flow_reader=lambda: {'phase': 'NO_FLOW'})
        ui.update_idletasks()
        assert app.title.get() == '写入补丁' and app.restore.cget('state') == 'normal'
        assert app.primary.cget('state') == 'disabled'
        app.ready.set(True); app.refresh()
        assert app.primary.cget('state') == 'normal' and app.action == 'simple-start'
        assert app.result.get() == app.timer.get() == app.progress_text.get() == ''
        app.close()
        rows['tk_initial_buttons'] = True
    replacement.main = gui_main
    sys.modules['simple_app'] = replacement
    sys.argv = [str(root / 'app/entry.py')]
    runpy.run_path(sys.argv[0], run_name='__main__')
    print(json.dumps(rows))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', required=True, type=Path)
    parser.add_argument('--probe', choices=('old', 'next'))
    args = parser.parse_args()
    root = args.package.resolve(strict=True)
    if args.probe:
        probe(root, args.probe)
        return
    legacy = root / 'state/workflow'
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / 'flow.json').write_text('{broken legacy pointer', 'utf-8')
    (legacy / 'patch/control').mkdir(parents=True, exist_ok=True)
    (legacy / 'patch/current.json').write_text('{broken journal', 'utf-8')
    old_usb = root / 'state/usb_restore/current.json'
    old_usb.parent.mkdir(parents=True, exist_ok=True)
    old_usb.write_text('{broken recovery', 'utf-8')
    before = {str(p): digest(p) for p in (root / 'state').rglob('*') if p.is_file()}
    def run(mode, inherited=None):
        env = dict(os.environ)
        if inherited: env['M4_TOOL_SESSION'] = inherited
        outcome = subprocess.run([sys.executable, '-I', '-B', '-X', 'utf8', str(Path(__file__).resolve()),
                                  '--package', str(root), '--probe', mode],
                                 env=env, check=True, capture_output=True, text=True, encoding='utf-8')
        return json.loads(outcome.stdout.splitlines()[-1])
    old = run('old')
    old_paths = {str(p): digest(p) for p in (root / 'state/sessions' / old['session']).rglob('*') if p.is_file()}
    # Startup ignores even an inherited old session ID. Each launch must choose its own.
    new = run('next', old['session'])
    again = run('next', new['session'])
    assert len({old['session'], new['session'], again['session']}) == 3
    assert all(digest(Path(p)) == h for p, h in {**before, **old_paths}.items())
    # --verify stays noninteractive and does not create a GUI session or request UAC.
    count = len(list((root / 'state/sessions').iterdir()))
    checked = subprocess.run([str(root / 'M4相机工具.exe'), '--verify'], timeout=60)
    assert checked.returncode == 0 and len(list((root / 'state/sessions').iterdir())) == count
    result = dict(passed=True, cases=9, tests=['legacy_corrupt_states_ignored', 'unresolved_previous_session_ignored',
        'inherited_session_replaced_at_gui_start', 'history_bytes_preserved', 'child_cli_inherits_session',
        'new_begin_reaches_patch_boundary', 'same_session_unresolved_blocks_replay', 'live_backend_lock_remains_global',
        'tk_initial_controls_and_noninteractive_launcher_verify'], probes=[new, again], device_operations=0,
        driver_tasks_dispatched=0, firmware_operations=0, uac_interaction_tested=False)
    target = root / 'state/source_tests/startup_session.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__': main()
