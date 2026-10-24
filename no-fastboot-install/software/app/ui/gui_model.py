from product_integrity import pinned, state_path
from pathlib import Path
import hashlib
import json
import re
WAITING = {'WAITING_FOR_NORMAL', 'WAITING_FOR_RESTART'}
TERMINAL = {'COMPLETE', 'STOPPED_BEFORE_DRIVER_CHANGE', 'NO_RUN'}
DEVICE_ACTIONS = {'read', 'apply', 'restore', 'recover'}
LABELS = {'simple-start': '写入补丁', 'simple-continue': '继续准备相机', 'simple-installed': '结束并恢复 USB', 'simple-failure': '保存异常结果', 'simple-recover-usb': '恢复普通 USB', 'flow-setup': '初始化此电脑', 'flow-begin': '准备安装包', 'flow-patch': '检查并准备相机', 'flow-open-menu': '准备更新菜单', 'flow-recover': '恢复普通连接', 'flow-menu-confirmed': '确认相机更新页', 'flow-installed': '记录安装结果', 'flow-failure': '保存异常结果', 'flow-cancel': '取消安装准备', 'read': '完整备份 p1', 'apply': '检查并补齐补丁', 'restore': '恢复备份原件', 'recover': '恢复普通 USB', 'check': '检查工具环境', 'connection': '检查连接', 'inspect': '检查 p1 文件', 'prepare-patch': '生成补丁材料', 'dat-check': '校验安装包', 'dat-label': '生成安装包'}
PHASES = {'PREPARING': '准备任务', 'PREFLIGHT': '核对相机连接', 'BINDING': '准备 USB 通道', 'BOUND': 'USB 通道已准备', 'READ_STARTING': '完整读取 p1', 'READ_VERIFIED': '备份核对通过', 'PATCH_PREPARING': '检查补丁与恢复材料', 'WRITE_STARTING': '正在写入 p1，请保持连接', 'WRITE_VERIFIED': '写入器校验通过', 'READBACK_STARTING': '独立完整回读 p1', 'SESSION_ENDED': '读取会话结束', 'RECOVERY_DISPATCHING': '恢复普通 USB', 'WAITING_FOR_RESTART': '请保持开机，重新插拔 USB 线后检查连接', 'WAITING_FOR_NORMAL': '等待普通 USB 连接', 'COMPLETE': '任务完成', 'REVIEW_REQUIRED': '结果需要核对，请保留日志', 'STOPPED_BEFORE_DRIVER_CHANGE': '连接准备未通过，未切换驱动'}

def patch_label(state):
    """Display the latest task's bound verification, never a fixed old p1 hash.

    This is a saved observation, not an authorization check or live camera read.
    Incomplete/uncertain tasks and unrelated offline inspections remain unknown.
    """
    unknown = '需重新检查'

    def obj(value):
        return value if isinstance(value, dict) else {}
    state = obj(state)
    if state.get('schema') != 'm4-toolchain-read/1' or state.get('phase') not in {'COMPLETE', *WAITING} or state.get('read_verified') is not True or (state.get('session_ended') is not True) or (state.get('phase') == 'COMPLETE' and state.get('normal_recovery_verified') is not True):
        return unknown
    digest = state.get('p1_sha256')
    report = obj(state.get('patch_state'))
    sd = obj(obj(report.get('libraries')).get('libsdfileinputupdaterapi.so'))
    core = obj(report.get('chkfirm_version_gate'))
    sites = core.get('sites')
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest) or report.get('schema') != 'm4-reviewed-full-p1-state/1' or (report.get('sha256') != digest) or (report.get('bytes') != 25100288) or (report.get('p1chksum_valid') is not True) or (report.get('trust_state') not in {'user_key_version_true', 'stock_key_version_true'}) or (type(report.get('signature_success_status')) is not int) or (report['signature_success_status'] != 0) or (type(report.get('version_boolean_return')) is not int) or (report['version_boolean_return'] != 1) or (report.get('signature_gate_forced_success') is not True) or (report.get('known_bad_version_boolean') is not False) or (sd.get('signature_bypass') is not True) or (sd.get('version_condition_forced_true') is not True) or (core.get('version_bypass') is not True) or (not isinstance(sites, list)) or (len(sites) != 2) or (not all((obj(site).get('patched') is True for site in sites))):
        return unknown

    def read_matches(result, job):
        result, job = (obj(result), obj(job))
        return result.get('verdict') == 'P1_READBACK_VERIFIED' and result.get('sha256') == digest and (result.get('bytes') == 25100288) and (result.get('chunks') == 766) and (result.get('block_writes') is False) and (result.get('firmware_written') is False) and (result.get('ram_chunks_cleaned') is True) and isinstance(job.get('nonce'), str) and re.fullmatch('[0-9a-f]{32}', job['nonce']) and (result.get('nonce') == job['nonce'])
    outcome = state.get('verified_outcome')
    if state.get('target_sha256') != digest:
        return unknown
    if outcome == 'ALREADY_AT_TARGET_FULL_READ_NO_WRITE':
        preparation = obj(state.get('preparation'))
        verified = state.get('firmware_write_attempted') is False and state.get('firmware_written') is False and (preparation.get('no_change') is True) and (preparation.get('source_sha256') == digest) and (preparation.get('target_sha256') == digest) and read_matches(state.get('reader_result'), state.get('reader'))
    elif outcome == 'PATCH_AND_INDEPENDENT_FULL_READBACK_VERIFIED':
        writer = obj(state.get('writer_result'))
        verified = state.get('firmware_write_attempted') is True and state.get('firmware_written') is True and (writer.get('outcome') == 'P1_TARGET_VERIFIED') and (writer.get('target_sha256') == digest) and read_matches(state.get('after_reader_result'), state.get('after_reader'))
    else:
        verified = False
    return '最近检查完整' if verified else unknown

def json_objects(text):
    """Progress JSON and a pretty-printed final object may share stdout."""
    decoder, result, cursor = (json.JSONDecoder(), [], 0)
    while cursor < len(text):
        start = text.find('{', cursor)
        if start < 0:
            break
        try:
            value, count = decoder.raw_decode(text[start:])
        except ValueError:
            cursor = start + 1
            continue
        if isinstance(value, dict):
            result.append(value)
        cursor = start + count
    return result

def final_payload(text):
    values = [value for value in json_objects(text[-2000000:]) if not ('progress_chunks' in value or value.get('stage') in {'offline_replay', 'parallel_proofs', 'proof_cancel'})]
    return values[-1] if values else {}

def progress(line):
    try:
        value = json.loads(line)
    except ValueError:
        value = {}
    if isinstance(value, dict) and type(value.get('progress_chunks')) is int:
        total, done = (value.get('total_chunks'), value['progress_chunks'])
        if type(total) is int and 0 <= done <= total and (total > 0):
            return (done / total, f'{done} / {total} 块')
    found = re.search('Validated ([\\d,]+)/([\\d,]+) blocks', line)
    if found:
        done, total = (int(part.replace(',', '')) for part in found.groups())
        if 0 <= done <= total and total > 0:
            return (done / total, f'{done:,} / {total:,} 块')
    return None

def offline_stage(line):
    try:
        value = json.loads(line)
    except ValueError:
        return None
    if not isinstance(value, dict):
        return None
    if value.get('stage') == 'proof_cancel' and value.get('status') == 'acknowledged':
        return dict(cancel_acknowledged=True)
    if value.get('stage') == 'parallel_proofs':
        if value.get('direction') in {'apply', 'restore'} and value.get('kind') in {'native', 'protocol'} and (value.get('status') in {'started', 'completed'}) and (type(value.get('completed')) is int) and (0 <= value['completed'] <= 4) and (value.get('total') == 4):
            return value
        return None
    if value.get('stage') != 'offline_replay':
        return None
    return {'replay_reader.py': 'reader', 'receiver_replay_writer.py': 'writer_native', 'receiver_test_usb_writer.py': 'writer_protocol'}.get(value.get('script'))

def prewrite_cancel_allowed(action, busy, state):
    return busy and action in {'apply', 'restore'} and (state.get('phase') == 'PATCH_PREPARING') and (state.get('read_verified') is True) and (state.get('firmware_write_attempted') is False) and (state.get('firmware_written') is False)

def classify(action, code, payload):
    phase = payload.get('phase')
    if code == 2 and phase in WAITING:
        return ('waiting', PHASES[phase])
    if code != 0:
        return ('failed', '任务已停止，查看日志了解原因')
    if action.startswith(('flow-', 'simple-')):
        if payload.get('schema') == 'm4-user-flow/1' and payload.get('passed') is True:
            return ('success', '安装步骤已完成，请按安装页继续')
        return ('review', '请查看安装流程和本轮记录')
    if action in DEVICE_ACTIONS:
        if phase == 'COMPLETE':
            if payload.get('outcome') == 'CANCELLED_BEFORE_WRITE_NORMAL_USB_VERIFIED':
                return ('success', '写入前取消，普通 USB 已恢复')
            return ('success', '补丁已正确，未写入 p1' if payload.get('outcome') == 'ALREADY_AT_TARGET_FULL_READ_NO_WRITE' else '任务完成，普通 USB 已恢复')
        if phase in WAITING:
            return ('waiting', PHASES[phase])
        return ('review', PHASES.get(phase, '结果未确认，请保留日志'))
    if action == 'connection':
        return ('success', payload.get('label', '连接检查完成')) if payload.get('passed') else ('review', '连接结果未确认')
    if action == 'check' or action.startswith('dat-'):
        return ('success', '环境检查通过' if action == 'check' else '安装包校验通过' if action == 'dat-check' else '安装包已生成') if payload.get('passed') is True else ('review', '结果未确认')
    if action == 'inspect' and payload.get('trust_state') in {'user_key_gate', 'sd_signature_bypass', 'user_key_legacy_version_false', 'user_key_version_true'}:
        return ('success', '补丁完整，无需补写' if payload['trust_state'] == 'user_key_version_true' else '检查完成，补丁需要处理')
    if action == 'prepare-patch' and payload.get('status') in {'NO_CHANGE_NEEDED', 'OFFLINE_PREPARED', 'PREPARED'}:
        return ('success', '补丁已正确，生成无写入材料' if payload['status'] == 'NO_CHANGE_NEEDED' else '补丁与恢复材料已生成')
    if action == 'prepare-patch' and payload.get('schema') == 'm4-reviewed-full-p1-bundle/1' and payload.get('candidate_sha256'):
        return ('success', '补丁与恢复材料已生成')
    return ('review', '结果未确认，请查看日志')

def action_enabled(action, busy, phase, orphan=False):
    if busy:
        return False
    if action == 'recover':
        return phase in WAITING
    if action in {'read', 'apply', 'restore'}:
        return phase in TERMINAL and (not orphan)
    return True

def fingerprint(path):
    spelling = str(path).replace('\\', '/')
    if spelling.startswith(('//', '/dev/')) or ':' in spelling[2:]:
        raise ValueError('请选择本机普通文件，不支持设备、网络或附加数据流路径')
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise ValueError('请选择普通文件')
    before = path.stat()
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('文件在计算摘要时发生变化，请重新选择')
    return dict(path=str(path), bytes=after.st_size, sha256=digest, mtime_ns=after.st_mtime_ns)
