"""Build an offline Windows x64 archive from explicitly supplied runtime assets."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile
import zipfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_fastboot_release import build as build_source
sha = lambda data: hashlib.sha256(data).hexdigest()


def build(args):
    with tempfile.TemporaryDirectory(prefix='a7m4-source-') as temp:
        source = Path(temp) / 'source.zip'
        build_source(source)
        with zipfile.ZipFile(source) as archive:
            files = {n.removeprefix('A7M4-Fastboot/'): archive.read(n) for n in archive.namelist()}
    files.pop('SHA256SUMS.txt')
    components = []

    def record(path, kind):
        components.append(dict(file=path.name, kind=kind, sha256=sha(path.read_bytes())))

    with zipfile.ZipFile(args.python_zip) as archive:
        for name in archive.namelist():
            if not name.endswith('/'):
                files['runtime/python/' + name] = archive.read(name)
    pth = next(n for n in files if n.startswith('runtime/python/') and n.endswith('._pth'))
    stdlib = next(n.rsplit('/', 1)[-1] for n in files if re.fullmatch(r'runtime/python/python\d+\.zip', n))
    files[pth] = (stdlib + '\n.\nLib/site-packages\n../../\nimport site\n').encode('utf-8')
    record(args.python_zip, 'CPython embedded runtime')
    for wheel in sorted(args.wheels.glob('*.whl')):
        with zipfile.ZipFile(wheel) as archive:
            for name in archive.namelist():
                if not name.endswith('/'):
                    files['runtime/python/Lib/site-packages/' + name] = archive.read(name)
        record(wheel, 'Python dependency wheel')

    with zipfile.ZipFile(args.platform_tools) as archive:
        for name in ('fastboot.exe', 'AdbWinApi.dll', 'AdbWinUsbApi.dll', 'NOTICE.txt', 'source.properties'):
            files['vendor/local/bin/' + name] = archive.read('platform-tools/' + name)
    record(args.platform_tools, 'Platform Tools original archive; selected Fastboot files and NOTICE')
    for name in ('fastboot.bin', 'uart_boot.ino.uf2'):
        files['vendor/local/bin/' + name] = files['fastboot/assets/' + name]
    sq = args.squashfs / 'bin' if (args.squashfs / 'bin').is_dir() else args.squashfs
    for path in sq.iterdir():
        if path.is_file() and (path.name in ('sqfs2tar.exe', 'tar2sqfs.exe') or path.suffix.lower() == '.dll'):
            files['vendor/local/squashfs/' + path.name] = path.read_bytes()
    for path in args.squashfs.rglob('*'):
        if path.is_file() and (path.name.startswith(('LICENSE', 'COPYING', 'NOTICE')) or
                              'licenses' in path.parts and path.suffix.lower() in ('.txt', '.md')):
            files['vendor/local/squashfs/licenses/' + path.relative_to(args.squashfs).as_posix()] = path.read_bytes()
    files['vendor/local/driver/zadig.exe'] = args.zadig.read_bytes()
    for name in ('zadig.ini', 'A7M4-Fastboot.cfg'):
        files['vendor/local/driver/' + name] = files['fastboot/driver/' + name]
    record(args.zadig, 'Zadig WinUSB driver installer')
    for path in sorted(args.sources.iterdir()):
        if path.is_file() and path.name.endswith(('.zip', '.tar.gz', '.tar.xz')) and not path.name.startswith('python-'):
            files['third-party-sources/' + path.name] = path.read_bytes()
            record(path, 'Corresponding third-party source archive')
            if path.name.startswith('libwdi-'):
                with zipfile.ZipFile(path) as archive:
                    for name in archive.namelist():
                        if name.rsplit('/', 1)[-1] in ('COPYING', 'COPYING-LGPL'):
                            files['licenses/libwdi/' + name.rsplit('/', 1)[-1]] = archive.read(name)
    for required in ('squashfs-tools-ng-1.3.2.tar.xz', 'libwdi-1.5.1.zip', 'lzo-2.10.tar.gz'):
        if 'third-party-sources/' + required not in files:
            raise ValueError('Required corresponding source missing: ' + required)
    vendor = {}
    for name, data in files.items():
        if name.startswith('vendor/local/'):
            vendor[name.removeprefix('vendor/local/')] = dict(size=len(data), sha256=sha(data))
    files['vendor/manifest.local.json'] = (json.dumps(dict(schema=1,
        distribution='Windows x64 portable bundle; third-party components retain their own licenses',
        files=vendor), indent=2) + '\n').encode('utf-8')
    files['PORTABLE_COMPONENTS.json'] = (json.dumps(dict(platform='Windows x64', components=components), indent=2) + '\n').encode('utf-8')
    files['README.md'] = '''# A7M4 Fastboot 便携工具

**仅适用于 Sony ILCE-7M4（A7 IV / A7M4），修改基线为官方 V6.02。刷写可能导致无法开机或数据丢失。先备份本机，使用原厂电池并保持供电。**

## 解压后使用

完整解压到本地目录，直接双击所需 BAT。支持 Windows 10/11 x64；无需安装系统 Python、下载依赖库或设置 PATH。包内已有 Python、pySerial、pyelftools、cryptography 及其依赖、电脑端 Fastboot、SquashFS 工具，以及相机端 BIN 和 RP2040 UF2。

仍需正确连接 Multi 刷机线和 RP2040-Zero；首次写入 RP2040 时按住 BOOTSEL 接入。硬件接线见 [说明](docs/wiring.md)。

## 首次安装 Fastboot 驱动

已有正确驱动可直接使用。新电脑在相机进入 Fastboot 后，双击“安装Fastboot驱动.bat”并确认管理员授权；进入流程也会在缺少驱动时打开安装窗口。

1. 在 Zadig 窗口选择 **Device → Load Preset Device**。
2. 打开包内 `vendor/local/driver/A7M4-Fastboot.cfg`，确认 **VID 18D1、PID 4EE0** 及目标驱动 **WinUSB**。
3. 点击 **Install Driver**，完成后运行“只检查fastboot连接.bat”。

安装预设保留 Android Fastboot 所需的设备接口 GUID。无需关闭驱动签名检查；不要为其他 USB 设备更换驱动。

## 操作入口

| 入口 | 用途 |
|---|---|
| 进入fastboot.bat / 退出fastboot开机.bat | 进入维护状态或重启相机 |
| 备份全部数据.bat | 保存 payload 提供的全部 eMMC 分区；不含独立 CP NOR |
| 查看或设置固件版本.bat | 查看或改变报告版本；不安装其他固件功能 |
| 刷入验签跳过版更新器.bat | 从本机备份生成自有公钥与 verifyKey 补丁，确认后刷写并读回 |
| 恢复官方验签公钥.bat | 从修改前的同机官方备份恢复公钥和验签代码 |
| 一键救砖_从SD卡恢复.bat | 相机已在 Fastboot 且更新环境受支持时，从卡槽1适用 BODYDATA.DAT 触发恢复 |
| 只检查fastboot连接.bat | 只枚举设备和查询型号 |
| 安装Fastboot驱动.bat | 打开随包 WinUSB 驱动安装器 |

一般维护入口保留本次完整备份、待写内容确认与写后全读。一键救砖没有第二次交互确认，详细适用条件见[救砖指南](methods/00-sd-recovery/README.md)。包内不含固件 DAT、机身备份或预制分区。

`setup.bat` 在便携包中仅检查随包资源，不联网安装。`vendor/manifest.local.json` 是随包资源清单，不是机身状态。

## 来源与许可

本项目原创代码采用 MIT；Python、第三方库及工具保留各自许可，见其 LICENSE/NOTICE 和 `PORTABLE_COMPONENTS.json`。WinUSB 安装使用 Zadig/libwdi，包中附带其源码以及 SquashFS 与压缩库的对应源码，见 `third-party-sources/`。相机启动组件的来源和许可范围见 [SOURCES](fastboot/SOURCES.md)。
'''.encode('utf-8')
    files['SHA256SUMS.txt'] = ''.join(sha(data) + '  ' + name + '\n' for name, data in sorted(files.items())).encode('utf-8')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            archive.writestr('A7M4-Fastboot/' + name, data)
    result = dict(file=args.output.name, bytes=args.output.stat().st_size, sha256=sha(args.output.read_bytes()))
    print(json.dumps(result))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python-zip', type=Path, required=True)
    parser.add_argument('--wheels', type=Path, required=True)
    parser.add_argument('--platform-tools', type=Path, required=True)
    parser.add_argument('--squashfs', type=Path, required=True)
    parser.add_argument('--zadig', type=Path, required=True)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    build(parser.parse_args())
