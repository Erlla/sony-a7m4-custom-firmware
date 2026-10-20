"""Public packaging and launcher checks; synthetic data only, no hardware."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch

import pytest

from a7m4 import recover_sd, sd_recovery as core
from a7m4.common import Assets, ToolError
from test_sd_recovery import settings_image, entry

ROOT = Path(__file__).resolve().parents[1]


def updater_image(bad_md5=False):
    image = bytearray(settings_image())
    initrd = b'synthetic-initrd-not-firmware'
    entry(image, 1536, 'P1CHKSUM', cluster=2, size=32)
    entry(image, 1568, 'BOOT', attr=0x10, cluster=3)
    entry(image, 4096, 'INITRD  IMG', cluster=4, size=len(initrd))
    image[4128:4608] = bytes(480)
    image[3584:3616] = b'0' * 32 if bad_md5 else hashlib.md5(initrd).hexdigest().encode('ascii')
    image[4608:4608 + len(initrd)] = initrd
    return bytes(image), hashlib.sha256(initrd).hexdigest()


def test_real_updater_inspection_accepts_only_exact_hash_and_md5():
    image, sha = updater_image()
    result = core.inspect_sd_environment(image, {'approved_initrd_hashes': {sha: 'synthetic'}})
    assert result['initrd_sha256'] == sha
    assert result['host_read_SD_card'] is False
    with pytest.raises(ToolError) as unknown:
        core.inspect_sd_environment(image, core.read_config())
    assert unknown.value.code == 'UPDATER_PROFILE'
    image, sha = updater_image(bad_md5=True)
    with pytest.raises(ToolError) as corrupt:
        core.inspect_sd_environment(image, {'approved_initrd_hashes': {sha: 'synthetic'}})
    assert corrupt.value.code == 'UPDATER_CHECKSUM'


def test_packaged_profile_has_no_local_runtime_or_generic_wildcard():
    config = core.read_config()
    assert config['product'] == 'ILCE-7M4'
    assert 'python_runtime' not in config
    assert list(config['approved_initrd_hashes']) == [
        'bd81714ed85b175ad6da41947adcb80b7b3deb965c23aab04c84901c99e52d98']


def test_missing_local_assets_stop_before_hardware(tmp_path):
    with patch.object(recover_sd, 'check_resources', side_effect=lambda: core.check_resources(Assets(tmp_path))), \
         patch.object(recover_sd, 'hardware_lock') as lock, patch.object(recover_sd, 'RecoveryTransport') as transport:
        with pytest.raises(ToolError) as caught:
            recover_sd.main(['--check-connection', '--sessions', str(tmp_path / 'sessions')])
        assert caught.value.code == 'ASSETS_MISSING'
        lock.assert_not_called()
        transport.assert_not_called()
        assert not (tmp_path / 'sessions').exists()


def test_custom_session_location_and_write_entry_dispatch(tmp_path):
    destination = tmp_path / 'custom sessions 中文'
    with patch.object(recover_sd, 'check_resources'), patch.object(recover_sd, 'read_config', return_value={}), \
         patch.object(recover_sd, 'hardware_lock'), patch.object(recover_sd, 'RecoveryTransport') as cls, \
         patch.object(recover_sd, 'recover') as flow:
        assert recover_sd.main(['--sessions', str(destination)]) == 0
        flow.assert_called_once()
        assert flow.call_args.args[0] is cls.return_value
        assert flow.call_args.args[1].parent == destination


def test_minimal_registration_does_not_require_boot_or_squashfs(tmp_path):
    source, destination = tmp_path / 'input 中文', tmp_path / 'registered'
    (source / 'bin').mkdir(parents=True)
    for name in ('fastboot.exe', 'AdbWinApi.dll', 'AdbWinUsbApi.dll', 'NOTICE.txt', 'unrelated.exe', 'fastboot.bin'):
        (source / 'bin' / name).write_bytes(b'not executable: synthetic data')
    result = subprocess.run([sys.executable, str(ROOT / 'tools/register_resources.py'), str(source),
                             '--destination', str(destination), '--recovery-only'],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    manifest = json.loads((destination / 'manifest.local.json').read_text('utf8'))
    assert set(manifest['files']) == {'bin/fastboot.exe', 'bin/AdbWinApi.dll', 'bin/AdbWinUsbApi.dll', 'bin/NOTICE.txt'}
    assert core.check_resources(Assets(destination))['camera_io'] is False
    assert Assets(destination).check()['ready'] is False
    again = subprocess.run([sys.executable, str(ROOT / 'tools/register_resources.py'), str(source),
                            '--destination', str(destination), '--recovery-only'],
                           capture_output=True, text=True, timeout=30)
    assert again.returncode != 0 and 'Manifest exists' in again.stderr


@pytest.mark.skipif(os.name != 'nt', reason='Windows BAT entry points')
@pytest.mark.parametrize('name,expected', [
    ('一键救砖_从SD卡恢复.bat', []), ('只检查fastboot连接.bat', ['--check-connection'])])
def test_real_batch_passes_arguments_and_exit_status_without_hardware(tmp_path, name, expected):
    root = tmp_path / 'public copy & 中文'
    (root / 'advanced').mkdir(parents=True)
    (root / 'a7m4').mkdir()
    for filename in (name, '_launch_recovery.cmd'):
        shutil.copyfile(ROOT / 'advanced' / filename, root / 'advanced' / filename)
    (root / 'a7m4/__init__.py').write_text('', 'utf8')
    (root / 'a7m4/recover_sd.py').write_text(
        'import json, sys\nfrom pathlib import Path\n'
        'Path("args.json").write_text(json.dumps(sys.argv[1:]), "utf8")\nraise SystemExit(7)\n', 'utf8')
    env = os.environ | {'A7M4_PYTHON': sys.executable, 'A7M4_NO_PAUSE': '1', 'A7M4_DEMO': '0'}
    result = subprocess.run(['cmd.exe', '/d', '/c', name], cwd=root / 'advanced',
                            capture_output=True, encoding='utf8', env=env, timeout=30)
    assert result.returncode == 7, result.stdout + result.stderr
    assert json.loads((root / 'args.json').read_text('utf8')) == expected
    assert 'Exit code: 7' in result.stdout


@pytest.mark.skipif(os.name != 'nt', reason='Windows BAT entry points')
def test_batch_refuses_demo_flag_instead_of_operating_hardware(tmp_path):
    env = os.environ | {'A7M4_PYTHON': sys.executable, 'A7M4_NO_PAUSE': '1', 'A7M4_DEMO': '1'}
    result = subprocess.run(['cmd.exe', '/d', '/c', str(ROOT / 'advanced/一键救砖_从SD卡恢复.bat')],
                            capture_output=True, encoding='utf8', env=env, timeout=30)
    assert result.returncode == 2
    assert 'Recovery does not use A7M4_DEMO' in result.stdout
