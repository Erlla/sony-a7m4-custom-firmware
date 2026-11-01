"""Export exactly the pinned runtime assets; never copy firmware, app or state."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import zipfile

HERE=Path(__file__).resolve().parent


def sha(stream):return hashlib.file_digest(stream,'sha256').hexdigest()


def fingerprint(files):
    return hashlib.sha256(''.join(n+'\0'+files[n]+'\n' for n in sorted(files)).encode()).hexdigest()


def verify(folder):
    lock=json.loads((HERE/'assets-files.json').read_text('utf-8'))
    for group,rule in lock['groups'].items():
        expected={n:v for n,v in lock['files'].items() if v['group']==group}
        actual={p.relative_to(folder).as_posix():p for p in (folder/group).rglob('*') if p.is_file()}
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
    output=output.resolve()
    if output.exists():raise ValueError('Output must be a new directory')
    output.mkdir(parents=True)
    with zipfile.ZipFile(package) as archive:
        roots={n.split('/')[0] for n in archive.namelist() if '/' in n}
        if len(roots)!=1:raise ValueError('Package needs exactly one root directory')
        prefix=next(iter(roots))+'/'
        names=archive.namelist()
        for name,row in lock['files'].items():
            member=prefix+name
            if names.count(member)!=1:raise ValueError('Missing or duplicated asset: '+name)
            target=output/name
            if not target.resolve().is_relative_to(output):raise ValueError('Invalid asset path')
            target.parent.mkdir(parents=True,exist_ok=True)
            with archive.open(member) as source,target.open('xb') as dest:shutil.copyfileobj(source,dest)
    verify(output)
    return dict(version='1.0.0',files=len(lock['files']),groups=len(lock['groups']),
                exact_bytes=True,firmware_exported=False,app_exported=False,state_exported=False)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--from-package',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--verify-only',action='store_true')
    args=p.parse_args()
    if args.verify_only:
        verify(args.output);result=dict(passed=True,mode='verify')
    else:
        if not args.from_package:p.error('--from-package is required for export')
        result=export(args.from_package,args.output)
    print(json.dumps(result))


if __name__=='__main__':main()
