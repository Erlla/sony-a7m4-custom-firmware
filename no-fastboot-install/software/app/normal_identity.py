"""Read normal-mode identity after driver binding; retry descriptor reads only."""
import hashlib
import time


class DescriptorReadError(RuntimeError):
    """No authentication or camera command was sent by this identity check."""
    def __init__(self, report):
        self.report = report
        super().__init__('USB 描述符暂时无法读取；更新菜单尚未准备，请按提示恢复普通 USB 后重试。')


class _NotReady(Exception):
    pass


def wait_normal_identity(probe, *, expected=None, instance_serial=None, timeout=8,
                         sleep=time.sleep, clock=time.monotonic):
    deadline = clock() + timeout
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
                raise _NotReady('normal USB device is still enumerating')
            dev = devices[0]
            # Device.langids caches an empty tuple when GET_DESCRIPTOR raises USBError.
            # Read directly to preserve the underlying error and re-enumerate on retry.
            langids = probe.usb.util.get_langids(dev)
            if not langids:
                raise _NotReady('LANGID descriptor is not ready')
            product = probe.usb.util.get_string(dev, dev.iProduct, langid=langids[0])
            serial = probe.usb.util.get_string(dev, dev.iSerialNumber, langid=langids[0])
            if product is None or not serial:
                raise _NotReady('product or serial string is not ready')
            identity = dict(model=product, normal_usb_serial_sha256=hashlib.sha256(serial.encode('utf-8')).hexdigest())
            if product != 'ILCE-7M4' or (instance_serial is not None and serial.casefold() != instance_serial.casefold()):
                raise RuntimeError('USB 型号或序列号与 Windows 机身不一致')
            if expected is not None and identity != expected:
                raise RuntimeError('当前 USB 机身与已绑定相机不一致')
            report.update(passed=True, identity=identity, language_id=langids[0])
            report['attempts'].append(dict(result='verified'))
            kept, dev = dev, None
            return kept, identity, report
        except (probe.usb.core.USBError, _NotReady, UnicodeError, IndexError) as error:
            report['attempts'].append(dict(result='not_ready', error_type=type(error).__name__,
                error=str(error), errno=getattr(error, 'errno', None),
                backend_error_code=getattr(error, 'backend_error_code', None)))
        finally:
            if dev is not None:
                probe.usb.util.dispose_resources(dev)
        if clock() >= deadline:
            raise DescriptorReadError(report)
        sleep(min(0.4, max(0, deadline - clock())))
