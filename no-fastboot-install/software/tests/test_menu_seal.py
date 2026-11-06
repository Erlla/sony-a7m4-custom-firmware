"""Build and seal both menu routes, stopping before all real device actions."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
import sys
import uuid


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--package', type=Path, required=True)
    p.add_argument('--lineage', choices=('stock', 'user'), required=True)
    args = p.parse_args()
    root = args.package.resolve(strict=True)
    for path in ('app', 'vendor/python', 'vendor/squashfs', 'vendor/usb', 'app/container',
                 'app/provider', 'app/reader', 'app/workflow', 'app/ui'):
        sys.path.insert(0, str(root / path))
    os.environ['ZIG_GLOBAL_CACHE_DIR'] = str(root / 'state/cache/zig-global')
    os.environ['ZIG_LOCAL_CACHE_DIR'] = str(root / 'state/cache' / ('zig-' + args.lineage))
    calls = []
    import usb.core
    def forbidden(*a, **k):
        calls.append('device')
        raise AssertionError('Offline test cannot use USB, bind a driver or open a camera session')
    usb.core.find = forbidden
    import importlib
    controller = importlib.import_module('install_controller_custom' if args.lineage == 'user' else 'install_controller')
    import user_provider
    import simple_workflow
    import wizard as flow
    import menu_preparation_retry as retry
    import simple_app
    import integrity_backend as backend
    from product_integrity import verify_release
    verify_release()
    user_provider.binding_path().parent.mkdir(parents=True, exist_ok=True)
    if not user_provider.binding_path().exists():
        user_provider.atomic(user_provider.binding_path(), dict(schema='offline-test-binding/1', device_operations=0))
    class BoundaryReached(Exception):
        pass
    class Provider:
        check = lambda self: dict(passed=True, device_operations=0)
        load_legacy = lambda self: None
        def preflight(self, folder):
            raise BoundaryReached('Intentionally stop before first Windows/device operation')
        bind = session = forbidden
    runtime = controller.runtime()
    runtime.Provider = Provider
    accepted_run = 'offline_' + args.lineage
    proof = dict(receiver_p1_sha256='a' * 64, receiver_bytes=25100288,
                 accepted_reader_nonce='11' * 16, accepted_run=accepted_run, hashes={})
    checks = []
    private = root / 'state/offline_menu_seal' / args.lineage / uuid.uuid4().hex
    trial = controller.Trial(private, services=runtime)
    private.mkdir(parents=True)
    with patch.object(controller, 'receiver_evidence', return_value=proof):
        job, _ = runtime.jobs.prepare()
        reader = runtime.reader_jobs.prepare()
        assert not (root / 'app/provider/release.json').exists()
        plan = trial.seal(job, reader, patch_only=True)
        assert str(root / 'app/release.json') in plan['hashes']
        assert not any('/provider/release.json' in name.replace('\\', '/') for name in plan['hashes'])
        assert trial.validate(initial=True)[0] == plan
        checks.append('real_menu_and_reader_materials_seal_and_validate_without_legacy_manifest')
        try:
            trial.execute(stable_power=True, patch_only=True)
        except BoundaryReached:
            pass
        else:
            raise AssertionError('Did not reach intentional device boundary')
        status = controller.read(trial.status_path)
        assert status['phase'] == 'BINDING_UNCONFIRMED' and not status['window_started']
        assert not (Path(job) / 'claim.json').exists() and not (Path(reader) / 'claim.json').exists()
        checks.append('execute_reaches_preflight_and_stops_before_binding_or_session')
        original = trial.plan_path.read_bytes()
        corrupt = json.loads(original)
        corrupt['hashes'][str(root / 'app/release.json')] = '0' * 64
        controller.atomic(trial.plan_path, corrupt)
        try:
            trial.validate()
        except ValueError:
            pass
        else:
            raise AssertionError('Bad release manifest binding accepted')
        trial.plan_path.write_bytes(original)
        checks.append('central_manifest_hash_still_enforced')

        value = dict(schema='m4-user-flow/1', flow=uuid.uuid4().hex, phase='REVIEW_REQUIRED',
                     updater_lineage=args.lineage, purpose='patch_and_menu_only',
                     package_validation='not_performed', patch_run=accepted_run,
                     error="[Errno 2] No such file or directory: '" + str(root / 'app/provider/release.json') + "'")
        folder = flow.folder(value); folder.mkdir(parents=True)
        flow.save(value, value['phase'])
        migrated = retry.mark_retry(value)
        assert migrated['phase'] == 'MENU_PREPARATION_RETRY'
        assert simple_app.presentation(migrated)[3] == 'simple-continue'
        with patch.object(simple_workflow, 'open_menu', return_value={'phase': 'FAKE_MENU'}) as opening, \
             patch.object(simple_workflow, 'patch_receiver', forbidden):
            assert simple_workflow.continue_flow(migrated)['phase'] == 'FAKE_MENU'
            assert opening.call_args[0][0]['phase'] == 'PATCH_READY'
            assert opening.call_args[0][0]['p1_rewrite_required'] is False
        checks.append('same_session_local_failure_resumes_menu_without_patch_write')
        for marker in ('plan.json', 'status.json', 'start', 'execution'):
            location = folder / marker
            if '.' in marker:
                location.write_text('{}', encoding='utf-8')
            else:
                location.mkdir()
            migrated['phase'] = 'MENU_PREPARATION_RETRY'
            try:
                retry.eligible(migrated)
            except ValueError:
                pass
            else:
                raise AssertionError('Existing menu execution/plan was ignored')
            if location.is_dir(): location.rmdir()
            else: location.unlink()
        checks.append('any_prior_plan_or_execution_blocks_repeat')
        migrated.update(phase='REVIEW_REQUIRED', error="[Errno 2] unrelated file")
        try:
            retry.eligible(migrated)
        except ValueError:
            pass
        else:
            raise AssertionError('Unrelated failure was treated as recoverable')
        migrated.update(phase='MENU_PREPARATION_RETRY', patch_run='another_run')
        try:
            retry.eligible(migrated)
        except ValueError:
            pass
        else:
            raise AssertionError('Proof from another patch accepted')
        checks.append('unrelated_failure_and_mismatched_patch_remain_blocked')
        from normal_identity import DescriptorReadError
        for recovery, phase in (('VERIFIED', 'MENU_CONNECTION_STOPPED'),
                                ('RESTART_REQUIRED', 'WAITING_FOR_RESTART'),
                                ('NORMAL_CONNECTION_PENDING', 'WAITING_FOR_NORMAL')):
            activity = []
            class DescriptorFailureProvider:
                check = lambda self: None
                load_legacy = lambda self: None
                preflight = lambda self, folder: None
                def bind(self, folder):
                    activity.append('bind')
                    raise DescriptorReadError(dict(camera_commands=0, passed=False, attempts=[]))
                def restore(self, folder, confirmation=False):
                    activity.append('restore'); return recovery
                session = forbidden
            runtime.Provider = DescriptorFailureProvider
            attempt = controller.Trial(private / ('descriptor_' + recovery), services=runtime)
            attempt.seal(job, reader, patch_only=True)
            result = attempt.execute(stable_power=True, patch_only=True)
            assert result['phase'] == 'MENU_CONNECTION_STOPPED' and result['stopped_before_session']
            assert not result['window_started'] and not result['preread_started'] and not result['firmware_written']
            assert activity == ['bind'] and result['normal_recovery'] == 'NOT_REQUESTED'
            result = attempt.restore(runtime.Provider(), attempt.private / 'start', result)
            assert result['phase'] == phase and activity == ['bind', 'restore']
        checks.append('descriptor_failure_keeps_driver_until_explicit_restore')
        from driver_restart import WindowsRestartRequired
        for stage in ('preflight', 'bind'):
            activity = []
            class StageRestartProvider(DescriptorFailureProvider):
                def preflight(self, folder):
                    if stage == 'preflight':
                        activity.append(stage); raise WindowsRestartRequired()
                def bind(self, folder):
                    activity.append(stage); raise WindowsRestartRequired()
                restore = session = forbidden
            runtime.Provider = StageRestartProvider
            attempt = controller.Trial(private / ('stage_restart_' + stage), services=runtime)
            attempt.seal(job, reader, patch_only=True)
            result = attempt.execute(stable_power=True, patch_only=True)
            assert result['phase'] == 'WINDOWS_RESTART_REQUIRED' and result['stopped_before_session']
            assert result['safe_to_restore'] and not result['preread_started'] and not result['window_started']
            assert not result['firmware_written'] and activity == [stage]
        checks.append('stagebind_restart_stops_menu_before_session_and_preread')
        activity = []
        class SessionDescriptorFailure(DescriptorFailureProvider):
            bind = lambda self, folder: None
            @contextmanager
            def session(self, folder):
                activity.append('session_descriptor')
                raise DescriptorReadError(dict(camera_commands=0, passed=False, attempts=[]))
                yield
            def restore(self, folder, confirmation=False): activity.append('restore'); return 'VERIFIED'
        runtime.Provider = SessionDescriptorFailure
        attempt = controller.Trial(private / 'session_descriptor', services=runtime)
        attempt.seal(job, reader, patch_only=True)
        result = attempt.execute(stable_power=True, patch_only=True)
        assert result['phase'] == 'MENU_CONNECTION_STOPPED' and activity == ['session_descriptor']
        checks.append('session_descriptor_failure_keeps_driver_without_authentication')
        class NormalPending(DescriptorFailureProvider):
            def preflight(self, folder):
                raise user_provider.CommunicationNotReady('normal PID pending')
            bind = session = restore = forbidden
        runtime.Provider = NormalPending
        attempt = controller.Trial(private / 'normal_pending', services=runtime)
        attempt.seal(job, reader, patch_only=True)
        result = attempt.execute(stable_power=True, patch_only=True)
        assert result['phase'] == 'MENU_CONNECTION_STOPPED' and result['driver_retained']
        assert not result['window_started'] and not result['preread_started']
        checks.append('normal_pid_wait_does_not_become_unknown_write_or_restore_driver')
        class UnknownBindFailure(DescriptorFailureProvider):
            def bind(self, folder): raise OSError('unknown bind outcome')
            restore = forbidden
        runtime.Provider = UnknownBindFailure
        attempt = controller.Trial(private / 'unknown_bind', services=runtime)
        attempt.seal(job, reader, patch_only=True)
        try: attempt.execute(stable_power=True, patch_only=True)
        except OSError: pass
        else: raise AssertionError('Unknown bind failure was cleared')
        assert controller.read(attempt.status_path)['phase'] == 'BINDING_UNCONFIRMED'
        checks.append('unknown_bind_failure_does_not_assume_safe_recovery')
        # Reproduce a verified p1 followed by a pre-authentication menu failure.
        # Recovery must never enter the writer-outcome branch for this state.
        class RestoreFailure(DescriptorFailureProvider):
            def restore(self, folder, confirmation=False): raise ValueError('Driver recovery failed')
        runtime.Provider = RestoreFailure
        value = dict(schema='m4-user-flow/1', flow=uuid.uuid4().hex, phase='REVIEW_REQUIRED',
                     updater_lineage=args.lineage, patch_run=accepted_run)
        attempt = controller.Trial(flow.folder(value), services=runtime)
        flow.folder(value).mkdir(parents=True)
        attempt.seal(job, reader, patch_only=True)
        result = attempt.execute(stable_power=True, patch_only=True)
        try: attempt.restore(runtime.Provider(), attempt.private / 'start', result)
        except ValueError: pass
        else: raise AssertionError('Expected a saved restoration failure')
        flow.save(value, 'REVIEW_REQUIRED')
        import menu_connection_recovery, usb_recovery, standalone_usb_restore
        class CompletedJournal:
            def __init__(self, *args): pass
            def load(self): return dict(phase='COMPLETE', run=accepted_run, read_verified=True,
                                       session_ended=True, normal_recovery_verified=True)
        with patch.object(backend.frozen, 'Journal', CompletedJournal), \
             patch.object(usb_recovery, 'recover_write_race', forbidden), \
             patch.object(standalone_usb_restore, 'recover', return_value=dict(phase='USB_RESTORE_COMPLETE', message='normal')) as restoring:
            result = usb_recovery.recover(value)
            assert result['phase'] == 'MENU_CONNECTION_STOPPED' and restoring.call_count == 1
        flow.save(value, 'REVIEW_REQUIRED')
        with patch.object(backend.frozen, 'Journal', CompletedJournal), \
             patch.object(usb_recovery, 'recover_write_race', forbidden), \
             patch.object(standalone_usb_restore, 'recover', return_value=dict(phase='USB_RESTORE_WINDOWS_RESTART', message='restart computer')):
            result = usb_recovery.recover(value)
            assert result['phase'] == 'WINDOWS_RESTART_REQUIRED' and not result['final_unplug_ready']
        saved = controller.read(attempt.status_path)
        saved['window_started'] = True; controller.atomic(attempt.status_path, saved)
        with patch.object(backend.frozen, 'Journal', CompletedJournal):
            assert menu_connection_recovery.proof(value) is None
        checks.append('verified_p1_and_unstarted_menu_recover_without_writer_gate_or_new_firmware_work')
    assert not calls
    result = dict(passed=True, lineage=args.lineage, tests=checks, cases=len(checks),
                  device_operations=0, driver_tasks_dispatched=0, fake_receiver_proof=True,
                  native_materials_built=True, physical_installation_tested=False)
    destination = root / 'state/source_tests' / ('menu_' + args.lineage + '.json')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
