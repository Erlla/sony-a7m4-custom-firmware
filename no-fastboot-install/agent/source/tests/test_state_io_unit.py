"""Real local state publication, including Windows sharing, without a package."""
from pathlib import Path
import importlib.util
import json
import os
import tempfile
import threading
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    'source_state_io', Path(__file__).resolve().parents[1]/'app/state_io.py')
io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(io)


class StateIoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='M4 状态-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root/'有 空格'/'state.json'

    def test_chinese_paths_and_values_round_trip(self):
        value = {'阶段':'本地验证', 'generation':1}
        io.atomic_json(self.target, value)
        self.assertEqual(io.read_json(self.target), value)
        self.assertFalse(list(self.target.parent.glob('j*.tmp')))

    def test_bom_document_is_read(self):
        self.target.parent.mkdir()
        self.target.write_text('{"value":1}', 'utf-8-sig')
        self.assertEqual(io.read_json(self.target), {'value':1})

    def test_existing_document_is_replaced(self):
        io.atomic_json(self.target, {'generation':1})
        io.atomic_json(self.target, {'generation':2})
        self.assertEqual(io.read_json(self.target), {'generation':2})

    def test_malformed_document_is_not_accepted(self):
        self.target.parent.mkdir(); self.target.write_text('{broken', 'utf-8')
        with self.assertRaises(ValueError): io.read_json(self.target)

    def test_disk_full_preserves_previous_document_and_removes_temporary(self):
        io.atomic_json(self.target, {'before':True})
        before = self.target.read_bytes()
        with patch.object(io, 'replace_state', side_effect=OSError(28, 'disk full')):
            with self.assertRaises(OSError): io.atomic_json(self.target, {'after':True})
        self.assertEqual(self.target.read_bytes(), before)
        self.assertFalse(list(self.target.parent.glob('j*.tmp')))

    def test_serialization_failure_preserves_previous_document(self):
        io.atomic_json(self.target, {'before':True})
        before = self.target.read_bytes()
        with self.assertRaises(TypeError): io.atomic_json(self.target, {'bad':object()})
        self.assertEqual(self.target.read_bytes(), before)
        self.assertFalse(list(self.target.parent.glob('j*.tmp')))

    def test_sharing_retry_has_a_deadline(self):
        class Denied(OSError): winerror = 32
        now = [0.0]
        with patch.object(io, '_replace_once', side_effect=Denied('held')) as operation:
            with self.assertRaises(Denied):
                io.replace_state('from', 'to', timeout=0.25, clock=lambda:now[0],
                                 sleep=lambda delay:now.__setitem__(0, now[0]+delay))
        self.assertAlmostEqual(now[0], 0.25)
        self.assertLess(operation.call_count, 12)

    def test_non_sharing_error_is_not_retried(self):
        with patch.object(io, '_replace_once', side_effect=OSError(28, 'disk full')) as operation:
            with self.assertRaises(OSError): io.replace_state('from', 'to')
        operation.assert_called_once()

    @unittest.skipUnless(os.name == 'nt', 'requires real Windows delete-sharing semantics')
    def test_windows_reader_does_not_block_replacement(self):
        io.atomic_json(self.target, {'generation':1})
        opened, release = threading.Event(), threading.Event()
        loaded, errors = [], []
        original = json.load
        def held(stream):
            opened.set()
            if not release.wait(5): raise TimeoutError('test reader was not released')
            return original(stream)
        def reading():
            try: loaded.append(io.read_json(self.target))
            except BaseException as error: errors.append(error)
        with patch.object(io.json, 'load', held):
            reader = threading.Thread(target=reading)
            reader.start()
            try:
                self.assertTrue(opened.wait(3))
                io.atomic_json(self.target, {'generation':2})
            finally:
                release.set(); reader.join(6)
        self.assertFalse(reader.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(loaded, [{'generation':1}])
        self.assertEqual(io.read_json(self.target), {'generation':2})

    @unittest.skipUnless(os.name == 'nt', 'requires real Windows delete-sharing semantics')
    def test_windows_denial_recovers_after_reader_closes(self):
        io.atomic_json(self.target, {'generation':1})
        held = self.target.open('rb')
        errors, done = [], threading.Event()
        def writing():
            try: io.atomic_json(self.target, {'generation':2})
            except BaseException as error: errors.append(error)
            finally: done.set()
        writer = threading.Thread(target=writing)
        try:
            writer.start()
            self.assertFalse(done.wait(0.15))
        finally:
            held.close(); writer.join(5)
        self.assertFalse(writer.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(io.read_json(self.target), {'generation':2})


if __name__ == '__main__': unittest.main(verbosity=2)
