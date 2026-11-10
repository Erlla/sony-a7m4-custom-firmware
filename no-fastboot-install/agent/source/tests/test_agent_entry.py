"""Packaged native entry checks; no doctor/probe, elevation or camera commands."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, required=True)
    root = parser.parse_args().package.resolve()
    env = os.environ.copy()
    env['PATH'] = str(root/'no-installed-tools')
    for key in list(env):
        if key.upper().startswith(('M4_', 'PYTHON')): env.pop(key)
    # A copy owned by run_offline.py is required; never change a delivery package.
    if not root.parent.name.startswith('m4-package-check-'):
        raise ValueError('Use tests/run_offline.py with its disposable package copy')
    rows = []

    def run(args, code, status):
        result = subprocess.run([str(root/'M4相机工具.exe'), '--agent', *args],
                                capture_output=True, encoding='utf-8-sig', timeout=40, env=env)
        value = json.loads(result.stdout)
        assert result.returncode == code, result
        assert value['status'] == status, value
        assert 'traceback' not in json.dumps(value).lower(), value
        rows.append(dict(arguments=args, status=status, passed=True))
        return value

    run(['status'], 0, 'NO_TASK')
    run(['status', 'a'*32], 1, 'COMMAND_REJECTED')
    run(['status', 'a'*32, '--watch'], 1, 'COMMAND_REJECTED')
    run(['start', 'a'*32, 'b'*32], 1, 'COMMAND_REJECTED')
    run(['resume', 'a'*32, 'b'*32, 'usb-replugged'], 1, 'COMMAND_REJECTED')
    for args in (['invalid'], ['start'], ['resume', 'a'*32, 'b'*32],
                 ['doctor', 'a'*32], ['status', '..'], ['status', 'a'*32, 'b'*32]):
        run(args, 1, 'LAUNCH_REJECTED')
    # Exercise the real verified entry and JSONL flushing, with an inert job.
    job = 'c' * 32
    status_path = root/'state/agent/jobs'/job/'status.json'
    status_path.parent.mkdir(parents=True)
    build_id = json.loads((root/'app/release.json').read_text('utf-8'))['agent_build_id']
    value = dict(schema='m4-agent/1', build_id=build_id, job=job,
                 status='RUNNING', phase='OFFLINE_FIXTURE', pending=None)
    status_path.write_text(json.dumps(value), 'utf-8')
    monitor = subprocess.Popen([str(root/'M4相机工具.exe'), '--agent', 'status', job, '--watch'],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               encoding='utf-8-sig', env=env)
    try:
        started = time.monotonic()
        first = json.loads(monitor.stdout.readline())
        assert first['status'] == 'RUNNING', first
        value.update(status='WAITING_USER', pending=dict(id='d'*32, kind='write',
                     message='Offline fixture only', answers=['approve-write']))
        temporary = status_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(value), 'utf-8'); temporary.replace(status_path)
        rest, errors = monitor.communicate(timeout=12)
        last = json.loads(rest.splitlines()[-1])
        assert monitor.returncode == 0 and last['status'] == 'WAITING_USER', (last, errors)
        assert last['pending']['id'] == 'd'*32
        rows.append(dict(arguments=['status', job, '--watch'], passed=True,
                         states=[first['status'], last['status']], seconds=time.monotonic()-started))
    finally:
        if monitor.poll() is None: monitor.kill(); monitor.wait(timeout=5)
        status_path.unlink()
    path = root/'app/agent_api.py'; original = path.read_bytes()
    try:
        path.write_bytes(original + b'\n# offline tamper fixture\n')
        run(['status'], 1, 'LAUNCH_REJECTED')
        run(['status', 'a'*32, '--watch'], 1, 'LAUNCH_REJECTED')
    finally:
        path.write_bytes(original)
    run(['status'], 0, 'NO_TASK')
    print(json.dumps(dict(passed=True, tests=rows, device_operations=0,
                          system_authorizations=0, installed_python_git_required=False)))


if __name__ == '__main__': main()
