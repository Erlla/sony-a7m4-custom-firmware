"""Unified packaging assigns the release label; tests never build or flash."""
import sys

import pytest

from a7m4 import firmware


@pytest.mark.parametrize("release", [None, "9.99"])
def test_package_release_must_be_explicit(monkeypatch, capsys, release):
    argv = ["a7m4.firmware", "build-fl23"]
    for name in ("official", "components", "public-key", "private-key", "output", "fx2-cc1", "fx2-block13"):
        argv += ["--" + name, "synthetic-" + name]
    if release is not None:
        argv += ["--version", release]
    received = []
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(firmware, "build", received.append)
    if release is None:
        with pytest.raises(SystemExit) as exc:
            firmware.main()
        assert exc.value.code == 2
        assert "--version" in capsys.readouterr().err
        assert received == []
    else:
        firmware.main()
        assert len(received) == 1
        assert received[0].version == release
