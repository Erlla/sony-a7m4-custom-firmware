"""Exact asset export/lock checks. Requires an existing clean portable ZIP."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import tempfile


def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();source=Path(__file__).resolve().parents[1];sys.path.insert(0,str(source))
    import prepare_assets as assets
    lock=hashlib.sha256((source/'dependencies.json').read_bytes()).hexdigest()
    result=assets.export(args.archive,args.output)
    assert result['files']==3257 and result['groups']==9
    assert not any((args.output/n).exists() for n in ('app','state','BODYDATA.DAT'))
    checks=['exact_3257_files_9_groups_export','no_app_state_or_firmware_exported']
    file=args.output/'licenses/python.txt'
    if not file.exists():file=next(p for p in (args.output/'licenses').rglob('*') if p.is_file())
    raw=file.read_bytes();file.write_bytes(raw+b'!')
    try:assets.verify(args.output)
    except ValueError:pass
    else:raise AssertionError('Tamper accepted')
    file.write_bytes(raw);checks.append('altered_asset_rejected')
    extra=args.output/'licenses/unlisted.txt';extra.write_text('unlisted','utf8')
    try:assets.verify(args.output)
    except ValueError:pass
    else:raise AssertionError('Extra file accepted')
    extra.unlink();checks.append('extra_asset_rejected')
    file.unlink()
    try:assets.verify(args.output)
    except ValueError:pass
    else:raise AssertionError('Missing asset accepted')
    file.write_bytes(raw);checks.append('missing_asset_rejected')
    assets.verify(args.output)
    assert hashlib.sha256((source/'dependencies.json').read_bytes()).hexdigest()==lock
    checks.append('original_group_lock_unchanged')
    print(json.dumps(dict(passed=True,cases=len(checks),tests=checks,export=result,device_operations=0,driver_tasks_dispatched=0)))


if __name__=='__main__':main()
