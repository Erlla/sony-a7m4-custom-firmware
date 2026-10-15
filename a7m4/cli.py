"""JSON-RPC 2.0 over newline-delimited UTF-8 stdio; no TCP listener."""
import argparse
import json
from pathlib import Path
import sys
from .common import Assets, ToolError, read_json
from .engine import Engine, validate_backup

METHODS = {
    "status": {"description": "In-memory status; no device commands", "params": {}},
    "doctor": {"description": "Validate bundled resources; no driver installation", "params": {}},
    "connect_backup": {"description": "Enter fastboot, install driver/UF2 if needed, then mandatory full backup", "params": {"destination": "optional directory", "enter": "optional bool, default true; false requires existing fastboot"}},
    "inspect": {"description": "Read version and updater state from verified session snapshots", "params": {}},
    "keygen": {"description": "Create local RSA-2048 key pair; never returns key content", "params": {"directory": "optional directory"}},
    "prepare": {"description": "Build a reviewable image from verified camera backups; no camera write", "params": {"action": "unlock | set_version | restore | restore_official", "value": "version for set_version", "public_key_path": "public PEM for unlock", "source_backup": "complete backup folder for restore/restore_official", "partition": "partition for restore"}},
    "apply": {"description": "Apply one reviewed in-session plan and verify full readback", "params": {"plan_id": "returned by prepare", "confirmation": "exact confirmation string returned by prepare"}},
    "reboot": {"description": "Leave fastboot; invalidates session write permission", "params": {}}
}


def dispatch(engine, method, params):
    if method == "capabilities":
        if not isinstance(params, dict) or params:
            raise ToolError("PARAMS", "capabilities accepts no parameters")
        return {"protocol": "jsonrpc-2.0-stdio", "api_version": 1, "methods": METHODS, "backup_required": True, "arbitrary_commands": False}
    if method not in METHODS:
        raise ToolError("METHOD", "Unknown method")
    if not isinstance(params, dict) or set(params) - set(METHODS[method]["params"]):
        raise ToolError("PARAMS", "Unknown or invalid parameters")
    if method == "doctor":
        return engine.assets.check()
    if method == "connect_backup" and "enter" in params:
        if type(params["enter"]) is not bool:
            raise ToolError("PARAMS", "enter must be a boolean")
    return getattr(engine, method)(**params)


def serve(engine, stream_in=None, stream_out=None):
    source, sink = stream_in or sys.stdin, stream_out or sys.stdout
    def send(value):
        sink.write(json.dumps(value, ensure_ascii=False, separators=(",", ":"))+"\n")
        sink.flush()
    engine.callback = lambda value: send({"jsonrpc": "2.0", "method": "progress", "params": value})
    for raw in source:
        request = None
        try:
            if len(raw) > 1024*1024:
                raise ToolError("REQUEST_SIZE", "Request exceeds 1 MiB")
            request = json.loads(raw)
            if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str) or "id" not in request or isinstance(request["id"], (dict, list, bool)):
                raise ToolError("REQUEST", "Expected a JSON-RPC request with scalar id")
            result = dispatch(engine, request["method"], request.get("params", {}))
            send({"jsonrpc": "2.0", "id": request["id"], "result": result})
        except Exception as e:
            code = e.code if isinstance(e, ToolError) else "INVALID_REQUEST" if isinstance(e, (ValueError, TypeError, KeyError)) else "INTERNAL"
            send({"jsonrpc": "2.0", "id": request.get("id") if isinstance(request, dict) else None,
                  "error": {"code": -32000, "message": str(e), "data": {"code": code, "hint": getattr(e, "hint", "")}}})


def main():
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="A7M4 Fastboot Toolkit")
    parser.add_argument("--demo", action="store_true", help="Use synthetic camera only")
    parser.add_argument("--data-dir", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("agent")
    sub.add_parser("doctor")
    backup = sub.add_parser("backup")
    backup.add_argument("--destination", type=Path)
    backup.add_argument("--already-fastboot", action="store_true")
    verify = sub.add_parser("verify-backup")
    verify.add_argument("folder", type=Path)
    from .maintenance import ACTIONS
    console = sub.add_parser("maintain", help="Advanced interactive workflow; always back up first")
    console.add_argument("--action", choices=ACTIONS, default="menu")
    console.add_argument("--destination", type=Path)
    console.add_argument("--already-fastboot", action="store_true", help="Skip boot preparation only; full backup is still required")
    args = parser.parse_args()
    from .demo import DemoTransport
    engine = Engine(transport=DemoTransport() if args.demo else None, home=args.data_dir)
    if args.command == "agent":
        if args.demo:
            original = engine.connect_backup
            engine.connect_backup = lambda destination=None, enter=True: original(destination, enter=False)
        serve(engine)
        return
    try:
        if args.command == "maintain":
            from .maintenance import run_maintenance
            run_maintenance(engine, action=args.action, destination=args.destination,
                        enter=not args.already_fastboot and not args.demo)
            return
        if args.command == "doctor":
            result = engine.assets.check()
        elif args.command == "verify-backup":
            result = validate_backup(args.folder)
        else:
            engine.callback = lambda data: print(json.dumps(data, ensure_ascii=False), flush=True)
            result = engine.connect_backup(args.destination, enter=not args.already_fastboot and not args.demo)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.command == "doctor" and not result["ready"]:
            raise SystemExit(1)
    except Exception as e:
        print(json.dumps({"error": str(e), "code": getattr(e, "code", "INTERNAL"), "hint": getattr(e, "hint", "")}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
