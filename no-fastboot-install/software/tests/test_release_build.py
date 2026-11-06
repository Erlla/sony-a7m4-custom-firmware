"""Version and atomic publication regressions; all fixtures are inert text."""
from pathlib import Path
import importlib.util
import json
import os
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('release_builder',Path(__file__).resolve().parents[1]/'build.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


class ReleaseBuildTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='M4 release 中文 ')
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.source=self.root/'source';(self.source/'app').mkdir(parents=True)
        self.output=self.root/'output'

    def version(self,source,metadata):
        (self.source/'app/product_version.py').write_text(source,'utf-8')
        with patch.object(builder,'HERE',self.source):
            return builder.release_version({'version':metadata})

    def test_matching_shared_version_is_read_without_importing_app(self):
        self.assertEqual(self.version("VERSION = '2.3.4'\nraise RuntimeError('must not run')",'2.3.4'),'2.3.4')

    def test_mismatched_dependency_metadata_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'differs from dependency'):
            self.version("VERSION = '1.0.0'",'1.00')

    def test_malformed_ambiguous_and_assembly_overflow_versions_are_rejected(self):
        for code,metadata in (("VERSION='1.00'",'1.00'),("VERSION='1.0.0'\nVERSION='1.0.1'",'1.0.1'),
                              ("VERSION='65536.0.0'",'65536.0.0'),("VERSION='1.0.0;bad'",'1.0.0;bad')):
            with self.subTest(code=code),self.assertRaises(ValueError):self.version(code,metadata)

    def test_failed_preparation_leaves_no_output_and_can_be_retried(self):
        with self.assertRaisesRegex(OSError,'disk fixture'):
            with builder.new_output(self.output) as stage:
                (stage/'partial.txt').write_text('inert partial','utf-8')
                raise OSError('disk fixture')
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob('.m4-build-*')),[])
        with builder.new_output(self.output) as stage:(stage/'ready.txt').write_text('complete','utf-8')
        self.assertEqual((self.output/'ready.txt').read_text('utf-8'),'complete')

    def test_existing_installation_and_unknown_state_are_preserved(self):
        self.output.mkdir();state=self.output/'state.json';state.write_text('unknown transaction','utf-8')
        with self.assertRaisesRegex(ValueError,'Output already exists'):
            with builder.new_output(self.output):self.fail('must not enter')
        self.assertEqual(state.read_text('utf-8'),'unknown transaction')

    def test_output_appearing_during_preparation_is_not_replaced(self):
        with self.assertRaisesRegex(ValueError,'Output appeared'):
            with builder.new_output(self.output) as stage:
                (stage/'new.txt').write_text('new','utf-8')
                self.output.mkdir();(self.output/'state.txt').write_text('preserve','utf-8')
        self.assertEqual((self.output/'state.txt').read_text('utf-8'),'preserve')
        self.assertFalse((self.output/'new.txt').exists())

    @unittest.skipUnless(os.name=='nt','Windows extended paths')
    def test_failed_preparation_cleans_real_extended_paths(self):
        with self.assertRaisesRegex(OSError,'compile fixture'):
            with builder.new_output(self.output) as stage:
                path=stage/('x'*100)/('y'*100)/('z'*100)/'fixture.txt'
                raw='\\\\?\\'+str(path)
                os.makedirs(os.path.dirname(raw))
                with open(raw,'wb') as stream:stream.write(b'inert')
                raise OSError('compile fixture')
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob('.m4-build-*')),[])


if __name__=='__main__':unittest.main(verbosity=2)
