param([Parameter(Mandatory=$true)][string]$Package)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$temp=Join-Path $Package ('state\source_tests\worker_'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temp | Out-Null
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$env:ProgramData=Join-Path $temp 'programdata'
$recoveryRoot=Join-Path $env:ProgramData ('M4CameraToolRecovery\'+$sid+'\operations')
$brokerPath=Join-Path $env:ProgramData ('M4CameraTool\'+$sid+'\operation.lock')
New-Item -ItemType Directory -Path $recoveryRoot -Force | Out-Null
New-Item -ItemType Directory -Path (Split-Path -Parent $brokerPath) -Force | Out-Null
[IO.File]::WriteAllText($brokerPath,'0')
$Nonce='a'*32;$BodyHash='b'*64;$base=Join-Path $temp 'operation'
New-Item -ItemType Directory -Path $base | Out-Null
$source=Get-Content -LiteralPath (Join-Path $Package 'app\workflow\standalone_usb_restore.ps1') -Raw -Encoding UTF8
$start=$source.IndexOf('$workerGuard=$null;')
if($start -lt 0){throw 'Apply boundary missing'}
$worker=$source.Substring($start)
# Bypass only the administrator prerequisite; all real lock acquisition/finally code remains.
$worker=$worker.Replace("if(-not `$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Administrator approval required.' }",'')
$command='$result.helper_exit_code=Invoke-RestoreHelper $evidence'
if(-not $worker.Contains($command)){throw 'Driver boundary changed; review fixture'}
$allUsers='$allUsers=@(Get-CimInstance Win32_PnPSignedDriver | Where-Object InfName -EQ $snapshot.normal.inf)'
$worker=$worker.Replace($allUsers,'$allUsers=@()')
$recoverySid=$sid;$windowsRoot=$env:SystemRoot
$script:checks=0
function Assert-Locked([string]$Path) {
 try{$h=[IO.File]::Open($Path,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)}
 catch [IO.IOException] {$script:checks++;return}
 $h.Dispose();throw 'Expected held lock'
}
function Test-WorkerLocks {
 Assert-Locked (Join-Path $recoveryRoot 'worker.lock')
 Assert-Locked $brokerPath
}
function Invoke-RestoreHelper([string]$Evidence) { Test-WorkerLocks;return 0 }
function Probe-Connection {
 @{normal_count=1;service_count=0;normal=@{body_sha256=$BodyHash;service='WinUSB';reviewed_driver=$true;inf='oem99.inf'}}
}
function Write-Result([string]$Path,$Value) {
 Test-WorkerLocks
 [IO.File]::WriteAllText($Path,($Value | ConvertTo-Json -Depth 8))
}
& ([scriptblock]::Create($worker))
$value=Get-Content -LiteralPath (Join-Path $base 'worker_result.json') -Raw | ConvertFrom-Json
if($value.status -ne 'HELPER_COMPLETE' -or $script:checks -ne 4){throw ($value | ConvertTo-Json)}
foreach($path in @((Join-Path $recoveryRoot 'worker.lock'),$brokerPath)) {
 $h=[IO.File]::Open($path,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None);$h.Dispose()
}
@{passed=$true;cases=3;tests=@('worker_and_broker_lock_held_during_apply','result_published_before_unlock','both_locks_released_after_result');device_operations=0;driver_tasks_dispatched=0;firmware_operations=0} | ConvertTo-Json -Compress
