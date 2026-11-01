"""Writable data is kept outside the native verified runtime snapshot."""
from pathlib import Path
import os


def data_root(program_root):
    value=os.environ.get('M4_TOOL_DATA_ROOT')
    if value:
        path=Path(value)
        if not path.is_absolute(): raise ValueError('工具数据目录必须是绝对路径')
        return path.resolve()
    return Path(program_root)/'state'
