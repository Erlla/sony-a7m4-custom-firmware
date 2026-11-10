from product_integrity import pinned, state_path
from datetime import datetime, timezone
from pathlib import Path
import argparse
import ast
import errno
import importlib.util
import json
import struct
import sys
import time
from common import file_sha, local_path, require, save_json
HARDWARE_TEST_REVIEWED = False
LAUNCH = struct.Struct('<8s16s10q')
MISSING_STATUS = 268435462

class ProtocolError(RuntimeError):
    pass

class NativeDeadline(TimeoutError):
    pass

class TransportDisconnected(ConnectionError):
    pass

class TransportTimeout(TimeoutError):
    pass

def transport_call(method, *args):
    """Classify only errors from transport calls, without importing USB."""
    try:
        return method(*args)
    except OSError as error:
        code = getattr(error, 'backend_error_code', None)
        if error.errno == errno.ENODEV or getattr(error, 'winerror', None) == 1167 or code == -4:
            raise TransportDisconnected(str(error)) from error
        if isinstance(error, TimeoutError) or error.errno == errno.ETIMEDOUT or code == -7:
            raise TransportTimeout(str(error)) from error
        raise
