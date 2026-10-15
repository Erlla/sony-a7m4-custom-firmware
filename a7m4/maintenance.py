"""Advanced interactive workflows; every invocation acquires a fresh full backup."""
import json

from .common import ToolError, require


ACTIONS = ("menu", "backup", "unlock", "set_version", "restore", "restore_official")


def run_maintenance(engine, *, action="menu", destination=None, enter=True,
                read=input, write=print):
    """Keep backup, preparation and writes in one Engine / process session.

    Input is always data, never a shell command. There is no image-path or
    skip-backup parameter, and a preselected action is shown only after backup.
    """
    require(action in ACTIONS, "ACTION", "Unknown maintenance action")
    previous = engine.callback
    last_progress = None

    def progress(item):
        nonlocal last_progress
        if item.get("total"):
            percent = min(100, int(item.get("completed", 0) / item["total"] * 100))
            marker = (item["phase"], item.get("partition"), percent)
            if marker == last_progress:
                return
            last_progress = marker
            write(f'{item["phase"]}: {item.get("partition", "")} {percent}%'
                  + (f' ({item["index"]}/{item["count"]})' if "index" in item else ""))
        if item.get("message"):
            write(item["message"])

    def show(result):
        write(json.dumps(result, ensure_ascii=False, indent=2))

    def perform(selected):
        params = {}
        if selected == "set_version":
            show(engine.inspect())
            value = read("新版本号（留空仅查看） / New version (blank = view only): ").strip()
            if not value:
                return
            params["value"] = value
        elif selected == "unlock":
            key = read("公钥 PEM 路径（留空生成自己的密钥） / Public PEM (blank = generate): ").strip()
            if not key:
                pair = engine.keygen()
                show(pair)
                write("请离线保存私钥 / Store your private key offline.")
                key = pair["public_key"]
            params["public_key_path"] = key
        elif selected in ("restore", "restore_official"):
            params["source_backup"] = read("完整备份目录（留空使用本次备份） / Full backup folder (blank = this session): ").strip() or None
            if selected == "restore":
                allowed = [p["name"] for p in engine.status()["partitions"] if p["writable"]]
                write("可恢复分区 / Restorable partitions: " + ", ".join(allowed))
                params["partition"] = read("分区名 / Partition: ").strip()
        plan = engine.prepare(selected, **params)
        show(plan)
        write("确认刷写后请保持供电，等待全分区读回校验。 / Keep power connected until readback finishes.")
        answer = read(f'输入完整确认文字；留空取消 / Type exactly; blank cancels:\n{plan["confirmation"]}\n> ')
        if answer != plan["confirmation"]:
            write("已取消，未写入 / Cancelled, no write.")
            return
        show(engine.apply(plan["plan_id"], answer))

    try:
        engine.callback = progress
        write("第一步：强制完整备份 / Step 1: mandatory full backup")
        write("接好 RP2040-Zero；首次安装按住 BOOTSEL 插入 USB。 / Connect RP2040; hold BOOTSEL on first setup.")
        if destination is None:
            destination = read("备份保存位置（留空使用默认目录） / Backup destination (blank = default): ").strip() or None
        status = engine.connect_backup(destination, enter=enter)
        require(status.get("write_enabled") is True and engine.state == "ready", "BACKUP_REQUIRED", "Full backup did not complete")
        write("全部分区备份已验证 / Full backup verified: " + str(engine.backup))
        if action == "backup":
            return status
        if action != "menu":
            perform(action)
            return engine.status()
        while engine.state == "ready":
            write("\n第二步：相机维护 / Step 2: maintenance\n"
                  "1  自签更新解锁 / Enable self-signed updates\n"
                  "2  查看或设置固件版本 / View or set version\n"
                  "3  分区恢复 / Restore partition\n"
                  "4  恢复官方验签 / Restore official verification\n"
                  "5  查看状态 / Inspect\n"
                  "6  退出 fastboot 并结束 / Reboot and exit\n"
                  "0  结束（保留 fastboot） / Exit (keep fastboot)")
            choice = read("> ").strip()
            if choice == "0":
                break
            try:
                if choice == "6":
                    show(engine.reboot())
                    break
                if choice == "5":
                    show(engine.inspect())
                elif choice in ("1", "2", "3", "4"):
                    perform({"1": "unlock", "2": "set_version", "3": "restore", "4": "restore_official"}[choice])
                else:
                    write("请输入 0–6 / Enter 0–6.")
            except ToolError as exc:
                if engine.state != "ready":
                    raise
                write(f"{exc.code}: {exc}\n{exc.hint}")
        return engine.status()
    except EOFError:
        raise ToolError("INPUT_CLOSED", "Maintenance input closed; no further action will be performed") from None
    finally:
        engine.callback = previous
        # Authorization cannot be reused by a caller after this workflow exits.
        engine.end_session()
