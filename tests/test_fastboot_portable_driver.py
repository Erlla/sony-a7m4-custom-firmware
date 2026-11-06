import hashlib
import json
import sys
from types import SimpleNamespace

import pytest

from a7m4.common import Assets
from a7m4 import cli, hardware


def portable_assets(tmp_path):
    names = ('bin/fastboot.exe', 'bin/fastboot.bin', 'bin/uart_boot.ino.uf2',
             'squashfs/sqfs2tar.exe', 'squashfs/tar2sqfs.exe', 'driver/zadig.exe',
             'driver/zadig.ini', 'driver/A7M4-Fastboot.cfg')
    files = {}
    for name in names:
        data = ('fixture:' + name).encode()
        path = tmp_path / 'local' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        files[name] = {'sha256': hashlib.sha256(data).hexdigest()}
    (tmp_path / 'manifest.local.json').write_text(json.dumps({'files': files}), 'utf8')
    return Assets(tmp_path)


def test_complete_winusb_bundle_and_missing_preset(tmp_path):
    assets = portable_assets(tmp_path)
    assert assets.check()['ready']
    (tmp_path / 'local/driver/A7M4-Fastboot.cfg').unlink()
    assert not assets.check()['ready']


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows installer dispatch')
def test_winusb_installer_uses_elevation_and_preserves_paths(tmp_path, monkeypatch):
    assets = portable_assets(tmp_path / "copy & user's 中文")
    calls, messages = [], []
    monkeypatch.setattr(hardware, 'run', lambda args, **kw: calls.append(args) or b'')
    hardware.install_driver(assets, messages.append)
    assert len(calls) == 1
    assert '-Verb RunAs' in calls[0][-1]
    assert 'zadig.exe' in calls[0][-1]
    assert "user''s" in calls[0][-1]
    assert any('A7M4-Fastboot.cfg' in item.get('message', '') for item in messages)


def test_demo_never_opens_driver_installer(monkeypatch, capsys):
    monkeypatch.setattr(cli, 'Engine', lambda **kw: SimpleNamespace())
    monkeypatch.setattr(hardware, 'install_driver', lambda *a: pytest.fail('Driver installer was invoked'))
    monkeypatch.setattr(sys, 'stdin', SimpleNamespace(reconfigure=lambda **kw: None))
    monkeypatch.setattr(sys, 'argv', ['a7m4', '--demo', 'install-driver'])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
    assert 'DEMO' in capsys.readouterr().err
