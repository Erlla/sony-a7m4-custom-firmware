from product_integrity import pinned, state_path
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import queue
import subprocess
import sys
import threading
import uuid
import gui_model as model
CASE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
DELIVERY = ROOT / 'app/ui'
CORE = ROOT / 'app/maintenance'
FAST_CORE = ROOT / 'app/maintenance_custom'
FAST_CASE = ROOT / 'app/receiver_custom'
INSTALL_CASE = ROOT / 'app/workflow'
LEGACY_RUNNER_SHA = '9164db8aaf334c91d935fee333c2be7ed5d8a2e7edac5b654ef25326769b3831'
PRIVATE = ROOT / 'state/ui'
CORE_SHA = 'a1dd5358d89fe321671d9fb76507cbfde590dfb89120d16ce2b888096cd7fe1d'
PYTHON = Path(sys.executable).with_name('python.exe')
ALLOWED = {'simple-start', 'simple-continue', 'simple-installed', 'simple-failure', 'simple-recover-usb', 'flow-setup'}

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def read(path):
    return json.loads(Path(path).read_text('utf-8-sig'))

def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)

def verify_release():
    from product_integrity import verify_release as verify
    return verify()

def state_snapshot():
    """Display-only snapshot. All operation authorization remains in the CLI."""
    base = ROOT / 'state/maintenance'
    if (ROOT / 'state/workflow/patch/current.json').exists():
        base = ROOT / 'state/workflow/patch'
    if not (base / 'current.json').exists():
        return dict(phase='NO_RUN')
    try:
        run = read(base / 'current.json')['run']
        import re
        if not re.fullmatch('[0-9]{8}T[0-9]{6}_[0-9a-f]{32}', run):
            raise ValueError('任务编号无效')
        return read(base / 'control' / (run + '.json'))
    except (OSError, ValueError, KeyError, TypeError) as error:
        return dict(phase='REVIEW_REQUIRED', error=str(error))

class Jobs:

    def __init__(self, events=None, private=None, executor=None, validate=True):
        self.events = events or queue.Queue()
        self.private = PRIVATE if private is None else Path(private)
        self.executor = executor or self._execute
        self.validate = validate
        self.busy = False
        self.thread = None
        self._guard = threading.Lock()
        self.process = None
        self.cancel_pending = False

    def start(self, action, arguments=None, source=None, output=False):
        if action not in ALLOWED:
            raise ValueError('未支持的操作')
        with self._guard:
            if self.busy:
                raise RuntimeError('已有任务正在运行')
            self.busy = True
        try:
            self.thread = threading.Thread(target=self._work, args=(action, list(arguments or []), source, output), daemon=True)
            self.thread.start()
        except BaseException:
            with self._guard:
                self.busy = False
            raise

    def _work(self, action, arguments, source, output):
        receipt, folder = (None, None)
        try:
            if self.validate:
                verify_release()
            name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_') + uuid.uuid4().hex[:12]
            folder = self.private / 'tasks' / name
            folder.mkdir(parents=True, exist_ok=False)
            receipt = dict(schema='m4-desktop-task/1', action=action, phase='RUNNING', created_utc=datetime.now(timezone.utc).isoformat(), pid=os.getpid())
            atomic(folder / 'receipt.json', receipt)
            self.events.put(('started', dict(action=action, folder=str(folder))))
            if source is not None:
                self.events.put(('line', '正在计算所选文件的完整 SHA-256…'))
                fingerprint = model.fingerprint(source)
                receipt['source'] = fingerprint['path']
                receipt['fingerprint'] = fingerprint
                self.events.put(('fingerprint', fingerprint))
                arguments += ['--source', fingerprint['path'], '--sha256', fingerprint['sha256']]
            if output:
                destination = self.private / 'outputs' / (name + '_' + action)
                destination.parent.mkdir(parents=True, exist_ok=True)
                arguments += ['--output', str(destination)]
                receipt['output'] = str(destination)
            receipt['arguments'] = arguments
            atomic(folder / 'receipt.json', receipt)
            code, text = self.executor(action, arguments, folder)
            payload = model.final_payload(text)
            state, summary = model.classify(action, code, payload)
            receipt.update(phase=state.upper(), summary=summary, returncode=code, result=payload, finished_utc=datetime.now(timezone.utc).isoformat())
            if action in model.DEVICE_ACTIONS and isinstance(payload.get('source'), str):
                receipt['source'] = payload['source']
            if isinstance(payload.get('preparation'), dict):
                receipt['preparation'] = payload['preparation']
            atomic(folder / 'receipt.json', receipt)
            self.events.put(('finished', receipt))
        except BaseException as error:
            if receipt is not None:
                receipt.update(phase='REVIEW_REQUIRED', summary=str(error), finished_utc=datetime.now(timezone.utc).isoformat())
                try:
                    atomic(folder / 'receipt.json', receipt)
                except OSError:
                    pass
            self.events.put(('error', str(error)))
        finally:
            with self._guard:
                self.busy = False
            self.events.put(('idle', None))

    def _execute(self, action, arguments, folder):
        if action.startswith('simple-') or action == 'flow-setup':
            command = [str(PYTHON), '-I', '-B', '-u', '-X', 'utf8', str(ROOT / 'app/entry.py'), action, *arguments]
        else:
            raise ValueError('不支持的操作')
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        environment = dict(os.environ, PYTHONUTF8='1', PYTHONUNBUFFERED='1')
        tail = deque(maxlen=12000)
        with (folder / 'stdout.log').open('w', encoding='utf-8', newline='\n') as log:
            child = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', bufsize=1, creationflags=flags, env=environment, shell=False)
            with self._guard:
                self.process = child
            log_error = None
            try:
                for line in child.stdout:
                    if log_error is None:
                        try:
                            log.write(line)
                            log.flush()
                        except OSError as error:
                            log_error = error
                    tail.append(line)
                    self.events.put(('line', line.rstrip()))
                    stage = model.offline_stage(line)
                    if stage:
                        self.events.put(('offline_stage', stage))
                    value = model.progress(line)
                    if value:
                        self.events.put(('progress', value))
            finally:
                code = child.wait()
                child.stdout.close()
                with self._guard:
                    self.process = None
            if log_error is not None:
                raise OSError('日志保存失败，子任务已结束，请核对任务记录：' + str(log_error))
        return (code, ''.join(tail))
