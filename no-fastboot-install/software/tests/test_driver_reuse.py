"""Host-only coverage for retained drivers, p1 completion and user handoff."""
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import argparse
import copy
import hashlib
import json
import os
import sys
import tempfile
import uuid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, required=True)
    root = parser.parse_args().package.resolve(strict=True)
    for name in ('app', 'vendor/python', 'vendor/squashfs', 'vendor/usb', 'app/container',
                 'app/provider', 'app/reader', 'app/workflow', 'app/ui', 'app/usb'):
        sys.path.insert(0, str(root / name))
    # This test exercises behavior with substitutes. Check the built launcher
    # inventory separately with --verify, without rescanning all assets here.
    import usb.core
    def forbidden(*a, **k):
        raise AssertionError('No camera, driver task or automatic restore in this path')
    usb.core.find = forbidden
    import user_provider as up, usb_session, normal_identity
    import integrity_backend as backend, wizard, simple_workflow, usb_recovery
    import standalone_usb_restore, driver_restart, simple_app, gui_model
    from p1_completion import complete
    checks = []
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        inf = folder / 'INF/oem42.inf'; inf.parent.mkdir()
        inf.write_bytes(b'reviewed-test-INF')
        protected = folder / 'protected/driver/ilce-7m4.inf'
        protected.parent.mkdir(parents=True); protected.write_bytes(inf.read_bytes())
        svc_inf = folder / 'protected/driver/ilce-7m4-svc.inf'
        svc_inf.write_bytes(b'reviewed-test-SVC-INF')
        staged_svc = folder / 'INF/oem43.inf'
        staged_svc.write_bytes(svc_inf.read_bytes())
        enrollment = folder / 'enrollment.json'; enrollment.write_text('{}')
        row = dict(instance=r'USB\VID_054C&PID_0DA5\TEST', service='USBSTOR',
                   inf='usbstor.inf', status='OK')
        identity = dict(model='ILCE-7M4', normal_usb_serial_sha256='c' * 64)
        provider = up.Provider()
        provider.protected = protected.parent.parent
        provider.binding = dict(identity=identity,
            camera_instance_sha256=hashlib.sha256(row['instance'].upper().encode()).hexdigest())
        hosts, snapshots, disposed = [], [], []
        def snapshot(destination, *, connection_only=False, wait_seconds=None):
            snapshots.append(connection_only)
            return folder, dict(normal_count=1, service_count=0,
                                normal=[copy.deepcopy(row)], pmhome=[], storage_checked=False)
        def host(action, destination, mode=None):
            assert (action, mode) == ('Broker', 'StageBind')
            hosts.append(mode); row.update(service='WinUSB', inf='oem42.inf')
            staged_svc.write_bytes(svc_inf.read_bytes())
            (folder / 'latest_StageBind.json').write_text('{"run_id":"fixture","status":"WINUSB_BOUND"}')
            return 0, dict(run_id='fixture', status='WINUSB_BOUND')
        probe = SimpleNamespace(usb=SimpleNamespace(util=SimpleNamespace(dispose_resources=disposed.append)))
        with patch.object(up, 'ENROLLMENT', enrollment), patch.dict(os.environ, SystemRoot=str(folder)), \
             patch.object(provider, 'snapshot', side_effect=snapshot), \
             patch.object(provider, 'host', side_effect=host), \
             patch.object(provider, 'prepare_driver_trust', return_value=False), \
             patch.object(driver_restart, 'require_ready', return_value=None), \
             patch.object(usb_session, 'load_backend', return_value=probe), \
             patch.object(normal_identity, 'wait_normal_identity',
                          return_value=(object(), identity, dict(passed=True, camera_commands=0))):
            provider.preflight(folder)
            provider.bind(folder)
            assert hosts == ['StageBind']
            checks.append('storage_without_pmhome_can_prepare_one_reviewed_binding')
            provider.preflight(folder)
            provider.bind(folder)
            provider.preflight(folder)
            provider.bind(folder)
            assert hosts == ['StageBind'] and len(disposed) == 3 and all(snapshots)
            assert json.loads((folder / 'driver_readiness.json').read_text())['reused']
            checks.append('patch_menu_and_next_operation_reuse_driver_without_new_tasks_or_volumes')
            staged_svc.unlink()
            provider.preflight(folder)
            provider.bind(folder)
            assert hosts == ['StageBind', 'StageBind'] and staged_svc.is_file()
            assert not json.loads((folder / 'driver_readiness.json').read_text())['reused']
            checks.append('missing_service_package_triggers_one_reviewed_rebind_before_reuse')
            row['instance'] += 'OTHER'
            try: provider.preflight(folder)
            except ValueError: pass
            else: raise AssertionError('Different body accepted')
            row['instance'] = row['instance'].removesuffix('OTHER')
            checks.append('body_binding_is_preserved_on_reuse')
            inf.write_bytes(b'unreviewed-INF')
            try: provider.preflight(folder)
            except ValueError: pass
            else: raise AssertionError('Unreviewed driver accepted')
            inf.write_bytes(protected.read_bytes())
            checks.append('same_service_name_with_unreviewed_inf_is_rejected')
            with patch.object(provider, 'snapshot', return_value=(folder, dict(normal_count=0, service_count=1))):
                assert provider.wait_communication(folder, timeout=0) is None
            assert hosts == ['StageBind', 'StageBind']
            checks.append('service_identity_pending_does_not_reinstall_or_reauthenticate')
            with patch.object(driver_restart, 'require_ready', side_effect=driver_restart.WindowsRestartRequired('3010')):
                try: provider.preflight(folder)
                except driver_restart.WindowsRestartRequired: pass
                else: raise AssertionError('Required Windows restart ignored')
            checks.append('real_windows_restart_requirement_is_not_bypassed')

        before = folder / 'before.bin'; after = folder / 'after.bin'
        before.write_bytes(b'A' * 25100288); after.write_bytes(b'B' * 25100288)
        def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
        class Device:
            driver_policy = 'retain'
            def __init__(self, changed=False, bad_readback=False, bad_exit=False):
                self.changed, self.bad_readback, self.bad_exit = changed, bad_readback, bad_exit
                self.reads = []; self.writes = 0; self.exits = 0
            def check(self): pass
            def runner_sha(self): return 'd' * 64
            def prepare_reader(self, path, role='before'): return dict(role=role, nonce=('11' if role=='before' else '22') * 16)
            def preflight(self, path): pass
            def bind(self, path): pass
            @contextmanager
            def session(self, path):
                yield SimpleNamespace(wire=SimpleNamespace(healthy=True))
                self.exits += 1
                if self.bad_exit: raise RuntimeError('Exit unconfirmed')
            def verify_ready(self, job, state): pass
            def run_reader(self, session, job, path):
                self.reads.append(job['role'])
                image = before if job['role']=='before' or self.bad_readback else after
                return image, dict(verdict='P1_READBACK_VERIFIED', bytes=25100288, chunks=766,
                    nonce=job['nonce'], block_writes=False, firmware_written=False, ram_chunks_cleaned=True, sha256=digest(image))
            def prepare_write(self, source, path, direction, bundle):
                return dict(lineage='stock', no_change=not self.changed, source_sha256=digest(before),
                    target_sha256=digest(after if self.changed else before), final_state={})
            def verify_write_ready(self, *args): pass
            def run_writer(self, *args):
                self.writes += 1
                return dict(outcome='P1_TARGET_VERIFIED', target_sha256=digest(after))
            def verify_written(self, *args): return {}
            def hold_session(self, session): session.wire.healthy = False
            restore = normal_ready = forbidden
        for changed in (False, True):
            device = Device(changed)
            engine = backend.frozen.Engine(device, folder / ('engine_' + str(changed)))
            result = engine.read('apply')
            assert complete(result) and result['phase']=='P1_COMPLETE'
            assert result['normal_recovery_verified'] is False and result['normal_recovery']=='NOT_REQUESTED'
            assert result['outcome']==result['verified_outcome']
            assert device.writes==int(changed) and device.exits==1
            assert device.reads==(['before','after'] if changed else ['before'])
            value = dict(schema='m4-user-flow/1', flow=uuid.uuid4().hex)
            with patch.object(wizard, 'PRIVATE', folder / 'flows'):
                assert wizard.sync_patch(value, result)['phase']=='PATCH_READY'
            checks.append('verified_' + ('write_and_full_readback' if changed else 'no_write_full_read') + '_completes_without_storage_restore')
        for name, options in [('readback', dict(changed=True,bad_readback=True)), ('session_exit', dict(bad_exit=True))]:
            device = Device(**options)
            engine = backend.frozen.Engine(device, folder / ('failure_' + name))
            try: engine.read('apply')
            except (ValueError, RuntimeError): pass
            else: raise AssertionError('Incomplete operation accepted')
            assert engine.state()['phase']=='REVIEW_REQUIRED' and not complete(engine.state())
            checks.append('unknown_' + name + '_never_becomes_complete_or_switches_drivers')
        assert not complete(dict(phase='P1_COMPLETE', driver_policy='retain', p1_operation_complete=True, read_verified=True))
        checks.append('completion_still_requires_session_exit_proof')
        value = dict(schema='m4-user-flow/1', flow=uuid.uuid4().hex, phase='AWAITING_MENU_OBSERVATION')
        fake_trial = SimpleNamespace(record_session_end=lambda path: dict(phase='USER_INSTALL_FINISHED'))
        with patch.object(wizard, 'PRIVATE', folder / 'end_flow'), \
             patch.object(wizard, 'trial', return_value=fake_trial), \
             patch.object(wizard, 'observed', return_value=folder/'observation.json'), \
             patch.object(up.Provider, 'restore', forbidden):
            done = simple_workflow.installed(value, True)
            assert done['phase']=='COMPLETE' and done['normal_usb_restored'] is False
            assert done['installation_result']=='user_reported_finished_not_read_back'
        assert '恢复' in simple_app.presentation(done)[1]
        checks.append('user_can_finish_installation_without_usb_reconnect_or_storage_claim')
        class Journal:
            def __init__(self, *a): pass
            def load(self): return result
        with patch.object(backend.frozen, 'Journal', Journal), \
             patch.object(standalone_usb_restore, 'recover', return_value=dict(phase='USB_RESTORE_COMPLETE')) as restoring:
            assert usb_recovery.recover(done)['phase']=='USB_RESTORE_COMPLETE'
            assert restoring.call_count==1
        checks.append('explicit_usb_restore_remains_available_after_operation_completion')
        # Checking patch status never requires storage restoration.
        assert gui_model.classify('apply', 0, result)[0]=='success'
        checks.append('p1_completion_has_its_own_ui_result')
    receipt = dict(passed=True,cases=len(checks),tests=checks,device_operations=0,
                   driver_tasks_dispatched=0,firmware_operations=0)
    output=root/'state/source_tests/driver_reuse.json';output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(receipt,indent=2)+'\n','utf-8')
    print(json.dumps(receipt))


if __name__ == '__main__': main()
