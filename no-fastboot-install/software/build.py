"""Build M4 Camera Tool from this checkout and separately supplied locked assets."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fingerprint(files):
    return hashlib.sha256(''.join(name + '\0' + files[name] + '\n' for name in sorted(files)).encode('utf-8')).hexdigest()


def release_version(dependencies=None):
    """One runtime version, checked against the unchanged dependency metadata."""
    dependencies = dependencies or json.loads((HERE / 'dependencies.json').read_text('utf-8'))
    module = ast.parse((HERE / 'app/product_version.py').read_text('utf-8-sig'))
    values = [node.value.value for node in module.body if isinstance(node, ast.Assign)
              and any(isinstance(name, ast.Name) and name.id == 'VERSION' for name in node.targets)
              and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)]
    # Accept the public X.YY label as well as existing X.Y.Z releases. The
    # literal must still match every manifest; never treat labels as aliases.
    if len(values) != 1 or not re.fullmatch(r'(0|[1-9][0-9]*)\.(?:[0-9]{2}|(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))', values[0]):
        raise ValueError('Invalid product version')
    version = values[0]
    if version != dependencies['version'] or any(int(part) > 65535 for part in version.split('.')):
        raise ValueError('Product version differs from dependency metadata')
    return version


def assembly_version(version):
    parts = [str(int(part)) for part in version.split('.')]
    return '.'.join(parts + ['0'] * (4 - len(parts)))


def safe_relative(name):
    if not isinstance(name, str) or not name or '\\' in name or name.startswith('/'):
        raise ValueError('Invalid asset path: ' + repr(name))
    reserved = {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$',
                *('COM' + str(i) for i in range(1, 10)), *('LPT' + str(i) for i in range(1, 10)),
                *('COM' + i for i in '¹²³'), *('LPT' + i for i in '¹²³')}
    for part in name.split('/'):
        if (part in ('', '.', '..') or part.endswith((' ', '.')) or
                any(ord(c) < 32 or c in '<>:"|?*' for c in part) or
                part.split('.')[0].upper() in reserved):
            raise ValueError('Invalid asset path: ' + repr(name))
    return name


def require_plain(path):
    if path.is_symlink() or getattr(path, 'is_junction', lambda: False)():
        raise ValueError('Linked assets are not accepted: ' + str(path))


def directory_assets(assets, group):
    safe_relative(group)
    require_plain(assets)
    parent = assets
    for part in group.split('/'):
        parent /= part
        require_plain(parent)
    paths = []
    for base, directories, names in os.walk(parent, followlinks=False):
        for name in directories + names:
            path = Path(base) / name
            require_plain(path)
            safe_relative(path.relative_to(assets).as_posix())
        paths.extend(Path(base) / name for name in names)
    aliases = [p.relative_to(assets).as_posix().casefold() for p in paths]
    if len(aliases) != len(set(aliases)):
        raise ValueError('Case-aliased asset paths')
    return sorted(paths)


def archive_assets(archive):
    """Reject Windows aliases/links before either asset entry point extracts."""
    seen, files, roots = {}, {}, set()
    for item in archive.infolist():
        original = item.orig_filename[:-1] if item.orig_filename.endswith('/') else item.orig_filename
        safe_relative(original)
        name = item.filename[:-1] if item.is_dir() else item.filename
        safe_relative(name)
        if stat.S_ISLNK(item.external_attr >> 16) or item.flag_bits & 1:
            raise ValueError('Linked or encrypted asset member')
        key = name.casefold()
        if key in seen:
            raise ValueError('Duplicate or case-aliased asset member: ' + name)
        seen[key] = item.is_dir()
        roots.add(name.split('/')[0])
        if not item.is_dir():
            if '/' not in name:
                raise ValueError('Assets ZIP must have exactly one top-level directory')
            files[name] = item
    if len(roots) != 1:
        raise ValueError('Assets ZIP must have exactly one top-level directory')
    for name in seen:
        parts = name.split('/')
        if any(seen.get('/'.join(parts[:i])) is False for i in range(1, len(parts))):
            raise ValueError('Asset member conflicts with a directory: ' + name)
    prefix = next(iter(roots)) + '/'
    return {name[len(prefix):]: item for name, item in files.items()}


def remove_owned(folder):
    require_plain(folder)
    path = str(folder.absolute())
    if os.name == 'nt' and not path.startswith('\\\\?\\'):
        path = '\\\\?\\UNC\\' + path[2:] if path.startswith('\\\\') else '\\\\?\\' + path
    shutil.rmtree(path)


@contextmanager
def new_output(output):
    """Publish a complete sibling directory; never overwrite a prior install."""
    output = output.absolute()
    if os.path.lexists(output):
        raise ValueError('Output already exists; preserve the installation and choose a new directory')
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.m4-build-', dir=output.parent))
    try:
        yield stage
        if os.path.lexists(output):
            raise ValueError('Output appeared during preparation; it was not replaced')
        stage.rename(output)
    finally:
        if stage.exists():
            remove_owned(stage)


def copy_assets(assets, output, dependencies):
    if assets.is_file():
        require_plain(assets)
        with zipfile.ZipFile(assets) as archive:
            available = archive_assets(archive)
            for group, lock in dependencies['groups'].items():
                safe_relative(group)
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
            paths = directory_assets(assets, group)
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
    version=release_version()
    if value.get('version') != version:
        raise ValueError('Launcher and release manifest versions differ')
    manifest=output / 'app/release.json'
    template=(HERE / 'Launcher.cs').read_text('utf-8-sig')
    source=(template.replace('@VERSION@',version).replace('@ASSEMBLY_VERSION@',assembly_version(version))
            .replace('@PYTHON@',value['gui_runtime_sha256'])
            .replace('@PYTHON_EXE@',value['python_sha256'])
            .replace('@ENTRY@',sha(output / 'app/entry.py')).replace('@RELEASE@',sha(manifest)))
    folder=output / '_launcher_build';folder.mkdir(exist_ok=True)
    managed=folder / 'Launcher.exe'
    (folder / 'Launcher.cs').write_text(source,encoding='utf-8',newline='\n')
    compiler=Path(os.environ['SystemRoot']) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    subprocess.run([str(compiler),'/nologo','/target:winexe','/optimize+','/codepage:65001',
        '/reference:System.Windows.Forms.dll','/reference:System.Web.Extensions.dll','/reference:System.Management.dll',
        '/out:'+str(managed),str(folder / 'Launcher.cs')],check=True,capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW)
    raw=managed.read_bytes()
    files=dict(value['files']);files['app/release.json']=sha(manifest)
    header='struct ExpectedFile {const char*name;const char*hash;};\n'
    header+='#define PRODUCT_VERSION '+json.dumps(version)+'\n'
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


def build_product(assets, destination):
    dependencies = json.loads((HERE / 'dependencies.json').read_text('utf-8'))
    version = release_version(dependencies)
    with new_output(destination) as output:
        copy_assets(assets.absolute(), output, dependencies)
        shutil.copytree(HERE / 'app', output / 'app', ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'release.json'))
        for name in ('README.md', 'THIRD_PARTY.md'):
            shutil.copyfile(HERE / name, output / name)
        shutil.copyfile(output / 'app/ui/使用说明.md', output / '使用说明.md')
        paths = [p for group in ('app', 'runtime', 'vendor', 'tools', 'licenses') for p in (output / group).rglob('*') if p.is_file()]
        paths += [output / name for name in ('README.md', 'THIRD_PARTY.md', '使用说明.md')]
        with ThreadPoolExecutor(max_workers=8) as pool:
            files = dict(zip((p.relative_to(output).as_posix() for p in paths), pool.map(sha, paths)))
        value = dict(schema='m4-clean-product-release/1', version=version, files=files,
                     python_sha256=sha(output / 'runtime/python/python.exe'), gui_runtime_sha256=sha(output / 'runtime/python/pythonw.exe'),
                     per_operation_validation='integrity_only', independent_full_readback=True,
                     bundled_firmware=False, bundled_camera_libraries=False, automatic_camera_actions=False,
                     startup_trust='native_exact_inventory_protected_snapshot',
                     integrity_cache='windows_read_lease_no_write_or_delete')
        agent_tree = ast.parse((HERE / 'app/agent_api.py').read_text('utf-8-sig'))
        value['agent_build_id'] = next(ast.literal_eval(node.value) for node in agent_tree.body
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'BUILD_ID' for t in node.targets))
        value['agent_interface'] = 'm4-agent/1'
        manifest = output / 'app/release.json'
        manifest.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
        compile_launcher(output)
        commands = ([str(output / 'runtime/python/python.exe'), '-I', '-s', '-B', '-X', 'utf8', str(output / 'app/entry.py'), '--check'],
                    [str(output / 'M4相机工具.exe'), '--verify'])
        for command in commands:
            checked = subprocess.run(command, check=True, capture_output=True, timeout=120, creationflags=subprocess.CREATE_NO_WINDOW)
            result = json.loads(checked.stdout)
            if result.get('version') != version or result.get('integrity') is not True or result.get('device_operations') != 0:
                raise ValueError('Built product did not confirm its version and integrity')
            if command[0].endswith('M4相机工具.exe') and result.get('native_verification') is not True:
                raise ValueError('Native launcher did not confirm native verification')
        for name in ('_launcher_build', 'state'):
            if (output / name).exists(): remove_owned(output / name)
    return dict(output=str(destination.resolve()), version=version, device_operations=0, native_verification=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, required=True, help='Locked clean runtime directory or portable ZIP; only runtime groups are copied')
    parser.add_argument('--output', type=Path, required=True, help='New directory; never an existing installation')
    args = parser.parse_args()
    try:
        print(json.dumps(build_product(args.assets, args.output)))
    except subprocess.CalledProcessError as error:
        for output in (error.stdout, error.stderr):
            if output:
                print(output.decode('utf-8', errors='replace') if isinstance(output, bytes) else output, file=sys.stderr)
        raise


if __name__ == '__main__': main()
