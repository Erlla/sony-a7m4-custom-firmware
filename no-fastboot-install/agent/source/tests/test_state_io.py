"""Real Windows file-sharing checks and local-only pre-device failure recovery."""
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch
import argparse
import json
import os
import sys
import tempfile
import threading
import time
import uuid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, required=True)
    root = parser.parse_args().package.resolve(strict=True)
    for name in ('app', 'vendor/python', 'vendor/squashfs', 'vendor/usb', 'app/container',
                 'app/provider', 'app/reader', 'app/workflow', 'app/ui'):
        sys.path.insert(0, str(root / name))
    import state_io as io
    import integrity_backend as backend
    import local_task_stop as local
    import wizard as flow
    import usb_recovery
    import standalone_usb_restore
    from product_integrity import verify_release
    verify_release()
    tests = []
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        target = base / 'sample.json'
        io.atomic_json(target, {'generation': 0})
        if os.name == 'nt':
            # Reproduce WinError 5/32 with the ordinary reader's delete-denying handle.
            old_reader = target.open('rb')
            outcome = []
            def writing():
                try: io.atomic_json(target, {'generation': 1}); outcome.append('done')
                except BaseException as e: outcome.append(e)
            worker = threading.Thread(target=writing)
            worker.start(); time.sleep(0.15)
            assert worker.is_alive() and not outcome
            old_reader.close(); worker.join(4)
            assert outcome == ['done'] and io.read_json(target)['generation'] == 1
            tests.append('real_windows_delete_denial_recovers_after_reader_closes')
            # Hold the new reader inside json.load: replacement must finish before it closes.
            opened, release = threading.Event(), threading.Event()
            original_load = io.json.load
            rows = []
            def held_load(stream):
                opened.set(); assert release.wait(3)
                return original_load(stream)
            def reading(): rows.append(io.read_json(target))
            with patch.object(io.json, 'load', held_load):
                reader = threading.Thread(target=reading); reader.start()
                assert opened.wait(2)
                try: io.atomic_json(target, {'generation': 2})
                finally: release.set()
                reader.join(3)
            assert rows == [{'generation': 1}] and io.read_json(target)['generation'] == 2
            tests.append('delete_sharing_reader_allows_atomic_replace_while_open')
        long = base / ('x' * 100) / ('y' * 100) / ('z' * 70) / 'value.json'
        io.atomic_json(long, {'complete': True})
        assert io.read_json(long) == {'complete': True}
        os.unlink(io.io_path(long))
        parent = long.parent
        while parent != base:
            assert parent.resolve().is_relative_to(base.resolve())
            os.rmdir(io.io_path(parent))
            parent = parent.parent
        tests.append('extended_paths_round_trip')
        # A persistent sharing error is bounded; disk-full is never retried.
        class Denied(OSError): winerror = 5
        clock = [0.0]; attempts = []
        def denying(*args): attempts.append(args); raise Denied('held')
        with patch.object(io, '_replace_once', denying):
            try: io.replace_state('source', 'target', timeout=0.25, clock=lambda: clock[0], sleep=lambda n: clock.__setitem__(0, clock[0] + n))
            except Denied: pass
            else: raise AssertionError('Persistent lock was ignored')
        assert 0.25 <= clock[0] <= 0.26 and len(attempts) < 10
        tests.append('persistent_lock_retry_is_bounded_metadata_only')
        original = target.read_bytes()
        with patch.object(io, 'replace_state', side_effect=OSError(28, 'disk full')):
            try: io.atomic_json(target, {'generation': 3})
            except OSError: pass
            else: raise AssertionError('Publication error was swallowed')
        assert target.read_bytes() == original and not list(base.glob('j*.tmp'))
        tests.append('failed_publication_preserves_old_document_and_cleans_temp')

        private = base / 'state/workflow/patch'
        flows = base / 'state/workflow'
        with patch.object(backend, 'STATE', private), patch.object(flow, 'PRIVATE', flows):
            def fixture():
                value = dict(schema='m4-user-flow/1', flow=uuid.uuid4().hex, phase='REVIEW_REQUIRED',
                             purpose='patch_and_menu_only', package_validation='not_performed',
                             created_utc=datetime.now(timezone.utc).isoformat())
                flow.folder(value).mkdir(parents=True)
                journal = backend.frozen.Journal(private)
                journal.create(backend.LOADED_SHA)
                value.update(updated_utc=datetime.now(timezone.utc).isoformat(),
                    error='[WinError 5] access denied: ' + str(private / 'control' / (journal.value['run'] + '.json')))
                flow.save(value, 'REVIEW_REQUIRED')
                return value, journal
            value, journal = fixture()
            assert local.proof(value, journal)['device_operations'] == 0
            restored = local.reconcile(value)
            assert restored['phase'] == 'CANCELLED_BEFORE_DEVICE' and restored['device_started'] is False
            assert backend.frozen.Journal(private).load()['phase'] == 'STOPPED_BEFORE_DRIVER_CHANGE'
            tests.append('matching_initial_record_failure_retires_without_device_work')
            for mutate in (
                lambda v, j: v.update(patch_run='another'),
                lambda v, j: v.update(created_utc='2099-01-01T00:00:00+00:00'),
                lambda v, j: v.update(error='unrelated failure'),
                lambda v, j: j.update('BINDING'),
                lambda v, j: j.update('WRITE_STARTING', firmware_write_attempted=True),
                lambda v, j: j.update('PREPARING', preparation={'writer': 'present'}),
                lambda v, j: (j.folder / 'execution').mkdir(),
                lambda v, j: (flow.folder(v) / 'status.json').write_text('{}', encoding='utf-8'),
            ):
                value, journal = fixture(); mutate(value, journal)
                try: result = local.proof(value, journal)
                except (ValueError, OSError, KeyError): result = None
                assert result is None
            tests.append('unrelated_mismatched_or_executed_tasks_cannot_be_cleared')
            value, journal = fixture()
            original_atomic = backend.frozen.atomic
            def fail_initial_action(path, row):
                if Path(path).parent.name == 'control' and row.get('revision') == 2 and row.get('phase') == 'PREPARING':
                    raise Denied('fake initial action publication denied')
                original_atomic(path, row)
            calls = []
            class Backend:
                check = lambda self: None
                runner_sha = lambda self: backend.LOADED_SHA
                def prepare_reader(self, *a): calls.append('reader'); raise AssertionError('Should not prepare or upload')
            # Use a fresh journal root so Engine.read can begin independently of fixtures.
            engine = backend.frozen.Engine(Backend(), base / 'engine')
            with patch.object(backend.frozen, 'atomic', fail_initial_action):
                try: engine.read('apply')
                except Denied: pass
                else: raise AssertionError('Expected the injected local failure')
            assert not calls and engine.state()['phase'] == 'STOPPED_BEFORE_DRIVER_CHANGE'
            tests.append('engine_action_record_failure_stops_before_reader_or_driver')
            value, journal = fixture()
            fake = dict(phase='USB_RESTORE_COMPLETE', message='normal', folder=None)
            with patch.object(standalone_usb_restore, 'recover', return_value=fake) as restore:
                result = usb_recovery.recover(value)
                assert result['phase'] == 'CANCELLED_BEFORE_DEVICE' and restore.call_count == 1
            tests.append('recovery_routes_local_stop_to_driver_only_entry')
    result = dict(passed=True, tests=tests, cases=len(tests), device_operations=0,
                  driver_tasks_dispatched=0, firmware_operations=0, real_windows_sharing_tested=os.name == 'nt')
    destination = root / 'state/source_tests/state_io.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(result))


if __name__ == '__main__': main()
