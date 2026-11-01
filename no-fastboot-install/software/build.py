"""Build M4 Camera Tool from this checkout and separately supplied locked assets."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fingerprint(files):
    return hashlib.sha256(''.join(name + '\0' + files[name] + '\n' for name in sorted(files)).encode('utf-8')).hexdigest()


def copy_assets(assets, output, dependencies):
    if assets.is_file():
        with zipfile.ZipFile(assets) as archive:
            roots = {item.split('/')[0] for item in archive.namelist() if '/' in item}
            if len(roots) != 1:
                raise ValueError('Assets ZIP must have exactly one top-level directory')
            prefix = next(iter(roots)) + '/'
            available = {name[len(prefix):]: name for name in archive.namelist() if name.startswith(prefix) and not name.endswith('/')}
            for group, lock in dependencies['groups'].items():
                selected = {name: original for name, original in available.items() if name.startswith(group + '/')}
                actual = {}
                for name, original in selected.items():
                    target = output / name
                    if not target.resolve().is_relative_to(output): raise ValueError('Invalid asset path')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(original) as stream, target.open('xb') as destination:
                        shutil.copyfileobj(stream, destination)
                    actual[name] = sha(target)
                if len(actual) != lock['files'] or fingerprint(actual) != lock['tree_sha256']:
                    raise ValueError('Runtime asset group differs: ' + group)
    else:
        for group, lock in dependencies['groups'].items():
            paths = sorted(p for p in (assets / group).rglob('*') if p.is_file())
            actual = {}
            for source in paths:
                if source.is_symlink(): raise ValueError('Linked assets are not accepted')
                name = source.relative_to(assets).as_posix()
                actual[name] = sha(source)
            if len(actual) != lock['files'] or fingerprint(actual) != lock['tree_sha256']:
                raise ValueError('Runtime asset group differs: ' + group)
            for name in actual:
                target = output / name; target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(assets / name, target)
            # Re-read the completed group: a source may change after preflight,
            # or an earlier destination may change while later files copy.
            copied = {name: sha(output / name) for name in actual}
            if copied != actual:
                raise ValueError('Copied runtime asset group differs: ' + group)


def compile_launcher(output):
    value=json.loads((output / 'app/release.json').read_text('utf-8'))
    manifest=output / 'app/release.json'
    template=(HERE / 'Launcher.cs').read_text('utf-8-sig')
    source=(template.replace('@PYTHON@',value['gui_runtime_sha256'])
            .replace('@PYTHON_EXE@',value['python_sha256'])
            .replace('@ENTRY@',sha(output / 'app/entry.py')).replace('@RELEASE@',sha(manifest)))
    folder=output / '_launcher_build';folder.mkdir(exist_ok=True)
    managed=folder / 'Launcher.exe'
    (folder / 'Launcher.cs').write_text(source,encoding='utf-8',newline='\n')
    compiler=Path(os.environ['SystemRoot']) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    subprocess.run([str(compiler),'/nologo','/target:winexe','/optimize+','/codepage:65001',
        '/reference:System.Windows.Forms.dll','/reference:System.Web.Extensions.dll',
        '/out:'+str(managed),str(folder / 'Launcher.cs')],check=True,capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW)
    raw=managed.read_bytes()
    files=dict(value['files']);files['app/release.json']=sha(manifest)
    header='struct ExpectedFile {const char*name;const char*hash;};\n'
    header+='#define FILE_COUNT '+str(len(files))+'\n'
    header+='static const struct ExpectedFile files[FILE_COUNT]={\n'
    header+=''.join('{'+json.dumps(n,ensure_ascii=False)+','+json.dumps(files[n])+'},\n' for n in sorted(files))+'};\n'
    header+='#define MANAGED_SHA '+json.dumps(hashlib.sha256(raw).hexdigest())+'\n'
    header+='static const unsigned char managed_payload[]={'+','.join(str(v) for v in raw)+'};\n'
    (folder / 'bootstrap_payload.h').write_text(header,encoding='utf-8',newline='\n')
    shutil.copyfile(HERE / 'launcher/bootstrap.c',folder / 'bootstrap.c')
    shutil.copyfile(HERE / 'app/writer/sha256.h',folder / 'sha256.h')
    exports=['GetModuleFileNameW','GetCommandLineW','CreateFileW','ReadFile','WriteFile','CloseHandle',
        'ExitProcess','GetLastError','GetFileAttributesW','CreateDirectoryW','GetProcessHeap',
        'HeapAlloc','HeapFree','LoadLibraryExW','GetProcAddress','GetSystemDirectoryW','LocalFree',
        'FindFirstFileW','FindNextFileW','FindClose','CreateProcessW','WaitForSingleObject','GetExitCodeProcess','GetStdHandle',
        'GetEnvironmentStringsW','FreeEnvironmentStringsW','SetEnvironmentVariableW']
    (folder / 'kernel32.def').write_text('LIBRARY KERNEL32.dll\nEXPORTS\n'+'\n'.join(exports)+'\n','utf-8')
    zig=output / 'tools/zig/zig.exe'
    env=os.environ.copy();env.pop('ZIG_LIB_DIR',None)
    env['ZIG_GLOBAL_CACHE_DIR']=str(output / 'state/cache/zig-host-global')
    env['ZIG_LOCAL_CACHE_DIR']=str(output / 'state/cache/zig-host-local')
    subprocess.run([str(zig),'dlltool','-m','i386:x86-64','-d',str(folder / 'kernel32.def'),'-l',str(folder / 'kernel32.lib')],
        check=True,capture_output=True,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
    subprocess.run([str(zig),'cc','-target','x86_64-windows-gnu','-O2','-nostdlib','-fno-builtin',
        '-fno-stack-protector','-mno-stack-arg-probe',str(folder / 'bootstrap.c'),str(folder / 'kernel32.lib'),
        '-Wl,--entry,WinMainCRTStartup','-Wl,--subsystem,windows','-Xlinker','--stack','-Xlinker','2097152',
        '-o',str(output / 'M4相机工具.exe')],check=True,capture_output=True,env=env,
        creationflags=subprocess.CREATE_NO_WINDOW)
    # Freestanding code has no CRT stack probe; commit the entire bounded stack.
    exe=output / 'M4相机工具.exe'
    raw=bytearray(exe.read_bytes());pe=struct.unpack_from('<I',raw,60)[0];optional=pe+24
    if raw[pe:pe+4]!=b'PE\0\0' or struct.unpack_from('<H',raw,optional)[0]!=0x20b:
        raise ValueError('Expected Windows x64 PE launcher')
    reserve=struct.unpack_from('<Q',raw,optional+72)[0]
    struct.pack_into('<Q',raw,optional+80,reserve)
    exe.write_bytes(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, required=True, help='Locked clean runtime directory or portable ZIP; only runtime groups are copied')
    parser.add_argument('--output', type=Path, required=True, help='New directory; never an existing installation')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists(): raise ValueError('Output already exists; preserve the installation and choose a new directory')
    dependencies = json.loads((HERE / 'dependencies.json').read_text('utf-8'))
    output.mkdir(parents=True)
    copy_assets(args.assets.resolve(strict=True), output, dependencies)
    shutil.copytree(HERE / 'app', output / 'app', ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'release.json'))
    for name in ('README.md', 'THIRD_PARTY.md'):
        shutil.copyfile(HERE / name, output / name)
    shutil.copyfile(output / 'app/ui/使用说明.md', output / '使用说明.md')
    paths = [p for group in ('app', 'runtime', 'vendor', 'tools', 'licenses') for p in (output / group).rglob('*') if p.is_file()]
    paths += [output / name for name in ('README.md','THIRD_PARTY.md','使用说明.md')]
    with ThreadPoolExecutor(max_workers=8) as pool:
        files = dict(zip((p.relative_to(output).as_posix() for p in paths), pool.map(sha, paths)))
    value = dict(schema='m4-clean-product-release/1', version='1.0.0', files=files,
                 python_sha256=sha(output / 'runtime/python/python.exe'), gui_runtime_sha256=sha(output / 'runtime/python/pythonw.exe'),
                 per_operation_validation='integrity_only', independent_full_readback=True,
                 bundled_firmware=False, bundled_camera_libraries=False, automatic_camera_actions=False,
                 startup_trust='native_exact_inventory_protected_snapshot',
                 integrity_cache='windows_read_lease_no_write_or_delete')
    manifest = output / 'app/release.json'
    manifest.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    compile_launcher(output)
    # --check is local integrity validation and cannot enumerate or command the camera.
    subprocess.run([str(output / 'runtime/python/python.exe'), '-I', '-s', '-B', '-X', 'utf8', str(output / 'app/entry.py'), '--check'],
                   check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    print(json.dumps(dict(output=str(output), version='1.0.0', device_operations=0)))


if __name__ == '__main__': main()
