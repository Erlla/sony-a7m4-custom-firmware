"""Session namespace contracts in a disposable root; no release or GUI needed."""
from pathlib import Path
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1] / 'app'
sys.path.insert(0, str(APP))
spec = importlib.util.spec_from_file_location('source_operation_session', APP/'operation_session.py')
sessions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sessions)


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='M4 会话-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        context = patch.object(sessions, 'ROOT', self.root)
        context.start(); self.addCleanup(context.stop)
        environment = patch.dict(os.environ)
        environment.start(); self.addCleanup(environment.stop)
        os.environ.pop(sessions.ENVIRONMENT, None)

    def test_without_session_uses_legacy_namespace(self):
        self.assertEqual(sessions.operation_path('workflow/patch'), self.root/'state/workflow/patch')

    def test_new_session_publishes_valid_record(self):
        folder = sessions.new_session()
        name = os.environ[sessions.ENVIRONMENT]
        self.assertRegex(name, '^[0-9a-f]{32}$')
        self.assertEqual(folder, self.root/'state/sessions'/name)
        record = json.loads((folder/'session.json').read_text('utf-8'))
        self.assertEqual(record['schema'], 'm4-operation-session/1')
        self.assertEqual(record['session'], name)
        self.assertEqual(record['pid'], os.getpid())

    def test_new_session_preserves_previous_history_bytes(self):
        old = sessions.new_session()
        (old/'history.txt').write_bytes(b'preserved evidence')
        saved = {p:p.read_bytes() for p in old.iterdir()}
        new = sessions.new_session()
        self.assertNotEqual(old, new)
        self.assertTrue(all(p.read_bytes() == data for p,data in saved.items()))

    def test_ensure_creates_only_one_session(self):
        first = sessions.ensure_session()
        self.assertEqual(sessions.ensure_session(), first)
        self.assertEqual(len(list((self.root/'state/sessions').iterdir())), 1)

    def test_invalid_environment_session_is_rejected(self):
        for name in ('', '../escape', 'A'*32, 'a'*31, 'a'*33):
            with self.subTest(name=name):
                os.environ[sessions.ENVIRONMENT] = name
                with self.assertRaises(ValueError): sessions.ensure_session()
        self.assertFalse((self.root/'state').exists())

    def test_missing_inherited_session_is_not_silently_created(self):
        os.environ[sessions.ENVIRONMENT] = 'a'*32
        with self.assertRaises(ValueError): sessions.ensure_session()
        self.assertFalse((self.root/'state').exists())

    def test_child_process_inherits_existing_session(self):
        folder = sessions.new_session()
        command = ('import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); '
                   'import operation_session as s; s.ROOT=Path(sys.argv[2]); '
                   'print(s.ensure_session())')
        result = subprocess.run([sys.executable, '-I', '-B', '-X', 'utf8', '-c', command,
                                 str(APP), str(self.root)], capture_output=True, text=True,
                                encoding='utf-8', timeout=15, check=True)
        self.assertEqual(Path(result.stdout.strip()), folder)
        self.assertEqual(len(list((self.root/'state/sessions').iterdir())), 1)

    def test_new_launch_replaces_inherited_session_id(self):
        first = sessions.new_session()
        inherited = os.environ[sessions.ENVIRONMENT]
        second = sessions.new_session()
        self.assertNotEqual(os.environ[sessions.ENVIRONMENT], inherited)
        self.assertNotEqual(first, second)
        self.assertTrue((first/'session.json').is_file())


if __name__ == '__main__': unittest.main(verbosity=2)
