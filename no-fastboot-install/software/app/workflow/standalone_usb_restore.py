from operation_session import operation_path
from recovery_registry import recovery_root, request_guard
"""Driver-only recovery; no enrollment, camera session or firmware operations."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import uuid

from local_json import atomic
from state_io import read_json as read
from product_integrity import verify_release

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = recovery_root()
POINTER = PRIVATE / 'current.json'
PATH_BUG_HASHES = {
    'standalone_usb_restore.ps1': '849b00445b97464d9f64c9df52e183c8567be5ab93efb20e785b2d4d2c7e1222',
    'restore_camera_driver.ps1': '0a26a5946c58ccdb9426c3d6480a71402c1c5346a534c777efc482cb7db8c577',
}


def require(value, message):
    if not value:
        raise ValueError(message)


def pending():
    if not POINTER.exists():
        return None
    name = read(POINTER)['recovery']
    require(re.fullmatch('[0-9a-f]{32}', name), 'USB 恢复记录编号无效')
    record = read(PRIVATE / name / 'recovery.json')
    require(record['recovery'] == name and record['schema'] == 'm4-driver-only-recovery/1', 'USB 恢复记录不一致')
    return record


def require_clear():
    value = pending()
    require(value is None or value['phase'] in ('VERIFIED', 'CANCELLED_BEFORE_CHANGE'),
            '请先点击“恢复普通 USB”确认上次驱动恢复结果，再写入补丁')


def prechange_stop(record):
    """Accept an explicit pre-driver stop or the pinned 1.00 evidence-path bug."""
    folder = PRIVATE / record['recovery']
    result_path = folder / 'worker_result.json'
    if not result_path.exists():
        return None
    result = read(result_path)
    if result.get('nonce') != record['recovery'] or result.get('body_sha256') != record['body_sha256']:
        return None
    if result.get('status') == 'STOPPED_BEFORE_DRIVER_CHANGE' and result.get('device_mutation_started') is False:
        return dict(reason='HELPER_PREFLIGHT_STOP', worker=result)
    # This exact worker always passed the shared registry path to the exact old
    # helper, whose first path guard rejected it before any PnP/driver operation.
    hashes_path = folder / 'helper_hashes.json'
    if result.get('status') == 'HELPER_NEEDS_CHECK' and result.get('helper_exit_code') == 1 and hashes_path.exists():
        hashes = read(hashes_path)
        if all(hashes.get(name) == expected for name, expected in PATH_BUG_HASHES.items()) and not (folder / 'state/results/auto_restore_result.private.json').exists():
            return dict(reason='KNOWN_100_EVIDENCE_PATH_REJECTED', worker=result, source_hashes=PATH_BUG_HASHES)
    return None


class Windows:
    def host(self, mode, folder=None, body=None, nonce=None):
        ps = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        script = Path(__file__).with_suffix('.ps1')
        command = [str(ps), '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                   '-File', str(script), '-Mode', mode]
        if folder:
            command += ['-Folder', str(folder), '-BodyHash', body, '-Nonce', nonce]
        environment = os.environ.copy()
        environment.pop('PSModulePath', None)
        result = subprocess.run(command, capture_output=True, encoding='utf-8-sig', errors='replace',
                                timeout=120, creationflags=subprocess.CREATE_NO_WINDOW, env=environment)
        if folder:
            atomic(folder / ('host_' + mode + '.json'), dict(returncode=result.returncode,
                   stdout=result.stdout, stderr=result.stderr))
        require(result.returncode == 0, 'Windows USB 恢复未开始或状态读取失败：' + result.stderr.strip())
        return json.loads(result.stdout.lstrip('\ufeff'))

    def probe(self):
        return self.host('Probe')

    def restart_state(self):
        from driver_restart import check
        return check(confirm=True)

    def launch(self, folder, body, nonce):
        sources = [Path(__file__).with_suffix('.ps1'),
                   ROOT / 'app/driver_restore/restore_camera_driver.ps1',
                   ROOT / 'app/driver_restore/camera_storage.ps1',
                   ROOT / 'app/driver_restore/camera_port.cs']
        hashes = {source.name: hashlib.sha256(source.read_bytes()).hexdigest() for source in sources}
        atomic(folder / 'helper_hashes.json', hashes)
        return self.host('Launch', folder, body, nonce)


def reply(phase, message, **fields):
    print(message, flush=True)
    return dict(phase=phase, message=message, scope='windows_driver_only', firmware_operations=0,
                camera_commands=0, automatic_retry=False, passed=phase not in ('USB_RESTORE_REVIEW_REQUIRED', 'USB_RESTORE_WINDOWS_RESTART'), **fields)


def storage_accessible(snapshot):
    # Older injected/recorded snapshots used the PMHOME-only field. Production
    # probes now report exact-camera storage access independently of its label.
    return snapshot.get('camera_storage_accessible', snapshot.get('camera_pmhome_accessible', False)) is True


def save(record, phase, **fields):
    record.update(phase=phase, **fields)
    atomic(PRIVATE / record['recovery'] / 'recovery.json', record)


def recover(windows=None, *, wait_seconds=35, sleep=time.sleep, clock=time.monotonic):
    with request_guard(PRIVATE):
        return _recover(windows, wait_seconds=wait_seconds, sleep=sleep, clock=clock)


def _recover(windows=None, *, wait_seconds=35, sleep=time.sleep, clock=time.monotonic):
    verify_release()
    windows = windows or Windows()
    prior = pending()
    if prior and prior['phase'] not in ('VERIFIED', 'CANCELLED_BEFORE_CHANGE'):
        stop = prechange_stop(prior)
        if stop:
            save(prior, 'CANCELLED_BEFORE_CHANGE', prechange_confirmation=stop)
    restart = windows.restart_state()
    if restart['phase'] == 'WINDOWS_RESTART_REQUIRED':
        from driver_restart import MESSAGE
        return reply('USB_RESTORE_WINDOWS_RESTART', MESSAGE, restart=restart)
    if restart['phase'] == 'RESTARTED_CONNECTION_PENDING':
        return reply('USB_RESTORE_REPLUG', '电脑已重启。请保持相机开机，重新插拔 USB 后再次确认普通连接。')
    snapshot = windows.probe()
    require(snapshot['normal_count'] <= 1 and snapshot['service_count'] <= 1,
            '请只连接一台 M4；此次未调度驱动恢复')
    if snapshot['service_count'] or snapshot['normal_count'] == 0:
        return reply('USB_RESTORE_REPLUG', '请保持相机开机，拔下再插上 USB 线，然后再次点击“恢复普通 USB”。')
    row = snapshot['normal']
    require(re.fullmatch('[0-9a-f]{64}', row['body_sha256']), '相机身份摘要无效')
    record = pending()
    if record and record['phase'] not in ('VERIFIED', 'CANCELLED_BEFORE_CHANGE'):
        require(record['body_sha256'] == row['body_sha256'], 'USB 恢复属于另一台相机，请连接原机身')
    else:
        record = None
    ordinary = row['service'] == 'USBSTOR' and row['inf'].lower() == 'usbstor.inf'
    ready = ordinary and row['status'] == 'OK' and storage_accessible(snapshot)
    if ready and not record:
        return reply('USB_RESTORE_COMPLETE', '普通 USB 连接已正常，无需修改驱动。')
    if ordinary and not record:
        return reply('USB_RESTORE_REPLUG', '驱动已是普通 USB。请保持相机开机，重新插拔 USB 线后再次点击“恢复普通 USB”。')
    if not record:
        require(row['service'] == 'WinUSB' and row['reviewed_driver'] is True,
                '当前驱动不是工具使用的已识别驱动，未进行更改，请保留运行记录')
        name = uuid.uuid4().hex
        folder = PRIVATE / name
        folder.mkdir(parents=True, exist_ok=False)
        record = dict(schema='m4-driver-only-recovery/1', recovery=name,
                      body_sha256=row['body_sha256'], firmware_operations=0, camera_commands=0,
                      automatic_retry=False, phase='DISPATCHING', before=snapshot)
        atomic(folder / 'recovery.json', record)
        atomic(POINTER, dict(recovery=name))
        print('正在恢复 Windows 普通 USB 驱动；首次执行请确认管理员授权。不会写入固件。', flush=True)
        try:
            launch = windows.launch(folder, row['body_sha256'], name)
        except BaseException as error:
            save(record, 'DISPATCH_UNKNOWN', error=str(error))
            raise
        require(launch.get('nonce') == name, '驱动恢复调度结果不匹配，请保留记录')
        if launch.get('cancelled_before_change') is True:
            save(record, 'CANCELLED_BEFORE_CHANGE')
            return reply('USB_RESTORE_CANCELLED', '管理员授权已取消，未修改驱动；可再次点击恢复。')
        require(launch.get('dispatched') is True, '驱动恢复是否启动尚未确认，请保留记录')
        save(record, 'DISPATCHED', process_id=launch['process_id'],
             process_start_utc=launch.get('process_start_utc'))
    folder = PRIVATE / record['recovery']
    deadline = clock() + wait_seconds
    while True:
        result_path = folder / 'worker_result.json'
        if result_path.exists():
            result = read(result_path)
            require(result.get('nonce') == record['recovery'] and result.get('body_sha256') == record['body_sha256'],
                    '驱动恢复结果属于其他任务')
            stop = prechange_stop(record)
            if stop:
                save(record, 'CANCELLED_BEFORE_CHANGE', prechange_confirmation=stop)
                return reply('USB_RESTORE_RETRY', '本次在驱动修改前停止；请查看日志，处理提示后再次点击“恢复普通 USB”。',
                             folder=str(folder), error=result.get('error'))
            current = windows.probe()
            if current['normal_count'] == 1 and current['service_count'] == 0:
                after = current['normal']
                require(after['body_sha256'] == record['body_sha256'], '连接机身已改变')
                good = (after['service'] == 'USBSTOR' and after['inf'].lower() == 'usbstor.inf'
                        and after['status'] == 'OK' and storage_accessible(current)
                        and current['reviewed_package_absent'])
                if good:
                    save(record, 'VERIFIED', after=current, worker=result)
                    return reply('USB_RESTORE_COMPLETE', '普通 USB 连接已恢复。', folder=str(folder))
                if after['service'] == 'USBSTOR':
                    save(record, 'WAITING_FOR_REPLUG', after=current, worker=result)
                    return reply('USB_RESTORE_REPLUG', '普通 USB 驱动已恢复。请保持相机开机，重新插拔 USB 线后再次点击“恢复普通 USB”确认连接。', folder=str(folder))
                save(record, 'REVIEW_REQUIRED', after=current, worker=result)
                return reply('USB_RESTORE_REVIEW_REQUIRED', '驱动恢复尚未确认，请保留运行记录；软件不会重复调度恢复。', folder=str(folder), error=result.get('error'))
            save(record, 'WAITING_FOR_REPLUG', worker=result)
            return reply('USB_RESTORE_REPLUG', '请保持相机开机，重新插拔 USB 线后再次点击“恢复普通 USB”确认连接。', folder=str(folder))
        if clock() >= deadline:
            return reply('USB_RESTORE_WAITING', '恢复任务仍在处理。请保持相机开机，重新插拔 USB 线后再次点击“恢复普通 USB”；不会重复调度任务。', folder=str(folder))
        sleep(min(1, max(0, deadline - clock())))
