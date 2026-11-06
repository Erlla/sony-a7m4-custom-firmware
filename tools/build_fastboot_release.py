"""Export only the Fastboot maintenance source, boot assets and entry scripts."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MODULES = ('__init__', '__main__', 'cli', 'common', 'transport', 'hardware', 'engine',
           'patching', 'fat', 'maintenance', 'demo', 'recover_sd', 'sd_recovery')
ENTRIES = ('进入fastboot', '退出fastboot开机', '备份全部数据', '查看或设置固件版本',
           '刷入验签跳过版更新器', '恢复官方验签公钥', '一键救砖_从SD卡恢复',
           '只检查fastboot连接', '安装Fastboot驱动')


def build(output):
    files = {f'a7m4/{name}.py': (ROOT / 'a7m4' / (name + '.py')).read_bytes() for name in MODULES}
    for name in ('pyproject.toml', 'setup.bat', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'REFERENCES.md',
                 'a7m4/profiles/updater.json', 'a7m4/profiles/sd-recovery.json',
                 'advanced/_launch.cmd', 'advanced/_launch_recovery.cmd',
                 'tools/register_resources.py', 'tools/prepare_fastboot_resources.py',
                 'tools/build_fastboot_release.py', 'tools/build_fastboot_portable.py', 'docs/setup.md', 'docs/setup.en.md',
                 'docs/wiring.md', 'docs/wiring.en.md',
                 'methods/00-sd-recovery/README.md', 'methods/00-sd-recovery/README.en.md'):
        files[name] = (ROOT / name).read_bytes()
    for entry in ENTRIES:
        name = entry + '.bat'
        files['advanced/' + name] = (ROOT / 'advanced' / name).read_bytes()
        files[name] = ('@echo off\r\ncall "%~dp0advanced\\' + name + '"\r\nexit /b %errorlevel%\r\n').encode('utf-8')
    for path in (ROOT / 'fastboot').rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts:
            files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    files['README.md'] = ('# A7M4 Fastboot 维护工具\n\n'
        '**刷写有风险。先阅读[操作与环境说明](fastboot/README.md)。**\n\n'
        '适用于 Sony ILCE-7M4（A7 IV / A7M4），官方 V6.02 为修改基线。\n\n'
        '包内包含相机端 fastboot.bin、RP2040 UF2、源码资料，以及进入/退出、全部 eMMC 备份、版本设置、更新器修改、恢复官方验签和一键救砖入口。\n\n'
        '需要 Windows 10/11、Python 3.11+、Multi 刷机线和 RP2040-Zero。运行 setup.bat 后按操作说明登记 Windows 外部工具；此 ZIP 不包含 Android SDK 驱动、Platform Tools 或 SquashFS 发行包。\n\n'
        '在根目录双击对应 BAT 即可运行。恢复官方验签需要修改前的同机官方备份。全部 eMMC 备份不包含独立 CP NOR。\n\n'
        '一键救砖要求相机已进入 Fastboot、更新环境匹配内置清单，并在卡槽1根目录放入适用的 BODYDATA.DAT；按[救砖说明](methods/00-sd-recovery/README.md)操作。\n\n'
        '[来源与许可范围](fastboot/SOURCES.md) · [文件校验](SHA256SUMS.txt)\n').encode('utf-8')
    # Documentation links to parts outside this focused archive remain navigable.
    import posixpath
    import re
    from urllib.parse import quote
    for name, data in list(files.items()):
        if not name.endswith('.md'):
            continue
        def link(match):
            target = match.group(1)
            if '://' in target or target.startswith('#'):
                return match.group(0)
            path, _, anchor = target.partition('#')
            relative = posixpath.normpath(posixpath.join(posixpath.dirname(name), path))
            if relative in files or any(k.startswith(relative.rstrip('/') + '/') for k in files):
                return match.group(0)
            return '](' + 'https://github.com/Erlla/sony-a7m4-custom-firmware/blob/main/' + quote(relative) + ('#' + anchor if anchor else '') + ')'
        files[name] = re.sub(r'\]\(([^\s)]+)\)', link, data.decode('utf-8')).encode('utf-8')
    files['SHA256SUMS.txt'] = ''.join(hashlib.sha256(data).hexdigest() + '  ' + name + '\n'
                                     for name, data in sorted(files.items())).encode('utf-8')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            archive.writestr('A7M4-Fastboot/' + name, data)
    result = dict(file=output.name, bytes=output.stat().st_size,
                  sha256=hashlib.sha256(output.read_bytes()).hexdigest(), files=len(files))
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    build(parser.parse_args().output)
