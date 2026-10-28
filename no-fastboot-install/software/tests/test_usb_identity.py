"""Use PyUSB's real descriptor decoders with synthetic USB control replies."""
from array import array
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import argparse
import hashlib
import json
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, required=True)
    root = parser.parse_args().package.resolve(strict=True)
    for name in ('app', 'vendor/python', 'vendor/squashfs', 'vendor/usb', 'app/container',
                 'app/provider', 'app/reader', 'app/workflow', 'app/ui', 'app/usb'):
        sys.path.insert(0, str(root / name))
    import usb.core, usb.util
    import normal_identity as helper
    from product_integrity import verify_release
    verify_release()
    rows = []
    serial = 'offline-camera'
    identity = dict(model='ILCE-7M4', normal_usb_serial_sha256=hashlib.sha256(serial.encode()).hexdigest())
    class Device:
        iProduct, iSerialNumber = 1, 2
        langids = ()  # Represents PyUSB's stale cached result after an earlier USBError.
        def __init__(self, owner, generation): self.owner, self.generation = owner, generation
        @property
        def product(self): raise AssertionError('Cached string accessor should not be used')
        serial_number = product
        def ctrl_transfer(self, bmRequestType, bRequest, wValue, wIndex, data_or_wLength):
            assert bmRequestType == 0x80 and bRequest == 6 and wValue >> 8 == 3
            index = wValue & 255
            self.owner.reads.append((self.generation, index, wIndex))
            if index == 0:
                if self.owner.failures and self.generation <= self.owner.failures:
                    raise usb.core.USBError('temporary access failure', error_code=-3, errno=13)
                return array('B', [4, 3, 0x11, 4])  # Japanese, intentionally not hardcoded 0x0409.
            assert wIndex == 0x0411
            value = self.owner.product if index == 1 else self.owner.serial
            encoded = value.encode('utf-16-le')
            return array('B', bytes([len(encoded) + 2, 3]) + encoded)
    class Backend:
        def __init__(self, failures=0, count=1, service=0, product='ILCE-7M4', actual_serial=serial):
            self.failures, self.count, self.service = failures, count, service
            self.product, self.serial = product, actual_serial
            self.generation, self.reads, self.disposed = 0, [], []
            self.usb = SimpleNamespace(core=SimpleNamespace(find=self.find, USBError=usb.core.USBError),
                                      util=SimpleNamespace(get_langids=usb.util.get_langids,
                                          get_string=usb.util.get_string, dispose_resources=self.dispose))
            self.libusb_package = SimpleNamespace(get_libusb1_backend=lambda: object())
        def find(self, **kwargs):
            if kwargs['idProduct'] == 822: return [object()] * self.service
            self.generation += 1
            return [Device(self, self.generation) for _ in range(self.count)]
        def dispose(self, dev): self.disposed.append(dev.generation)
    def acquire(backend, **kwargs):
        now = [0.0]
        return helper.wait_normal_identity(backend, clock=lambda: now[0],
                  sleep=lambda seconds: now.__setitem__(0, now[0] + seconds), **kwargs)
    backend = Backend(failures=2)
    dev, actual, receipt = acquire(backend, expected=identity, instance_serial=serial.upper())
    assert actual == identity and receipt['passed'] and receipt['language_id'] == 0x0411
    assert backend.disposed == [1, 2] and dev.generation == 3
    assert receipt['attempts'][0]['errno'] == 13 and receipt['attempts'][0]['backend_error_code'] == -3
    assert all(request[1] in (0, 1, 2) for request in backend.reads)
    rows += ['cached_empty_langid_does_not_hide_fresh_descriptor', 'transient_failure_reenumerates_and_disposes_handles',
             'only_device_advertised_language_is_requested', 'underlying_usb_error_preserved_without_camera_commands']
    backend = Backend(failures=100)
    try: acquire(backend, expected=identity, timeout=0.8)
    except helper.DescriptorReadError as error:
        assert len(error.report['attempts']) == 3 and error.report['camera_commands'] == 0
        assert backend.disposed == [1, 2, 3]
    else: raise AssertionError('Persistent descriptor error was accepted')
    rows.append('permanent_failure_is_bounded_and_closes_all_handles')
    for kwargs, expected in (({'product': 'ILCE-OTHER'}, identity), ({'actual_serial': 'different'}, identity),
                             ({}, dict(identity, normal_usb_serial_sha256='0' * 64))):
        backend = Backend(**kwargs)
        try: acquire(backend, expected=expected, instance_serial=serial)
        except RuntimeError as error:
            assert not isinstance(error, helper.DescriptorReadError)
            assert backend.generation == 1 and backend.disposed == [1]
        else: raise AssertionError('Mismatched body was accepted')
    rows.append('model_serial_and_saved_identity_mismatch_fail_without_retry')
    for kwargs in ({'count': 2}, {'service': 1}):
        backend = Backend(**kwargs)
        try: acquire(backend)
        except RuntimeError:
            assert backend.generation == 1 and not backend.reads
        else: raise AssertionError('Ambiguous/service USB was accepted')
    rows.append('multiple_or_service_devices_never_read_or_authenticate')
    backend = Backend(count=0)
    try: acquire(backend, timeout=0.8)
    except helper.DescriptorReadError: assert not backend.reads
    else: raise AssertionError('Absent camera was accepted')
    rows.append('reenumeration_timeout_keeps_device_commands_zero')
    # Exercise the real Provider.bind integration, replacing only the host and USB backend.
    import user_provider, usb_session
    provider = user_provider.Provider(); provider.binding = dict(identity=identity)
    backend = Backend(failures=1)
    row = dict(service='WinUSB', instance='USB\\VID_054C&PID_0DA5\\' + serial)
    folder = root / 'state/source_tests/identity-bind'; folder.mkdir(parents=True, exist_ok=True)
    from state_io import atomic_json
    atomic_json(folder / 'latest_StageBind.json', {'run_id': 'offline'})
    with patch.object(user_provider, 'ENROLLMENT', root / 'app/release.json'), \
         patch.object(provider, 'host', return_value=(0, dict(status='WINUSB_BOUND', run_id='offline'))) as host, \
         patch.object(provider, 'snapshot', return_value=(folder, {})), \
         patch.object(provider, 'same_body', return_value=row), \
         patch.object(usb_session, 'load_backend', return_value=backend):
        provider.bind(folder)
        host.assert_called_once_with('Broker', folder, 'StageBind')
        assert backend.disposed == [1, 2]
        assert json.loads((folder / 'usb_identity.json').read_text('utf-8'))['passed']
    rows.append('provider_binds_once_and_retries_descriptor_reads_only')
    result = dict(passed=True, cases=len(rows), tests=rows, device_operations=0,
                  driver_tasks_dispatched=0, firmware_operations=0, real_pyusb_descriptor_decoders=True)
    (root / 'state/source_tests/usb_identity.json').write_text(json.dumps(result, indent=2) + '\n', 'utf-8')
    print(json.dumps(result))


if __name__ == '__main__': main()
