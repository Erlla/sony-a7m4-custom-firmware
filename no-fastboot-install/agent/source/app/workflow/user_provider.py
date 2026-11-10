from data_paths import data_root
from diagnostics import OperationFailure, describe, secondary
from product_integrity import pinned, state_path
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
CASE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / 'app/provider'
sys.path.insert(0, str(TOOL))
import provider as old
from engine import read, sha, require, local_under
from local_json import atomic
ENROLLMENT = data_root(ROOT) / 'workflow/enrollment.private.json'
BROKER = CASE.parent / 'driver'
PS = old.PS

def powershell_environment():
    environment = os.environ.copy()
    environment.pop('PSModulePath', None)
    return environment

def binding_path():
    return ENROLLMENT

class CommunicationNotReady(RuntimeError):
    """The normal PID did not return before any bind or service command."""


class Provider(old.Provider):

    def preflight(self, folder):
        from driver_restart import require_ready
        require_ready()
        current = self.wait_communication(folder, timeout=30)
        if current is None:
            raise CommunicationNotReady('相机通信身份尚未恢复，请保持开机，重新插拔 USB 后重试。')
        snapshot, state = current
        row = self.same_body(state)
        driver = self.communication_driver(row)
        if driver == 'storage':
            # Only the known signature refusal may enter this repair. Other
            # unresolved operations keep the existing gate before any setup.
            for mode in ('SelfTest', 'StageBind', 'Restore'):
                index = snapshot / ('latest_' + mode + '.json')
                if index.exists():
                    prior = read(index)
                    signature_refusal = (mode == 'StageBind' and prior.get('status') == 'NEEDS_REVIEW'
                        and prior.get('error') == 'Driver staging failed: -2146762487')
                    if prior.get('status') in ('RUNNING', 'FAILED', 'NEEDS_REVIEW', 'REFUSED_BEFORE_CHANGE') and not signature_refusal:
                        self.tasks_clear(snapshot)
        # The service signer may still be untrusted on machines that enrolled
        # before the service package existed; this asks once and changes nothing
        # when both certificates are already trusted.
        if self.prepare_driver_trust(folder):
            snapshot, state = self.snapshot(folder, connection_only=True)
            self.communication_driver(self.same_body(state))
        self.tasks_clear(snapshot)

    def prepare_driver_trust(self, folder):
        output = folder / ('driver_setup_' + uuid.uuid4().hex + '.json')
        command = [str(PS), '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
                   str(CASE / 'driver_trust.ps1'), '-Output', str(output)]
        result = subprocess.run(command, capture_output=True, encoding='utf-8-sig', errors='replace',
                                creationflags=subprocess.CREATE_NO_WINDOW, env=powershell_environment())
        atomic(folder / 'driver_setup_host.json', dict(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr))
        try:
            report = read(output)
        except FileNotFoundError:
            report = {}
        if report.get('phase') == 'DRIVER_TRUST_CANCELLED':
            raise ValueError('尚未授权安装相机 USB 驱动证书，本次未切换驱动。')
        require(result.returncode == 0 and report.get('phase') == 'DRIVER_TRUST_READY',
                '相机 USB 驱动准备未完成：' + str(report.get('error') or result.stderr.strip()))
        return bool(report.get('stores_added') or report.get('prior_signature_failure_reviewed'))

    def communication_driver(self, row):
        if row['service'] == 'USBSTOR' and row['inf'].lower() == 'usbstor.inf':
            return 'storage'
        require(row['service'] == 'WinUSB' and re.fullmatch(r'oem\d+\.inf', row['inf'], re.I),
                '当前 USB 驱动不受支持，请先恢复普通 USB。')
        installed = Path(os.environ['SystemRoot']) / 'INF' / row['inf']
        reviewed = self.protected / 'driver/ilce-7m4.inf'
        require(installed.is_file() and sha(installed) == sha(reviewed),
                '当前 WinUSB 不是本工具已核对的驱动，请先恢复普通 USB。')
        return 'winusb'

    def wait_communication(self, folder, *, timeout=30, clock=time.monotonic, sleep=time.sleep):
        """Wait for the bound normal PID; do not enumerate disks or change drivers."""
        deadline = clock() + timeout
        while True:
            snapshot, state = self.snapshot(folder, connection_only=True)
            if state['normal_count'] == 1 and state['service_count'] == 0:
                self.same_body(state)
                return snapshot, state
            require(state['normal_count'] == 0 and state['service_count'] in (0, 1),
                    '请只连接这一台 M4，相机 USB 身份不明确。')
            if clock() >= deadline:
                return None
            sleep(0.5)

    def wait_for_normal(self, folder, *, timeout=45, clock=time.monotonic, sleep=time.sleep):
        return self.wait_communication(folder, timeout=timeout, clock=clock, sleep=sleep) is not None

    def restore(self, folder, confirmation=False):
        from driver_restart import check
        def known_restart(result):
            if result['phase'] == 'WINDOWS_RESTART_REQUIRED':
                atomic(folder / 'windows_restart.json', result)
                return 'WINDOWS_RESTART_REQUIRED'
            if result['phase'] == 'DRIVER_RESTART_RECOVERY_VERIFIED':
                atomic(folder / 'windows_restart_confirmed.json', result)
                return 'VERIFIED'
            return None
        outcome = known_restart(check(confirm=True))
        if outcome is not None:
            return outcome
        try:
            return super().restore(folder, confirmation=confirmation)
        except ValueError:
            outcome = known_restart(check(confirm=False))
            if outcome is not None:
                return outcome
            raise

    def check(self):
        from product_integrity import verify_release
        self.manifest = verify_release()
        require(ENROLLMENT.exists(), '首次使用，请先完成 Windows 管理员授权')
        require(sha(sys.executable) == self.manifest['python_sha256'], 'Python 运行时不匹配')
        self.binding = read(ENROLLMENT)
        require(self.binding['schema'] == 'm4-user-enrollment/1' and self.binding['model'] == 'ILCE-7M4', '机身配置格式不匹配')
        self.protected = Path(os.environ['ProgramData']) / 'M4CameraTool' / self.binding['user_sid']
        config_path = self.protected / 'deployment.private.json'
        require(sha(config_path) == self.binding['deployment_sha256'], '驱动配置已改变')
        config = read(config_path)
        require(config['user_sid'] == self.binding['user_sid'] and config['camera_instance_sha256'].lower() == self.binding['camera_instance_sha256'].lower(), '机身或 Windows 用户不匹配')
        for item in config['files']:
            path = local_under(self.protected, item['name'].replace('\\', '/'))
            require(sha(path).lower() == item['sha256'].lower(), '驱动文件已改变')
        require(shutil.disk_usage(CASE).free >= 2 * 1024 ** 3, '请至少保留 2 GiB 可用磁盘空间')
        return dict(passed=True, hardware_operations=0, model='ILCE-7M4', scope='enrolled_user_body')

    def host(self, action, folder, mode=None):
        require(ENROLLMENT.exists(), '请先完成首次配置')
        enrolled = ENROLLMENT.exists()
        if enrolled and action == 'Connection':
            _, state = self.snapshot(folder)
            return (0, state)
        name = 'oneclick_' + uuid.uuid4().hex
        command = [str(PS), '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File']
        if action == 'Snapshot':
            command += [str(CASE / 'windows_snapshot.ps1'), '-Name', name]
            if mode == 'Communication':
                command += ['-CommunicationOnly']
        else:
            require(action == 'Broker' and mode in ('SelfTest', 'StageBind', 'Restore'), '驱动动作无效')
            command += [str(BROKER / 'invoke_broker.ps1'), '-Mode', mode]
        try:
            result = subprocess.run(command, capture_output=True, encoding='utf-8-sig', errors='replace', timeout=150, creationflags=subprocess.CREATE_NO_WINDOW, env=powershell_environment())
        except subprocess.TimeoutExpired as error:
            error.diagnostic = dict(code='DRIVER_HOST_TIMEOUT' if action == 'Broker' else 'WINDOWS_SNAPSHOT_TIMEOUT',
                stage='BINDING' if mode == 'StageBind' else 'RECOVERY_DISPATCHING' if mode == 'Restore' else 'PREFLIGHT',
                message=('驱动任务 %s 等待结果超时。' % mode) if action == 'Broker' else 'Windows 连接状态读取超时。',
                next_step='先查看原任务记录并恢复普通 USB；不要重复调度驱动任务。' if action == 'Broker' else '检查电脑和 USB 连接后重试状态检查。',
                action=action, mode=mode, timeout_seconds=error.timeout)
            try:
                atomic(folder / (name + '_host.json'), dict(diagnostic=describe(error),
                    stdout=(error.stdout or b'').decode('utf-8', errors='replace') if isinstance(error.stdout, bytes) else error.stdout,
                    stderr=(error.stderr or b'').decode('utf-8', errors='replace') if isinstance(error.stderr, bytes) else error.stderr))
            except OSError as storage_error:
                secondary(error, storage_error, 'save_driver_timeout')
            raise
        atomic(folder / (name + '_host.json'), dict(action=action, mode=mode, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr))
        if action == 'Broker' and mode == 'Restore' and ('No unique normal camera; no privileged task was dispatched.' in result.stderr):
            return (2, dict(mode='Restore', status='NOT_DISPATCHED_NO_NORMAL_CAMERA', task_dispatched=False))
        try:
            return (result.returncode, json.loads(result.stdout.lstrip('\ufeff')))
        except ValueError as error:
            if action == 'Snapshot':
                raise RuntimeError('Windows 连接状态读取失败，请查看本轮记录中的 host.json。此次状态读取未调度驱动任务。') from error
            raise RuntimeError('驱动结果未确认，请保留记录，不重复调度') from error

    def snapshot(self, folder, *, connection_only=False):
        code, value = self.host('Snapshot', folder, 'Communication' if connection_only else None)
        require(code == 0, 'Windows snapshot failed')
        name = value['snapshot']
        require(isinstance(name, str) and re.fullmatch('oneclick_[0-9a-f]{32}', name), 'Invalid snapshot name')
        snap = local_under(old.SNAPSHOTS, name)
        state = read(snap / 'windows_state.private.json')
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(state['checked_utc'].replace('Z', '+00:00'))).total_seconds()
        require(0 <= age < 120, 'Stale Windows snapshot')
        require(sha(snap / 'deployment.private.json') == self.binding['deployment_sha256'], 'Driver binding changed')
        config = read(snap / 'deployment.private.json')
        for item in config['files']:
            require(sha(local_under(snap, item['name'].replace('\\', '/'))).lower() == item['sha256'].lower(), 'Snapshot dependency differs')
        atomic(folder / (name + '_snapshot_ref.json'), dict(path=str(snap), state_sha256=sha(snap / 'windows_state.private.json')))
        return (snap, state)

    def tasks_clear(self, snapshot):
        require(ENROLLMENT.exists(), '请先完成首次配置')
        for mode in ('SelfTest', 'StageBind', 'Restore'):
            path = snapshot / ('latest_' + mode + '.json')
            if path.exists():
                value = read(path)
                if value['status'] in ('RUNNING', 'FAILED', 'NEEDS_REVIEW', 'REFUSED_BEFORE_CHANGE'):
                    cause = str(value.get('error') or 'Windows 未返回具体错误；请查看该任务的 worker 日志')
                    raise OperationFailure('DRIVER_TASK_UNRESOLVED', 'BINDING' if mode == 'StageBind' else 'PREFLIGHT',
                        '驱动任务需要检查：%s（%s）；%s' % (mode, value['status'], cause),
                        '点击“恢复普通 USB”核对原任务结果；如提示需要重启，重启 Windows 后继续。',
                        mode=mode, task_status=value['status'], run_id=value.get('run_id'),
                        reboot_required=value.get('reboot_required'))

    def service_package_staged(self):
        """Windows must find the service INF in its driver store, or it cannot
        bind WinUSB when the camera re-enumerates as USB\\VID_054C&PID_0336
        after authentication."""
        pinned = sha(self.protected / 'driver/ilce-7m4-svc.inf')
        windows = Path(os.environ['SystemRoot']) / 'INF'
        return any(sha(path) == pinned for path in windows.glob('oem*.inf'))

    def bind(self, folder):
        require(ENROLLMENT.exists(), '请先完成首次配置')
        snapshot, state = self.snapshot(folder, connection_only=True)
        row = self.same_body(state)
        self.tasks_clear(snapshot)
        driver = self.communication_driver(row)
        reuse = driver == 'winusb' and self.service_package_staged()
        if not reuse:
            code, result = self.host('Broker', folder, 'StageBind')
            require(code == 0 and result['status'] == 'WINUSB_BOUND', '驱动切换未确认：' + str(result.get('error') or result.get('status')))
            if result.get('reboot_required') is True:
                atomic(folder / 'stage_bind_restart.json', result)
                from driver_restart import WindowsRestartRequired
                raise WindowsRestartRequired(result)
            snapshot, state = self.snapshot(folder, connection_only=True)
            row = self.same_body(state)
            require(self.communication_driver(row) == 'winusb' and
                    read(snapshot / 'latest_StageBind.json')['run_id'] == result['run_id'],
                    '当前机身驱动结果不匹配')
            require(self.service_package_staged(), '服务驱动包未就绪')
        else:
            print('复用已就绪的 USB 驱动。', flush=True)
        atomic(folder / 'driver_readiness.json', dict(schema='m4-driver-readiness/1',
               reused=reuse, storage_volume_required=False,
               camera_instance_sha256=self.binding['camera_instance_sha256'], inf=row['inf']))
        backend_dir = ROOT / 'app/usb'
        sys.path.insert(0, str(backend_dir))
        module = importlib.import_module('usb_session')
        probe = module.load_backend()
        from normal_identity import wait_normal_identity, DescriptorReadError
        try:
            device, identity, receipt = wait_normal_identity(probe,
                expected=self.binding.get('identity'), instance_serial=row['instance'].rsplit('\\', 1)[-1])
        except DescriptorReadError as error:
            atomic(folder / 'usb_identity.json', error.report)
            raise
        try:
            atomic(folder / 'usb_identity.json', receipt)
        finally:
            probe.usb.util.dispose_resources(device)
        require(self.binding.get('identity') in (None, identity), 'USB 机身身份发生变化')
        if self.binding.get('identity') is None:
            self.binding['identity'] = identity
            atomic(ENROLLMENT, self.binding)

def enroll():
    """Explicit GUI action; a fresh machine needs normal Windows UAC approval."""
    from integrity_backend import release_check
    release_check()
    require(not ENROLLMENT.exists(), '此电脑已初始化，请先检查现有连接')
    script = CASE / 'enroll.ps1'
    output = data_root(ROOT) / 'workflow' / ('setup_' + uuid.uuid4().hex)
    output.mkdir(parents=True)
    spec = importlib.util.spec_from_file_location('m4_setup_bundle', BROKER / 'prepare_bundle.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    bundle = module.prepare()
    command = [str(PS), '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(script), '-Bundle', bundle['bundle'], '-BundleHash', bundle['manifest_sha256'], '-Installer', str(BROKER / 'install_broker.ps1'), '-Output', str(output / 'enrollment.json')]
    result = subprocess.run(command, capture_output=True, encoding='utf-8-sig', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW, env=powershell_environment())
    atomic(output / 'host.json', dict(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr))
    detail = ''
    try:
        receipt = read(Path(bundle['bundle']) / 'installation.private.json')
        if receipt.get('error'):
            detail = str(receipt['error'])
    except (FileNotFoundError, ValueError):
        pass
    combined = (detail + ' ' + result.stderr).lower()
    if 'installation requires exactly one connected normal camera' in combined:
        detail = '未检测到唯一的普通连接 M4；请将相机开机，设置 USB 海量存储模式并重新连接，再重新检查。'
    elif 'camera is still in its service identity' in combined:
        detail = '相机仍在服务连接模式；请先恢复普通 USB，再重新检查。'
    elif 'restore ordinary usb before setup' in combined:
        detail = '相机仍在工具的 WinUSB 驱动模式下；请先点击「恢复普通 USB」，等相机盘符回来后重新「首次使用」'
    elif 'an existing m4 task is running' in combined:
        detail = '已有 M4 后台任务正在运行；请等待当前操作结束，再重新检查。'
    elif 'unexpected task definition' in combined:
        detail = '已有后台任务配置未通过核对，已保留原状；具体差异见本次运行记录。'
    elif 'existing driver setup differs' in combined:
        detail = '本机已有的驱动组件与当前软件不一致，已停止覆盖，请保留运行记录。'
    elif 'incomplete installation has operation records' in combined:
        detail = '未完成的初始化目录中仍有操作记录，已保留，请先检查原任务结果。'
    elif detail:
        detail = '；原因：' + detail
    else:
        detail = ''
    if detail and not detail.startswith('；'):
        detail = '；' + detail
    require(result.returncode == 0, '初始化未完成，请查看记录：' + str(output) + detail)
    binding = read(output / 'enrollment.json')
    require(binding['schema'] == 'm4-user-enrollment/1' and binding['model'] == 'ILCE-7M4', '初始化结果不完整')
    require(not ENROLLMENT.exists(), '初始化结果已存在')
    atomic(ENROLLMENT, binding)
    Provider().check()
    return dict(passed=True, scope='current_windows_user_and_one_body', firmware_operations=0)
