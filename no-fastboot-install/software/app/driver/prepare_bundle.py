from product_integrity import pinned, state_path
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import secrets
CASE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
OLD = CASE.parent / 'driver_restore'
PACKAGE = ROOT / 'tools/driver'

def prepare():
    name = 'bundle_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + secrets.token_hex(4)
    folder = ROOT / 'state/driver' / name
    folder.mkdir(parents=True, exist_ok=False)
    restored = (OLD / 'restore_camera_driver.ps1').read_text('utf-8')
    restored = restored.replace("$ErrorActionPreference = 'Stop'", "$ErrorActionPreference = 'Stop'\n$brokerWindowsRoot = [IO.Path]::GetDirectoryName([Environment]::SystemDirectory)", 1)
    restored = restored.replace('$env:SystemRoot', '$brokerWindowsRoot')
    restored = restored.replace("Add-Type -Path (Join-Path $PSScriptRoot 'camera_port.cs')", "Add-Type -Path (Join-Path $PSScriptRoot 'camera_driver_native.dll')")
    restored = restored.replace('New-Item -ItemType Directory -Path $taskEvidence -Force | Out-Null', 'New-BrokerDirectory $taskEvidence')
    restored = restored.replace('New-Item -ItemType Directory -Path $taskExport -Force | Out-Null', 'New-BrokerDirectory $taskExport')
    restored = restored.replace('function Save-Result { $taskResult | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $taskResultPath -Encoding UTF8 }', 'function Save-Result { Write-BrokerJson $taskResultPath $taskResult }')
    restored = restored.replace('$id = $devices[0].InstanceId', "$id = $devices[0].InstanceId\n    $bound = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'deployment.private.json') -Raw | ConvertFrom-Json\n    $digest = [Security.Cryptography.SHA256]::Create()\n    try { $instanceHash = [BitConverter]::ToString($digest.ComputeHash([Text.Encoding]::UTF8.GetBytes($id.ToUpperInvariant()))).Replace('-','') } finally { $digest.Dispose() }\n    if ($instanceHash -ne $bound.camera_instance_sha256) { throw 'Connected camera differs from the authorized body.' }", 1)
    native = (OLD / 'camera_port.cs').read_text('utf-8') + '\npublic static class M4CameraToolBind {\n [System.Runtime.InteropServices.DllImport("newdev.dll",CharSet=System.Runtime.InteropServices.CharSet.Unicode,SetLastError=true)]\n [return:System.Runtime.InteropServices.MarshalAs(System.Runtime.InteropServices.UnmanagedType.Bool)]\n public static extern bool UpdateDriverForPlugAndPlayDevicesW(System.IntPtr hwnd,string id,string inf,uint flags,[System.Runtime.InteropServices.MarshalAs(System.Runtime.InteropServices.UnmanagedType.Bool)]out bool reboot);\n}\n'
    content = {'worker.ps1': (CASE / 'worker.ps1').read_bytes(), 'restore_camera_driver.ps1': restored.encode('utf-8'), 'camera_port.cs': native.encode('utf-8'), 'driver/ilce-7m4.inf': (PACKAGE / 'ilce-7m4.inf').read_bytes(), 'driver/ILCE-7M4.cat': (PACKAGE / 'ILCE-7M4.cat').read_bytes()}
    files = []
    for name, data in content.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        files.append({'name': name.replace('/', '\\'), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    manifest = {'schema': 1, 'files': files, 'allowed_modes': ['SelfTest', 'StageBind', 'Restore'], 'triggers': []}
    raw = (json.dumps(manifest, indent=2) + '\n').encode()
    (folder / 'bundle_manifest.json').write_bytes(raw)
    result = {'bundle': str(folder), 'manifest_sha256': hashlib.sha256(raw).hexdigest(), 'usb_accessed': False}
    (ROOT / 'state/driver/prepared_bundle.private.json').write_text(json.dumps(result, indent=2) + '\n', 'utf-8', newline='\n')
    return result
