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
import uuid
CASE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / 'app/provider'
sys.path.insert(0, str(TOOL))
import provider as old
from engine import read, sha, require, local_under
from local_json import atomic
ENROLLMENT = ROOT / 'state/workflow/enrollment.private.json'
BROKER = CASE.parent / 'driver'
PS = old.PS

def powershell_environment():
    environment = os.environ.copy()
    environment.pop('PSModulePath', None)
    return environment

def binding_path():
    return ENROLLMENT

class Provider(old.Provider):

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
        else:
            require(action == 'Broker' and mode in ('SelfTest', 'StageBind', 'Restore'), '驱动动作无效')
            command += [str(BROKER / 'invoke_broker.ps1'), '-Mode', mode]
        result = subprocess.run(command, capture_output=True, encoding='utf-8-sig', errors='replace', timeout=150, creationflags=subprocess.CREATE_NO_WINDOW, env=powershell_environment())
        atomic(folder / (name + '_host.json'), dict(action=action, mode=mode, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr))
        if action == 'Broker' and mode == 'Restore' and ('No unique normal camera; no privileged task was dispatched.' in result.stderr):
            return (2, dict(mode='Restore', status='NOT_DISPATCHED_NO_NORMAL_CAMERA', task_dispatched=False))
        try:
            return (result.returncode, json.loads(result.stdout.lstrip('\ufeff')))
        except ValueError as error:
            if action == 'Snapshot':
                raise RuntimeError('Windows 连接状态读取失败，请查看本轮记录中的 host.json。此次状态读取未调度驱动任务。') from error
            raise RuntimeError('驱动结果未确认，请保留记录，不重复调度') from error

    def snapshot(self, folder):
        code, value = self.host('Snapshot', folder)
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
                require(value['status'] not in ('RUNNING', 'FAILED', 'NEEDS_REVIEW', 'REFUSED_BEFORE_CHANGE'), '驱动任务需要检查：' + mode)

    def bind(self, folder):
        require(ENROLLMENT.exists(), '请先完成首次配置')
        code, result = self.host('Broker', folder, 'StageBind')
        require(code == 0 and result['status'] == 'WINUSB_BOUND', '驱动切换未确认')
        snapshot, state = self.snapshot(folder)
        row = self.same_body(state)
        require(row['service'] == 'WinUSB' and read(snapshot / 'latest_StageBind.json')['run_id'] == result['run_id'], '当前机身驱动结果不匹配')
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
    output = ROOT / 'state/workflow' / ('setup_' + uuid.uuid4().hex)
    output.mkdir(parents=True)
    spec = importlib.util.spec_from_file_location('m4_setup_bundle', BROKER / 'prepare_bundle.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    bundle = module.prepare()
    command = [str(PS), '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(script), '-Bundle', bundle['bundle'], '-BundleHash', bundle['manifest_sha256'], '-Installer', str(BROKER / 'install_broker.ps1'), '-Output', str(output / 'enrollment.json')]
    result = subprocess.run(command, capture_output=True, encoding='utf-8-sig', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW, env=powershell_environment())
    atomic(output / 'host.json', dict(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr))
    require(result.returncode == 0, '初始化未完成，请查看记录：' + str(output))
    binding = read(output / 'enrollment.json')
    require(binding['schema'] == 'm4-user-enrollment/1' and binding['model'] == 'ILCE-7M4', '初始化结果不完整')
    require(not ENROLLMENT.exists(), '初始化结果已存在')
    atomic(ENROLLMENT, binding)
    Provider().check()
    return dict(passed=True, scope='current_windows_user_and_one_body', firmware_operations=0)
