"""Read normal-mode identity after driver binding; retry descriptor reads only."""
import hashlib
import time
from connection_stop import ConnectionStop


class DescriptorReadError(ConnectionStop):
    """No authentication or camera command was sent by this identity check."""
    def __init__(self, report):
        self.report = report
        last = next((row for row in reversed(report.get('attempts', [])) if row.get('result') == 'not_ready'), {})
        self.errno = last.get('errno')
        self.backend_error_code = last.get('backend_error_code')
        kind = last.get('failure_kind', 'descriptor_transfer_failed')
        reason = {
            'normal_device_absent': '等待普通 USB 身份超时，未枚举到相机',
            'language_descriptor_unavailable': '相机已枚举，但未返回可用的 USB 语言描述符',
            'identity_string_unavailable': '相机已枚举，但型号或序列号描述符尚不可读',
        }.get(kind, '相机 USB 描述符读取失败')
        backend_name = {-3: 'LIBUSB_ERROR_ACCESS', -4: 'LIBUSB_ERROR_NO_DEVICE',
                        -6: 'LIBUSB_ERROR_BUSY', -7: 'LIBUSB_ERROR_TIMEOUT',
                        -9: 'LIBUSB_ERROR_PIPE'}.get(self.backend_error_code)
        codes = [str(v) for v in (backend_name,
                 'errno=' + str(self.errno) if self.errno is not None else None,
                 'backend=' + str(self.backend_error_code) if self.backend_error_code is not None else None) if v is not None]
        message = reason + ('（' + '，'.join(codes) + '）' if codes else '') + '；本次身份检查未发送相机认证或读写命令。'
        super().__init__(message, 'USB_IDENTITY_UNAVAILABLE', report)
        self.diagnostic = dict(code=self.reason, message=message, failure_kind=kind,
            backend_error_code=self.backend_error_code, attempts=len(report.get('attempts', [])),
            elapsed_seconds=report.get('elapsed_seconds'), camera_commands=0,
            next_step='先查看原任务和驱动状态；确认没有相机操作进行中后，按当前待办检查连接或恢复普通 USB。底层错误码本身不能证明线材、驱动或权限的唯一根因。')


class _NotReady(Exception):
    def __init__(self, message, kind):
        self.kind = kind
        super().__init__(message)


def wait_normal_identity(probe, *, expected=None, instance_serial=None, timeout=8,
                         sleep=time.sleep, clock=time.monotonic):
    started = clock()
    deadline = started + timeout
    report = dict(scope='normal_usb_descriptor_reads_only', camera_commands=0, attempts=[], passed=False)
    while True:
        dev = None
        try:
            backend = probe.libusb_package.get_libusb1_backend()
            devices = list(probe.usb.core.find(find_all=True, idVendor=1356, idProduct=3493, backend=backend))
            service = list(probe.usb.core.find(find_all=True, idVendor=1356, idProduct=822, backend=backend))
            if len(devices) > 1 or service:
                raise RuntimeError('请只连接一台处于普通 USB 模式的 M4')
            if not devices:
                raise _NotReady('normal USB device is still enumerating', 'normal_device_absent')
            dev = devices[0]
            # Device.langids caches an empty tuple when GET_DESCRIPTOR raises USBError.
            # Read directly to preserve the underlying error and re-enumerate on retry.
            langids = probe.usb.util.get_langids(dev)
            if not langids:
                raise _NotReady('LANGID descriptor is not ready', 'language_descriptor_unavailable')
            product = probe.usb.util.get_string(dev, dev.iProduct, langid=langids[0])
            serial = probe.usb.util.get_string(dev, dev.iSerialNumber, langid=langids[0])
            if product is None or not serial:
                raise _NotReady('product or serial string is not ready', 'identity_string_unavailable')
            identity = dict(model=product, normal_usb_serial_sha256=hashlib.sha256(serial.encode('utf-8')).hexdigest())
            if product != 'ILCE-7M4' or (instance_serial is not None and serial.casefold() != instance_serial.casefold()):
                raise RuntimeError('USB 型号或序列号与 Windows 机身不一致')
            if expected is not None and identity != expected:
                raise RuntimeError('当前 USB 机身与已绑定相机不一致')
            report.update(passed=True, identity=identity, language_id=langids[0])
            report['elapsed_seconds'] = round(clock() - started, 3)
            report['attempts'].append(dict(result='verified'))
            kept, dev = dev, None
            return kept, identity, report
        except (probe.usb.core.USBError, _NotReady, UnicodeError, IndexError) as error:
            report['attempts'].append(dict(result='not_ready', error_type=type(error).__name__,
                error=str(error), errno=getattr(error, 'errno', None),
                failure_kind=getattr(error, 'kind', 'descriptor_transfer_failed'),
                backend_error_code=getattr(error, 'backend_error_code', None)))
        finally:
            if dev is not None:
                probe.usb.util.dispose_resources(dev)
        if clock() >= deadline:
            report['elapsed_seconds'] = round(clock() - started, 3)
            raise DescriptorReadError(report)
        sleep(min(0.4, max(0, deadline - clock())))
