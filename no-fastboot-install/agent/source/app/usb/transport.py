from product_integrity import pinned, state_path
import struct
from draft_policy import DraftOnlyError, require_device_access
SONY_VID = 1356
NORMAL_PID = 3493
SERVICE_PID = 822
JIRITSU_CATEGORY = 4097
CP_KEYS = {44302337: 8192, 44302349: 28672}
AP_KEYS = {47125192, 47125194, 47125424, 47125456, 47125566, 47125568}
READ_PATHS = {'/usr/lib/appFw.so', '/cp/cpapp-b.bin', '/etc/ld.so.preload', '/tmp/jiritsu/a7m4.install.result', '/tmp/jiritsu/a7m4.install.request', '/version.txt', '/etc/fstab', '/proc/mounts', '/tmp/jbusy'}

def packet(command, body):
    return struct.pack('<HH', JIRITSU_CATEGORY, command) + body

def read_file_packets(path):
    """Select a volatile work-area path, then GET_FILE2 (small-file verified).

    The former inline GET_FILE 0x08 route returned 0x10000006 on the current
    camera. The native GET_FILE2 handler may mount its regular work area;
    this encoder never sends a file-write, delete, DEBUG or module command.
    """
    if path not in READ_PATHS:
        raise ValueError('读取路径不在M4白名单内')
    selected = '/tmp/jiritsu/../..' + path
    return (packet(15, b'\x00' + selected.encode('ascii') + b'\x00'), packet(17, b'\x00\xff\x00'))

def small_temp_write_packets(name, data):
    if name != 'a7m4.install.request' or len(data) != 16:
        raise ValueError('此草稿只描述16字节原生请求的写入编码')
    return (packet(15, b'\x00/tmp/jiritsu/' + name.encode('ascii') + b'\x00'), packet(16, b'\x00\xff\x00' + data), packet(15, b'\x00\x00'))

class Session:

    def __init__(self, expected_identity=None):
        require_device_access('open-m4-usb-session')

    def __enter__(self):
        require_device_access('authenticate-m4')

    def __exit__(self, *args):
        return False

def stage_native_module(blob):
    raise DraftOnlyError('M4正常启动的大模块上传协议未验证；不能照搬C2的0xff分块上传')
