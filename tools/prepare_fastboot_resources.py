"""Register the published boot assets with user-supplied Windows dependencies."""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform-tools', type=Path, required=True)
    parser.add_argument('--usb-driver', type=Path, required=True)
    parser.add_argument('--squashfs', type=Path, required=True)
    args = parser.parse_args()
    sq = args.squashfs / 'bin' if (args.squashfs / 'bin').is_dir() else args.squashfs
    for path in (args.platform_tools / 'fastboot.exe', args.usb_driver / 'android_winusb.inf',
                 sq / 'sqfs2tar.exe', sq / 'tar2sqfs.exe'):
        if not path.is_file():
            parser.error('Required file missing: ' + str(path))
    if (ROOT / 'vendor/manifest.local.json').exists():
        parser.error('Resources already registered; use a clean extraction to change them')
    source = ROOT / 'local/resources'

    def copy(path, relative):
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)

    for name in ('fastboot.bin', 'uart_boot.ino.uf2'):
        copy(ROOT / 'fastboot/assets' / name, 'bin/' + name)
    for path in args.platform_tools.iterdir():
        if path.is_file() and (path.name == 'fastboot.exe' or path.suffix.lower() in ('.dll', '.txt')):
            copy(path, 'bin/' + path.name)
    for path in args.usb_driver.rglob('*'):
        if path.is_file() and path.suffix.lower() in ('.inf', '.cat', '.dll', '.properties', '.txt'):
            copy(path, 'driver/' + path.relative_to(args.usb_driver).as_posix())
    for path in sq.iterdir():
        if path.is_file() and (path.name in ('sqfs2tar.exe', 'tar2sqfs.exe') or path.suffix.lower() == '.dll'):
            copy(path, 'squashfs/' + path.name)
    for path in args.squashfs.rglob('*'):
        if path.is_file() and (path.name.startswith(('LICENSE', 'COPYING', 'NOTICE')) or
                              'licenses' in path.parts and path.suffix.lower() in ('.txt', '.md')):
            copy(path, 'squashfs/licenses/' + path.relative_to(args.squashfs).as_posix())
    subprocess.run([sys.executable, str(ROOT / 'tools/register_resources.py'), str(source)], check=True)


if __name__ == '__main__':
    main()
