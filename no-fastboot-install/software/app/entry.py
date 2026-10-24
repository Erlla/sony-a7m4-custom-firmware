from pathlib import Path
import os
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
os.environ.pop('ZIG_LIB_DIR', None)
os.environ['ZIG_GLOBAL_CACHE_DIR'] = str(ROOT / 'state/cache/zig-global')
os.environ['ZIG_LOCAL_CACHE_DIR'] = str(ROOT / 'state/cache/zig-local')
for relative in ('app', 'vendor/python', 'vendor/squashfs', 'vendor/usb', 'app/container', 'app/provider', 'app/reader', 'app/workflow', 'app/ui'):
    sys.path.insert(0, str(ROOT / relative))
from product_integrity import verify_release
verify_release()
if len(sys.argv) > 1:
    action, *arguments = sys.argv[1:]
    if action.startswith('simple-'):
        sys.argv = [str(ROOT / 'app/workflow/simple_workflow.py'), action[7:], *arguments]
        runpy.run_path(sys.argv[0], run_name='__main__')
    elif action == 'flow-setup':
        import wizard
        import json
        print(json.dumps(wizard.act('setup'), ensure_ascii=False))
    elif action == '--check':
        import json
        print(json.dumps(dict(version='1.00', integrity=True, device_operations=0)))
    else:
        raise SystemExit('Unsupported operation')
else:
    import simple_app
    simple_app.main()
