"""Fixed, nonce-bound native reader diagnostics; never a recovery proof."""
import errno
import struct

FRAME = struct.Struct('<8s16s8q')
STAGES = {
    1: '独立读取进程初始化', 2: '释放临时 worker', 3: '检查相机 RAM 空间',
    4: '关闭继承句柄', 5: '发布 ready', 10: '等待 START', 11: '读取 START',
    12: '移除已消费 START', 20: '读取 loader maps', 21: '检查 libJit 映射',
    22: '打开 loader fd 目录', 23: '枚举 loader fd', 24: '解析 loader fd 项',
    25: '读取 loader fd 链接', 26: '检查 libJit 句柄', 27: '关闭 loader fd 目录',
    28: '保存 loader maps', 29: '保存 loader fd 审计',
    30: '检查 p1 挂载', 31: '打开只读 p1', 32: '检查 p1 几何信息',
    33: '首次完整读取 p1', 34: '第二次完整读取 p1', 35: '比较两次摘要',
    36: '关闭 p1', 37: '发布 RAM 分块', 38: '发布分块摘要',
}


def decode(raw, nonce, native):
    if len(raw) != FRAME.size:
        raise ValueError('Incomplete reader diagnostic')
    magic, identity, version, stage, error, pid, loader, subject, attempts, flags = FRAME.unpack(raw)
    if (magic != b'M4RDDG01' or identity.hex() != nonce or version != 1
            or error != native['error'] or pid != native['pid'] or loader != native['loader_pid']
            or flags != native['flags'] or stage not in STAGES or not 0 <= attempts <= 3):
        raise ValueError('Reader diagnostic identity differs')
    return dict(stage_id=stage, operation=STAGES[stage], native_error=error,
                native_errno=errno.errorcode.get(-error, 'UNKNOWN'),
                pid=pid, loader_pid=loader, subject=subject, audit_attempts=attempts)


def failure(report):
    native = report['native']
    detail = report.get('native_diagnostic')
    if detail:
        message = '相机端%s失败：%s (%s)' % (detail['operation'], detail['native_errno'], native['error'])
        if detail['stage_id'] == 25:
            message += '，fd=%s，已检查 %s 次' % (detail['subject'], detail['audit_attempts'])
    else:
        message = '相机端只读预检失败：错误 %s；未取得具体失败对象，不能据此判断 p1 损坏。' % native['error']
    cleaned = report.get('ram_chunks_cleaned') is True
    return dict(code='NATIVE_READER_FAILED', stage='READ_STARTING', message=message,
                next_step='临时数据已清理，可恢复普通 USB。' if cleaned else
                '清理结果尚未确认；保留运行记录，先核对相机状态，不要重发读写任务。',
                native=native, native_detail=detail, cleanup_confirmed=cleaned)
