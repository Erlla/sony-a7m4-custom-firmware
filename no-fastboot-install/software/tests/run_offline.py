"""Run USB source regressions and optional trusted-package checks offline.

No dependency download, driver preparation or camera action is performed.
Package tests always receive a disposable copy, never the supplied package.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET
import shutil

HERE = Path(__file__).resolve().parent
SOFTWARE = HERE.parent
SOURCE_CASES = (
    ('build-assets', 'test_build_assets.py'),
    ('normal-identity', 'test_normal_identity_unit.py'),
    ('operation-session', 'test_operation_session_unit.py'),
    ('state-io', 'test_state_io_unit.py'),
    ('runner', 'test_offline_runner.py'),
)
PACKAGE_CASES = (
    ('native-verify', None, ()),
    ('usb-recovery', 'test_usb_recovery.py', ()),
    ('local-failure', 'test_local_failure.py', ()),
    ('state-io', 'test_state_io.py', ()),
    ('startup-session', 'test_startup_session.py', ()),
    ('usb-identity', 'test_usb_identity.py', ()),
    ('menu-stock', 'test_menu_seal.py', ('--lineage', 'stock')),
    ('menu-user', 'test_menu_seal.py', ('--lineage', 'user')),
)
COPY_DIRS = ('app', 'runtime', 'vendor', 'tools', 'licenses')


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.'+path.name+'.', suffix='.tmp', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def stop_process_tree(child):
    if child.poll() is not None: return
    if os.name == 'nt':
        killer = Path(os.environ['SystemRoot'])/'System32/taskkill.exe'
        try:
            subprocess.run([str(killer), '/PID', str(child.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
        finally:
            if child.poll() is None: child.kill()
    else:
        try: os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError: pass
    child.wait(timeout=15)


def run_process(command, timeout):
    environment = dict(os.environ)
    for name in ('PYTHONPATH', 'PYTHONHOME', 'M4_TOOL_SESSION'):
        environment.pop(name, None)
    started = time.monotonic()
    # A file avoids unbounded in-memory capture when a failing test is noisy.
    with tempfile.TemporaryFile() as output:
        flags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == 'nt' else 0
        child = subprocess.Popen([str(v) for v in command], stdin=subprocess.DEVNULL,
                                 stdout=output, stderr=subprocess.STDOUT, env=environment,
                                 creationflags=flags, start_new_session=os.name != 'nt')
        timed_out = False
        try:
            child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            stop_process_tree(child)
        finally:
            if child.poll() is None: stop_process_tree(child)
        output.seek(0, 2); size = output.tell()
        output.seek(max(0, size - 65536))
        tail = output.read().decode('utf-8', errors='replace')
    return dict(exit_code=child.returncode, timed_out=timed_out, output=tail,
                output_truncated=size > 65536, seconds=time.monotonic()-started)


def unit_worker(case, destination):
    choices = dict(SOURCE_CASES)
    if case not in choices: raise ValueError('Unknown source test case')
    module = load_module('offline_' + case.replace('-', '_'), HERE/choices[case])
    records = []
    class Result(unittest.TextTestResult):
        def addSuccess(self, test):
            super().addSuccess(test); records.append(dict(id=test.id(), status='PASS'))
        def addSkip(self, test, reason):
            super().addSkip(test, reason); records.append(dict(id=test.id(), status='SKIP', reason=reason))
        def addFailure(self, test, error):
            super().addFailure(test, error)
            records.append(dict(id=test.id(), status='FAIL', reason=self._exc_info_to_string(error, test)))
        def addError(self, test, error):
            super().addError(test, error)
            records.append(dict(id=test.id(), status='FAIL', reason=self._exc_info_to_string(error, test)))
        def addSubTest(self, test, subtest, error):
            super().addSubTest(test, subtest, error)
            if error is not None:
                records.append(dict(id=str(subtest), status='FAIL', reason=self._exc_info_to_string(error, test)))
    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    result = unittest.TextTestRunner(verbosity=2, resultclass=Result).run(suite)
    atomic_json(destination, dict(passed=result.wasSuccessful(), tests_run=result.testsRun,
                                 tests=records, skipped=len(result.skipped)))
    return 0 if result.wasSuccessful() else 1


def run_source_case(case, timeout):
    try:
        with tempfile.TemporaryDirectory(prefix='m4-source-check-') as directory:
            result_path = Path(directory)/'result.json'
            result = run_process([sys.executable, '-I', '-B', '-X', 'utf8', __file__,
                                  '--worker', case, '--worker-result', result_path], timeout)
            details = None
            if result_path.exists(): details = json.loads(result_path.read_text('utf-8'))
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as error:
        return dict(id='source.'+case, status='FAIL', reason=str(error))
    passed = (not result['timed_out'] and result['exit_code'] == 0 and
              details is not None and details.get('passed') is True and details.get('tests_run', 0) > 0)
    return dict(id='source.'+case, status='PASS' if passed else 'FAIL',
                details=details, **result)


def package_preflight(package):
    """Use trusted checkout code to read/hash inputs, never import package code."""
    if os.name != 'nt':
        return dict(status='BLOCKED', reason='Windows is required for the packaged integration checks')
    package = Path(package).resolve(strict=True)
    required = ('app/release.json', 'runtime/python/python.exe', 'M4相机工具.exe')
    if not all((package/name).is_file() for name in required):
        return dict(status='BLOCKED', reason='A complete locally built package is required')
    builder = load_module('offline_checked_builder', SOFTWARE/'build.py')
    manifest = json.loads((package/'app/release.json').read_text('utf-8'))
    if manifest.get('schema') != 'm4-clean-product-release/1' or manifest.get('version') != '1.00':
        raise ValueError('Unsupported release manifest')
    for group in COPY_DIRS:
        folder = package/group
        if folder.is_symlink() or getattr(folder, 'is_junction', lambda:False)():
            raise ValueError('Linked package roots are not accepted')
        for path in (package/group).rglob('*'):
            if path.is_symlink() or getattr(path, 'is_junction', lambda:False)():
                raise ValueError('Linked package paths are not accepted')
    files = manifest['files']
    for relative, expected in files.items():
        if (not isinstance(relative, str) or '\\' in relative or ':' in relative or
                '..' in relative.split('/') or relative.split('/')[0] not in COPY_DIRS):
            raise ValueError('Unsafe release path')
        path = package/relative
        if not path.resolve().is_relative_to(package): raise ValueError('Unsafe release path')
        if builder.sha(path) != expected: raise ValueError('Release file differs: '+relative)
    dependencies = json.loads((SOFTWARE/'dependencies.json').read_text('utf-8'))
    for group, lock in dependencies['groups'].items():
        actual = {p.relative_to(package).as_posix():builder.sha(p)
                  for p in (package/group).rglob('*') if p.is_file()}
        if len(actual) != lock['files'] or builder.fingerprint(actual) != lock['tree_sha256']:
            raise ValueError('Runtime asset group differs: '+group)
        if any(files.get(name) != digest for name,digest in actual.items()):
            raise ValueError('Release does not cover locked assets: '+group)
    def app_files(root, ignore_cache=False):
        return {p.relative_to(root).as_posix():builder.sha(p) for p in (root/'app').rglob('*')
                if p.is_file() and p.name != 'release.json' and
                (not ignore_cache or (p.suffix != '.pyc' and '__pycache__' not in p.parts))}
    expected_app = app_files(SOFTWARE, ignore_cache=True)
    if app_files(package) != expected_app:
        raise ValueError('Package app does not match this checkout')
    if any(files.get(name) != digest for name,digest in expected_app.items()):
        raise ValueError('Release does not cover the checkout app')
    return dict(status='PASS', reason='Release files, original dependency locks and checkout app match')


def copy_package(package, target):
    for group in COPY_DIRS:
        shutil.copytree(package/group, target/group)
    shutil.copyfile(package/'M4相机工具.exe', target/'M4相机工具.exe')
    # Deliberately omit state, backups, logs and unrelated root files.


def run_package_cases(package, timeout):
    rows = []
    try:
        checked = package_preflight(package)
    except (OSError, ValueError, KeyError, TypeError) as error:
        checked = dict(status='FAIL', reason=str(error))
    if checked['status'] != 'PASS':
        if checked['status'] == 'FAIL': rows.append(dict(id='package.preflight', **checked))
        rows.extend(dict(id='package.'+name, status='BLOCKED', reason=checked['reason'])
                    for name, _, _ in PACKAGE_CASES)
        return rows
    for name, script, extra in PACKAGE_CASES:
        with tempfile.TemporaryDirectory(prefix='m4-package-check-') as directory:
            disposable = Path(directory)/'package'
            try:
                copy_package(package, disposable)
                copied = package_preflight(disposable)
                if copied['status'] != 'PASS': raise ValueError(copied['reason'])
                command = ([disposable/'M4相机工具.exe', '--verify'] if script is None else
                           [disposable/'runtime/python/python.exe', '-I', '-B', '-X', 'utf8',
                            HERE/script, '--package', disposable, *extra])
                result = run_process(command, timeout)
                passed = result['exit_code'] == 0 and not result['timed_out']
                rows.append(dict(id='package.'+name, status='PASS' if passed else 'FAIL', **result))
            except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
                rows.append(dict(id='package.'+name, status='FAIL', reason=str(error)))
    return rows


def overall_status(rows):
    if any(row['status'] == 'FAIL' for row in rows): return 'FAIL'
    if any(row['status'] == 'BLOCKED' for row in rows): return 'PARTIAL'
    return 'PASS'


def junit(report):
    suite = ET.Element('testsuite', name='m4-usb-offline')
    properties = ET.SubElement(suite, 'properties')
    for name in ('schema', 'scope', 'status', 'camera_validated'):
        ET.SubElement(properties, 'property', name=name, value=str(report.get(name, 'unspecified')))
    failures = skipped = count = 0
    for row in report['checks']:
        tests = (row.get('details') or {}).get('tests') or [dict(id=row['id'], status=row['status'],
                  reason=row.get('reason') or row.get('output', ''))]
        if row['status'] == 'FAIL' and not any(t['status']=='FAIL' for t in tests):
            tests = [*tests, dict(id=row['id']+'.worker', status='FAIL',
                                 reason=row.get('reason') or row.get('output', 'Worker failed'))]
        for test in tests:
            count += 1
            case = ET.SubElement(suite, 'testcase', classname=row['id'], name=test['id'])
            if test['status'] in ('BLOCKED', 'SKIP'):
                skipped += 1
                ET.SubElement(case, 'skipped', message=test['status']).text = test.get('reason', '')
            elif test['status'] == 'FAIL':
                failures += 1
                ET.SubElement(case, 'failure').text = test.get('reason', '')
    suite.set('tests', str(count)); suite.set('failures', str(failures)); suite.set('skipped', str(skipped))
    return ET.tostring(suite, encoding='unicode')


def validate_outputs(paths, package=None):
    resolved = [Path(p).resolve() for p in paths if p is not None]
    if len(resolved) != len(set(resolved)): raise ValueError('Report paths must differ')
    protected = [SOFTWARE/'app', HERE]
    if package is not None: protected.append(Path(package).resolve())
    for path in resolved:
        if any(path.is_relative_to(root) for root in protected):
            raise ValueError('Reports must stay outside app/tests and the supplied package')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--source-only', action='store_true', help='Source checks only; no release validation claim')
    scope.add_argument('--package', type=Path, help='Trusted locally built package; tests run only on copies')
    parser.add_argument('--report', type=Path, help='JSON report outside the supplied package')
    parser.add_argument('--junit', type=Path, help='JUnit XML outside the supplied package')
    parser.add_argument('--timeout', type=float, default=900, help='Seconds per isolated check')
    parser.add_argument('--worker', choices=dict(SOURCE_CASES), help=argparse.SUPPRESS)
    parser.add_argument('--worker-result', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not 0 < args.timeout <= 3600: parser.error('--timeout must be in (0, 3600]')
    if args.worker:
        if not args.worker_result: parser.error('Worker result path required')
        return unit_worker(args.worker, args.worker_result)
    try: validate_outputs([args.report, args.junit], args.package)
    except ValueError as error: parser.error(str(error))
    rows = []
    for name, _ in SOURCE_CASES:
        row = run_source_case(name, args.timeout); rows.append(row)
        print(row['status']+' '+row['id'], flush=True)
    if not args.source_only:
        if args.package:
            rows.extend(run_package_cases(args.package.resolve(), args.timeout))
        else:
            rows.extend(dict(id='package.'+name, status='BLOCKED', reason='No complete --package supplied')
                        for name, _, _ in PACKAGE_CASES)
    report = dict(schema='m4-usb-offline-tests/1', scope='source-only' if args.source_only else 'source-and-package',
                  status=overall_status(rows), checks=rows, device_operations=0, camera_validated=False,
                  package_checks_passed=bool(not args.source_only and args.package and
                      all(r['status']=='PASS' for r in rows if r['id'].startswith('package.'))))
    report['summary'] = dict(checks=len(rows),
        passed=sum(r['status']=='PASS' for r in rows),
        failed=sum(r['status']=='FAIL' for r in rows),
        blocked=sum(r['status']=='BLOCKED' for r in rows),
        unit_tests=sum((r.get('details') or {}).get('tests_run', 0) for r in rows),
        unit_skips=sum((r.get('details') or {}).get('skipped', 0) for r in rows))
    if args.report: atomic_json(args.report, report)
    if args.junit:
        args.junit.parent.mkdir(parents=True, exist_ok=True)
        args.junit.write_text(junit(report)+'\n', 'utf-8')
    for row in rows:
        if row['id'].startswith('package.'): print(row['status']+' '+row['id'], flush=True)
        if row['status'] == 'FAIL':
            print(row.get('reason') or row.get('output', 'Check failed')[-4000:], file=sys.stderr, flush=True)
    print('Source unit tests: '+str(report['summary']['unit_tests'])+
          '; platform skips: '+str(report['summary']['unit_skips']), flush=True)
    print(report['status']+' ('+report['scope']+'); camera validation: NOT PERFORMED', flush=True)
    return {'PASS':0, 'FAIL':1, 'PARTIAL':2}[report['status']]


if __name__ == '__main__': raise SystemExit(main())
