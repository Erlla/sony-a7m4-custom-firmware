"""Publication input guards for the exact custom-ratio playback components."""
import subprocess
import sys
from pathlib import Path

import pytest
from a7m4 import aspect_playback as p


@pytest.mark.parametrize('component', ['ap', 'mpr'])
def test_unknown_input_rejected_before_compiler(component):
    with pytest.raises(ValueError, match=component + ' input: SHA-256 mismatch'):
        p.compose(b'unsupported component', Path('missing-compiler'), component)


def test_published_sources_match_the_recipe():
    for profile in p.LAYOUT['components'].values():
        for name, sha in profile['sources'].items():
            p.check_hash((p.NATIVE / name).read_bytes(), sha, name)


@pytest.mark.parametrize('component', ['ap', 'mpr'])
def test_existing_output_is_preserved(tmp_path, component):
    target = tmp_path / 'component.so'
    target.write_bytes(b'keep')
    result = subprocess.run([sys.executable, '-B', '-m', 'a7m4.aspect_playback',
        '--component', component, '--input', 'missing-input', '--zig', 'missing-compiler',
        '--output', str(target)], cwd=p.ROOT, capture_output=True)
    assert result.returncode != 0 and b'Output exists' in result.stderr
    assert target.read_bytes() == b'keep'


def test_optimized_python_is_rejected():
    result = subprocess.run([sys.executable, '-O', '-B', '-c',
                             'import a7m4.aspect_playback'],
                            cwd=p.ROOT, capture_output=True)
    assert result.returncode != 0 and b'binary invariant checks are required' in result.stderr
