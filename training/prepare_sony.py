"""Extract locally supplied Sony reference files; never install or run Sony apps."""
from pathlib import Path
import argparse
import hashlib
import shutil
import subprocess

PACKAGE_SHA='d7927efe5a4d67707b8d74b14511b39f353a5ca5cb79240554d73b3bda4707ab'
BINARY_SHA='43ae5e1cb4bc18a52183b430e02b16a4506b89a907a6fd0feed359fa85a82ce9'
TABLE_SHA='ef1dd637b6656dc895246265bd311fbc63b0e95f7b50005ceb61c19d472d9aba'


def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb')as f:
        for block in iter(lambda:f.read(8<<20),b''):h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--package',required=True,type=Path,help='Official IE410_2603a.dmg obtained by the user')
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--sevenzip',default=shutil.which('7z'))
    a=p.parse_args()
    if digest(a.package)!=PACKAGE_SHA:raise ValueError('Unsupported official package identity')
    if not a.sevenzip:p.error('Install7-Zip or supply --sevenzip')
    if a.output.exists():raise FileExistsError('Choose a new extraction directory')
    a.output.mkdir(parents=True)
    def extract(src,dest,*members):
        subprocess.run([a.sevenzip,'x','-y','-bso0','-bsp0','-o'+str(dest),str(src),*members],check=True)
    extract(a.package,a.output/'suite')
    extract(a.output/'suite/IE_INST.pkg',a.output/'pkg')
    # CPIO member spelling is significant; do not extract Framework symlinks.
    extract(a.output/'pkg/Payload~',a.output/'files',r'.\Edit.app\Contents\MacOS\Edit',
            r'.\Edit.app\Contents\Resources\*')
    root=a.output/'files/Edit.app/Contents'
    binary,table=root/'MacOS/Edit',root/'Resources/srsettings0000.tbl'
    if digest(binary)!=BINARY_SHA or digest(table)!=TABLE_SHA:
        raise ValueError('Extracted reference identities differ')
    print('Sony Edit binary:',binary.resolve())
    print('srsettings:',table.resolve())
    print('Reference extraction verified; no Sony process or camera accessed.')


if __name__=='__main__':main()
