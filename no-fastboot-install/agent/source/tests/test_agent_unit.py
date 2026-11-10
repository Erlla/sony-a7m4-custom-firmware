"""Agent control plane with inert host/workflow. Never enumerates or touches USB."""
from contextlib import ExitStack
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
import io
import json
import os
import sys
import tempfile
import threading
import time
import unittest

APP = Path(__file__).resolve().parents[1] / 'app'
sys.path.insert(0, str(APP))
import agent_api as api
import agent_coordination as coord
import agent_guidance as guide
import agent_platform as platform


class Host:
    def __init__(self): self.launches = []; self.connection = dict(normal_count=1, service_count=0)
    def probe(self): return self.connection
    def launch(self, exe, job, dispatch): self.launches.append((exe, job, dispatch))


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.dict(os.environ, {'ProgramData': str(self.root/'programdata'),
                                                         'M4_TOOL_DATA_ROOT': str(self.root/'state')}))
        self.stack.enter_context(patch('recovery_registry.user_sid', return_value='TEST-USER'))
        self.store = api.Store(self.root); self.host = Host()

    def prepared(self):
        return api.doctor(self.store, self.host)

    def submit(self, value):
        return api.submit(self.store, self.host, 'start', value['job'], value['pending']['id'], 'approve-write')

    def dispatch(self, value, execute):
        saved = self.store.load(value['job'])
        return api.worker(self.store, value['job'], saved['dispatch'], execute=execute)

    def test_new_machine_does_not_need_runtime_installed(self):
        value = self.prepared()
        self.assertEqual(value['pending']['kind'], 'write'); self.assertEqual(self.host.launches, [])
        self.assertFalse((self.root/'programdata').exists())

    def test_independent_agent_version_and_experimental_task_separation(self):
        value = self.prepared()
        self.assertEqual(value['version'], '1.01')
        self.assertEqual(value['build_id'], api.BUILD_ID)
        saved = self.store.load(value['job'])
        saved['build_id'] = '1.02-agent-20261110-r6'
        self.store.save(saved)
        with self.assertRaisesRegex(ValueError, '构建标识不匹配'):
            self.store.load(value['job'])
        self.assertEqual(self.host.launches, [])

    def test_missing_or_multiple_cameras(self):
        for normal, service in ((0, 0), (2, 0), (1, 1)):
            self.host.connection = dict(normal_count=normal, service_count=service)
            self.assertEqual(api.doctor(self.store, self.host)['status'], 'CONNECTION_REQUIRED')
        self.assertIsNone(self.store.current())

    def test_unconfirmed_wrong_or_old_reply_is_rejected(self):
        value = self.prepared()
        for request, answer in (('0'*32, 'approve-write'), (value['pending']['id'], 'usb-replugged')):
            with self.assertRaises(ValueError): api.submit(self.store, self.host, 'start', value['job'], request, answer)
        self.assertEqual(self.host.launches, [])

    def test_duplicate_start_does_not_dispatch_twice(self):
        value = self.prepared(); self.submit(value)
        with self.assertRaises(ValueError): self.submit(value)
        self.assertEqual(len(self.host.launches), 1)

    def test_doctor_after_client_restart_returns_same_job(self):
        value = self.prepared(); self.submit(value)
        again = api.doctor(api.Store(self.root), self.host)
        self.assertEqual(again['job'], value['job']); self.assertEqual(len(self.host.launches), 1)

    def test_uac_cancel_creates_new_confirmation(self):
        value = self.prepared(); error = OSError('cancel'); error.winerror = 1223
        with patch.object(self.host, 'launch', side_effect=error), self.assertRaises(OSError): self.submit(value)
        saved = self.store.load(value['job'])
        self.assertEqual(saved['phase'], 'ADMIN_CANCELLED'); self.assertNotEqual(saved['pending']['id'], value['pending']['id'])

    def test_unknown_launch_failure_cannot_be_retried(self):
        value = self.prepared()
        with patch.object(self.host, 'launch', side_effect=OSError('lost reply')), self.assertRaises(OSError): self.submit(value)
        self.assertIsNone(self.store.load(value['job'])['pending'])
        with self.assertRaises(ValueError): self.submit(value)

    def test_worker_claim_is_single_use(self):
        value = self.prepared(); self.submit(value); calls = []
        def execute(action, **kwargs): calls.append(action); return dict(phase='COMPLETE')
        self.dispatch(value, execute)
        with self.assertRaises(ValueError): self.dispatch(value, execute)
        self.assertEqual(calls, ['start'])

    def test_background_progress_and_cause(self):
        value = self.prepared(); self.submit(value)
        def execute(*args, **kwargs):
            print('{"progress_chunks":65,"total_chunks":766}')
            raise OSError('original read error')
        result = self.dispatch(value, execute)
        self.assertEqual(result['progress']['completed'], 65)
        self.assertEqual(result['diagnostic']['original_error'], 'original read error')
        self.assertNotIn('traceback', result['diagnostic'])

    def test_patch_complete_is_not_menu_or_install_success(self):
        value = self.prepared(); self.submit(value)
        result = self.dispatch(value, lambda *a, **k: dict(phase='HANDOFF_NOT_READY', p1_operation_complete=True))
        self.assertTrue(result['p1_operation_complete']); self.assertFalse(result['menu_ready'])
        self.assertEqual(result['installation_outcome'], 'not_started')
        self.assertEqual(result['pending']['kind'], 'camera-restart')

    def test_stagebind_requires_windows_restart(self):
        value = self.prepared(); self.submit(value)
        result = self.dispatch(value, lambda *a, **k: dict(phase='WINDOWS_RESTART_REQUIRED', prewrite_stop=True))
        self.assertEqual(result['pending']['answers'], ['windows-restarted'])
        with self.assertRaises(ValueError): api.submit(self.store, self.host, 'resume', value['job'], result['pending']['id'], 'usb-replugged')

    def test_menu_expiry_replaces_allowed_answer_without_new_window(self):
        value = self.prepared(); saved = self.store.load(value['job'])
        api.ask(saved, 'menu', 'check menu', ['menu-confirmed', 'menu-unavailable'])
        saved['window_bound'] = dict(monotonic=time.monotonic()-590, utc=(datetime.now(timezone.utc)-timedelta(seconds=590)).isoformat())
        self.store.save(saved); shown = api.public(saved)
        self.assertFalse(shown['menu_ready']); self.assertEqual(shown['pending']['kind'], 'expired-menu')
        with self.assertRaises(ValueError): api.submit(self.store, self.host, 'resume', saved['job'], saved['pending']['id'], 'menu-confirmed')
        result = api.submit(self.store, self.host, 'resume', saved['job'], saved['pending']['id'], 'ended-restarted')
        self.assertEqual(result['status'], 'DISPATCHING'); self.assertEqual(self.store.load(saved['job'])['operation'], 'recover-usb')

    def test_install_in_progress_ignores_window_expiry(self):
        value = self.prepared(); saved = self.store.load(value['job'])
        api.ask(saved, 'install-result', '等待相机结束，不断电', ['installed-ok', 'install-failed'])
        saved['window_bound'] = dict(monotonic=0, utc='2000-01-01T00:00:00+00:00')
        self.assertEqual(api.public(saved)['pending']['kind'], 'install-result')

    def test_foreign_active_task_blocks_new_submission(self):
        coord.registry().parent.mkdir(parents=True)
        api.atomic_json(coord.registry(), dict(job='a'*32, source=str(self.root/'other'), closed=False))
        result = api.doctor(self.store, self.host)
        self.assertEqual(result['status'], 'OTHER_INSTALLATION_PENDING'); self.assertEqual(self.host.launches, [])

    def test_gui_cannot_take_over_agent_task(self):
        coord.registry().parent.mkdir(parents=True)
        api.atomic_json(coord.registry(), dict(job='a'*32, source=str(self.root), closed=False))
        with patch.dict(os.environ, {'M4_TOOL_SESSION':'b'*32}), self.assertRaises(RuntimeError):
            with coord.desktop_guard(): pass

    def test_unsupported_platform_never_constructs_host(self):
        for system, arch in (('Darwin', 'arm64'), ('Darwin', 'x86_64'), ('Linux', 'x86_64'), ('Windows', 'ARM64')):
            self.assertFalse(platform.capability(system, arch)['supported'])

    def test_clock_discontinuity_refuses_menu(self):
        bound = dict(monotonic=100, utc='2026-11-10T00:00:00+00:00')
        self.assertEqual(guide.remaining(bound, (110, datetime.fromisoformat('2026-11-10T00:10:00+00:00'))), 0)

    def test_driver_wait_variants_have_actionable_prompts(self):
        expected = {'USB_RESTORE_REPLUG': 'replug', 'USB_RESTORE_WINDOWS_RESTART': 'windows-restart',
                    'USB_RESTORE_WAITING': 'replug', 'USB_RESTORE_CANCELLED': 'restore', 'USB_RESTORE_RETRY': 'restore'}
        for phase, kind in expected.items(): self.assertEqual(guide.next_request(dict(phase=phase))[0], kind)

    def test_unknown_write_result_does_not_offer_recovery(self):
        self.assertIsNone(guide.next_request(dict(phase='REVIEW_REQUIRED', firmware_written=None)))

    def test_state_save_failure_prevents_dispatch(self):
        value = self.prepared()
        with patch.object(self.store, 'save', side_effect=OSError('disk full')), self.assertRaises(OSError): self.submit(value)
        self.assertEqual(self.host.launches, [])

    def test_concurrent_clients_only_dispatch_once(self):
        value = self.prepared(); entered = threading.Event(); release = threading.Event(); calls = []
        def launch(*args): calls.append(args); entered.set(); release.wait(5)
        errors = []
        def submit():
            try: self.submit(value)
            except Exception as error: errors.append(error)
        with patch.object(self.host, 'launch', side_effect=launch):
            first = threading.Thread(target=submit); first.start(); self.assertTrue(entered.wait(5))
            second = threading.Thread(target=submit); second.start(); second.join(5)
            release.set(); first.join(5)
        self.assertEqual(len(calls), 1); self.assertEqual(len(errors), 1)

    def test_complete_user_handoff_has_no_second_start(self):
        value = self.prepared(); self.submit(value); calls = []
        flow_id = 'c'*32
        base = self.root/'state/sessions'/value['job']/'workflow'
        folder = base/'flows'/flow_id
        flow = dict(flow=flow_id, phase='AWAITING_MENU_OBSERVATION', final_unplug_ready=True, p1_operation_complete=True)
        api.atomic_json(base/'flow.json', dict(flow=flow_id))
        api.atomic_json(folder/'flow.json', flow)
        api.atomic_json(folder/'status.json', dict(window_start_bound=dict(monotonic=time.monotonic(), utc=api.utc())))
        def execute(action, **kwargs):
            calls.append(action)
            return dict(phase='COMPLETE') if action == 'installed' else flow
        menu = self.dispatch(value, execute)
        self.assertTrue(menu['menu_ready']); self.assertGreater(menu['seconds_remaining'], 90)
        waiting = api.submit(self.store, self.host, 'resume', value['job'], menu['pending']['id'], 'menu-confirmed')
        self.assertEqual(waiting['pending']['kind'], 'install-result'); self.assertEqual(calls, ['start'])
        self.assertEqual(len(self.host.launches), 1)
        with self.assertRaises(ValueError): api.submit(self.store, self.host, 'resume', value['job'], menu['pending']['id'], 'menu-confirmed')
        api.submit(self.store, self.host, 'resume', value['job'], waiting['pending']['id'], 'installed-ok')
        done = self.dispatch(value, execute)
        self.assertEqual(calls, ['start', 'installed']); self.assertEqual(done['status'], 'FINISHED')
        self.assertEqual(done['installation_outcome'], 'user_reported_success_not_read_back')
        self.assertTrue(coord.current()['closed'])

    def test_worker_entry_failure_keeps_real_cause(self):
        value = self.prepared(); self.submit(value); saved = self.store.load(value['job'])
        with patch.object(api, 'worker', side_effect=RuntimeError('another operation owns USB')), self.assertRaises(RuntimeError):
            api.run_worker(self.store, value['job'], saved['dispatch'])
        saved = self.store.load(value['job'])
        self.assertEqual(saved['phase'], 'WORKER_ENTRY_FAILED')
        self.assertEqual(saved['diagnostic']['original_error'], 'another operation owns USB')
        self.assertIsNone(saved['pending'])

    def test_gui_pending_operation_blocks_agent(self):
        coord.registry().parent.mkdir(parents=True)
        api.atomic_json(coord.registry(), dict(job='a'*32, source=str(self.root), client='desktop', closed=False))
        self.assertEqual(api.doctor(self.store, self.host)['status'], 'OTHER_INSTALLATION_PENDING')

    def test_stale_heartbeat_never_implies_finished(self):
        value = self.prepared(); self.submit(value); saved = self.store.load(value['job'])
        saved.update(status='RUNNING', heartbeat_utc='2000-01-01T00:00:00+00:00')
        shown = api.public(saved)
        self.assertEqual(shown['status'], 'RUNNING'); self.assertIsNone(shown['pending'])
        self.assertEqual(len(shown['commands']), 1)

    def test_authorization_prompt_does_not_say_no_action(self):
        value = self.prepared(); saved = self.store.load(value['job'])
        reporter = api.Reporter(self.store, saved, io.StringIO())
        reporter.write('首次使用：请确认 Windows 管理员授权窗口。\n')
        self.assertIn('手动确认', saved['message'])
        self.assertNotIn('无需操作', saved['message'])

    def test_restore_authorization_and_progress_reset(self):
        value = self.prepared(); saved = self.store.load(value['job'])
        saved['progress'] = dict(completed=766, total=766)
        reporter = api.Reporter(self.store, saved, io.StringIO())
        reporter.write('正在恢复普通 USB，首次执行请确认管理员授权。\n')
        self.assertNotIn('无需操作', saved['message'])
        reporter.write('开始一次性写入。请勿拔线。\n')
        self.assertIsNone(saved['progress'])
        self.assertIn('开始一次性写入', saved['message'])

    def test_watch_reads_same_task_and_stops_at_human_request(self):
        value = self.prepared(); self.submit(value); rows = []; clock = [0]
        def pause(seconds):
            clock[0] += seconds
            saved = self.store.load(value['job'])
            api.ask(saved, 'menu', 'look', ['menu-confirmed'])
            self.store.save(saved)
        api.watch_status(self.store, value['job'], emit=rows.append, clock=lambda: clock[0], sleep=pause)
        self.assertEqual([r['status'] for r in rows], ['DISPATCHING', 'WAITING_USER'])
        self.assertEqual(len(self.host.launches), 1)

    def test_watch_timeout_does_not_cancel_or_dispatch(self):
        value = self.prepared(); self.submit(value); rows = []; clock = [0]
        api.watch_status(self.store, value['job'], emit=rows.append, clock=lambda: clock[0],
                         sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds), duration=7)
        self.assertEqual(clock[0], 7)
        self.assertEqual(self.store.load(value['job'])['status'], 'DISPATCHING')
        self.assertEqual(len(self.host.launches), 1)

    def test_failed_install_reply_needs_no_background_and_rejects_stale_reply(self):
        value = self.prepared(); saved = self.store.load(value['job'])
        api.ask(saved, 'install-result', 'result', ['install-failed'])
        self.store.save(saved)
        result = api.submit(self.store, self.host, 'resume', value['job'], saved['pending']['id'], 'install-failed')
        self.assertEqual(result['pending']['kind'], 'failed-install')
        self.assertEqual(self.host.launches, [])
        with self.assertRaises(ValueError):
            api.submit(self.store, self.host, 'resume', value['job'], saved['pending']['id'], 'install-failed')

    def test_usb_restore_complete_is_not_install_success(self):
        value = self.prepared(); saved = self.store.load(value['job'])
        api.finish(self.store, saved, dict(phase='USB_RESTORE_COMPLETE'))
        self.assertIn('普通 USB 连接已恢复', saved['message'])
        self.assertEqual(saved['installation_outcome'], 'not_started')

    def legacy_menu_job(self, status='FINISHED'):
        value=self.prepared();saved=self.store.load(value['job'])
        flow_id='d'*32;base=self.root/'state/sessions'/value['job']/'workflow'
        flow=dict(flow=flow_id,phase='MENU_CONNECTION_STOPPED',p1_operation_complete=True,patch_run='same-p1')
        api.atomic_json(base/'flow.json',dict(flow=flow_id))
        api.atomic_json(base/'flows'/flow_id/'flow.json',flow)
        saved.update(build_id=api.LEGACY_BUILD,version='1.00',status=status,p1_operation_complete=True,pending=None)
        self.store.save(saved);return saved,flow

    def test_legacy_stopped_menu_reopens_with_fresh_confirmation_only(self):
        saved,flow=self.legacy_menu_job()
        result=api.reopen_menu(self.store,saved['job'])
        self.assertEqual(result['pending']['kind'],'restore')
        self.assertEqual(result['build_id'],api.BUILD_ID)
        self.assertEqual(result['version'],'1.01')
        self.assertEqual(self.store.load(saved['job'])['created_version'],'1.00')
        self.assertEqual(self.store.load(saved['job'])['created_build_id'],api.LEGACY_BUILD)
        self.assertEqual(self.host.launches,[])
        self.assertFalse(result['menu_ready'])

    def test_running_legacy_task_cannot_be_reopened(self):
        saved,_=self.legacy_menu_job('RUNNING')
        with self.assertRaises(ValueError):api.reopen_menu(self.store,saved['job'])
        self.assertEqual(self.host.launches,[])

    def test_recovered_menu_continues_same_job_without_new_start(self):
        saved,flow=self.legacy_menu_job();result=api.reopen_menu(self.store,saved['job']);calls=[]
        def execute(action,**kwargs):
            calls.append(action)
            return dict(flow,phase='MENU_CONTINUATION_READY',normal_usb_restored=True) if action=='recover-usb' else dict(flow,phase='REVIEW_REQUIRED')
        api.submit(self.store,self.host,'recover-usb',saved['job'],result['pending']['id'],'restore-usb')
        continued=self.dispatch(saved,execute)
        self.assertEqual(continued['pending']['kind'],'continue-menu')
        self.assertTrue(continued['normal_usb_restored']);self.assertEqual(continued['status'],'WAITING_USER')
        api.submit(self.store,self.host,'resume',saved['job'],continued['pending']['id'],'continue-menu')
        self.dispatch(saved,execute)
        self.assertEqual(calls,['recover-usb','continue'])

    def test_window_clock_uses_new_attempt_receipt(self):
        saved,flow=self.legacy_menu_job();flow['menu_attempt']='e'*32
        folder=self.root/'state/sessions'/saved['job']/'workflow/flows'/flow['flow']
        api.atomic_json(folder/'status.json',dict(window_start_bound=dict(utc='old')))
        api.atomic_json(folder/'menu_attempts'/flow['menu_attempt']/'status.json',dict(window_start_bound=dict(utc='new')))
        self.assertEqual(api.load_window(self.store,saved['job'],flow)['utc'],'new')


if __name__ == '__main__': unittest.main()
