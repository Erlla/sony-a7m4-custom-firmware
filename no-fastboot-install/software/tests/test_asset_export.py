"""Exercise exact export and retry behavior with text-only asset fixtures."""
from pathlib import Path
import hashlib
import importlib.util
import json
import io
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SOURCE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('export_assets',SOURCE/'prepare_assets.py')
assets=importlib.util.module_from_spec(spec);spec.loader.exec_module(assets)


class AssetExportTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='m4-export-fixtures-')
        self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.output=self.root/'output';self.archive=self.root/'input.zip'
        self.files={'vendor/example/a.txt':b'first inert asset','vendor/example/中文.txt':b'second inert asset'}
        hashes={n:hashlib.sha256(v).hexdigest() for n,v in self.files.items()}
        self.lock={'version':'1.0.0','groups':{'vendor/example':{'files':2,'tree_sha256':assets.fingerprint(hashes)}},
                   'files':{n:{'group':'vendor/example','bytes':len(self.files[n]),'sha256':h} for n,h in hashes.items()}}
        (self.root/'assets-files.json').write_text(json.dumps(self.lock),'utf-8')
        here=patch.object(assets,'HERE',self.root);here.start();self.addCleanup(here.stop)

    def archive_with(self,files):
        with zipfile.ZipFile(self.archive,'w') as archive:
            for name,data in files.items():archive.writestr('portable/'+name,data)

    def test_exact_export_omits_unlocked_app_state_and_firmware(self):
        self.archive_with({**self.files,'app/fixture.txt':b'excluded','state/history.txt':b'excluded','BODYDATA.DAT':b'inert excluded text'})
        result=assets.export(self.archive,self.output)
        self.assertTrue(result['exact_bytes'])
        self.assertEqual({p.relative_to(self.output).as_posix():p.read_bytes() for p in self.output.rglob('*') if p.is_file()},self.files)

    def test_missing_asset_failure_can_retry_same_output(self):
        self.archive_with({next(iter(self.files)):b'first inert asset'})
        with self.assertRaises(ValueError):assets.export(self.archive,self.output)
        self.assertFalse(self.output.exists())
        self.archive_with(self.files);assets.export(self.archive,self.output)
        self.assertEqual(assets.verify(self.output),self.lock)

    def test_changed_asset_is_rejected_without_publishing_partial_directory(self):
        changed=dict(self.files);changed['vendor/example/a.txt']=b'tampered'
        self.archive_with(changed)
        with self.assertRaises(ValueError):assets.export(self.archive,self.output)
        self.assertFalse(self.output.exists())

    def test_existing_output_is_never_overwritten(self):
        self.archive_with(self.files);self.output.mkdir();sentinel=self.output/'state.txt';sentinel.write_text('preserve','utf-8')
        with self.assertRaises(ValueError):assets.export(self.archive,self.output)
        self.assertEqual(sentinel.read_text('utf-8'),'preserve')

    def test_invalid_zip_does_not_leave_output(self):
        self.archive.write_bytes(b'inert invalid archive')
        with self.assertRaises(zipfile.BadZipFile):assets.export(self.archive,self.output)
        self.assertFalse(self.output.exists())


class DownloadTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='m4-download-fixture-')
        self.addCleanup(temporary.cleanup);self.root=Path(temporary.name);self.cache=self.root/'cache';self.cache.mkdir()
        self.data=b'inert archive bytes, never executed'
        self.digest=hashlib.sha256(self.data).hexdigest()
        self.url='https://github.com/Erlla/sony-a7m4-custom-firmware/releases/download/fixture/runtime.zip'
        (self.root/'assets-files.json').write_text(json.dumps({'source_package_sha256':self.digest}),'utf-8')
        self.metadata={'input':{'sha256':self.digest,'bytes':len(self.data),'archive_url':self.url}}
        self.write_metadata()
        here=patch.object(assets,'HERE',self.root);here.start();self.addCleanup(here.stop)

    def write_metadata(self):(self.root/'assets-sources.json').write_text(json.dumps(self.metadata),'utf-8')

    def response(self,data,status=200,content_range=None):
        value=io.BytesIO(data);value.status=status;value.url='https://release-assets.githubusercontent.com/fixture'
        value.headers={'Content-Type':'application/octet-stream'}
        if content_range:value.headers['Content-Range']=content_range
        return value

    def test_verified_cache_is_reused_without_network(self):
        target=self.cache/'runtime.zip';target.write_bytes(self.data)
        with patch.object(assets,'open_https') as request:
            self.assertEqual(assets.download_package(self.cache),target)
        request.assert_not_called()

    def test_https_download_requires_final_digest_and_writes_receipt(self):
        with patch.object(assets,'open_https',return_value=self.response(self.data)):
            target=assets.download_package(self.cache)
        self.assertEqual(target.read_bytes(),self.data)
        self.assertEqual(json.loads((self.cache/'runtime.zip.download.json').read_text('utf-8'))['status'],'PASS')

    def test_resume_requires_matching_content_range_and_final_hash(self):
        (self.cache/'runtime.zip.part').write_bytes(self.data[:7])
        response=self.response(self.data[7:],206,f'bytes 7-{len(self.data)-1}/{len(self.data)}')
        with patch.object(assets,'open_https',return_value=response) as request:
            self.assertEqual(assets.download_package(self.cache).read_bytes(),self.data)
        self.assertEqual(request.call_args.args[0].get_header('Range'),'bytes=7-')

    def test_range_mismatch_preserves_original_partial(self):
        partial=self.cache/'runtime.zip.part';partial.write_bytes(self.data[:7])
        response=self.response(self.data,206,f'bytes 0-{len(self.data)-1}/{len(self.data)}')
        with patch.object(assets,'open_https',return_value=response),self.assertRaisesRegex(ValueError,'Content-Range'):
            assets.download_package(self.cache)
        self.assertEqual(partial.read_bytes(),self.data[:7])
        self.assertFalse((self.cache/'runtime.zip').exists())

    def test_ignored_range_restarts_instead_of_appending(self):
        (self.cache/'runtime.zip.part').write_bytes(self.data[:7])
        with patch.object(assets,'open_https',return_value=self.response(self.data)):
            self.assertEqual(assets.download_package(self.cache).read_bytes(),self.data)

    def test_changed_download_never_becomes_a_verified_archive(self):
        changed=b'x'*len(self.data)
        with patch.object(assets,'open_https',return_value=self.response(changed)),self.assertRaisesRegex(ValueError,'SHA-256 differs'):
            assets.download_package(self.cache)
        self.assertFalse((self.cache/'runtime.zip').exists())

    def test_bad_existing_cache_is_preserved(self):
        target=self.cache/'runtime.zip';target.write_bytes(b'unknown existing bytes')
        with patch.object(assets,'open_https') as request,self.assertRaisesRegex(ValueError,'Existing cached archive differs'):
            assets.download_package(self.cache)
        self.assertEqual(target.read_bytes(),b'unknown existing bytes');request.assert_not_called()

    def test_non_https_or_conflicting_provenance_is_refused_before_network(self):
        for key,value in (('archive_url',self.url.replace('https:','http:')),('sha256','0'*64)):
            with self.subTest(key=key),patch.object(assets,'open_https') as request:
                original=self.metadata['input'][key];self.metadata['input'][key]=value;self.write_metadata()
                with self.assertRaises(ValueError):assets.download_package(self.cache)
                self.metadata['input'][key]=original;request.assert_not_called()

    def test_interrupted_transfer_retries_from_flushed_partial(self):
        class Interrupted(io.BytesIO):
            status=200
            url='https://release-assets.githubusercontent.com/fixture'
            headers={'Content-Type':'application/octet-stream'}
            def read(self,size=-1):
                if self.tell():raise assets.http.client.IncompleteRead(b'',5)
                return super().read(7)
        replies=[Interrupted(self.data),self.response(self.data[7:],206,f'bytes 7-{len(self.data)-1}/{len(self.data)}')]
        with patch.object(assets,'open_https',side_effect=replies) as request,patch.object(assets.time,'sleep'):
            self.assertEqual(assets.download_package(self.cache).read_bytes(),self.data)
        self.assertEqual(request.call_count,2)
        self.assertEqual(request.call_args.args[0].get_header('Range'),'bytes=7-')

    def test_http_failure_is_recorded_with_status(self):
        error=assets.urllib.error.HTTPError(self.url,503,'fixture unavailable',{},None)
        with patch.object(assets,'open_https',side_effect=error),self.assertRaises(assets.urllib.error.HTTPError):
            assets.download_package(self.cache,attempts=1)
        record=json.loads((self.cache/'runtime.zip.download.json').read_text('utf-8'))
        self.assertEqual(record['attempts'][-1]['http_status'],503)

    def test_https_redirect_cannot_downgrade_transport(self):
        request=assets.urllib.request.Request(self.url)
        with self.assertRaisesRegex(ValueError,'Non-HTTPS'):
            assets.HTTPSOnlyRedirect().redirect_request(request,None,302,'redirect',{},'http://example.invalid/data')


if __name__=='__main__':unittest.main(verbosity=2)
