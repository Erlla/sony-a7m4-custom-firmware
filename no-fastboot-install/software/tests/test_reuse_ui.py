"""Render the two completion states without opening a camera or launching jobs."""
from pathlib import Path
from types import SimpleNamespace
import argparse
import json
import queue
import sys
import tkinter as tk


def main():
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True)
    root=p.parse_args().package.resolve(strict=True)
    for name in ('app','app/ui','app/workflow','app/container','app/provider','app/reader',
                 'vendor/python','vendor/usb','vendor/squashfs'):
        sys.path.insert(0,str(root/name))
    import simple_app,gui_model
    top=tk.Tk();top.withdraw()
    state=dict(phase='AWAITING_MENU_OBSERVATION',remaining=300)
    jobs=SimpleNamespace(busy=False,events=queue.Queue())
    app=simple_app.App(top,jobs=jobs,flow_reader=lambda:state,patch_reader=lambda:dict(phase='NO_RUN'))
    try:
        app.refresh();top.update_idletasks()
        assert app.primary.cget('text')=='更新已结束' and app.restore.cget('state')=='normal'
        assert gui_model.LABELS['simple-installed']=='更新已结束'
        state.clear();state.update(phase='COMPLETE',usb_recovery='NOT_REQUESTED')
        app.refresh();top.update_idletasks()
        assert app.title.get()=='本轮操作已结束' and '按需' in app.result.get()
        assert '已恢复' not in app.result.get() and app.restore.cget('state')=='normal'
        assert app.primary.cget('text')=='写入补丁'
    finally: app.close()
    result=dict(passed=True,cases=2,device_operations=0,driver_tasks_dispatched=0,
                tests=['handoff_button_only_records_finished_update','operation_completion_does_not_claim_storage_recovery'])
    out=root/'state/source_tests/reuse_ui.json';out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result)+'\n','utf-8');print(json.dumps(result))


if __name__=='__main__':main()
