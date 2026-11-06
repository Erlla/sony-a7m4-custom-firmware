import sys
from types import SimpleNamespace

import pytest

from a7m4 import cli, hardware


@pytest.mark.parametrize('command', ['enter', 'exit', 'reboot'])
def test_standalone_entry_does_not_backup_or_flash(monkeypatch, capsys, command):
    calls = []
    engine = SimpleNamespace(transport=object(), assets=object(), callback=None,
                             reboot=lambda: calls.append('reboot') or {'state': 'disconnected'})
    monkeypatch.setattr(cli, 'Engine', lambda **kw: engine)
    monkeypatch.setattr(hardware, 'enter_fastboot', lambda transport, assets, callback:
                        calls.append('enter') or {'product': 'ILCE-7M4'})
    monkeypatch.setattr(sys, 'argv', ['a7m4', command])
    monkeypatch.setattr(sys, 'stdin', SimpleNamespace(reconfigure=lambda **kw: None))
    cli.main()
    assert calls == ['enter' if command == 'enter' else 'reboot']
    assert capsys.readouterr().out
