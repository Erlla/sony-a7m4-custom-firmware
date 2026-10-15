from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


class ToolError(Exception):
    def __init__(self, code, message, hint=""):
        super().__init__(message)
        self.code, self.hint = code, hint


def require(condition, code, message, hint=""):
    if not condition:
        raise ToolError(code, message, hint)


def sha256(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def root_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def data_dir():
    base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    return base / "A7M4Toolkit"


def run(args, *, cwd=None, timeout=300, stdin=None, stdout=None):
    # No shell; filenames are arguments, never executable command text.
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        result = subprocess.run([str(a) for a in args], cwd=cwd, stdin=stdin,
                                stdout=stdout or subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=timeout,
                                creationflags=flags)
    except subprocess.TimeoutExpired as e:
        raise ToolError("TIMEOUT", "Operation timed out", "Check cables and power; reconnect and create a new backup before retrying.") from e
    except OSError as e:
        raise ToolError("EXEC_FAILED", str(e), "Check the offline resource pack.") from e
    out = (result.stdout or b"") + (result.stderr or b"")
    require(result.returncode == 0, "COMMAND_FAILED", out.decode("utf-8", "replace")[-6000:])
    return out


class Assets:
    def __init__(self, base=None):
        self.base = Path(base or root_dir() / "vendor")

    def get(self, relative):
        manifest_path = self.base / "manifest.local.json"
        require(manifest_path.is_file(), "ASSETS_MISSING", "Offline resource manifest is missing", "Run tools/import_local_resources.py or install a complete local build.")
        manifest = read_json(manifest_path)
        expected = manifest.get("files", {}).get(relative)
        path = (self.base / "local" / relative).resolve()
        require(path.is_relative_to((self.base / "local").resolve()), "PATH", "Invalid resource path")
        require(expected and path.is_file() and sha256(path) == expected["sha256"], "ASSET_INTEGRITY", f"Missing or modified resource: {relative}")
        return path

    def check(self):
        manifest = read_json(self.base / "manifest.local.json") if (self.base / "manifest.local.json").exists() else {"files": {}}
        errors = []
        required = ["bin/fastboot.exe", "bin/fastboot.bin", "bin/uart_boot.ino.uf2", "driver/android_winusb.inf", "squashfs/sqfs2tar.exe", "squashfs/tar2sqfs.exe"]
        for name in set(required) | set(manifest["files"]):
            try:
                self.get(name)
            except ToolError as e:
                errors.append(str(e))
        return {"ready": not errors, "errors": errors, "distribution": manifest.get("distribution", "missing")}


def event(callback, phase, **values):
    if callback:
        callback({"type": "progress", "phase": phase, "time": time.time(), **values})
