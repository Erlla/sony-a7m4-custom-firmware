"""Persistent, bounded command surface for local agents. No raw device commands."""
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import os
import re
import sys
import threading
import time
import uuid

from agent_guidance import PREPARE, next_request, remaining, request_action
from agent_platform import capability, host, file_lock
from data_paths import data_root
from product_version import VERSION
from state_io import atomic_json, read_json, claim_once

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'm4-agent/1'
BUILD_ID = '1.00-agent-20261110-r1'
ID = re.compile('[0-9a-f]{32}')


def utc(): return datetime.now(timezone.utc).isoformat()


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value): raise ValueError('任务或待办编号无效')
    return value


class Store:
    def __init__(self, source=ROOT):
        self.source = Path(source).absolute()
        self.base = data_root(self.source) / 'agent'

    def plain(self, path):
        path = Path(path).absolute()
        if not path.is_relative_to(self.base.absolute()): raise ValueError('Agent 状态路径越界')
        for item in (path, *path.parents):
            if item.exists() and (item.is_symlink() or getattr(item, 'is_junction', lambda: False)()):
                raise ValueError('Agent 状态目录不能使用链接或联接')
            if item == self.source: break
        return path

    def folder(self, job): return self.plain(self.base / 'jobs' / identifier(job))

    def load(self, job):
        value = read_json(self.folder(job) / 'status.json')
        if value.get('job') != job or value.get('schema') != SCHEMA or value.get('build_id') != BUILD_ID:
            raise ValueError('任务身份或构建标识不匹配，请使用创建任务的原始工具目录')
        return value

    def save(self, value):
        value['updated_utc'] = utc()
        atomic_json(self.folder(value['job']) / 'status.json', value)

    def current(self):
        path = self.plain(self.base / 'current.json')
        return self.load(read_json(path)['job']) if path.exists() else None

    def create(self, kind='write'):
        job = uuid.uuid4().hex
        self.folder(job).mkdir(parents=True, exist_ok=False)
        value = dict(schema=SCHEMA, version=VERSION, build_id=BUILD_ID, job=job,
                     created_utc=utc(), status='WAITING_USER', phase='AWAITING_CONFIRMATION',
                     flow={}, progress=None, p1_operation_complete=False, menu_ready=False,
                     installation_outcome='not_started', normal_usb_restored=False,
                     automatic_retry=False, firmware_written=None, pending=None)
        ask(value, kind, PREPARE if kind == 'write' else '请连接相机，确认当前没有安装固件或其他相机任务进行中。是否恢复普通 USB？',
            ['approve-write'] if kind == 'write' else ['restore-usb'])
        self.save(value); atomic_json(self.plain(self.base / 'current.json'), dict(job=job))
        return value


def ask(value, kind, message, answers):
    value.update(status='WAITING_USER', message=message,
                 pending=dict(id=uuid.uuid4().hex, kind=kind, message=message, answers=answers))


def public(value):
    result = {k: value.get(k) for k in ('schema', 'version', 'build_id', 'job', 'status', 'phase', 'message',
              'progress', 'p1_operation_complete', 'menu_ready', 'installation_outcome', 'normal_usb_restored',
              'firmware_written', 'firmware_write_attempted', 'pending', 'updated_utc', 'heartbeat_utc', 'automatic_retry', 'diagnostic')}
    result['query_ok'] = True
    result['requires_user_response'] = result['pending'] is not None
    if (value.get('pending') or {}).get('kind') == 'menu':
        seconds = remaining(value.get('window_bound'))
        result['seconds_remaining'] = seconds
        if seconds < 90:
            pending = dict(value['pending'], kind='expired-menu', answers=['ended-restarted', 'installed-ok'],
                           message='菜单窗口剩余不足。未开始安装时，请确认相机没有更新进行中后正常重启并回复 ended-restarted；已开始时等待结束，再反馈实际结果。')
            result.update(menu_ready=False, phase='MENU_WINDOW_EXPIRED', pending=pending,
                          requires_user_response=True, message='菜单窗口已过期或剩余不足，请勿开始安装。若已开始安装，请等待结束；否则保持供电，确认相机没有更新进行中后正常重启，再恢复普通 USB。')
    if value.get('status') in ('RUNNING', 'DISPATCHING'):
        # A lost client is not a failed camera task. Never turn age into retry permission.
        result['next_step'] = '继续查询同一任务并向用户报告进度，不重复 start。若一直无新记录，保留原任务供核对。'
        result['monitor_arguments'] = ['--agent', 'status', value['job'], '--watch']
    if isinstance(result.get('diagnostic'), dict): result['diagnostic'] = diagnostic_summary(result['diagnostic'])
    result['commands'] = [dict(arguments=['--agent', 'status', value['job']], purpose='查询原任务')]
    if result.get('pending'):
        pending = result['pending']
        for answer in pending['answers']:
            action = {'write': 'start', 'restore': 'recover-usb'}.get(pending['kind'], 'resume')
            args = ['--agent', action, value['job'], pending['id']]
            if action == 'resume': args.append(answer)
            result['commands'].append(dict(user_reply_required=answer, arguments=args))
    return result


def diagnostic_summary(value):
    return {k: value[k] for k in ('code', 'stage', 'message', 'next_step', 'errno', 'winerror',
                                 'exception_type', 'original_error') if k in value}


def shared_pending(store):
    from agent_coordination import current
    value = current()
    if value and not value.get('closed'):
        if value.get('client') == 'desktop' or Path(value.get('source', '')).resolve() != store.source.resolve():
            return dict(schema=SCHEMA, query_ok=True, status='OTHER_INSTALLATION_PENDING',
                        message='另一工具目录仍有未结束任务，请在原目录查询。', job=value.get('job'),
                        original_tool_directory=value.get('source'), pending=None)
    return None


def doctor(store, machine):
    other = shared_pending(store)
    if other: return other
    current = store.current()
    if current and current['status'] not in ('FINISHED',):
        # Do not mint a new write approval for an unresolved operation.
        return public(current)
    probe = machine.probe()
    if probe.get('normal_count', 0) + probe.get('service_count', 0) != 1:
        return dict(schema=SCHEMA, query_ok=True, status='CONNECTION_REQUIRED', connection=probe,
                    message='请只连接一台 M4，开机并设置 USB 海量存储模式，连接后重新检查。', pending=None)
    value = store.create(); value['connection'] = probe; store.save(value)
    return public(value)


def submit(store, machine, action, job, request_id, answer):
    other = shared_pending(store)
    if other: return other
    with file_lock(store.plain(store.base / 'request.lock')):
        value = store.load(identifier(job)); pending = public(value).get('pending')
        if value['status'] != 'WAITING_USER' or not pending or pending['id'] != identifier(request_id):
            raise ValueError('当前待办不匹配或已经执行，请查询原任务；不要重发。')
        if answer not in pending['answers']: raise ValueError('回复不在当前待办选项中')
        if action == 'start' and pending['kind'] != 'write': raise ValueError('当前不是写入确认步骤')
        if action == 'recover-usb' and pending['kind'] != 'restore': raise ValueError('请按当前任务使用 resume')
        operation, confirmed = request_action(pending, answer, value.get('flow', {}))
        if operation == 'menu-confirmed' and remaining(value.get('window_bound')) < 90:
            raise ValueError('菜单窗口剩余不足，不能开始安装；先查询原任务并按提示恢复。')
        # These three replies only update guidance in the user's own state.
        # No driver, protected owner record or camera operation is involved.
        if operation in ('menu-confirmed', 'menu-unavailable', 'install-failed'):
            record_observation(value, operation)
            value['accepted_request'] = request_id
            store.save(value)
            return public(value)
        dispatch = uuid.uuid4().hex
        value.update(status='DISPATCHING', phase='AWAITING_SYSTEM_AUTHORIZATION', pending=None,
                     message='请确认 Windows 管理员授权窗口；等待授权完成，不要再次发送任务。',
                     dispatch=dispatch, operation=operation, confirmed=confirmed, answer=answer,
                     accepted_request=request_id)
        store.save(value)
        try: machine.launch(store.source / 'M4相机工具.exe', job, dispatch)
        except OSError as error:
            if getattr(error, 'winerror', None) == 1223:
                value.update(status='WAITING_USER', phase='ADMIN_CANCELLED')
                ask(value, pending['kind'], '管理员授权已取消，尚未派发本次操作。确认准备继续后回复原选项。', pending['answers'])
                store.save(value)
            # Other launch failures may be ambiguous. Retain dispatch and original error.
            else:
                value.update(diagnostic=dict(code='LAUNCH_FAILED', message=str(error)),
                             message='后台启动结果未确认，请查询原任务，不要重发。')
                store.save(value)
            raise
    return public(store.load(job))


def load_flow(store, job):
    folder = data_root(store.source) / 'sessions' / identifier(job) / 'workflow'
    pointer = folder / 'flow.json'
    if not pointer.exists(): return dict(phase='NO_FLOW')
    flow_id = identifier(read_json(pointer)['flow'])
    return read_json(folder / 'flows' / flow_id / 'flow.json')


def load_window(store, job, flow):
    if not flow.get('flow'): return None
    path = data_root(store.source) / 'sessions' / job / 'workflow/flows' / identifier(flow['flow']) / 'status.json'
    return read_json(path).get('window_start_bound') if path.exists() else None


def patch_facts(store, job):
    folder = data_root(store.source) / 'sessions' / job / 'workflow/patch'
    pointer = folder / 'current.json'
    if not pointer.exists(): return {}
    name = read_json(pointer)['run']
    if not re.fullmatch('[0-9]{8}T[0-9]{6}_[0-9a-f]{32}', name): raise ValueError('补丁任务编号无效')
    value = read_json(folder / 'control' / (name + '.json'))
    return {key: value[key] for key in ('firmware_written', 'firmware_write_attempted') if key in value}


class Reporter:
    def __init__(self, store, value, stream):
        self.store, self.value, self.stream = store, value, stream
        self.lock = threading.RLock(); self.partial = ''; self.last = 0

    def write(self, text):
        self.stream.write(text); self.stream.flush()
        with self.lock:
            self.partial += text
            while '\n' in self.partial:
                line, self.partial = self.partial.split('\n', 1)
                try: data = json.loads(line)
                except (ValueError, TypeError): data = {}
                if 'progress_chunks' in data:
                    self.value['progress'] = dict(completed=data['progress_chunks'], total=data['total_chunks'], unit='块')
                # Only fixed progress text is public; arbitrary logs stay local.
                if '管理员授权' in line or '证书授权' in line:
                    self.value['message'] = line + ' 请在 Windows 系统窗口手动确认；取消后会保留原因和后续步骤。'
                elif line.startswith(('正在', '复用', '读取器完整性', '补丁和恢复材料', '开始一次性写入', '写入器校验通过')):
                    self.value['message'] = line + ' 请保持供电和连接，暂时无需操作。'
                    if line.startswith(('正在读取', '开始一次性写入', '写入器校验通过')):
                        self.value['progress'] = None
            if time.monotonic() - self.last >= 1: self.flush_state()
        return len(text)

    def flush(self): self.stream.flush()

    def flush_state(self):
        self.last = time.monotonic(); self.value['heartbeat_utc'] = utc()
        self.store.save(self.value)

    def watch(self, stop):
        while not stop.wait(3):
            try:
                with self.lock:
                    flow = load_flow(self.store, self.value['job'])
                    self.value['phase'] = flow['phase']; self.value['flow'] = flow
                    self.value['p1_operation_complete'] = flow.get('p1_operation_complete', False)
                    self.value.update(patch_facts(self.store, self.value['job']))
                    self.flush_state()
            except (OSError, ValueError, KeyError):
                # State publication errors are reported by the main worker at its next boundary.
                pass


def finish(store, value, flow):
    value.update(patch_facts(store, value['job']))
    value.update(flow=flow, phase=flow.get('phase', 'REVIEW_REQUIRED'), pending=None,
                 p1_operation_complete=flow.get('p1_operation_complete', value.get('p1_operation_complete', False)),
                 menu_ready=flow.get('phase') == 'AWAITING_MENU_OBSERVATION' and flow.get('final_unplug_ready') is True,
                 status='STOPPED', diagnostic=flow.get('diagnostic', value.get('diagnostic')))
    if value['menu_ready']: value['window_bound'] = load_window(store, value['job'], flow)
    if not value.get('diagnostic') and flow.get('error'):
        value['diagnostic'] = dict(code='OPERATION_STOPPED', stage=value['phase'],
                                   message=str(flow['error']), original_error=str(flow['error']))
    if flow.get('phase') in ('COMPLETE', 'USB_RESTORE_COMPLETE'):
        value.update(status='FINISHED', message=('普通 USB 连接已恢复，本次恢复没有写入固件。' if flow.get('phase') == 'USB_RESTORE_COMPLETE' else '本轮操作已结束。安装结果来自用户反馈；需要电脑存储连接时可单独恢复普通 USB。'),
                     normal_usb_restored=flow.get('phase') == 'USB_RESTORE_COMPLETE' or flow.get('normal_usb_restored') is True,
                     menu_ready=False)
        if value.get('answer') == 'installed-ok': value['installation_outcome'] = 'user_reported_success_not_read_back'
        elif value.get('answer') == 'cancelled-restarted': value['installation_outcome'] = 'user_reported_cancelled'
    else:
        request = next_request(flow)
        if request: ask(value, *request)
        else: value['message'] = '当前结果需要核对，未自动重发任务。请保留记录，先阅读原始错误和失败阶段。'
    store.save(value)


def record_observation(value, operation):
    if operation == 'menu-confirmed':
        ask(value, 'install-result', '请在相机确认页核对目标版本并选择执行更新，保持 USB 断开及供电稳定。'
            '等待更新完成并自动重启，再检查版本、拍摄、保存和回放，回复结果。已开始安装时不要因倒计时结束而断电。',
            ['installed-ok', 'install-failed', 'cancelled-restarted'])
        value.update(phase='WAITING_FOR_USER_INSTALL_RESULT', installation_outcome='awaiting_user_report', menu_ready=False)
    else:
        ask(value, 'failed-install', '请说明相机屏幕和指示灯状态。仍在更新时保持供电等待；'
            '确认更新结束或未开始、正常重启进入拍摄界面后，回复 ended-restarted 再恢复 USB。', ['ended-restarted'])
        value.update(phase='USER_REPORTED_FAILURE', installation_outcome='user_reported_failure', menu_ready=False)


def status_result(store, job=None):
    other = shared_pending(store)
    value = None if other else (store.load(identifier(job)) if job else store.current())
    result = other or (public(value) if value else dict(schema=SCHEMA, query_ok=True, status='NO_TASK', message='尚无 Agent 任务，请先运行 doctor。'))
    if value and value['status'] == 'DISPATCHING':
        path = store.folder(value['job']) / 'launch-error.json'
        if path.exists():
            error = read_json(path)
            if error.get('dispatch') == value.get('dispatch'):
                result.update(status='LAUNCH_FAILED', diagnostic=error,
                              message='受保护后台未能启动，请保留记录检查启动错误；未自动重新派发。')
    return result


def watch_status(store, job=None, *, emit=None, clock=time.monotonic, sleep=time.sleep, duration=45):
    """One verified read-only process; bounded JSONL stream, never dispatches."""
    emit = emit or (lambda row: print(json.dumps(row, ensure_ascii=False), flush=True))
    deadline = clock() + duration
    while True:
        result = status_result(store, job)
        emit(result)
        if result.get('status') not in ('RUNNING', 'DISPATCHING') or clock() >= deadline:
            return
        sleep(min(3, max(0, deadline - clock())))


def worker(store, job, dispatch, execute=None):
    """Called only by the verified, elevated launcher; consume each dispatch once."""
    from agent_coordination import owner, claim, close
    from recovery_registry import request_guard
    job, dispatch = identifier(job), identifier(dispatch)
    value = store.load(job)
    if value.get('dispatch') != dispatch or value['status'] != 'DISPATCHING': raise ValueError('后台任务已消费或不匹配')
    claim_once(store.folder(job) / (dispatch + '.claim'), dict(job=job, dispatch=dispatch))
    os.environ['M4_TOOL_SESSION'] = job
    session = data_root(store.source) / 'sessions' / job
    session.mkdir(parents=True, exist_ok=True)
    if not (session / 'session.json').exists():
        atomic_json(session / 'session.json', dict(schema='m4-operation-session/1', session=job, created_utc=utc(), ui_version=VERSION))
    # Imports must follow M4_TOOL_SESSION binding; workflow constants are session-local.
    with owner(job), request_guard():
        claim(job, store.source)
        with (store.folder(job) / ('worker_' + dispatch + '.log')).open('w', encoding='utf-8') as log:
            reporter = Reporter(store, value, log); stop = threading.Event()
            value.update(status='RUNNING', phase='PREPARING', message='正在准备原任务，请保持连接并等待。')
            store.save(value)
            thread = threading.Thread(target=reporter.watch, args=(stop,), daemon=True); thread.start()
            try:
                with redirect_stdout(reporter), redirect_stderr(reporter):
                    if execute is None:
                        import simple_workflow
                        execute = simple_workflow.act
                    operation = value['operation']
                    flow = load_flow(store, job)
                    if operation == 'menu-confirmed':
                        stop.set(); thread.join()
                        if remaining(value.get('window_bound')) < 90: raise ValueError('菜单窗口剩余不足，不能开始安装')
                        ask(value, 'install-result', '请在相机确认页自行核对目标版本并选择执行更新，保持 USB 断开及供电稳定。'
                            '等待更新完成并自动重启，再检查版本、拍摄、保存和回放，回复结果。若已开始安装，不因倒计时结束而断电。',
                            ['installed-ok', 'install-failed', 'cancelled-restarted'])
                        value.update(phase='WAITING_FOR_USER_INSTALL_RESULT', installation_outcome='awaiting_user_report', menu_ready=False)
                    elif operation in ('menu-unavailable', 'install-failed'):
                        stop.set(); thread.join()
                        ask(value, 'failed-install', '请说明相机屏幕和指示灯状态。若仍在更新中，请保持供电等待，不要断电。'
                            '只有已确认更新结束或未开始、相机已正常重启进入拍摄界面，才能回复 ended-restarted 并恢复 USB。', ['ended-restarted'])
                        value.update(phase='USER_REPORTED_FAILURE', installation_outcome='user_reported_failure', menu_ready=False)
                    else:
                        result = execute(operation, ready=operation == 'start', confirmed=value.get('confirmed', False))
                        stop.set(); thread.join(); finish(store, value, result)
            except BaseException as error:
                from diagnostics import describe
                stop.set(); thread.join()
                flow = load_flow(store, job)
                if flow['phase'] == 'NO_FLOW': flow = dict(phase='REVIEW_REQUIRED')
                value['diagnostic'] = flow.get('diagnostic') or describe(error, value.get('phase', 'UNKNOWN'))
                try: finish(store, value, flow)
                except Exception:
                    value.update(status='STOPPED', pending=None, phase='REVIEW_REQUIRED', message='原任务结果未确认，请保留日志核对。')
                    store.save(value)
                log.write('\n' + json.dumps(value['diagnostic'], ensure_ascii=False) + '\n')
            finally:
                stop.set(); thread.join()
                store.save(value)
        if value['status'] == 'FINISHED': close(job)
    return public(value)


def run_worker(store, job, dispatch):
    try: return worker(store, job, dispatch)
    except BaseException as error:
        from diagnostics import describe
        # Claim/lock/initialization failures happen outside the inner workflow handler.
        try:
            value = store.load(identifier(job))
            if value.get('dispatch') == dispatch and value['status'] in ('DISPATCHING', 'RUNNING'):
                value.update(status='STOPPED', phase='WORKER_ENTRY_FAILED', pending=None,
                             diagnostic=describe(error, 'AGENT_WORKER_ENTRY'),
                             message='后台入口未完成。请查看具体原因并保留原任务，未自动重新发送。')
                store.save(value)
        finally: raise


def main(arguments=None):
    parser = argparse.ArgumentParser(description='M4 本地 Agent 接口；请按 JSON 待办指导用户。')
    parser.add_argument('action', choices=('doctor', 'start', 'status', 'resume', 'recover-usb'))
    parser.add_argument('job', nargs='?'); parser.add_argument('request', nargs='?'); parser.add_argument('answer', nargs='?')
    parser.add_argument('--watch', action='store_true', help='status 专用：持续输出最多45秒 JSONL；不启动设备任务')
    args = parser.parse_args(arguments)
    if args.watch and args.action != 'status': parser.error('--watch 只能用于 status')
    supported = capability()
    if not supported['supported']:
        print(json.dumps(dict(schema=SCHEMA, status='PLATFORM_NOT_VALIDATED', **supported), ensure_ascii=False)); return 2
    store, machine = Store(), host()
    try:
        if args.action == 'status':
            if args.watch:
                watch_status(store, args.job); return 0
            result = status_result(store, args.job)
        elif args.action == 'doctor': result = doctor(store, machine)
        elif args.action == 'recover-usb' and not args.job:
            other = shared_pending(store); current = store.current()
            result = other or public(current if current and current['status'] != 'FINISHED' else store.create('restore'))
        else:
            answer = args.answer or {'start': 'approve-write', 'recover-usb': 'restore-usb'}.get(args.action)
            result = submit(store, machine, args.action, args.job, args.request, answer)
        print(json.dumps(result, ensure_ascii=False)); return 0
    except Exception as error:
        from diagnostics import describe
        print(json.dumps(dict(schema=SCHEMA, query_ok=False, status='COMMAND_REJECTED', diagnostic=diagnostic_summary(describe(error, 'AGENT_COMMAND')),
                              message='操作未被确认执行，请查询原任务并按提示处理，不要重复发送。'), ensure_ascii=False)); return 1
