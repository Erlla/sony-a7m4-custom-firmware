"""Exercise the actual workflow failure boundary with local-only fakes."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import argparse
import json
import sys
import uuid


def main():
    p = argparse.ArgumentParser(); p.add_argument('--package', type=Path, required=True)
    root = p.parse_args().package.resolve(strict=True)
    for name in ('app', 'vendor/python', 'vendor/squashfs', 'vendor/usb', 'app/container',
                 'app/provider', 'app/reader', 'app/workflow', 'app/ui'):
        sys.path.insert(0, str(root / name))
    import simple_workflow as workflow
    import wizard as flow
    import simple_app
    import usb.core
    from product_integrity import verify_release
    verify_release()
    def forbidden(*a, **k):
        raise AssertionError('No firmware or device operations in this test')
    class Journal:
        def __init__(self, *a): pass
        def load(self): return {'run': 'offline_patch'}
    tests = []
    for prior_plan, execute_failure in ((False, False), (True, False), (False, True)):
        value = dict(schema='m4-user-flow/1', flow=uuid.uuid4().hex, phase='PATCH_READY', patch_run='offline_patch')
        folder = flow.folder(value); folder.mkdir(parents=True)
        flow.save(value, value['phase'])
        if prior_plan: (folder / 'plan.json').write_text('{}', encoding='utf-8')
        def prepare():
            if not execute_failure:
                raise OSError('Injected local compilation failure')
            return Path('unused'), {}
        class Trial:
            def rt(self):
                return SimpleNamespace(jobs=SimpleNamespace(prepare=prepare),
                                       reader_jobs=SimpleNamespace(prepare=lambda: Path('unused_reader')))
            def seal(self, *a, **k):
                (folder / 'plan.json').write_text('{}', encoding='utf-8')
            def execute(self, *a, **k):
                raise OSError('Injected failure after sealing')
        with patch.object(usb.core, 'find', forbidden), patch.object(workflow.backend.frozen, 'Journal', Journal), \
             patch.object(flow, 'trial', return_value=Trial()), patch.object(workflow, 'patch_receiver', forbidden):
            try: workflow.open_menu(value)
            except OSError: pass
            else: raise AssertionError('Expected controlled failure')
        saved = json.loads((folder / 'flow.json').read_text('utf-8'))
        expected = 'REVIEW_REQUIRED' if prior_plan or execute_failure else 'MENU_PREPARATION_RETRY'
        assert saved['phase'] == expected
        assert saved['menu_preparation_device_started'] == (expected == 'REVIEW_REQUIRED')
        tests.append(('prior_plan_blocks_retry' if prior_plan else 'post_seal_failure_stays_review'
                      if execute_failure else 'local_preseal_failure_is_resumable'))
    value = dict(phase='MENU_PREPARATION_RETRY')
    assert simple_app.presentation(value)[3] == 'simple-continue'
    assert not simple_app.startup_can_reset(value, lambda: {})
    with patch.object(flow, 'load', return_value=value), patch.object(workflow, 'patch_receiver', forbidden):
        try: workflow.begin(True)
        except ValueError: pass
        else: raise AssertionError('Fresh patch allowed while menu retry is pending')
    tests.append('retry_ui_offers_continue_and_blocks_fresh_patch')
    result = dict(passed=True, cases=len(tests), tests=tests, device_operations=0, driver_tasks_dispatched=0)
    path = root / 'state/source_tests/local.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(result))


if __name__ == '__main__': main()
