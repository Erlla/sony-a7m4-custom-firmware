"""Asset-copy regressions using inert text fixtures, not a product runtime.

Run directly with Python 3.12+: no third-party assets, release manifest, camera
or Windows driver is required. All input and output files are disposable.
"""
from pathlib import Path
import hashlib
import importlib.util
import tempfile
import unittest
from unittest.mock import patch
import zipfile


spec = importlib.util.spec_from_file_location(
    'm4_usb_builder', Path(__file__).resolve().parents[1] / 'build.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class BuildAssetsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='M4 资产测试-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.assets = self.root / 'assets'
        self.output = self.root / 'output'
        self.output.mkdir()
        self.files = {
            'vendor/example/a.txt': b'original text A\n',
            'vendor/example/中文 b.txt': b'original text B\n',
        }
        for name, content in self.files.items():
            path = self.assets / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        digests = {name: hashlib.sha256(data).hexdigest()
                   for name, data in self.files.items()}
        # This synthetic lock authenticates text fixtures only. It cannot build
        # a camera tool and never replaces the project's dependencies.json.
        self.dependencies = {'groups': {'vendor/example': {
            'files': len(digests), 'tree_sha256': builder.fingerprint(digests)}}}

    def assert_expected_output(self):
        actual = {p.relative_to(self.output).as_posix(): p.read_bytes()
                  for p in self.output.rglob('*') if p.is_file()}
        self.assertEqual(actual, self.files)

    def test_directory_preserves_locked_bytes_and_names(self):
        builder.copy_assets(self.assets, self.output, self.dependencies)
        self.assert_expected_output()

    def test_zip_preserves_locked_bytes_and_ignores_unlocked_entries(self):
        archive = self.root / 'assets.zip'
        with zipfile.ZipFile(archive, 'w') as stream:
            for name, content in self.files.items():
                stream.writestr('portable/' + name, content)
            stream.writestr('portable/app/untrusted.txt', b'excluded')
            stream.writestr('portable/state/history.txt', b'excluded')
            stream.writestr('portable/BODYDATA.DAT', b'not firmware; excluded')
        builder.copy_assets(archive, self.output, self.dependencies)
        self.assert_expected_output()

    def test_directory_does_not_copy_unlocked_app_state_or_firmware(self):
        for name in ('app/untrusted.txt', 'state/history.txt', 'BODYDATA.DAT'):
            path = self.assets / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'unlocked text fixture')
        builder.copy_assets(self.assets, self.output, self.dependencies)
        self.assert_expected_output()

    def test_changed_input_is_rejected_before_copy(self):
        (self.assets / 'vendor/example/a.txt').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Runtime asset group differs: vendor/example'):
            builder.copy_assets(self.assets, self.output, self.dependencies)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_extra_group_file_is_rejected_before_copy(self):
        (self.assets / 'vendor/example/extra.txt').write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError, 'Runtime asset group differs: vendor/example'):
            builder.copy_assets(self.assets, self.output, self.dependencies)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_input_change_between_hash_and_copy_is_rejected(self):
        copyfile = builder.shutil.copyfile

        def change_then_copy(source, destination):
            # Deterministic concurrent-edit boundary, without threads or sleeps.
            if Path(source).name == 'a.txt':
                Path(source).write_bytes(b'modified text A\n')
            return copyfile(source, destination)

        with patch.object(builder.shutil, 'copyfile', side_effect=change_then_copy):
            with self.assertRaisesRegex(ValueError, 'Copied runtime asset group differs: vendor/example'):
                builder.copy_assets(self.assets, self.output, self.dependencies)

    def test_earlier_output_changed_during_later_copy_is_rejected(self):
        copyfile = builder.shutil.copyfile
        copied = []

        def copy_then_change_earlier_output(source, destination):
            result = copyfile(source, destination)
            if copied:
                copied[0].write_bytes(b'changed after the first copy')
            copied.append(Path(destination))
            return result

        with patch.object(builder.shutil, 'copyfile', side_effect=copy_then_change_earlier_output):
            with self.assertRaisesRegex(ValueError, 'Copied runtime asset group differs: vendor/example'):
                builder.copy_assets(self.assets, self.output, self.dependencies)

    def test_copy_error_is_propagated(self):
        with patch.object(builder.shutil, 'copyfile', side_effect=OSError('simulated disk failure')):
            with self.assertRaisesRegex(OSError, 'simulated disk failure'):
                builder.copy_assets(self.assets, self.output, self.dependencies)


if __name__ == '__main__':
    unittest.main(verbosity=2)
