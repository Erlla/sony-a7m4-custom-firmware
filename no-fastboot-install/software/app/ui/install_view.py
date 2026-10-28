from operation_session import operation_path
from state_io import read_json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
from product_integrity import pinned, state_path
from pathlib import Path
import json
import re
import time
import tkinter as tk
from tkinter import filedialog, messagebox
CASE = Path(__file__).resolve().parent
FLOW = CASE.parent / 'workflow'
PRIVATE = operation_path('workflow')
DONE = {'COMPLETE', 'CANCELLED_BEFORE_DEVICE', 'NO_FLOW'}

def snapshot():
    try:
        pointer = PRIVATE / 'flow.json'
        if not pointer.exists():
            if (PRIVATE / 'flows').exists() and any((PRIVATE / 'flows').iterdir()):
                return dict(phase='REVIEW_REQUIRED', error='流程索引缺失')
            return dict(phase='NO_FLOW')
        name = read_json(pointer)['flow']
        if not re.fullmatch('[0-9a-f]{32}', name):
            raise ValueError('流程编号无效')
        state = read_json(PRIVATE / 'flows' / name / 'flow.json')
        if state.get('flow') != name or state.get('schema') != 'm4-user-flow/1':
            raise ValueError('流程状态无效')
        state['folder'] = str(PRIVATE / 'flows' / name)
        if state['phase'] == 'AWAITING_MENU_OBSERVATION':
            native = read_json(Path(state['folder']) / 'status.json')
            from datetime import datetime, timezone
            start = native['window_start_bound']
            wall = (datetime.now(timezone.utc) - datetime.fromisoformat(start['utc'])).total_seconds()
            mono = time.monotonic() - start['monotonic']
            state['remaining'] = max(0, int(600 - max(wall, mono, native.get('window_elapsed_floor', 0)))) if min(wall, mono) >= 0 and abs(wall - mono) <= 5 else 0
        return state
    except (OSError, ValueError, KeyError, TypeError) as error:
        return dict(phase='REVIEW_REQUIRED', error=str(error))
