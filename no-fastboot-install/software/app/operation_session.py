"""A new operation workspace per GUI launch; history is never resumed on startup."""
from datetime import datetime, timezone
from pathlib import Path
import os
import re
import uuid

from state_io import atomic_json

ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT = 'M4_TOOL_SESSION'


def operation_path(*parts):
    name = os.environ.get(ENVIRONMENT)
    base = ROOT / 'state'
    if name is not None:
        if re.fullmatch('[0-9a-f]{32}', name) is None:
            raise ValueError('本次会话编号无效，请重新打开软件')
        base = base / 'sessions' / name
    return base.joinpath(*parts)


def new_session():
    name = uuid.uuid4().hex
    os.environ[ENVIRONMENT] = name
    folder = operation_path()
    folder.mkdir(parents=True, exist_ok=False)
    atomic_json(folder / 'session.json', dict(schema='m4-operation-session/1', session=name,
                created_utc=datetime.now(timezone.utc).isoformat(), pid=os.getpid(), ui_version='1.00'))
    return folder


def ensure_session():
    if ENVIRONMENT not in os.environ:
        return new_session()
    folder = operation_path()
    if not (folder / 'session.json').is_file():
        raise ValueError('本次会话不存在，请重新打开软件')
    return folder
