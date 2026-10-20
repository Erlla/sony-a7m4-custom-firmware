"""Per-camera MODE5 trigger. No RAM entry, driver install or NOR writer."""
from contextlib import contextmanager
from datetime import datetime, timezone
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

from .common import Assets, ToolError, require, atomic_json, sha256, read_json
from .fat import Fat
from .transport import Fastboot

HERE = Path(__file__).resolve().parent
BACKUP_NAMES = ('nflashaB0', 'nflashaB1', 'nflasha1', 'nflasha2', 'nflasha8', 'nflasha13')
SETTINGS_SIZE = 20971520


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_config():
    return read_json(HERE / 'profiles' / 'sd-recovery.json')


def check_resources(assets=None):
    """Use the public host's local manifest, never package external executables."""
    assets = assets or Assets()
    manifest = read_json(assets.base / 'manifest.local.json') if (assets.base / 'manifest.local.json').is_file() else {'files': {}}
    names = {'bin/fastboot.exe'}
    names.update(n for n in manifest['files'] if n.startswith('bin/') and n.lower().endswith('.dll'))
    for name in sorted(names):
        assets.get(name)
    return {'files': sorted(names), 'camera_io': False}


def command_failure(text, fallback_code='FASTBOOT_FAILED'):
    """Some bundled fastboot commands print FAILED but still exit with code 0."""
    usb_timeout = ('信号灯超时时间已到' in text or
                   (re.search(r'\b121\b', text) and
                    re.search(r'Adb\w*Endpoint|usb[_ ](?:read|write)', text, re.I)))
    if usb_timeout:
        return ToolError('USB_TIMEOUT', 'USB通信超时（121），未获得有效的fastboot应答。',
                         '先重新确认fastboot模式、数据线和供电，再运行只检查连接；保留本次sessions日志。')
    if fallback_code == 'TIMEOUT':
        return ToolError('TIMEOUT', '等待fastboot进程应答超时。',
                         '先做只读连接检查；超时本身不能说明分区写入或机内更新是否完成。')
    if re.search(r'Adb\w*Endpoint|usb[_ ](?:read|write)|device.*disconnected', text, re.I):
        return ToolError('USB_TRANSPORT', 'USB传输失败，fastboot命令未取得正常应答。',
                         '检查连接和驱动，保留sessions日志；写入阶段出错时不要自动重试或重启。')
    return ToolError(fallback_code, 'fastboot命令失败：' + text.strip()[-2000:],
                     '查看本次sessions/commands.jsonl中的原始输出；不要跳过机型或写后读回检查。')


class RecoveryTransport(Fastboot):
    """The only persistent command is flash nflasha2, explicitly armed once."""
    def __init__(self, folder, assets=None):
        super().__init__(assets or Assets())
        self.folder = Path(folder)
        self._armed = None

    def command(self, *args, timeout=300):
        read = (args in (('getvar', 'product'), ('oem', 'partition')) or
                (len(args) == 6 and args[:3] == ('oem', 'partition', 'dump') and args[3] in BACKUP_NAMES) or
                (len(args) == 2 and args[0] == 'get_staged'))
        write = len(args) == 3 and args[:2] == ('flash', 'nflasha2')
        require(read or write or args == ('reboot',), 'COMMAND_BLOCKED', '禁止的fastboot命令')
        if write:
            require(self._armed is not None and Path(args[2]).resolve() == self._armed[0] and
                    sha256(args[2]) == self._armed[1], 'WRITE_NOT_ARMED', '待写文件未获本次校验')
            self._armed = None  # Never retry a potentially partial write automatically.
        with (self.folder / 'commands.jsonl').open('a', encoding='utf8') as f:
            f.write(json.dumps({'utc': datetime.now(timezone.utc).isoformat(),
                                'args': list(map(str, args)), 'phase': 'before'}, ensure_ascii=False) + '\n')
        try:
            output = super().command(*args, timeout=timeout)
            decoded = output.decode('utf8', 'replace')
            if re.search(r'(?im)(?:^|\s)FAILED(?:\s*\(|\s*$)|^fastboot:\s*error:', decoded):
                raise command_failure(decoded)
        except ToolError as original:
            error = (command_failure(str(original), original.code)
                     if original.code in ('COMMAND_FAILED', 'TIMEOUT') else original)
            with (self.folder / 'commands.jsonl').open('a', encoding='utf8') as f:
                f.write(json.dumps({'utc': datetime.now(timezone.utc).isoformat(),
                                    'args': list(map(str, args)), 'phase': 'error',
                                    'error_code': error.code, 'error': str(error),
                                    'hint': error.hint,
                                    'output': locals().get('decoded', str(original))},
                                   ensure_ascii=False) + '\n')
            raise error from None
        with (self.folder / 'commands.jsonl').open('a', encoding='utf8') as f:
            f.write(json.dumps({'utc': datetime.now(timezone.utc).isoformat(),
                                'args': list(map(str, args)), 'output': output.decode('utf8', 'replace')},
                               ensure_ascii=False) + '\n')
        return output

    def write_settings(self, partition, image, expected_hash):
        require(partition.name == 'nflasha2' and partition.size == SETTINGS_SIZE and
                Path(image).stat().st_size == SETTINGS_SIZE and sha256(image) == expected_hash,
                'WRITE_SCOPE', '只能写本次生成并校验的设置分区')
        self._armed = (Path(image).resolve(), expected_hash)
        self.command('flash', 'nflasha2', Path(image), timeout=300)


def check_connection(transport, folder):
    """Enumerate and query product only; do not read partitions, write, or reboot."""
    result = dict(status='CHECKING_CONNECTION', read_only=True,
                  flash_attempted=False, reboot_attempted=False, update_completed=False)
    path = Path(folder) / 'result.json'
    atomic_json(path, result)
    try:
        result.update(identity=transport.select(), status='CONNECTION_OK')
    except ToolError as error:
        result.update(status='CONNECTION_CHECK_FAILED', error=str(error),
                      error_code=error.code, hint=error.hint, error_type=type(error).__name__)
        raise
    finally:
        atomic_json(path, result)
    return result


def decode_version(raw):
    require(len(raw) == 2 and all((b >> 4) <= 9 and (b & 15) <= 9 for b in raw),
            'BCD', 'DAT4不是合法的双字节BCD')
    minor, major = ((b >> 4) * 10 + (b & 15) for b in raw)
    return major * 100 + minor


def encode_version(value):
    require(isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 9999,
            'BCD', '版本超出BCD范围')
    major, minor = divmod(value, 100)
    return bytes(((minor // 10) * 16 + minor % 10, (major // 10) * 16 + major % 10))


def version_text(value):
    return f'{value // 100}.{value % 100:02d}'


def all_files(fs):
    files = {}
    def walk(first=None, prefix=''):
        for name, (_, cluster, _, attr) in fs.entries(first).items():
            if name in ('.', '..'):
                continue
            path = prefix + name
            if attr & 16:
                walk(cluster, path + '/')
            else:
                files[path] = fs.read(path)
    walk()
    return files


def make_trigger(original):
    """Only DAT4 data and at most two unused 32-byte directory slots may change."""
    require(len(original) == SETTINGS_SIZE, 'SETTINGS_SIZE', '设置分区大小不符合已验证A7M4布局')
    fs = Fat(original)
    current = decode_version(fs.read('updater/dat4'))
    require(current == 0 or current // 100 == 6,
            'VERSION_SCOPE', '当前工具只支持已验证的6.x更新环境')
    root = fs.entries().get('UPDATER')
    require(root and root[3] & 16, 'UPDATER_DIR', '缺少原厂UPDATER目录')
    entries = fs.entries(root[1])
    conflicting = {'MODE1', 'MODE2', 'MODE3', 'MODE4', 'MODE6', 'MODE7', 'UINCOMP'} & entries.keys()
    require(not conflicting, 'OTHER_UPDATE_MODE', '存在其他更新状态，停止自动处理：' + ','.join(sorted(conflicting)))
    missing = []
    for name in ('MODE', 'MODE5'):
        if name in entries:
            entry = entries[name]
            require(not entry[3] & 16 and entry[1] == 0 and entry[2] == 0,
                    'BAD_MODE_FLAG', name + '不是无簇空标志文件')
        else:
            missing.append(name)
    before_files = all_files(fs)
    dat4_entry, cluster, size, _ = fs.locate('updater/dat4')
    require(size == 2, 'DAT4_SIZE', 'DAT4长度错误')
    value_offset = fs.offset(cluster)
    # The SD file stays inside slot 1. Its target version is unknown to the host.
    # 0.00 permits same-version and downgrade rescue through the native BCD gate.
    gate = 0
    fs.replace('updater/dat4', encode_version(gate))
    allowed = [(value_offset, 2)]
    created = []
    if missing:
        slots = [off for c in fs.chain(root[1])
                 for off in range(fs.offset(c), fs.offset(c) + fs.cluster_size, 32)]
        first_zero = next((i for i, off in enumerate(slots) if fs.data[off] == 0), None)
        require(first_zero is not None and first_zero + len(missing) < len(slots),
                'NO_DIRECTORY_ROOM', 'UPDATER目录没有足够的既有空槽；不扩容或重建文件系统')
        use = slots[first_zero:first_zero + len(missing) + 1]
        require(all(fs.data[off:off + 32] == bytes(32) for off in use),
                'DIR_TAIL_NOT_EMPTY', '目录尾部不是已验证空槽')
        for name, off in zip(missing, use):
            row = bytearray(32)
            row[:11] = name.encode('ascii').ljust(8, b' ') + b'   '
            row[11], row[12] = 0x20, 8  # empty archive file, lowercase display
            row[14:26] = original[dat4_entry + 14:dat4_entry + 26]
            require(row[20:22] == b'\0\0', 'FAT_HIGH_CLUSTER', 'FAT12/16高位簇字段异常')
            fs.data[off:off + 32] = row
            allowed.append((off, 32))
            created.append(name)
    candidate = fs.bytes()
    after = Fat(candidate)
    require(after.read('updater/mode') == after.read('updater/mode5') == b'', 'FLAG_VERIFY', '标志读回失败')
    require(after.read('updater/dat4') == b'\0\0', 'GATE', '临时版本门控未满足')
    files_after = all_files(after)
    require(set(files_after) - set(before_files) == {'UPDATER/' + n for n in created} and
            not set(before_files) - set(files_after), 'FILES_CHANGED', '文件集合出现意外变化')
    for path, data in before_files.items():
        expected = encode_version(gate) if path == 'UPDATER/DAT4' else data
        require(files_after[path] == expected, 'FILE_CHANGED', '原文件被改动：' + path)
    require(candidate[fs.fat_start:fs.data_start] == original[fs.fat_start:fs.data_start],
            'FAT_CHANGED', 'FAT或根目录被改动')
    changes = [i for i, (a, b) in enumerate(zip(original, candidate)) if a != b]
    require(all(any(lo <= i < lo + n for lo, n in allowed) for i in changes),
            'UNEXPECTED_DIFF', '候选存在声明范围之外的字节变化')
    require(after.read('Backup.bin') == fs.read('Backup.bin'), 'CALIBRATION_CHANGED', '机身个体数据变化')
    return candidate, dict(current=version_text(current), target='卡槽1:/BODYDATA.DAT',
                           target_version_known_to_host=False,
                           temporary_gate=version_text(gate), created_flags=created,
                           changed_bytes=len(changes), changed_offsets=changes,
                           allowed_ranges=allowed, calibration_preserved=True,
                           other_files_preserved=True, FAT_unchanged=True)


def inspect_sd_environment(image, config):
    fs = Fat(image)
    initrd = fs.read('boot/initrd.img')
    require(hashlib.md5(initrd).hexdigest().encode('ascii') in fs.read('p1chksum'),
            'UPDATER_CHECKSUM', 'SD更新环境的原厂MD5不匹配')
    initrd_hash = digest(initrd)
    require(initrd_hash in config['approved_initrd_hashes'],
            'UPDATER_PROFILE', '当前SD更新环境不在已验证清单；保留备份并停止')
    return dict(initrd_sha256=initrd_hash, updater_environment_known=True,
                SD_firmware_validation='performed by original camera updater',
                host_read_SD_card=False)


@contextmanager
def hardware_lock():
    require(os.name == 'nt', 'PLATFORM', '设备操作只支持Windows')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
    kernel.ReleaseMutex.argtypes = (ctypes.c_void_p,)
    kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
    handle = kernel.CreateMutexW(None, False, 'Local\\A7M4FastbootToolkit-Hardware')
    require(handle, 'LOCK', '不能创建设备锁')
    acquired = kernel.WaitForSingleObject(handle, 0) in (0, 0x80)
    try:
        require(acquired, 'BUSY', '其他工具正在操作相机，请先关闭')
        yield
    finally:
        if acquired:
            kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)


def recover(transport, folder, config, inspect_updater=inspect_sd_environment,
            disk_free=None, notify=print):
    """Caller holds hardware_lock. A fresh snapshot is mandatory for every run."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    result = dict(status='PREFLIGHT', firmware='卡槽1:/BODYDATA.DAT', flash_attempted=False,
                  readback_verified=False, reboot_attempted=False, update_completed=False,
                  backup_scope=list(BACKUP_NAMES), full_eMMC_backup=False,
                  NOR_direct_write=False, hardware_entry_attempted=False)
    save = lambda: atomic_json(folder / 'result.json', result)
    save()
    try:
        identity = transport.select()
        require(identity['product'] == 'ILCE-7M4', 'MODEL', '只支持ILCE-7M4')
        parts = {p.name: p for p in transport.partitions()}
        require(set(BACKUP_NAMES) <= parts.keys() and parts['nflasha2'].size == SETTINGS_SIZE,
                'LAYOUT', '分区布局不符合已验证A7M4')
        required = sum(parts[n].size for n in BACKUP_NAMES) + SETTINGS_SIZE * 5 + (32 << 20)
        free = shutil.disk_usage(folder).free if disk_free is None else disk_free
        require(free > required, 'DISK_SPACE', '备份和读回所需磁盘空间不足')
        result.update(identity=identity, partitions={n: p.json() for n, p in parts.items()}, files={})
        result['status'] = 'BACKING_UP'
        save()
        for name in BACKUP_NAMES:
            notify('备份：' + name)
            path = folder / (name + '.before.bin')
            transport.dump(parts[name], path)
            require(path.stat().st_size == parts[name].size, 'SHORT_BACKUP', '备份长度不足：' + name)
            result['files'][name] = dict(file=path.name, bytes=path.stat().st_size, sha256=sha256(path))
            save()
        # Rehash every saved file before any write permission can be acquired.
        for row in result['files'].values():
            require(sha256(folder / row['file']) == row['sha256'], 'BACKUP_CHANGED', '本次备份被修改')
        result['updater'] = inspect_updater((folder / 'nflasha1.before.bin').read_bytes(), config)
        original = (folder / 'nflasha2.before.bin').read_bytes()
        candidate, plan = make_trigger(original)
        result['plan'] = plan
        result['personalization_sha256'] = digest(Fat(original).read('Backup.bin'))
        # Preserve UPDATE.LOG locally when the source partition is a readable FAT.
        try:
            logfs = Fat((folder / 'nflasha13.before.bin').read_bytes())
            log = logfs.read('HISTORY/UPDATE.LOG')
            (folder / 'UPDATE.before.LOG').write_bytes(log)
            result['update_log_sha256'] = digest(log)
        except ToolError as error:
            result['update_log_extract_error'] = str(error)
        path = folder / 'nflasha2.MODE5.candidate.bin'
        with path.open('xb') as f:
            f.write(candidate)
            f.flush()
            os.fsync(f.fileno())
        candidate_hash = digest(candidate)
        require(sha256(path) == candidate_hash, 'CANDIDATE_CHANGED', '候选保存校验失败')
        result.update(status='TRIGGER_PREPARED', candidate_sha256=candidate_hash)
        save()
        # Recheck same-camera content immediately before the one permitted write.
        require(transport.select() == identity, 'DEVICE_CHANGED', '设备连接发生变化')
        require({p.name: p.json() for p in transport.partitions()} == result['partitions'],
                'LAYOUT_CHANGED', '分区布局在备份后发生变化')
        checkdir = folder / 'prewrite'
        checkdir.mkdir()
        for name in ('nflashaB0', 'nflashaB1', 'nflasha2'):
            fresh = checkdir / (name + '.bin')
            transport.dump(parts[name], fresh)
            require(sha256(fresh) == result['files'][name]['sha256'],
                    'DEVICE_CONTENT_CHANGED', '同机状态变化：' + name)
        require(sha256(path) == candidate_hash and path.read_bytes() == candidate,
                'CANDIDATE_CHANGED', '候选在写入前被修改')
        if candidate != original:
            result.update(status='WRITING_TRIGGER', flash_attempted=True)
            save()
            transport.write_settings(parts['nflasha2'], path, candidate_hash)
        result['status'] = 'VERIFYING_TRIGGER'
        save()
        after = folder / 'nflasha2.after.bin'
        transport.dump(parts['nflasha2'], after)
        require(sha256(after) == candidate_hash and after.read_bytes() == candidate,
                'READBACK_FAILED', '写后读回不一致；保持fastboot，不自动重试或重启')
        result.update(status='TRIGGER_VERIFIED', readback_verified=True)
        save()
        result.update(status='REBOOT_SENDING', reboot_attempted=True)
        save()
        transport.reboot()
        result['status'] = 'SD_UPDATE_TRIGGERED_PENDING_CAMERA'
        save()
        return result
    except BaseException as error:
        result.update(status='REBOOT_OUTCOME_UNCERTAIN' if result['reboot_attempted'] else 'STOPPED_KEEP_FASTBOOT',
                      error=str(error), error_type=type(error).__name__,
                      error_code=getattr(error, 'code', type(error).__name__),
                      hint=getattr(error, 'hint', ''))
        save()
        raise
