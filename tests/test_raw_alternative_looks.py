"""Boundaries and composition contracts of the RAW alternative-look layer."""
import json
from pathlib import Path
import subprocess
import sys

import pytest
from a7m4 import raw_alternative_looks as raw
from a7m4 import aspect_capture_clone, awb_priority


def test_unknown_input_rejected_before_compiler():
    with pytest.raises(ValueError, match='Unsupported CP input'):
        raw.compose(b'unknown component', Path('missing-compiler'))


def test_sources_are_the_pinned_native_implementation():
    for name, expected in raw.LAYOUT['sources'].items():
        raw.check_hash((raw.NATIVE/name).read_bytes(), expected, name)


def test_current_clone_awb_raw_component_chain():
    lut = json.loads((raw.ROOT/'methods/08-custom-lut/reference-layout.json').read_text('utf8'))
    cp = next(x['sha256'] for x in lut['components'] if x['component'] == 'CP')
    assert cp in {x['output_sha256'] for x in aspect_capture_clone.LAYOUT['identities'].values()}
    after_awb = awb_priority.load_profile()['identities'][cp]['output_sha256']
    identity = raw.LAYOUT['identities'][after_awb]
    assert lut['raw_alternative_looks']['input_sha256'] == after_awb
    assert lut['raw_alternative_looks']['output_sha256'] == identity['output_sha256']
    assert lut['raw_alternative_looks']['recipe'] == '../../native/raw-alternative-looks/layout.json'


def test_native_patch_regions_do_not_overlap():
    spans = sorted((int(p['VA'], 0), int(p['VA'], 0)+len(bytes.fromhex(p['before'])))
                   for p in raw.LAYOUT['patches'])
    assert all(a[1] <= b[0] for a,b in zip(spans, spans[1:]))
    assert sum(end-start for start,end in spans) == 128
    assert raw.LAYOUT['sr2']['output_bytes']-raw.LAYOUT['sr2']['input_bytes'] == 2*raw.LAYOUT['sr2']['child_stride']


def test_existing_output_is_not_overwritten(tmp_path):
    output = tmp_path/'component.bin'
    output.write_bytes(b'keep')
    result = subprocess.run([sys.executable, '-B', '-m', 'a7m4.raw_alternative_looks',
        '--input', 'missing-input', '--compiler', 'missing-compiler', '--output', str(output)],
        cwd=raw.ROOT, capture_output=True)
    assert result.returncode != 0 and b'Output exists' in result.stderr
    assert output.read_bytes() == b'keep'


def test_python_optimization_is_rejected():
    result = subprocess.run([sys.executable, '-O', '-B', '-c', 'import a7m4.raw_alternative_looks'],
                            cwd=raw.ROOT, capture_output=True)
    assert result.returncode != 0 and b'binary invariant checks are required' in result.stderr
