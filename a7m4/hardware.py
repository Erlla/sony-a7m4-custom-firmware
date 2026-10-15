"""RP2040 serial boot protocol and Windows driver preparation.

Wire-format interoperability based on ILCE-7M4-RE and the user's existing tool.
No driver installation or serial reset occurs at import time.
"""
import ctypes
import os
from pathlib import Path
import shutil
import struct
import subprocess
import time
import zlib
from .common import ToolError, require, run, event


def bootsel_drives():
    if os.name != "nt":
        return []
    found = []
    for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
        root = Path(letter + ":/")
        try:
            text = (root / "INFO_UF2.TXT").read_text(encoding="utf-8", errors="replace")
            if "Board-ID: RPI-RP2" in text and "RP2040" in text:
                found.append(root)
        except OSError:
            pass
    return found


def rp_ports():
    from serial.tools.list_ports import comports
    return [p.device for p in comports() if p.vid == 0x2e8a]


def uf2_check(data):
    require(data and len(data) % 512 == 0, "UF2", "Invalid UF2 length")
    total = len(data)//512
    for i in range(total):
        block = data[i*512:(i+1)*512]
        a, b, flags, addr, size, number, count, family = struct.unpack_from("<8I", block)
        require(a == 0x0a324655 and b == 0x9e5d5157 and struct.unpack_from("<I", block, 508)[0] == 0x0ab16f30
                and flags & 0x2000 and family == 0xe48bff56 and number == i and count == total and 0 < size <= 476
                and 0x10000000 <= addr < 0x11000000, "UF2", "Invalid RP2040 UF2 block")


class RpLink:
    def __init__(self, port, callback=None):
        import serial
        self.serial = serial.Serial(port, 115200, timeout=0.3, write_timeout=5)
        self.callback = callback

    def close(self):
        self.serial.close()

    def packet(self, deadline):
        def read(count):
            data = bytearray()
            while len(data) < count:
                require(time.monotonic() < deadline, "RP_TIMEOUT", "RP2040 did not respond", "Hold BOOTSEL while connecting the RP2040 USB, then retry.")
                data.extend(self.serial.read(count-len(data)))
            return bytes(data)
        header = read(3)
        size = int.from_bytes(header[1:], "little")
        require(size <= 8192, "RP_PROTOCOL", "Invalid RP2040 response length")
        return header[0], read(size)

    def command(self, number, payload=b""):
        self.serial.write(bytes([number])+struct.pack("<H", len(payload))+payload)
        deadline = time.monotonic()+8
        while True:
            kind, body = self.packet(deadline)
            if kind == 0x81:
                return body
            if kind == 0x82:
                raise ToolError("RP_ERROR", body.decode("utf-8", "replace"))
            require(kind == 0x83, "RP_PROTOCOL", "Unexpected RP2040 response")


def boot_records(payload):
    def frame(kind, value, data=b""):
        body = struct.pack("<IHI", 10+len(data), kind, value)+data
        return body+struct.pack("<I", zlib.crc32(body))
    yield frame(0x123, 0)
    for off in range(0, len(payload), 512):
        yield frame(1, 0xfe020000+off, payload[off:off+512])
    token = struct.pack("<I", 0xdeadbeef)
    yield frame(1, 0xfe02f398, token+struct.pack("<I", zlib.crc32(token)^0xffffffff))
    yield frame(0xffff, 0xfe020000)
    yield frame(0, 0xdeadbeef)
    yield frame(0x123, 0)


def prepare_rp(assets, callback):
    drives = bootsel_drives()
    require(len(drives) <= 1, "RP_AMBIGUOUS", "Multiple BOOTSEL boards found; connect one RP2040 only")
    if drives:
        firmware = assets.get("bin/uart_boot.ino.uf2")
        uf2_check(firmware.read_bytes())
        event(callback, "rp_flash", message="Writing RP2040 UF2 / 正在写入 RP2040 固件")
        try:
            shutil.copyfile(firmware, drives[0]/"A7M4.UF2")
        except OSError as e:
            raise ToolError("UF2_COPY", str(e), "Hold BOOTSEL while connecting the board, then retry.") from e
        deadline = time.monotonic()+20
        while time.monotonic() < deadline and not rp_ports():
            time.sleep(0.25)
    ports = rp_ports()
    require(len(ports) == 1, "RP_NOT_FOUND", f"Expected one RP2040 COM port, found {len(ports)}", "按住 BOOTSEL 接入 RP2040 USB，再点击连接。Hold BOOTSEL while connecting RP2040 USB, then retry.")
    link = RpLink(ports[0], callback)
    try:
        version = link.command(1)
        # Upstream v1 and the local v2 build share commands 1..5 used here.
        # Command 6 (interactive UART transmit) is deliberately never exposed.
        require(version in (b"uart_boot 1", b"uart_boot 2"), "RP_FIRMWARE", f"Unexpected RP2040 firmware: {version!r}", "Build the documented uart_boot bridge and reconnect holding BOOTSEL.")
        payload = assets.get("bin/fastboot.bin").read_bytes()
        require(0 < len(payload) < 0xf000, "PAYLOAD", "Payload exceeds audited SRAM range")
        event(callback, "payload", message="Sending camera boot payload / 推送相机启动程序")
        link.command(2)
        link.command(3, b"\x01")
        time.sleep(0.5)
        try:
            records = list(boot_records(payload))
            for idx, record in enumerate(records):
                link.command(4, record)
                event(callback, "payload", completed=idx+1, total=len(records))
                time.sleep(0.0144)
        finally:
            link.command(3, b"\x00")
        link.command(5, struct.pack("<I", 115200))
        deadline, output = time.monotonic()+15, b""
        try:
            while b"[mira] fastboot ready" not in output:
                kind, body = link.packet(deadline)
                if kind == 0x83:
                    output = (output+body)[-8192:]
        except ToolError as e:
            raise ToolError("CAMERA_BOOT", "Camera did not enter fastboot", "检查相机开机、TX/RX/RST/共地和电平转换。Check power, wiring and voltage levels; then retry.") from e
        finally:
            link.command(5, struct.pack("<I", 0))
    finally:
        link.close()


def install_driver(assets, callback):
    require(os.name == "nt", "PLATFORM", "Automatic driver installation requires Windows")
    # Validate every driver file, including signed catalogs, before elevation.
    from .common import read_json
    files = read_json(assets.base / "manifest.local.json")["files"]
    for name in files:
        if name.startswith("driver/"):
            assets.get(name)
    inf = assets.get("driver/android_winusb.inf")
    require("VID_18D1&PID_4EE0" in inf.read_text(encoding="utf-8-sig", errors="replace"), "DRIVER", "Driver does not match the payload USB ID")
    event(callback, "driver", message="Installing WinUSB; accept the Windows UAC prompt / 安装 WinUSB，请接受系统 UAC 提示")
    # Elevate only pnputil. No persistent elevated task, service or policy changes.
    path = str(inf).replace("'", "''")
    script = "$ErrorActionPreference='Stop'; $p=Start-Process -FilePath ($env:WINDIR+'\\System32\\pnputil.exe') -ArgumentList '/add-driver',('\"'+'" + path + "'+'\"'),'/install' -Verb RunAs -WindowStyle Hidden -Wait -PassThru; if ($p.ExitCode -notin @(0,3010)) { exit $p.ExitCode }"
    try:
        run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], timeout=180)
    except ToolError as e:
        raise ToolError("DRIVER_INSTALL", str(e), "Accept the administrator prompt. If Windows blocks the signed driver, use Device Manager to install the provided INF; keep driver-signature enforcement enabled.") from e


def enter_fastboot(transport, assets, callback):
    status = assets.check()
    require(status["ready"], "ASSETS_MISSING", "\n".join(status["errors"]))
    if transport.devices():
        return transport.select()
    if os.name == "nt":
        # A camera already running the payload may only be missing its driver.
        # Recover that state without requiring an RP2040 reset/boot cycle.
        found = run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                     "@(Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPDeviceID -like 'USB\\VID_18D1&PID_4EE0*' }).Count"], timeout=30).strip()
        if found.isdigit() and int(found) > 0:
            install_driver(assets, callback)
            for _ in range(20):
                if transport.devices():
                    return transport.select()
                time.sleep(1)
            raise ToolError("DRIVER_BINDING", "Fastboot USB device exists but the driver is not bound", "Reconnect the camera USB cable. In Device Manager, select the bundled signed WinUSB INF; then retry.")
    prepare_rp(assets, callback)
    event(callback, "usb", message="Connect the camera USB cable / 请接入相机 USB 数据线")
    deadline, installed = time.monotonic()+60, False
    while time.monotonic() < deadline:
        if transport.devices():
            return transport.select()
        if not installed:
            install_driver(assets, callback)
            installed = True
            deadline = time.monotonic()+60
        time.sleep(1)
    raise ToolError("USB_TIMEOUT", "Camera USB fastboot not detected", "检查 USB 数据线、驱动绑定和供电，再点连接。Check the USB data cable, driver binding and power, then reconnect.")
