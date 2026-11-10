from product_integrity import pinned, state_path
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import argparse
import hashlib
import importlib
import json
import math
import os
import struct
import sys
import time
import uuid
CASE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
P1_SHA = None
P1_BYTES, CHUNK_BYTES, CHUNKS = (25100288, 32768, 766)
READ_FRAME = struct.Struct('<8s16s11q32s32s')
READ_FIELDS = ('version', 'phase', 'error', 'euid', 'pid', 'ppid', 'loader_pid', 'cleanup', 'bytes', 'chunks', 'flags')

def require(value, message):
    if not value:
        raise ValueError(message)

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def read(path):
    return json.loads(Path(path).read_text('utf-8-sig'))

def decode_reader(raw, nonce):
    require(len(raw) == READ_FRAME.size, 'Incomplete full-reader frame')
    magic, actual, *values = READ_FRAME.unpack(raw)
    require(magic == b'M4P1RD01' and actual.hex() == nonce, 'Wrong full-reader nonce')
    result = dict(zip(READ_FIELDS, values[:11]))
    result.update(first_sha256=values[11].hex(), second_sha256=values[12].hex())
    require(result['version'] == 1, 'Wrong full-reader ABI')
    return result

def verify_full_read(folder, reader, expected_sha=P1_SHA):
    """Check actual saved bytes and all 766 chunks against the native read."""
    folder = Path(folder)
    proof = read(folder / 'run.json')
    require(proof.get('verdict') == 'P1_READBACK_VERIFIED' and proof.get('nonce') == reader['nonce'] and (proof.get('sha256') == expected_sha) and (proof.get('bytes') == P1_BYTES) and (proof.get('chunks') == CHUNKS) and (proof.get('ram_chunks_cleaned') is True) and (proof.get('block_writes') is False) and (proof.get('module_uploads') == 1) and (proof.get('start_attempts') == 1) and (proof.get('ack_attempts') == 1), 'Actual independent full read is incomplete')
    rows = {name: decode_reader((folder / (name + '.bin')).read_bytes(), reader['nonce']) for name in ('ready', 'result', 'cleaned')}
    ready, final, cleaned = (rows[name] for name in ('ready', 'result', 'cleaned'))
    require(ready['phase'] == 1 and ready['error'] == 0 and (ready['flags'] == 3) and (ready['euid'] == 0) and (ready['ppid'] == 1) and (ready['cleanup'] == 0) and (ready['pid'] > 1) and (ready['loader_pid'] > 1) and (ready['pid'] != ready['loader_pid']), 'Reader ready identity differs')
    require(final == proof['native'] and final['phase'] == 4 and (final['error'] == 0) and (final['flags'] == 127) and (final['bytes'] == P1_BYTES) and (final['chunks'] == CHUNKS) and (final['first_sha256'] == final['second_sha256'] == expected_sha), 'Reader double-source digest differs')
    require(cleaned == dict(final, phase=5) and all((row[k] == ready[k] for row in (final, cleaned) for k in ('euid', 'pid', 'ppid', 'loader_pid', 'cleanup'))), 'Reader cleanup/identity differs')
    path = folder / 'nflasha1.bin'
    require(path.stat().st_size == P1_BYTES and sha(path) == expected_sha, 'Actual full p1 differs from expected digest')
    digests = (folder / 'digests.bin').read_bytes()
    require(len(digests) == CHUNKS * 32, 'Wrong chunk digest extent')
    with path.open('rb') as stream:
        for index in range(CHUNKS):
            chunk = stream.read(min(CHUNK_BYTES, P1_BYTES - index * CHUNK_BYTES))
            require(hashlib.sha256(chunk).digest() == digests[index * 32:(index + 1) * 32], 'Saved p1 chunk differs')
        require(stream.read(1) == b'', 'Extra p1 bytes')
    return {str(folder / name): sha(folder / name) for name in ('run.json', 'ready.bin', 'result.bin', 'cleaned.bin', 'digests.bin', 'nflasha1.bin')}
