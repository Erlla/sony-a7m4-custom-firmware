"""Input/output safety for the exact-image JPEG metadata component builder."""
import os
import subprocess
import sys
from pathlib import Path
import pytest
from a7m4 import jpeg_exif_dimensions as j


def test_wrong_mpr_rejected_before_compiler_access():
    with pytest.raises(ValueError, match='libmpr input: SHA-256 mismatch'):
        j.compose(b'unsupported stock or modified DSO', Path('missing-zig.exe'))


def test_sources_match_the_reviewed_recipe():
    for name, sha in j.LAYOUT['sources'].items():
        j.check_hash((j.NATIVE / name).read_bytes(), sha, name)


def test_cli_refuses_existing_output_before_reading_input(tmp_path):
    output=tmp_path/'libmpr.so';output.write_bytes(b'keep')
    result=subprocess.run([sys.executable,'-B','-m','a7m4.jpeg_exif_dimensions','--input','missing-input',
        '--zig','missing-zig','--output',str(output)],cwd=j.ROOT,capture_output=True,text=True)
    assert result.returncode!=0 and 'Output exists' in result.stderr
    assert output.read_bytes()==b'keep'


def test_optimized_python_rejected():
    result=subprocess.run([sys.executable,'-O','-B','-c','import a7m4.jpeg_exif_dimensions'],
        cwd=j.ROOT,env=os.environ.copy(),capture_output=True,text=True)
    assert result.returncode!=0 and 'binary invariant checks are required' in result.stderr
