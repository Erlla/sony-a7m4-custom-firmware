from product_integrity import pinned, state_path
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
from engine import atomic, local_under, read, require, sha
HERE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'app'
PS = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
READER = BASE / 'reader'
WRITER = BASE / 'writer'
SNAPSHOTS = ROOT / 'state/snapshots'

class Provider:

    def load_legacy(self):
        path = ROOT / 'app/reader/current_reader.py'
        spec = importlib.util.spec_from_file_location('m4_current_reader', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.legacy = module
        return module

    def same_body(self, state):
        require(state['normal_count'] == 1 and len(state['normal']) == 1 and (state['service_count'] == 0), '请只连接这一台已绑定的 M4，并切至 USB 海量存储模式。')
        row = state['normal'][0]
        require(hashlib.sha256(row['instance'].upper().encode()).hexdigest().lower() == self.binding['camera_instance_sha256'].lower(), '连接的不是已绑定机身。')
        require(row['status'] == 'OK', 'Windows camera status is not OK')
        return row

    def preflight(self, folder):
        snapshot, state = self.snapshot(folder)
        row = self.same_body(state)
        require(row['service'] == 'USBSTOR' and row['inf'] == 'usbstor.inf' and any((v['accessible'] and v['belongs_to_camera'] for v in state['pmhome'])), '普通 USBSTOR/PMHOME 尚未恢复，未切换驱动。')
        self.tasks_clear(snapshot)

    @contextmanager
    def session(self, folder):
        out = folder / 'execution'
        out.mkdir(exist_ok=False)
        path = BASE / 'protocol/identity.py'
        spec = importlib.util.spec_from_file_location('oneclick_bound_session', path)
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        backend = helper.backend(out)
        with backend.ResearchSession(out / 'session', expected=self.binding['identity']) as session:
            atomic(out / 'identity.private.json', session.identity)
            atomic(out / 'libraries.json', helper.libraries(session, out))
            yield session

    def hold_session(self, session):
        session.wire.healthy = False

    def normal_ready(self, folder):
        _, state = self.snapshot(folder)
        if state['normal_count'] == 0 and state['service_count'] == 0:
            return False
        row = self.same_body(state)
        return row['service'] == 'USBSTOR' and row['inf'] == 'usbstor.inf' and any((v['accessible'] and v['belongs_to_camera'] for v in state['pmhome']))

    def wait_for_normal(self, folder, *, timeout=45, clock=time.monotonic, sleep=time.sleep):
        """Only poll PnP; do not dispatch Restore while normal USB is absent."""
        deadline = clock() + timeout
        while True:
            code, state = self.host('Connection', folder)
            require(code == 0, 'Read-only connection probe failed')
            if state['normal_count'] == 1 and state['service_count'] == 0:
                self.same_body(state)
                return True
            require(state['normal_count'] == 0 and state['service_count'] in (0, 1), 'Multiple or ambiguous cameras; Restore was not dispatched')
            if clock() >= deadline:
                return False
            sleep(min(2, max(0, deadline - clock())))

    def restore(self, folder, confirmation=False):
        if not confirmation and (not self.wait_for_normal(folder)):
            return 'NORMAL_CONNECTION_PENDING'
        if confirmation:
            snapshot, state = self.snapshot(folder)
            row = self.same_body(state)
            require(row['service'] == 'USBSTOR' and row['inf'] == 'usbstor.inf' and any((v['accessible'] and v['belongs_to_camera'] for v in state['pmhome'])), 'Normal connection is not ready for confirmation')
            prior = read(snapshot / 'latest_Restore.json')
            if prior['status'] in ('RECOVERY_CONFIRMED', 'USBSTOR_RESTORED'):
                self.tasks_clear(snapshot)
                return 'VERIFIED'
            pending = read(folder / 'recovery_pending.json')
            require(prior['status'] == 'NEEDS_REVIEW' and prior['run_id'] == pending['run_id'], 'Pending recovery belongs to a different task')
        code, result = self.host('Broker', folder, 'Restore')
        if code == 2 and result.get('mode') == 'Restore' and (result.get('status') == 'NOT_DISPATCHED_NO_NORMAL_CAMERA') and (result.get('task_dispatched') is False):
            return 'NORMAL_CONNECTION_PENDING'
        snapshot, state = self.snapshot(folder)
        row = self.same_body(state)
        require(read(snapshot / 'latest_Restore.json')['run_id'] == result['run_id'], 'Restore task run changed')
        if code == 0 and result['status'] in ('USBSTOR_RESTORED', 'RECOVERY_CONFIRMED'):
            require(row['service'] == 'USBSTOR' and row['inf'] == 'usbstor.inf' and any((v['accessible'] and v['belongs_to_camera'] for v in state['pmhome'])), 'Restore postcondition failed')
            self.tasks_clear(snapshot)
            if confirmation:
                final = read(snapshot / 'Restore_task_result.json')
                require(result['status'] == 'RECOVERY_CONFIRMED' and final['device_mutation_started'] is False, 'Recovery confirmation unexpectedly mutated a device')
            return 'VERIFIED'
        final = read(snapshot / 'Restore_task_result.json')
        detail = read(snapshot / 'Restore_auto_restore_result.private.json')
        require(not confirmation and code == 1 and (result['status'] == 'NEEDS_REVIEW') and (final['run_id'] == result['run_id']) and (final['status'] == 'NEEDS_REVIEW') and (final['error'] == 'Restore helper returned 1') and (final['device_mutation_started'] is True) and (detail['error'] == 'USBSTOR/PMHOME did not become accessible within the postcondition deadline.') and (row['service'] == 'USBSTOR') and (row['inf'] == 'usbstor.inf'), '驱动恢复结果需要人工核对，未重复操作。')
        atomic(folder / 'recovery_pending.json', dict(run_id=result['run_id']))
        return 'RESTART_REQUIRED'
