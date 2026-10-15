import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from a7m4.common import ToolError
from a7m4.maintenance import run_maintenance
from a7m4.demo import DemoTransport
from a7m4.engine import Engine

@pytest.fixture
def engine(tmp_path):
    return Engine(transport=DemoTransport(), home=tmp_path / "console")


def test_maintenance_preselected_action_waits_for_full_backup(engine):
    prompts = []
    def read(prompt):
        prompts.append(prompt)
        assert engine.state == "ready"
        assert len(engine.manifest["partitions"]) == 17
        assert engine.manifest["complete"]
        if "New version" in prompt:
            return "6.03"
        return prompt.splitlines()[-2]  # Exact plan-bound confirmation.
    result = run_maintenance(engine, action="set_version", destination=engine.home / "backups",
                         enter=False, read=read, write=lambda _: None)
    assert len(prompts) == 2
    assert result["last_result"]["status"] == "verified"
    assert engine.transport.writes == ["nflasha2"]
    assert engine.state == "disconnected" and not engine.plans


@pytest.mark.parametrize("action", ["menu", "unlock", "set_version", "restore", "restore_official"])
def test_maintenance_backup_failure_never_reaches_action_or_menu(engine, action):
    engine.transport.fail_partition = "nflasha2"
    output = []
    with pytest.raises(ToolError, match="Injected read failure"):
        run_maintenance(engine, action=action, destination=engine.home / "backups", enter=False,
                    read=lambda _: pytest.fail("Action prompt reached without full backup"), write=output.append)
    assert not engine.transport.writes
    assert not any("Step 2" in line for line in output)
    assert engine.state == "disconnected"


@pytest.mark.parametrize("answer", ["", "yes", "FLASH nflasha2 wronghash"])
def test_maintenance_requires_exact_confirmation(engine, answer):
    replies = iter(["6.03", answer])
    run_maintenance(engine, action="set_version", destination=engine.home / "backups", enter=False,
                read=lambda _: next(replies), write=lambda _: None)
    assert not engine.transport.writes


def test_maintenance_menu_reuses_one_backup_for_multiple_actions(engine):
    replies = iter(["2", "6.03", "3", "", "nflasha2", "0"])
    output = []
    def read(prompt):
        if "Type exactly" in prompt:
            return prompt.splitlines()[-2]
        return next(replies)
    result = run_maintenance(engine, destination=engine.home / "backups", enter=False, read=read, write=output.append)
    assert result["last_result"]["status"] == "verified"
    assert engine.transport.writes == ["nflasha2", "nflasha2"]
    assert len(list((engine.home / "backups").glob("*/manifest.json"))) == 1
    assert sum("Full backup verified:" in line for line in output) == 1


@pytest.mark.skipif(os.name != "nt", reason="Windows batch entry points")
def test_batch_version_workflow_in_demo(tmp_path):
    # Exercise the actual localized BAT path, launcher, quoting and exit code.
    root = Path(__file__).resolve().parents[1]
    env = os.environ | {"A7M4_DEMO": "1", "A7M4_NO_PAUSE": "1", "A7M4_PYTHON": sys.executable}
    destination = tmp_path / "with spaces & 中文"
    result = subprocess.run(["cmd.exe", "/d", "/c", str(root / "advanced" / "查看或设置固件版本.bat")],
                            input=str(destination)+"\n\n", capture_output=True, encoding="utf-8", env=env, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Full backup verified:" in result.stdout and '"version": "6.02"' in result.stdout
    manifests = list(destination.glob("*/manifest.json"))
    assert len(manifests) == 1 and json.loads(manifests[0].read_text())["complete"]
