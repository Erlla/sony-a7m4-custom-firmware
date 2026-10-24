from product_integrity import pinned, state_path
from pathlib import Path
import os
import queue
import time
import tkinter as tk
from tkinter import messagebox, ttk
import backend_bridge as bridge
import install_view
BG, WHITE, INK, MUTED, GREEN = ('#f3f5f1', '#ffffff', '#203b2d', '#627367', '#28654f')
NEW = {'NO_FLOW', 'COMPLETE', 'CANCELLED_BEFORE_DEVICE', 'READ_REJECTED_COMPLETE', 'ABANDONED_BEFORE_MENU'}
RECOVERY = {'PATCH_RECOVERY', 'POST_RESTART_NORMAL_CHECK', 'WAITING_FOR_RESTART', 'WAITING_FOR_NORMAL', 'PATCH_REJECTED_RECOVERY'}
HANDOFF = {'AWAITING_MENU_OBSERVATION', 'WAITING_FOR_USER_INSTALL_RESULT'}
ALLOWED = {'simple-start', 'simple-continue', 'simple-installed', 'simple-failure', 'simple-recover-usb'}

def startup_can_reset(state, patch_reader):
    if state['phase'] in NEW:
        return True
    if state['phase'] != 'PATCH_READY':
        return False
    patch = patch_reader()
    folder = state.get('folder')
    return patch.get('run') == state.get('patch_run') and patch.get('phase') == 'COMPLETE' and (patch.get('normal_recovery_verified') is True) and (patch.get('read_verified') is True) and (patch.get('session_ended') is True) and (not folder or not (Path(folder) / 'status.json').exists())
USB_RECOVERY = {'PATCH_RECOVERY', 'PATCH_REJECTED_RECOVERY', 'REVIEW_REQUIRED', 'USB_RECOVERY_WAITING'}

def presentation(state):
    phase = state['phase']
    if phase == 'PATCH_REJECTED_RECOVERY':
        return ('补丁未写入，请恢复连接', '完整备份已保存，但更新器兼容性检查未通过。\n保持相机开机，重新插拔 USB 后继续；本次只恢复连接。', '已重新插拔，恢复连接', 'simple-continue')
    if phase == 'USB_RECOVERY_WAITING':
        return ('等待普通 USB 连接', '保持相机开机，重新插拔 USB 线后点击“恢复普通 USB”。', '等待恢复', None)
    if phase == 'READ_REJECTED_COMPLETE':
        detail = '上次已完成备份但未写入补丁，普通 USB 已恢复。'
        if state.get('compatibility_fix') != 'reviewed_custom_route':
            return ('更新器兼容性检查未通过', detail + '\n请保留运行记录，先确认固件是否受支持。', '等待处理', None)
        return ('可以重新操作', detail, '写入补丁', 'simple-start')
    if phase == 'CANCELLED_BEFORE_DEVICE':
        detail = state.get('error', '请核对存储卡和 USB 连接。')
        if state.get('reconciliation') and state.get('stop_verified') == 'STOPPED_BEFORE_DRIVER_CHANGE':
            detail = '上次在本地检查阶段停止，未开始相机读写。已完成修复，可以重新操作；原始日志已保留。'
        elif 'find_card.ps1' in detail and 'timed out' in detail:
            detail = '上次停在存储卡查找阶段，未开始补丁读写。当前版本已移除此步骤，可以重新操作。'
        return ('尚未开始补丁读写', detail, '重新检查并写入补丁', 'simple-start')
    if phase in NEW:
        return ('写入补丁', '1  自行将要安装的 BODYDATA.DAT 放入卡槽 1 存储卡根目录。\n2  将 M4 开机，以 USB 海量存储模式连接电脑。\n3  保持电量充足，点击下方按钮，等待软件提示。', '写入补丁', 'simple-start')
    if phase == 'MENU_PREPARATION_RETRY':
        return ('继续准备更新菜单', '补丁和完整回读已完成。上次在电脑端准备菜单时停止，可继续本轮操作。', '继续准备更新菜单', 'simple-continue')
    if phase == 'PATCH_RECOVERY':
        return ('请重新连接 USB', '本轮补丁读写已结束。保持相机开机，拔下再插上 USB 线后继续。\n软件还会自动准备更新菜单，现在先不要更新。', '已重新插拔，继续', 'simple-continue')
    if phase in {'PATCH_PREPARED', 'PATCH_READY'}:
        return ('继续准备相机', '保持供电和 USB 连接，软件将自动完成后续准备。', '继续', 'simple-continue')
    if phase in HANDOFF:
        return ('可以拔下 USB 开始更新', '保持相机开机，拔下 USB，先回拍摄界面，再进入“版本／软件更新”。\n自行核对目标版本并执行更新，等待相机自动重启。', '结束并恢复 USB', 'simple-installed')
    if phase == 'POST_RESTART_NORMAL_CHECK':
        return ('准备恢复普通 USB', '请以 USB 海量存储模式重新连接相机，完成普通连接检查。', '已重新连接，完成检查', 'simple-continue')
    if phase in {'WAITING_FOR_RESTART', 'WAITING_FOR_NORMAL'}:
        return ('请重新连接 USB', '保持相机开机，重新插拔 USB 线后继续。\n这一步只确认普通连接。', '已重新插拔，继续', 'simple-continue')
    if phase in {'PREPARING', 'PATCH_RUNNING', 'MENU_PREPARING', 'MENU_RUNNING'}:
        return ('正在准备相机', '请保持相机开机、供电和 USB 稳定，等待软件提示。', '正在处理…', None)
    return ('操作需要检查', '请保留相机提示和运行记录，暂不要重复操作。', '等待处理', None)

class App:

    def __init__(self, root, jobs=None, flow_reader=install_view.snapshot, patch_reader=bridge.state_snapshot):
        self.root, self.jobs = (root, jobs or bridge.Jobs())
        self.flow_reader, self.patch_reader = (flow_reader, patch_reader)
        self.closed, self.current_action, self.last_folder = (False, None, None)
        self.started_at, self._poll_id, self.log_open, self.last_phase = (None, None, False, None)
        self.state = self.flow_reader()
        self.startup_reset_key = (self.state.get('flow'), self.state['phase']) if startup_can_reset(self.state, self.patch_reader) else None
        self.previous_phase = None
        self.usb_message = None
        root.title('M4 相机工具')
        root.configure(bg=BG)
        root.geometry('920x710+35+35')
        root.minsize(760, 660)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.option_add('*Font', ('Microsoft YaHei UI', 11))
        icon = bridge.DELIVERY / 'M4.ico'
        if icon.exists():
            root.iconbitmap(str(icon))
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('Horizontal.TProgressbar', background=GREEN, troughcolor='#e5ece2', borderwidth=0)
        outer = tk.Frame(root, bg=BG)
        outer.pack(fill='both', expand=True, padx=30, pady=24)
        header = tk.Frame(outer, bg=BG)
        header.pack(fill='x', pady=(0, 20))
        tk.Label(header, text='M4 相机工具', font=('Microsoft YaHei UI', 23, 'bold'), bg=BG, fg=INK).pack(side='left')
        tk.Label(header, text='1.00', bg=BG, fg=MUTED).pack(side='right')
        card = tk.Frame(outer, bg=WHITE, padx=26, pady=22)
        card.pack(fill='x')
        self.title, self.detail, self.timer, self.progress_text = (tk.StringVar() for _ in range(4))
        tk.Label(card, textvariable=self.title, font=('Microsoft YaHei UI', 21, 'bold'), bg=WHITE, fg=INK).pack(anchor='w')
        self.description = tk.Label(card, textvariable=self.detail, bg=WHITE, fg=MUTED, justify='left', anchor='w', wraplength=780)
        self.description.pack(fill='x', pady=(12, 12))
        self.ready = tk.BooleanVar(value=False)
        self.confirmation = tk.Checkbutton(card, text='相机已开机，USB 已连接，电量充足', variable=self.ready, command=self.refresh, bg=WHITE, fg=INK, activebackground=WHITE, anchor='w', highlightthickness=0)
        self.confirmation.pack(fill='x', pady=(0, 10))
        self.timer_label = tk.Label(card, textvariable=self.timer, bg=WHITE, fg=GREEN, justify='left', wraplength=760)
        self.timer_label.pack(anchor='w', pady=(0, 8))
        controls = tk.Frame(card, bg=WHITE)
        controls.pack(fill='x')
        self.primary = self.button(controls, '写入补丁', self.advance, primary=True)
        self.primary.pack(side='left')
        self.restore = self.button(controls, '恢复普通 USB', self.recover_usb)
        self.restore.pack(side='left', padx=(12, 0))
        self.issue = self.button(controls, '遇到问题', self.failure)
        self.issue.pack(side='left', padx=(12, 0))
        self.result = tk.StringVar(value='')
        tk.Label(outer, textvariable=self.result, bg=BG, fg=INK, anchor='w', wraplength=700, justify='left').pack(fill='x', pady=(12, 4))
        self.bar = ttk.Progressbar(outer, mode='determinate', maximum=100)
        self.bar.pack(fill='x')
        self.progress_label = tk.Label(outer, textvariable=self.progress_text, bg=BG, fg=MUTED, justify='left', anchor='w', wraplength=800)
        self.progress_label.pack(fill='x', pady=(4, 10))
        self.logs = tk.Frame(outer, bg=BG)
        self.log = tk.Text(self.logs, height=5, wrap='word', state='disabled', bg='#edf1e9', relief='flat')
        self.log.pack(fill='both', expand=True)
        footer = tk.Frame(outer, bg=BG)
        footer.pack(side='bottom', fill='x', pady=(12, 0))
        tk.Label(footer, text='安装包由你自行准备，本工具不检查安装包。\n恢复官方固件：满足官方条件后，按索尼更新流程安装适用原包。', bg=BG, fg=MUTED, wraplength=800, justify='left').pack(anchor='w', pady=(0, 10))
        links = tk.Frame(footer, bg=BG)
        links.pack(fill='x')
        self.log_button = self.button(links, '查看日志', self.toggle_log)
        self.log_button.pack(side='left')
        self.button(links, '打开运行记录', self.open_records).pack(side='left', padx=8)
        self.button(links, '使用说明', lambda: self.open_path(bridge.DELIVERY / '使用说明.md')).pack(side='right')
        root.bind('<Configure>', self.resize)
        self.refresh()
        self._poll_id = root.after(120, self.poll)

    def button(self, parent, title, command, primary=False):
        return tk.Button(parent, text=title, command=command, bg=GREEN if primary else '#e7ede3', fg=WHITE if primary else INK, activebackground='#345f4a', activeforeground=WHITE, relief='flat', borderwidth=0, padx=18, pady=10, cursor='hand2')

    def resize(self, event):
        if event.widget == self.root:
            width = max(550, event.width - 120)
            self.description.configure(wraplength=width)
            self.timer_label.configure(wraplength=width)
            self.progress_label.configure(wraplength=width)

    def refresh(self):
        self.state = self.flow_reader()
        if self.startup_reset_key != (self.state.get('flow'), self.state['phase']):
            self.startup_reset_key = None
        display = dict(phase='NO_FLOW') if self.startup_reset_key else self.state
        if self.state['phase'] == 'COMPLETE' and self.previous_phase != 'COMPLETE':
            self.ready.set(False)
        self.previous_phase = self.state['phase']
        title, detail, label, self.action = presentation(display)
        self.title.set(title)
        self.detail.set(detail)
        self.primary.configure(text=label)
        fresh = display['phase'] in NEW
        if fresh:
            if not self.confirmation.winfo_manager():
                self.confirmation.pack(fill='x', pady=(0, 10), before=self.timer_label)
        else:
            self.confirmation.pack_forget()
        enabled = self.action is not None and (not self.jobs.busy) and (not fresh or self.ready.get())
        self.primary.configure(state='normal' if enabled else 'disabled')
        self.restore.configure(state='normal' if not self.jobs.busy else 'disabled')
        if self.state['phase'] in HANDOFF:
            if not self.issue.winfo_manager():
                self.issue.pack(side='left', padx=(12, 0))
            self.issue.configure(state='disabled' if self.jobs.busy else 'normal')
        else:
            self.issue.pack_forget()
        seconds = self.state.get('remaining')
        if seconds == 0:
            self.title.set('请确认本轮更新状态')
            self.detail.set('菜单窗口已到期。如果尚未开始，请勿执行更新。\n如果更新已经开始，保持供电并等待完成；完成后再确认版本和拍摄保存。')
        self.timer.set((f'请在 {seconds // 60:02d}:{seconds % 60:02d} 内开始更新；已开始更新后请等待相机完成。' if seconds else '窗口已到期：尚未开始则请勿更新；若已开始更新，请等待相机完成。') if seconds is not None else '')
        if self.state['phase'] == 'COMPLETE' and (not self.startup_reset_key):
            self.result.set('本轮已结束，普通 USB 连接已恢复。')
        if self.usb_message and not self.jobs.busy:
            self.result.set(self.usb_message)

    def run(self, action, arguments=None):
        if action not in ALLOWED or self.jobs.busy:
            return False
        try:
            self.jobs.start(action, arguments or [])
            self.current_action, self.started_at = (action, time.monotonic())
            self.last_phase = None
            self.usb_message = None
            self.result.set('正在处理，请保持连接。')
            self.progress_text.set('')
            self.bar.configure(mode='indeterminate')
            self.bar.start(12)
            self.refresh()
            return True
        except Exception as error:
            self.result.set('操作未开始：' + str(error))
            return False

    def advance(self):
        self.refresh()
        if self.primary.cget('state') != 'normal':
            return
        arguments = []
        if self.action == 'simple-start':
            arguments = ['--ready']
        if self.action == 'simple-installed':
            if not messagebox.askokcancel('恢复普通 USB', '请确认相机已完成更新并自动重启，或取消更新后正常重启。\n当前已进入拍摄界面，未在更新中。然后重新连接 USB。', parent=self.root):
                return
            arguments = ['--confirmed']
        self.run(self.action, arguments)

    def failure(self):
        if messagebox.askokcancel('保留本轮记录', '停止后续操作并保留记录。请记下相机的完整提示；更新过程中不要断电。', parent=self.root):
            self.run('simple-failure')

    def recover_usb(self):
        self.refresh()
        if self.restore.cget('state') == 'normal':
            arguments = []
            if self.state['phase'] in HANDOFF:
                if not messagebox.askokcancel('恢复普通 USB', '请确认相机已完成或取消更新，并已重启回到拍摄界面。更新过程中请等待完成。', parent=self.root):
                    return
                arguments = ['--confirmed']
            self.run('simple-recover-usb', arguments)

    def poll(self):
        if self.closed:
            return
        if self._poll_id is not None:
            self.root.after_cancel(self._poll_id)
            self._poll_id = None
        for _ in range(400):
            try:
                event, value = self.jobs.events.get_nowait()
            except queue.Empty:
                break
            if event == 'started':
                self.last_folder = value['folder']
            elif event == 'line':
                self.log.configure(state='normal')
                self.log.insert('end', value + '\n')
                if int(self.log.index('end-1c').split('.')[0]) > 600:
                    self.log.delete('1.0', '100.0')
                self.log.see('end')
                self.log.configure(state='disabled')
            elif event == 'progress':
                self.bar.stop()
                self.bar.configure(mode='determinate', value=value[0] * 100)
                self.progress_text.set(value[1])
            elif event == 'finished':
                self.bar.stop()
                self.bar.configure(mode='determinate', value=100 if value['phase'] == 'SUCCESS' else 0)
                self.result.set('请按上方提示继续。' if value['phase'] == 'SUCCESS' else '操作已停止，请查看日志和上方提示。')
                if value.get('action') == 'simple-recover-usb':
                    payload = value.get('result') or {}
                    self.usb_message = payload.get('message')
                    self.bar.configure(value=100 if payload.get('phase') == 'USB_RESTORE_COMPLETE' else 0)
                    if payload.get('folder'):
                        self.last_folder = payload['folder']
            elif event == 'error':
                self.bar.stop()
                self.result.set('操作已停止，请保留运行记录。')
                self.log.configure(state='normal')
                self.log.insert('end', str(value) + '\n')
                self.log.configure(state='disabled')
            elif event == 'idle':
                self.current_action = None
        self.refresh()
        if self.jobs.busy:
            phase = self.state['phase']
            if phase == 'PATCH_RUNNING':
                phase = self.patch_reader().get('phase', phase)
            if phase != self.last_phase:
                self.last_phase = phase
                self.bar.stop()
                self.bar.configure(mode='indeterminate')
                self.bar.start(12)
                labels = {'PREPARING': '正在检查工具和相机配置', 'PATCH_PREPARING': '正在校验补丁与恢复材料', 'READ_STARTING': '正在完整备份', 'WRITE_STARTING': '正在写入补丁，请勿断开连接', 'READBACK_STARTING': '正在完整回读验证', 'MENU_PREPARING': '正在准备更新菜单', 'MENU_RUNNING': '正在完成更新菜单准备', 'RECOVERY_DISPATCHING': '正在恢复普通连接'}
                self.progress_text.set(labels.get(phase, '正在处理，请保持连接'))
        self._poll_id = self.root.after(150, self.poll)

    def toggle_log(self):
        self.log_open = not self.log_open
        if self.log_open:
            self.logs.pack(fill='both', expand=True)
        else:
            self.logs.pack_forget()
        self.log_button.configure(text='收起日志' if self.log_open else '查看日志')

    def open_path(self, path):
        path = Path(path).resolve()
        if path.exists():
            os.startfile(str(path))

    def open_records(self):
        self.open_path(self.last_folder or self.state.get('folder') or bridge.PRIVATE)

    def close(self):
        if self.jobs.busy:
            messagebox.showinfo('操作仍在进行', '请等待当前操作结束后再关闭窗口。', parent=self.root)
            return False
        self.closed = True
        self.bar.stop()
        if self._poll_id is not None:
            self.root.after_cancel(self._poll_id)
        self.root.destroy()
        return True

def main():
    bridge.verify_release()
    import msvcrt
    bridge.PRIVATE.mkdir(parents=True, exist_ok=True)
    with (bridge.PRIVATE / 'desktop.lock').open('a+b') as handle:
        if handle.seek(0, 2) == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo('M4 相机工具', '软件已经运行，请切回原窗口。', parent=root)
            root.destroy()
            return
        try:
            root = tk.Tk()
            App(root)
            root.mainloop()
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
if __name__ == '__main__':
    main()
