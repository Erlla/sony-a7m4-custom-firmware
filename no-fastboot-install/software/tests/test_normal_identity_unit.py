"""Descriptor retry policy with fake devices; never imports a USB backend."""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import importlib.util
import unittest

spec = importlib.util.spec_from_file_location(
    'source_normal_identity', Path(__file__).resolve().parents[1] / 'app/normal_identity.py')
identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity)


class UsbError(Exception):
    errno = 13
    backend_error_code = -3


class Probe:
    def __init__(self, failures=0, count=1, service=0, model='ILCE-7M4', serial='offline-body'):
        self.failures, self.count, self.service = failures, count, service
        self.model, self.serial = model, serial
        self.generation, self.disposed, self.reads, self.requests = 0, [], [], []
        self.languages = (0x0411,)
        self.usb = SimpleNamespace(
            core=SimpleNamespace(find=self.find, USBError=UsbError),
            util=SimpleNamespace(get_langids=self.langids, get_string=self.string,
                                 dispose_resources=lambda dev: self.disposed.append(dev.generation)))
        self.libusb_package = SimpleNamespace(get_libusb1_backend=lambda: object())

    def find(self, **kwargs):
        self.requests.append(kwargs)
        if kwargs['idProduct'] == 822:
            return [object()] * self.service
        self.generation += 1
        return [SimpleNamespace(generation=self.generation, iProduct=1, iSerialNumber=2)
                for _ in range(self.count)]

    def langids(self, dev):
        if dev.generation <= self.failures:
            raise UsbError('descriptor not ready')
        return self.languages

    def string(self, dev, index, langid):
        self.reads.append((dev.generation, index, langid))
        return self.model if index == 1 else self.serial


class IdentityTests(unittest.TestCase):
    def acquire(self, probe, **kwargs):
        self.now = 0.0
        def sleep(seconds): self.now += seconds
        return identity.wait_normal_identity(probe, clock=lambda: self.now, sleep=sleep, **kwargs)

    def test_success_uses_advertised_language_and_keeps_returned_handle(self):
        probe = Probe()
        dev, body, receipt = self.acquire(probe)
        self.assertEqual(body, {'model':'ILCE-7M4', 'normal_usb_serial_sha256':
                               hashlib.sha256(b'offline-body').hexdigest()})
        self.assertTrue(receipt['passed'])
        self.assertEqual(receipt['camera_commands'], 0)
        self.assertEqual(probe.reads, [(1, 1, 0x0411), (1, 2, 0x0411)])
        self.assertEqual(probe.disposed, [])
        self.assertEqual(dev.generation, 1)
        self.assertTrue(all(r['idVendor'] == 1356 and r['find_all'] for r in probe.requests))

    def test_transient_failure_reenumerates_and_preserves_error(self):
        probe = Probe(failures=2)
        dev, _, receipt = self.acquire(probe)
        self.assertEqual(dev.generation, 3)
        self.assertEqual(probe.disposed, [1, 2])
        self.assertEqual(receipt['attempts'][0]['errno'], 13)
        self.assertEqual(receipt['attempts'][0]['backend_error_code'], -3)

    def test_permanent_failure_is_bounded_and_disposes_every_handle(self):
        probe = Probe(failures=100)
        with self.assertRaises(identity.DescriptorReadError) as caught:
            self.acquire(probe, timeout=0.8)
        self.assertEqual(self.now, 0.8)
        self.assertEqual(probe.disposed, [1, 2, 3])
        self.assertEqual(caught.exception.report['camera_commands'], 0)

    def test_absent_device_times_out_without_string_reads(self):
        probe = Probe(count=0)
        with self.assertRaises(identity.DescriptorReadError): self.acquire(probe, timeout=0.4)
        self.assertEqual(probe.reads, [])
        self.assertEqual(probe.disposed, [])

    def test_empty_language_list_retries_without_guessing_language(self):
        probe = Probe(); probe.languages = ()
        with self.assertRaises(identity.DescriptorReadError): self.acquire(probe, timeout=0)
        self.assertEqual(probe.reads, [])
        self.assertEqual(probe.disposed, [1])

    def test_multiple_devices_are_rejected_without_descriptor_reads(self):
        probe = Probe(count=2)
        with self.assertRaises(RuntimeError): self.acquire(probe)
        self.assertEqual(probe.reads, [])
        self.assertEqual(probe.generation, 1)

    def test_service_device_blocks_normal_identity(self):
        probe = Probe(service=1)
        with self.assertRaises(RuntimeError): self.acquire(probe)
        self.assertEqual(probe.reads, [])

    def test_model_mismatch_does_not_retry_and_releases_handle(self):
        probe = Probe(model='ILCE-OTHER')
        with self.assertRaises(RuntimeError) as caught: self.acquire(probe)
        self.assertNotIsInstance(caught.exception, identity.DescriptorReadError)
        self.assertEqual(probe.disposed, [1])
        self.assertEqual(self.now, 0)

    def test_saved_body_mismatch_is_rejected_without_retry(self):
        probe = Probe()
        with self.assertRaises(RuntimeError): self.acquire(probe, expected={'model':'ILCE-7M4'})
        self.assertEqual(probe.disposed, [1])
        self.assertEqual(self.now, 0)

    def test_windows_serial_comparison_is_case_insensitive(self):
        _, _, receipt = self.acquire(Probe(), instance_serial='OFFLINE-BODY')
        self.assertTrue(receipt['passed'])

    def test_windows_serial_mismatch_is_not_retried(self):
        probe = Probe()
        with self.assertRaises(RuntimeError): self.acquire(probe, instance_serial='other-body')
        self.assertEqual(probe.disposed, [1])
        self.assertEqual(self.now, 0)


if __name__ == '__main__': unittest.main(verbosity=2)
