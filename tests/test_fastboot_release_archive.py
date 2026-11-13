import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from tools.build_fastboot_release import build


def test_recovery_archive_has_importable_source_and_exact_profile(tmp_path):
    output = tmp_path / 'release.zip'
    build(output)
    root = tmp_path / 'extract'
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        for name in ('一键救砖_从SD卡恢复.bat', '只检查fastboot连接.bat',
                     'advanced/_launch_recovery.cmd', 'a7m4/recover_sd.py',
                     'a7m4/sd_recovery.py', 'a7m4/profiles/sd-recovery.json',
                     'methods/00-sd-recovery/README.md'):
            assert 'A7M4-Fastboot/' + name in names
        archive.extractall(root)
    package = root / 'A7M4-Fastboot'
    for name in ('LICENSE', 'LICENSE-MIT-LEGACY'):
        source_license = Path(__file__).resolve().parents[1] / name
        assert (package / name).read_bytes() == source_license.read_bytes()
    source = Path(__file__).resolve().parents[1] / 'a7m4/profiles/sd-recovery.json'
    assert (package / 'a7m4/profiles/sd-recovery.json').read_bytes() == source.read_bytes()
    result = subprocess.run([sys.executable, '-B', '-c',
                             'from a7m4.recover_sd import main; '
                             'from a7m4.sd_recovery import read_config; '
                             'assert read_config()["product"] == "ILCE-7M4"'],
                            cwd=package, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(os.name != 'nt', reason='Windows BAT entry points')
@pytest.mark.parametrize('name,expected', [('一键救砖_从SD卡恢复.bat', []),
                                          ('只检查fastboot连接.bat', ['--check-connection'])])
def test_root_recovery_wrappers_preserve_dispatch_without_hardware(tmp_path, name, expected):
    output = tmp_path / 'release.zip'
    build(output)
    root = tmp_path / 'copy & 中文'
    with zipfile.ZipFile(output) as archive:
        archive.extractall(root)
    package = root / 'A7M4-Fastboot'
    (package / 'a7m4/recover_sd.py').write_text(
        'import json,sys\nfrom pathlib import Path\n'
        'Path("args.json").write_text(json.dumps(sys.argv[1:]), "utf8")\nraise SystemExit(7)\n', 'utf8')
    env = os.environ | {'A7M4_PYTHON': sys.executable, 'A7M4_NO_PAUSE': '1', 'A7M4_DEMO': '0'}
    result = subprocess.run(['cmd.exe', '/d', '/c', name], cwd=package,
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 7, result.stdout + result.stderr
    assert json.loads((package / 'args.json').read_text('utf8')) == expected
