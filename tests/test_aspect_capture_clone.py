"""Input boundaries and composition contracts for the capture-copy component."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
from a7m4 import aspect_capture_clone as p
from a7m4 import awb_priority


def test_unknown_input_is_rejected_before_compiler():
    with pytest.raises(ValueError, match='Unsupported CP input'):
        p.compose(b'unknown', Path('missing-compiler'))


def test_published_sources_match_the_recipe():
    for name, expected in p.LAYOUT['sources'].items():
        p.check_hash((p.NATIVE / name).read_bytes(), expected, name)


def test_optional_awb_and_clone_orders_converge():
    awb = awb_priority.load_profile()['identities']
    identities = p.LAYOUT['identities']
    base = next(sha for sha, v in identities.items() if not v['AWB_priority_applied'])
    with_awb = awb[base]['output_sha256']
    assert identities[with_awb]['AWB_priority_applied']
    assert awb[identities[base]['output_sha256']]['output_sha256'] == identities[with_awb]['output_sha256']


def test_lut_current_cp_follows_clone_component():
    lut = json.loads((p.ROOT/'methods/08-custom-lut/reference-layout.json').read_text('utf8'))
    current = next(row for row in lut['components'] if row['component'] == 'CP')
    assert current['sha256'] in {v['output_sha256'] for v in p.LAYOUT['identities'].values()}
    assert lut['aspect_capture_clone']['recipe'] == '../../native/aspect-capture-clone/layout.json'


def test_existing_output_is_preserved(tmp_path):
    output = tmp_path/'component.bin'; output.write_bytes(b'keep')
    run = subprocess.run([sys.executable, '-B', '-m', 'a7m4.aspect_capture_clone',
        '--input', 'missing-input', '--compiler', 'missing-compiler', '--output', str(output)],
        cwd=p.ROOT, capture_output=True)
    assert run.returncode != 0 and b'Output exists' in run.stderr
    assert output.read_bytes() == b'keep'


def test_optimized_python_is_rejected():
    run = subprocess.run([sys.executable, '-O', '-B', '-c', 'import a7m4.aspect_capture_clone'],
                         cwd=p.ROOT, capture_output=True)
    assert run.returncode != 0 and b'binary invariant checks are required' in run.stderr
