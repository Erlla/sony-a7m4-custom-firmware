from state_io import read_json as read, atomic_json as atomic
from product_integrity import pinned, state_path
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import uuid
TOOL_VERSION = '1.00'
PATCH_SET = 'm4-updater-four-gates/1'

def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def local_under(root, relative):
    require(isinstance(relative, str) and relative and ('\\' not in relative) and (':' not in relative) and (not relative.startswith('/')) and all((p not in ('', '.', '..') for p in relative.split('/'))), 'Invalid local relative path')
    path = Path(root) / relative
    require(path.resolve().is_relative_to(Path(root).resolve()), 'Path escapes local root')
    for item in (path, *path.parents):
        if item.exists():
            require(not getattr(item.lstat(), 'st_file_attributes', 0) & 1024, 'Reparse path is not accepted for this tool')
        if item == Path(root):
            break
    return path

@contextmanager
def single_instance(private):
    """A held byte-range lock releases on process death; stale files are harmless."""
    import msvcrt
    private = Path(private)
    private.mkdir(parents=True, exist_ok=True)
    handle = (private / 'tool.lock').open('a+b')
    try:
        if handle.seek(0, 2) == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise RuntimeError('已有一个补丁工具正在运行，请等待它完成。') from error
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        handle.close()
PHASES = {'PREPARING', 'PREFLIGHT', 'BINDING', 'BOUND', 'READING', 'BUILDING', 'PATCHING', 'VERIFYING', 'RESTORING', 'WAITING_FOR_RESTART', 'WAITING_FOR_NORMAL', 'COMPLETE', 'STOPPED', 'REVIEW_REQUIRED', 'SUPERSEDED'}
SAFE_TO_START_FRESH = {'COMPLETE', 'STOPPED', 'PREPARING', 'PREFLIGHT', 'SUPERSEDED'}
SUCCESS = {'PATCH_AND_FULL_READBACK_VERIFIED', 'ALREADY_PATCHED_NO_WRITE'}
