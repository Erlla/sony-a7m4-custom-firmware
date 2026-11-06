"""Offline tests: fake Windows/PnP only; never launch recovery against a device."""
from contextlib import contextmanager
from pathlib import Path
import argparse
import copy
import hashlib
import json
import queue
import sys
import tempfile
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, required=True)
    root = parser.parse_args().package.resolve(strict=True)
    for name in ('app', 'vendor/python', 'vendor/squashfs', 'vendor/usb', 'app/container',
                 'app/provider', 'app/reader', 'app/workflow', 'app/ui'):
        sys.path.insert(0, str(root / name))
    import usb.core
    device_calls = []
    def forbidden(*a, **k):
        device_calls.append(True)
        raise AssertionError('No real USB or PowerShell calls in this test')
    usb.core.find = forbidden
    import standalone_usb_restore as direct
    import usb_recovery
    import integrity_backend as backend
    import simple_workflow
    import simple_app
    from product_integrity import verify_release
    verify_release()
    tests = []
    bad = dict(normal_count=1, service_count=0, camera_pmhome_accessible=False,
               reviewed_package_absent=False, normal=dict(body_sha256='a' * 64, service='WinUSB',
               inf='oem99.inf', status='OK', reviewed_driver=True))
    good = copy.deepcopy(bad)
    good.update(camera_pmhome_accessible=True, reviewed_package_absent=True)
    good['normal'].update(service='USBSTOR', inf='usbstor.inf', reviewed_driver=False)

    class Windows:
        def restart_state(self): return dict(phase='CLEAR')
        def __init__(self, *states, terminal=True, cancel=False, fail=False):
            self.states = list(states)
            self.launches = 0
            self.terminal, self.cancel, self.fail = terminal, cancel, fail
        def probe(self):
            if len(self.states) > 1:
                return copy.deepcopy(self.states.pop(0))
            return copy.deepcopy(self.states[0])
        def launch(self, folder, body, nonce):
            self.launches += 1
            if self.fail:
                raise TimeoutError('Fake dispatch timeout')
            if self.cancel:
                return dict(nonce=nonce, cancelled_before_change=True, dispatched=False)
            if self.terminal:
                direct.atomic(folder / 'worker_result.json', dict(nonce=nonce, body_sha256=body, status='HELPER_COMPLETE'))
            return dict(nonce=nonce, dispatched=True, process_id=123)

    @contextmanager
    def isolated():
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            with patch.object(direct, 'PRIVATE', path), patch.object(direct, 'POINTER', path / 'current.json'), \
                 patch.object(direct.Windows, 'host', forbidden):
                yield path

    def reject(call):
        try:
            call()
        except (ValueError, RuntimeError):
            return
        raise AssertionError('Unsafe action was accepted')

    with isolated():
        windows = Windows(good)
        assert direct.recover(windows)['phase'] == 'USB_RESTORE_COMPLETE'
        assert windows.launches == 0 and not direct.POINTER.exists()
        tests.append('already_normal_does_not_elevate_or_enroll')
    with isolated():
        state = copy.deepcopy(good)
        state.update(camera_pmhome_accessible=False, camera_storage_accessible=True)
        windows = Windows(state)
        assert direct.recover(windows)['phase'] == 'USB_RESTORE_COMPLETE'
        assert windows.launches == 0
        tests.append('accessible_camera_card_without_pmhome_is_already_restored')
    with isolated():
        state = copy.deepcopy(good)
        state.update(camera_pmhome_accessible=True, camera_storage_accessible=False)
        windows = Windows(state)
        assert direct.recover(windows)['phase'] == 'USB_RESTORE_REPLUG'
        assert windows.launches == 0
        tests.append('explicit_storage_failure_cannot_fall_back_to_legacy_pmhome_flag')
    with isolated():
        state = copy.deepcopy(good)
        state.update(camera_pmhome_accessible=False, camera_storage_accessible=True)
        windows = Windows(bad, state)
        assert direct.recover(windows, wait_seconds=0)['phase'] == 'USB_RESTORE_COMPLETE'
        assert direct.pending()['phase'] == 'VERIFIED' and windows.launches == 1
        tests.append('pending_restore_completes_on_the_same_camera_card_without_pmhome')
    with isolated():
        windows = Windows(bad, good)
        assert direct.recover(windows, wait_seconds=0)['phase'] == 'USB_RESTORE_COMPLETE'
        assert direct.pending()['phase'] == 'VERIFIED' and windows.launches == 1
        assert direct.recover(windows, wait_seconds=0)['phase'] == 'USB_RESTORE_COMPLETE'
        assert windows.launches == 1
        tests.append('fresh_start_restores_without_patch_record_and_does_not_repeat')
    for normal, service in ((0, 0), (0, 1), (1, 1)):
        with isolated():
            state = copy.deepcopy(bad); state.update(normal_count=normal, service_count=service)
            windows = Windows(state)
            assert direct.recover(windows)['phase'] == 'USB_RESTORE_REPLUG'
            assert windows.launches == 0
    tests.append('absent_or_service_mode_only_requests_replug')
    with isolated():
        state = copy.deepcopy(bad); state['normal_count'] = 2
        windows = Windows(state)
        reject(lambda: direct.recover(windows))
        assert windows.launches == 0
        tests.append('multiple_cameras_refused')
    with isolated():
        state = copy.deepcopy(bad); state['normal']['reviewed_driver'] = False
        windows = Windows(state)
        reject(lambda: direct.recover(windows))
        assert windows.launches == 0
        tests.append('unreviewed_driver_refused')
    with isolated():
        windows = Windows(bad, terminal=False)
        assert direct.recover(windows, wait_seconds=0)['phase'] == 'USB_RESTORE_WAITING'
        assert direct.recover(windows, wait_seconds=0)['phase'] == 'USB_RESTORE_WAITING'
        assert windows.launches == 1
        reject(direct.require_clear)
        record = direct.pending()
        direct.atomic(direct.PRIVATE / record['recovery'] / 'worker_result.json',
                      dict(nonce=record['recovery'], body_sha256='a' * 64, status='HELPER_NEEDS_CHECK'))
        windows.states = [good]
        assert direct.recover(windows, wait_seconds=0)['phase'] == 'USB_RESTORE_COMPLETE'
        direct.require_clear()
        assert windows.launches == 1
        tests.append('pending_task_blocks_patch_but_replug_confirms_without_redispatch')
    with isolated():
        windows = Windows(bad)
        assert direct.recover(windows, wait_seconds=0)['phase'] == 'USB_RESTORE_REVIEW_REQUIRED'
        direct.recover(windows, wait_seconds=0)
        assert windows.launches == 1
        tests.append('failed_driver_change_never_automatically_repeated')
    with isolated():
        windows = Windows(bad, terminal=False)
        direct.recover(windows, wait_seconds=0)
        other = copy.deepcopy(bad); other['normal']['body_sha256'] = 'b' * 64
        windows.states = [other]
        reject(lambda: direct.recover(windows, wait_seconds=0))
        assert windows.launches == 1
        tests.append('pending_body_identity_enforced')
    with isolated():
        windows = Windows(bad, cancel=True)
        assert direct.recover(windows, wait_seconds=0)['phase'] == 'USB_RESTORE_CANCELLED'
        direct.require_clear()
        tests.append('uac_cancellation_is_before_change')
    with isolated():
        windows = Windows(bad, fail=True)
        try:
            direct.recover(windows, wait_seconds=0)
        except TimeoutError:
            pass
        else:
            raise AssertionError('Expected fake timeout')
        assert direct.pending()['phase'] == 'DISPATCH_UNKNOWN'
        assert direct.recover(windows, wait_seconds=0)['phase'] == 'USB_RESTORE_WAITING'
        assert windows.launches == 1
        tests.append('unknown_dispatch_preserved_without_retry')

    class Journal:
        phase = None
        def __init__(self, *a):
            pass
        def load(self):
            return dict(phase=self.phase) if self.phase else None
    with patch.object(backend.frozen, 'Journal', Journal), patch.object(direct, 'recover', return_value=dict(phase='FAKE_DONE')) as restore:
        assert usb_recovery.recover(dict(phase='NO_FLOW'))['phase'] == 'FAKE_DONE'
        Journal.phase = 'WRITE_STARTING'
        reject(lambda: usb_recovery.recover(dict(phase='NO_FLOW')))
        assert restore.call_count == 1
    tests.append('backend_fresh_route_and_unresolved_write_guard')
    reject(lambda: usb_recovery.recover(dict(phase='PATCH_RUNNING')))
    reject(lambda: usb_recovery.recover(dict(phase='AWAITING_MENU_OBSERVATION'), confirmed=False))
    with patch.object(usb_recovery, 'recover_write_race', return_value={'phase': 'EXISTING_PROOF_ROUTE'}) as old:
        assert usb_recovery.recover(dict(phase='REVIEW_REQUIRED'))['phase'] == 'EXISTING_PROOF_ROUTE'
        assert old.call_count == 1
    tests.append('existing_write_and_menu_evidence_not_bypassed')
    assert usb_recovery.ROOT == root

    # The enrollment provider must use the same storage postcondition as the
    # standalone route. All Windows and broker dispatch boundaries are mocks.
    import provider as enrolled
    camera_row = dict(instance=r'USB\VID_054C&PID_0DA5\INERT-CAMERA', status='OK',
                      service='USBSTOR', inf='usbstor.inf')
    camera_state = dict(normal_count=1, service_count=0, normal=[camera_row], pmhome=[],
                        storage=[dict(accessible=True, belongs_to_camera=True, label='')])
    class EnrolledFixture(enrolled.Provider):
        # The base class receives these Windows/broker interfaces from its
        # concrete provider; this fixture forbids them unless explicitly mocked.
        snapshot = tasks_clear = host = forbidden
    instance = EnrolledFixture()
    instance.binding = dict(camera_instance_sha256=hashlib.sha256(camera_row['instance'].upper().encode()).hexdigest())
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        with patch.object(instance, 'snapshot', return_value=(folder, camera_state)), \
             patch.object(instance, 'tasks_clear'), patch.object(instance, 'host', forbidden):
            assert instance.normal_ready(folder)
            instance.preflight(folder)
            direct.atomic(folder / 'latest_Restore.json', dict(status='USBSTOR_RESTORED'))
            assert instance.restore(folder, confirmation=True) == 'VERIFIED'
        tests.append('enrolled_preflight_ready_and_confirmation_accept_unlabelled_camera_card')
        for volumes in ([], [dict(accessible=True, belongs_to_camera=False)],
                        [dict(accessible=False, belongs_to_camera=True)]):
            state = dict(camera_state, storage=volumes,
                         pmhome=[dict(accessible=True, belongs_to_camera=True)])
            with patch.object(instance, 'snapshot', return_value=(folder, state)), \
                 patch.object(instance, 'tasks_clear'), patch.object(instance, 'host', forbidden):
                assert not instance.normal_ready(folder)
                reject(lambda: instance.preflight(folder))
                reject(lambda: instance.restore(folder, confirmation=True))
        tests.append('enrolled_storage_failure_foreign_volume_and_unreadable_root_fail_closed')
        legacy = dict(camera_state)
        legacy.pop('storage'); legacy['pmhome'] = [dict(accessible=True, belongs_to_camera=True)]
        assert instance.storage_accessible(legacy)
        tests.append('legacy_snapshot_remains_readable_without_rewriting_old_evidence')
        result = dict(run_id='a' * 32, status='NEEDS_REVIEW')
        direct.atomic(folder / 'latest_Restore.json', result)
        direct.atomic(folder / 'Restore_task_result.json', dict(result, error='Restore helper returned 1', device_mutation_started=True))
        for error in ('USBSTOR/PMHOME did not become accessible within the postcondition deadline.',
                      'USBSTOR/camera storage did not become accessible within the postcondition deadline.'):
            path = folder / 'Restore_auto_restore_result.private.json'
            path.write_text(json.dumps(dict(error=error)))
            with patch.object(instance, 'snapshot', return_value=(folder, camera_state)), \
                 patch.object(instance, 'wait_for_normal', return_value=True), \
                 patch.object(instance, 'host', return_value=(1, result)) as dispatch:
                assert instance.restore(folder) == 'RESTART_REQUIRED'
                assert dispatch.call_count == 1
        tests.append('enrolled_restore_classifies_old_and_new_storage_deadline_without_retry')

    import tkinter as tk
    class Jobs:
        busy = False
        def __init__(self):
            self.events = queue.Queue(); self.actions = []
        def start(self, action, arguments):
            self.actions.append((action, arguments)); self.busy = True
    top = tk.Tk(); top.withdraw()
    try:
        state = dict(phase='NO_FLOW')
        jobs = Jobs()
        app = simple_app.App(top, jobs=jobs, flow_reader=lambda: state.copy(), patch_reader=lambda: {})
        top.update_idletasks()
        assert not app.ready.get() and app.primary['state'] == 'disabled'
        assert app.restore['state'] == 'normal'
        app.restore.invoke()
        assert jobs.actions == [('simple-recover-usb', [])]
        assert app.restore['state'] == 'disabled'
        jobs.busy = False
        state['phase'] = 'REVIEW_REQUIRED'; app.refresh()
        assert app.restore['state'] == 'normal'
        tests.append('gui_recovery_available_at_start_without_checkbox_and_disabled_while_busy')
    finally:
        top.destroy()
    assert not device_calls
    report = dict(passed=True, tests=tests, cases=len(tests), device_operations=0,
                  driver_tasks_dispatched=0, administrator_elevations=0)
    destination = root / 'state/source_tests/usb.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
