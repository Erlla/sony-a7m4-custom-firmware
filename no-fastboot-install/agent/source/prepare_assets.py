"""Export exactly the pinned runtime assets; never copy firmware, app or state."""
from pathlib import Path
import argparse
import hashlib
import http.client
import importlib.util
import json
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

HERE=Path(__file__).resolve().parent
BUILD_SCRIPT=HERE/'build.py'


def support():
    spec=importlib.util.spec_from_file_location('m4_asset_build_support',BUILD_SCRIPT)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def sha(stream):return hashlib.file_digest(stream,'sha256').hexdigest()


def fingerprint(files):
    return hashlib.sha256(''.join(n+'\0'+files[n]+'\n' for n in sorted(files)).encode()).hexdigest()


def file_sha(path):
    with path.open('rb') as stream:return sha(stream)


class HTTPSOnlyRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,message,headers,newurl):
        if urllib.parse.urlsplit(newurl).scheme!='https':raise ValueError('Non-HTTPS asset redirect refused')
        return super().redirect_request(request,fp,code,message,headers,newurl)


def open_https(request,timeout):
    return urllib.request.build_opener(HTTPSOnlyRedirect()).open(request,timeout=timeout)


def download_package(cache, attempts=4):
    """Fetch data only. Resume HTTPS downloads, then require the pinned ZIP hash."""
    lock=json.loads((HERE/'assets-files.json').read_text('utf-8'))
    source=json.loads((HERE/'assets-sources.json').read_text('utf-8'))['input']
    expected=lock['source_package_sha256']
    if source['sha256']!=expected or not isinstance(source['bytes'],int) or source['bytes']<=0:
        raise ValueError('Archive provenance differs from the pinned asset inventory')
    urls=[url for url in (source.get('api_asset_url'),source.get('archive_url')) if url]
    for url in urls:
        parsed=urllib.parse.urlsplit(url)
        if parsed.scheme!='https' or parsed.username or parsed.password or parsed.hostname not in ('github.com','api.github.com'):
            raise ValueError('Asset download requires an official public GitHub HTTPS URL')
    if not urls:raise ValueError('No published runtime archive URL is recorded')
    name=urllib.parse.unquote(urllib.parse.urlsplit(source['archive_url']).path.rsplit('/',1)[-1])
    support().safe_relative(name)
    if '/' in name:raise ValueError('Invalid cache filename')
    cache=cache.absolute();cache.mkdir(parents=True,exist_ok=True);support().require_plain(cache)
    target=cache/name;partial=cache/(name+'.part')
    for path in (target,partial):support().require_plain(path)
    def complete(path):return path.is_file() and path.stat().st_size==source['bytes'] and file_sha(path)==expected
    if target.exists():
        if complete(target):return target
        raise ValueError('Existing cached archive differs; preserve it and choose another cache directory')
    if complete(partial):partial.rename(target);return target
    if partial.exists() and partial.stat().st_size>=source['bytes']:
        raise ValueError('Incomplete cache has an invalid size or SHA-256; preserve it for review')
    record=dict(expected_sha256=expected,expected_bytes=source['bytes'],attempts=[])
    receipt=cache/(name+'.download.json')
    for attempt in range(attempts):
        if complete(partial):
            partial.rename(target);record['status']='PASS'
            receipt.write_text(json.dumps(record,indent=2)+'\n','utf-8')
            return target
        offset=partial.stat().st_size if partial.exists() else 0
        url=urls[attempt%len(urls)]
        headers={'User-Agent':'M4-USB-assets','Accept':'application/octet-stream'}
        if offset:headers['Range']='bytes='+str(offset)+'-'
        try:
            request=urllib.request.Request(url,headers=headers)
            with open_https(request,timeout=45) as response:
                if urllib.parse.urlsplit(response.url).scheme!='https':raise ValueError('Non-HTTPS asset redirect refused')
                status=response.status
                if 'json' in response.headers.get('Content-Type',''):raise ValueError('Received GitHub metadata instead of archive bytes')
                if status==206:
                    import re
                    match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',response.headers.get('Content-Range',''))
                    if not match or int(match[1])!=offset or int(match[3])!=source['bytes'] or not offset<=int(match[2])<source['bytes']:
                        raise ValueError('Incorrect Content-Range; no bytes appended')
                    limit=int(match[2])+1;mode='ab'
                elif status==200:offset=0;limit=source['bytes'];mode='wb'
                else:raise ValueError('Unexpected HTTP status: '+str(status))
                record['attempts'].append(dict(url=url,status=status,offset=offset))
                with partial.open(mode) as output:
                    while True:
                        chunk=response.read(1024*1024)
                        if not chunk:break
                        if offset+len(chunk)>limit:raise ValueError('Archive response exceeds its declared range')
                        output.write(chunk);offset+=len(chunk)
            if offset!=source['bytes']:raise OSError('Archive transfer ended before the pinned byte count')
            if not complete(partial):raise ValueError('Downloaded archive SHA-256 differs; it will not be exported')
            partial.rename(target);record['status']='PASS'
            receipt.write_text(json.dumps(record,indent=2)+'\n','utf-8')
            return target
        except (OSError,ValueError,http.client.HTTPException) as error:
            record['attempts'].append(dict(url=url,error=str(error),http_status=getattr(error,'code',None)))
            record['status']='FAILED'
            receipt.write_text(json.dumps(record,indent=2)+'\n','utf-8')
            if isinstance(error,ValueError) or attempt+1==attempts:raise
            time.sleep(2)


def verify(folder):
    lock=json.loads((HERE/'assets-files.json').read_text('utf-8'))
    builder=support()
    for group,rule in lock['groups'].items():
        expected={n:v for n,v in lock['files'].items() if v['group']==group}
        actual={p.relative_to(folder).as_posix():p for p in builder.directory_assets(folder,group)}
        if set(actual)!=set(expected):
            raise ValueError('Asset inventory differs: '+group+' missing='+repr(sorted(set(expected)-set(actual))[:8])+
                             ' extra='+repr(sorted(set(actual)-set(expected))[:8]))
        hashes={}
        for name,path in actual.items():
            if path.is_symlink() or path.stat().st_size!=expected[name]['bytes']:
                raise ValueError('Asset size/link differs: '+name)
            with path.open('rb') as source:hashes[name]=sha(source)
            if hashes[name]!=expected[name]['sha256']:raise ValueError('Asset digest differs: '+name)
        if len(hashes)!=rule['files'] or fingerprint(hashes)!=rule['tree_sha256']:
            raise ValueError('Asset group lock differs: '+group)
    return lock


def export(package, output):
    lock=json.loads((HERE/'assets-files.json').read_text('utf-8'))
    builder=support()
    builder.require_plain(package)
    with builder.new_output(output) as stage:
        with zipfile.ZipFile(package) as archive:
            members=builder.archive_assets(archive)
            for name,row in lock['files'].items():
                builder.safe_relative(name)
                if name not in members:raise ValueError('Missing asset: '+name)
                target=stage/name
                target.parent.mkdir(parents=True,exist_ok=True)
                with archive.open(members[name]) as source,target.open('xb') as dest:shutil.copyfileobj(source,dest)
        verify(stage)
    return dict(version=lock['version'],files=len(lock['files']),groups=len(lock['groups']),
                exact_bytes=True,firmware_exported=False,app_exported=False,state_exported=False)


def main():
    p=argparse.ArgumentParser()
    inputs=p.add_mutually_exclusive_group()
    inputs.add_argument('--from-package',type=Path)
    inputs.add_argument('--download',action='store_true',help='Download the pinned public USB ZIP as data, then export its exact runtime assets')
    p.add_argument('--cache',type=Path,default=Path('downloads'))
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--verify-only',action='store_true')
    args=p.parse_args()
    if args.verify_only:
        if args.download or args.from_package:p.error('--verify-only cannot download or extract')
        verify(args.output);result=dict(passed=True,mode='verify')
    else:
        package=download_package(args.cache) if args.download else args.from_package
        if not package:p.error('--from-package or --download is required for export')
        if args.download and args.output.exists():
            lock=verify(args.output);result=dict(passed=True,mode='reuse-verified',files=len(lock['files']))
        else:result=export(package,args.output)
    print(json.dumps(result))


if __name__=='__main__':main()
