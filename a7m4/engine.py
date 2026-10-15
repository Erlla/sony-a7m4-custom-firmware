"""Shared safety boundary for desktop and Agent operations."""
from contextlib import contextmanager
from dataclasses import asdict
import ctypes
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
import uuid

from .common import Assets, ToolError, require, digest, sha256, atomic_json, read_json, data_dir, event
from .fat import Fat
from .transport import Fastboot, Partition, BOOT
from .patching import Updater, version, set_version, new_keypair


@contextmanager
def hardware_lock():
    """Serialize all toolkit instances, including separate GUI/Agent processes."""
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel.CreateMutexW.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.ReleaseMutex.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.CreateMutexW(None, False, "Local\\A7M4FastbootToolkit-Hardware")
        require(handle, "LOCK", "Could not create device lock")
        acquired = kernel.WaitForSingleObject(handle, 0) in (0, 0x80)
        try:
            require(acquired, "BUSY", "Another toolkit process is using the camera")
            yield
        finally:
            if acquired:
                kernel.ReleaseMutex(handle)
            kernel.CloseHandle(handle)
    else:
        import fcntl
        with open(Path(tempfile.gettempdir())/"a7m4-toolkit.lock", "a+") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as e:
                raise ToolError("BUSY", "Another toolkit process is using the camera") from e
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)


def content_binding(folder):
    """Conservative content binding, NOT a unique hardware serial number."""
    folder = Path(folder)
    personal = Fat((folder/"nflasha2.bin").read_bytes()).read("Backup.bin")
    require(len(personal) > 64, "IDENTITY", "Missing camera personalization data")
    return {"boot0_sha256": sha256(folder/"nflashaB0.bin"),
            "boot1_sha256": sha256(folder/"nflashaB1.bin"),
            "personalization_sha256": digest(personal)}


def validate_backup(folder):
    folder = Path(folder).resolve()
    manifest = read_json(folder/"manifest.json")
    require(manifest.get("schema") == 1 and manifest.get("complete") is True and manifest.get("device", {}).get("product") == "ILCE-7M4", "BACKUP_INCOMPLETE", "A complete A7M4 backup manifest is required")
    rows = manifest.get("partitions", [])
    require(rows and len(rows) == len({p["name"] for p in rows}), "BACKUP", "Duplicate or empty partition list")
    from .transport import parse_partitions
    # Reuse the strict partition grammar, bounds and overlap validation.
    parsed = parse_partitions("\n".join(f'{p["name"]} {p["start"]:08x} {p["sectors"]:08x} {p["kind"]}' for p in rows))
    require(len(parsed) == len(rows), "BACKUP", "Invalid partition list")
    for row in rows:
        require(row["file"] == row["name"]+".bin", "BACKUP", "Invalid backup filename")
        path = folder/row["file"]
        require(path.resolve().is_relative_to(folder) and not path.is_symlink() and path.is_file(), "BACKUP", "Backup file missing or redirected")
        require(path.stat().st_size == row["sectors"]*512 and sha256(path) == row["sha256"], "BACKUP_INTEGRITY", f'Backup damaged: {row["name"]}')
    require(content_binding(folder) == manifest.get("binding"), "BACKUP_INTEGRITY", "Backup content binding mismatch")
    return manifest


class Engine:
    def __init__(self, transport=None, assets=None, home=None, callback=None):
        self.assets = assets or Assets()
        self.transport = transport or Fastboot(self.assets)
        self.updater = Updater(self.assets)
        self.home = Path(home or data_dir()).resolve()
        self.home.mkdir(parents=True, exist_ok=True)
        self.callback = callback
        self._mutex = threading.Lock()
        self.cancel = threading.Event()
        self.state, self.backup, self.manifest = "disconnected", None, None
        self.parts, self.current, self.plans = {}, {}, {}
        self.last_result = None

    @contextmanager
    def operation(self):
        require(self._mutex.acquire(False), "BUSY", "Another operation is active")
        try:
            with hardware_lock():
                yield
        finally:
            self._mutex.release()

    def status(self):
        return {"state": self.state, "write_enabled": self.state == "ready", "backup": str(self.backup) if self.backup else None,
                "partitions": [p.json() | {"writable": p.name not in BOOT} for p in self.parts.values()], "last_result": self.last_result}

    def _emit(self, phase, **kwargs):
        event(self.callback, phase, **kwargs)

    def connect_backup(self, destination=None, enter=True):
        with self.operation():
            self.cancel.clear()
            self.state, self.backup, self.manifest = "connecting", None, None
            self.current, self.plans = {}, {}
            try:
                self._emit("connecting", message="Connecting / 连接中")
                if enter:
                    from .hardware import enter_fastboot
                    device = enter_fastboot(self.transport, self.assets, self.callback)
                else:
                    device = self.transport.select()
                self.parts = {p.name: p for p in self.transport.partitions()}
                total = sum(p.size for p in self.parts.values())
                base = Path(destination or self.home/"backups").resolve()
                base.mkdir(parents=True, exist_ok=True)
                require(shutil.disk_usage(base).free > total + max(p.size for p in self.parts.values()) + 64*1024*1024, "DISK_SPACE", "Not enough free disk space for complete backup and verification")
                folder = base/(time.strftime("%Y%m%d-%H%M%S")+"-"+uuid.uuid4().hex[:8])
                folder.mkdir()
                self.backup = folder
                self.state = "backing_up"
                manifest = {"schema": 1, "complete": False, "session": uuid.uuid4().hex, "created": time.time(), "device": device, "partitions": []}
                atomic_json(folder/"manifest.json", manifest)
                done = 0
                for index, p in enumerate(self.parts.values(), 1):
                    self._emit("backup", partition=p.name, completed=done, total=total, index=index, count=len(self.parts))
                    def progress(part_done, part_total):
                        self._emit("backup", partition=p.name, completed=done+part_done, total=total, partition_completed=part_done, partition_total=part_total, index=index, count=len(self.parts))
                    target = folder/(p.name+".bin")
                    self.transport.dump(p, target, progress, self.cancel.is_set)
                    row = p.json() | {"file": target.name, "sha256": sha256(target)}
                    manifest["partitions"].append(row)
                    atomic_json(folder/"manifest.json", manifest)
                    self.current[p.name] = target
                    done += p.size
                require(not self.cancel.is_set(), "CANCELLED", "Backup cancelled; writes remain locked")
                self._emit("backup_verify", completed=total, total=total, message="Verifying all backup hashes / 校验全部备份")
                manifest["binding"] = content_binding(folder)
                manifest["complete"] = True
                atomic_json(folder/"manifest.json", manifest)
                self.manifest = validate_backup(folder)
                require(not self.cancel.is_set(), "CANCELLED", "Backup cancelled; writes remain locked")
                self.state = "ready"
                self._emit("ready", completed=total, total=total, message="Backup verified; functions unlocked / 备份已验证，功能已解锁")
                return self.status()
            except Exception:
                self.state = "locked"
                self.plans.clear()
                raise

    def _ready(self):
        require(self.state == "ready" and self.backup and self.manifest, "BACKUP_REQUIRED", "Connect and complete a fresh full backup in this session first")
        self._emit("integrity", message="Checking complete backup integrity / 校验完整备份")
        try:
            validated = validate_backup(self.backup)
            require(validated == self.manifest, "BACKUP_INTEGRITY", "Backup manifest changed since acquisition")
        except Exception:
            self.state = "locked"
            self.plans.clear()
            raise

    def end_session(self):
        """Forget authorization, without device access or deleting saved data."""
        # No hardware lock is needed: another process cannot share this session.
        require(self._mutex.acquire(False), "BUSY", "Another operation is active")
        try:
            self.state, self.backup, self.manifest = "disconnected", None, None
            self.parts, self.current, self.plans = {}, {}, {}
        finally:
            self._mutex.release()

    def _check_connection(self):
        self.transport.select()
        require([p.json() for p in self.transport.partitions()] == [p.json() for p in self.parts.values()], "DEVICE_CHANGED", "Partition table changed since backup")

    def _read(self, name, folder, phase):
        target = Path(folder)/(name+".bin")
        self.transport.dump(self.parts[name], target, lambda d, t: self._emit(phase, partition=name, completed=d, total=t))
        return target

    def inspect(self):
        with self.operation():
            self._ready()
            result = {"version": version(self.current["nflasha2"].read_bytes())}
            try:
                result["updater"] = self.updater.inspect(self.current["nflasha1"].read_bytes())
            except ToolError as e:
                result["updater"] = {"official": False, "error": str(e), "code": e.code}
            return result

    def keygen(self, directory=None):
        with self.operation():
            return new_keypair(directory or self.home/"keys"/uuid.uuid4().hex[:8])

    def prepare(self, action, *, value=None, public_key_path=None, source_backup=None, partition=None):
        with self.operation():
            self._ready()
            require(action in ("unlock", "set_version", "restore", "restore_official"), "ACTION", "Unknown action")
            target_name = partition if action == "restore" else "nflasha2" if action == "set_version" else "nflasha1"
            require(target_name in self.parts and target_name not in BOOT, "PARTITION", "Partition is absent or backup-only")
            require(shutil.disk_usage(self.home).free > 2*self.parts[target_name].size + 64*1024*1024, "DISK_SPACE", "Not enough space to retain the source snapshot and generated image")
            self._check_connection()
            plan_id = uuid.uuid4().hex
            folder = self.home/"plans"/plan_id
            folder.mkdir(parents=True)
            # Always acquire a fresh operation source from the current camera.
            source = self._read(target_name, folder, "prepare_read")
            require(sha256(source) == sha256(self.current[target_name]), "STALE_SOURCE", "Partition changed since the verified snapshot; reconnect and back up again")
            source_hash = sha256(source)
            if action == "set_version":
                image, evidence = set_version(source.read_bytes(), value)
            elif action == "unlock":
                require(public_key_path and Path(public_key_path).is_file(), "KEY", "Select or generate your own RSA-2048 public key")
                self._emit("patch", message="Building updater from this camera backup / 从当前相机备份构建更新器")
                image, evidence = self.updater.unlock(source.read_bytes(), Path(public_key_path).read_bytes())
            else:
                source_folder = Path(source_backup or self.backup).resolve()
                old = validate_backup(source_folder)
                require(old["binding"] == self.manifest["binding"], "CAMERA_BINDING", "Restore source does not match this camera's backup content binding")
                old_parts = {p["name"]: p for p in old["partitions"]}
                row = old_parts.get(target_name)
                require(row and all(row[k] == self.parts[target_name].json()[k] for k in ("name", "start", "sectors", "kind")), "LAYOUT", "Restore source partition layout differs")
                image = (source_folder/(target_name+".bin")).read_bytes()
                if action == "restore_official":
                    self.updater.validate_official_restore(source.read_bytes(), image)
                evidence = {"restore_manifest": str(source_folder/"manifest.json"), "restore_session": old["session"], "source_image_sha256": digest(image)}
            require(len(image) == self.parts[target_name].size, "SIZE", "Generated image size differs from device partition")
            artifact = folder/"generated.bin"
            with artifact.open("xb") as f:
                f.write(image)
                f.flush()
                os.fsync(f.fileno())
            result = {"plan_id": plan_id, "action": action, "partition": target_name, "session": self.manifest["session"], "backup_manifest": str(self.backup/"manifest.json"), "source_sha256": source_hash,
                      "image_sha256": sha256(artifact), "size": len(image), "image": str(artifact), "evidence": evidence, "no_change": source_hash == sha256(artifact), "created": time.time()}
            result["confirmation"] = f'FLASH {target_name} {result["image_sha256"][:12]}'
            atomic_json(folder/"plan.json", result)
            # Hold a private copy: client edits to a returned JSON object cannot alter a plan.
            self.plans[plan_id] = json.loads(json.dumps(result))
            return result

    def apply(self, plan_id, confirmation):
        with self.operation():
            self._ready()
            plan = self.plans.get(plan_id)
            require(plan and plan["session"] == self.manifest["session"], "PLAN", "Unknown, used or expired plan; prepare again")
            require(confirmation == plan["confirmation"], "CONFIRMATION", "Confirmation must match the reviewed partition and image hash")
            artifact = Path(plan["image"])
            require(artifact.is_file() and sha256(artifact) == plan["image_sha256"] and artifact.stat().st_size == plan["size"], "ARTIFACT_INTEGRITY", "Prepared image changed")
            needed = 2*plan["size"] + sum(self.parts[n].size for n in ("nflashaB0", "nflashaB1", "nflasha2")) + 64*1024*1024
            require(shutil.disk_usage(self.home).free > needed, "DISK_SPACE", "Not enough space for preflight, staging and full post-write readback")
            self._check_connection()
            with tempfile.TemporaryDirectory(prefix="a7m4-check-", dir=self.home) as temp:
                # Serial is constant: compare immutable snapshots plus personalization.
                for name in ("nflashaB0", "nflashaB1", "nflasha2"):
                    self._read(name, temp, "preflight")
                require(content_binding(temp) == self.manifest["binding"], "CAMERA_BINDING", "Camera content binding changed; reconnect and back up again")
                target = plan["partition"]
                before = Path(temp)/(target+".bin")
                if not before.exists():
                    before = self._read(target, temp, "preflight")
                require(sha256(before) == plan["source_sha256"], "STALE_PLAN", "Target changed after preparation; refusing a stale write")
                staged = Path(temp)/"write.bin"
                shutil.copyfile(artifact, staged)
                require(sha256(staged) == plan["image_sha256"], "ARTIFACT_INTEGRITY", "Image changed while staging")
                self.plans.pop(plan_id)
                if plan["no_change"]:
                    self.last_result = {"plan_id": plan_id, "status": "no_change", "partition": target}
                    return self.last_result
                self.state = "writing"
                receipt = {"plan_id": plan_id, "partition": target, "expected_sha256": plan["image_sha256"], "status": "started", "started": time.time()}
                receipt_path = artifact.parent/"receipt.json"
                atomic_json(receipt_path, receipt)
                try:
                    require(shutil.disk_usage(self.home).free > plan["size"]+64*1024*1024, "DISK_SPACE", "Readback space was exhausted before the write")
                    self._emit("writing", partition=target, message="Writing; keep camera powered and connected / 正在写入，请勿断电或拔线")
                    self.transport.flash(self.parts[target], staged)
                    self.state = "verifying"
                    verified = self._read(target, artifact.parent/"readback", "verify")
                    require(sha256(verified) == plan["image_sha256"], "READBACK_MISMATCH", "Full partition readback does not match the generated image", "Keep fastboot running. Reconnect and complete a new backup, then restore the original verified backup.")
                    self.current[target] = verified
                    receipt.update(status="verified", finished=time.time(), readback_sha256=sha256(verified))
                    self.state = "ready"
                except Exception as e:
                    self.state = "recovery_required"
                    self.plans.clear()
                    receipt.update(status="failed", error=str(e), finished=time.time())
                    raise
                finally:
                    atomic_json(receipt_path, receipt)
                self.last_result = receipt
                self._emit("complete", partition=target, completed=1, total=1, message="Full readback verified / 全分区读回校验通过")
                return receipt

    def reboot(self):
        with self.operation():
            require(self.state not in ("writing", "verifying", "recovery_required"), "STATE", "Resolve the failed write before rebooting")
            self.transport.select()
            self.transport.reboot()
            self.state, self.plans = "disconnected", {}
            return self.status()
