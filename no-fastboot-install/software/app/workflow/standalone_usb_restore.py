from operation_session import operation_path
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
from product_integrity import verify_release

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = operation_path('usb_restore')
POINTER = PRIVATE / 'current.json'


def read(path):
    return json.loads(path.read_text('utf-8-sig'))


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


class Windows:
    def host(self, mode, folder=None, body=None, nonce=None):
        ps = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        script = (folder / 'helper/standalone_usb_restore.ps1') if folder else Path(__file__).with_suffix('.ps1')
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

    def launch(self, folder, body, nonce):
        helper = folder / 'helper'
        helper.mkdir()
        sources = [Path(__file__).with_suffix('.ps1'),
                   ROOT / 'app/driver_restore/restore_camera_driver.ps1',
                   ROOT / 'app/driver_restore/camera_port.cs']
        for source in sources:
            shutil.copyfile(source, helper / source.name)
        hashes = {source.name: hashlib.sha256(source.read_bytes()).hexdigest() for source in sources}
        atomic(folder / 'helper_hashes.json', hashes)
        return self.host('Launch', folder, body, nonce)


def reply(phase, message, **fields):
    print(message, flush=True)
    return dict(phase=phase, message=message, scope='windows_driver_only', firmware_operations=0,
                camera_commands=0, automatic_retry=False, passed=phase != 'USB_RESTORE_REVIEW_REQUIRED', **fields)


def save(record, phase, **fields):
    record.update(phase=phase, **fields)
    atomic(PRIVATE / record['recovery'] / 'recovery.json', record)


def recover(windows=None, *, wait_seconds=35, sleep=time.sleep, clock=time.monotonic):
    verify_release()
    windows = windows or Windows()
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
    ready = ordinary and row['status'] == 'OK' and snapshot['camera_pmhome_accessible']
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
        save(record, 'DISPATCHED', process_id=launch['process_id'])
    folder = PRIVATE / record['recovery']
    deadline = clock() + wait_seconds
    while True:
        result_path = folder / 'worker_result.json'
        if result_path.exists():
            result = read(result_path)
            require(result.get('nonce') == record['recovery'] and result.get('body_sha256') == record['body_sha256'],
                    '驱动恢复结果属于其他任务')
            current = windows.probe()
            if current['normal_count'] == 1 and current['service_count'] == 0:
                after = current['normal']
                require(after['body_sha256'] == record['body_sha256'], '连接机身已改变')
                good = (after['service'] == 'USBSTOR' and after['inf'].lower() == 'usbstor.inf'
                        and after['status'] == 'OK' and current['camera_pmhome_accessible']
                        and current['reviewed_package_absent'])
                if good:
                    save(record, 'VERIFIED', after=current, worker=result)
                    return reply('USB_RESTORE_COMPLETE', '普通 USB 连接已恢复。', folder=str(folder))
                if after['service'] == 'USBSTOR':
                    save(record, 'WAITING_FOR_REPLUG', after=current, worker=result)
                    return reply('USB_RESTORE_REPLUG', '普通 USB 驱动已恢复。请保持相机开机，重新插拔 USB 线后再次点击“恢复普通 USB”确认连接。', folder=str(folder))
                save(record, 'REVIEW_REQUIRED', after=current, worker=result)
                return reply('USB_RESTORE_REVIEW_REQUIRED', '驱动恢复尚未确认，请保留运行记录；软件不会重复调度恢复。', folder=str(folder))
            save(record, 'WAITING_FOR_REPLUG', worker=result)
            return reply('USB_RESTORE_REPLUG', '请保持相机开机，重新插拔 USB 线后再次点击“恢复普通 USB”确认连接。', folder=str(folder))
        if clock() >= deadline:
            return reply('USB_RESTORE_WAITING', '恢复任务仍在处理。请保持相机开机，重新插拔 USB 线后再次点击“恢复普通 USB”；不会重复调度任务。', folder=str(folder))
        sleep(min(1, max(0, deadline - clock())))
