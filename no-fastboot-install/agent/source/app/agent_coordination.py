"""Agent lifecycle guard, shared with GUI operations under request_guard()."""
from contextlib import contextmanager
from pathlib import Path
import os
from state_io import read_json, atomic_json

_owner = None


def registry():
    from recovery_registry import recovery_root
    return recovery_root() / 'agent-active.json'


def current():
    path = registry()
    return read_json(path) if path.exists() else None


def check(allow_desktop=False):
    value = current()
    if allow_desktop and value and value.get('client') == 'desktop': return
    if value and not value.get('closed') and value.get('job') != _owner:
        raise RuntimeError('AI Agent 任务尚未结束，请在原工具目录查询原任务；不要重复写入。')


@contextmanager
def owner(job):
    global _owner
    previous = _owner; _owner = job
    try: yield
    finally: _owner = previous


def claim(job, source):
    check()
    atomic_json(registry(), dict(schema='m4-agent-owner/1', job=job,
                                source=str(Path(source).resolve()), closed=False))


def close(job):
    value = current()
    if value and value['job'] == job:
        atomic_json(registry(), dict(value, closed=True))


@contextmanager
def desktop_guard():
    """Hold lifecycle ownership between GUI actions as well as during a USB call."""
    if _owner is not None:
        check(); yield; return
    name = os.environ.get('M4_TOOL_SESSION')
    if not name:
        # Older/internal calls still use request_guard; do not invent a session.
        check(); yield; return
    with owner(name):
        check(allow_desktop=True)
        from data_paths import data_root
        from product_integrity import ROOT
        source = Path(os.environ.get('M4_TOOL_SOURCE_ROOT', data_root(ROOT).parent))
        atomic_json(registry(), dict(schema='m4-agent-owner/1', job=name, source=str(source),
                                    client='desktop', closed=False))
        try: yield
        finally:
            try:
                import wizard
                value = wizard.load()
                if value['phase'] in ('NO_FLOW', 'COMPLETE', 'CANCELLED_BEFORE_DEVICE', 'READ_REJECTED_COMPLETE'):
                    close(name)
            except Exception:
                pass
