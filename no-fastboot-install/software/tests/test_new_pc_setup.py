"""First-use setup boundaries with fake Windows state and subprocess results."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import argparse
import hashlib
import json
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, required=True)
    root = parser.parse_args().package.resolve(strict=True)
    for name in ('app', 'app/provider', 'app/workflow'):
        sys.path.insert(0, str(root / name))
    import user_provider as up
    import driver_restart
    checks = []
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        enrollment = folder / 'enrollment.json'
        enrollment.write_text('{}')
        row = dict(instance=r'USB\VID_054C&PID_0DA5\FIXTURE', service='USBSTOR',
                   inf='usbstor.inf', status='OK')
        state = dict(normal_count=1, service_count=0, normal=[row])
        provider = up.Provider()
        provider.binding = dict(camera_instance_sha256=hashlib.sha256(row['instance'].upper().encode()).hexdigest())
        old = folder / 'old'; new = folder / 'new'
        old.mkdir(); new.mkdir()
        pending = old / 'latest_StageBind.json'
        pending.write_text(json.dumps(dict(status='NEEDS_REVIEW', error='Driver staging failed: -2146762487')))
        (new / 'latest_StageBind.json').write_text(json.dumps(dict(status='STAGE_SIGNATURE_REFUSAL_REVIEWED')))
        with patch.object(up, 'ENROLLMENT', enrollment), \
             patch.object(driver_restart, 'require_ready'), \
             patch.object(provider, 'wait_communication', return_value=(old, state)), \
             patch.object(provider, 'prepare_driver_trust', return_value=True) as prepare, \
             patch.object(provider, 'snapshot', return_value=(new, state)) as snapshot:
            provider.preflight(folder)
            assert prepare.call_count == snapshot.call_count == 1
            assert json.loads(pending.read_text())['status'] == 'NEEDS_REVIEW'
            checks.append('known_signature_failure_gets_fresh_confirmation_without_rewriting_snapshot')
            pending.write_text(json.dumps(dict(status='RUNNING', error='unrelated operation')))
            prepare.reset_mock(); snapshot.reset_mock()
            try:
                provider.preflight(folder)
            except ValueError as error:
                assert 'unrelated operation' in str(error)
            else:
                raise AssertionError('Unrelated pending task entered setup')
            assert prepare.call_count == snapshot.call_count == 0
            checks.append('other_pending_tasks_stop_before_certificate_setup')
            pending.unlink()
            prepare.return_value = False
            provider.preflight(folder)
            assert prepare.call_count == 1 and snapshot.call_count == 0
            checks.append('unchanged_trust_does_not_repeat_windows_snapshot')

        def run_report(report, code=0):
            def run(command, **kwargs):
                assert command[command.index('-File') + 1].endswith('driver_trust.ps1')
                assert 'capture_output' in kwargs
                if report is not None:
                    Path(command[command.index('-Output') + 1]).write_text(json.dumps(report))
                return SimpleNamespace(returncode=code, stdout='', stderr='fixture script error' if code else '')
            return run
        for report, code, expected in [
            (dict(phase='DRIVER_TRUST_CANCELLED'), 1, '未切换驱动'),
            (dict(phase='DRIVER_TRUST_FAILED', error='specific signing error'), 1, 'specific signing error'),
            (None, 1, 'fixture script error'),
        ]:
            with patch.object(up.subprocess, 'run', side_effect=run_report(report, code)):
                try:
                    provider.prepare_driver_trust(folder)
                except ValueError as error:
                    assert expected in str(error)
                else:
                    raise AssertionError('Failed or cancelled setup accepted')
        checks.append('cancel_script_failure_and_missing_receipt_are_reported_without_binding')
        with patch.object(up.subprocess, 'run', side_effect=run_report(dict(
                phase='DRIVER_TRUST_READY', stores_added=['Root', 'TrustedPublisher']))):
            assert provider.prepare_driver_trust(folder)
        checks.append('certificate_install_receipt_requires_fresh_state')
    print(json.dumps(dict(passed=True, cases=len(checks), tests=checks,
                         certificate_stores_modified=0, driver_tasks_dispatched=0, device_operations=0)))


if __name__ == '__main__':
    main()
