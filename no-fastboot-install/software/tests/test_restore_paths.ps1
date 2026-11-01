param([Parameter(Mandatory=$true)][string]$Package,[Parameter(Mandatory=$true)][string]$OldHelper)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$temp=Join-Path ([IO.Path]::GetTempPath()) ('m4restore_'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temp | Out-Null
$env:ProgramData=Join-Path $temp 'data'
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$recoveryRoot=Join-Path $env:ProgramData ('M4CameraToolRecovery\'+$sid+'\operations')
$source=Get-Content -LiteralPath (Join-Path $Package 'app\workflow\standalone_usb_restore.ps1') -Raw -Encoding UTF8
$functionStart=$source.IndexOf('function Invoke-RestoreHelper(')
$workerStart=$source.IndexOf('$workerGuard=$null;')
if($functionStart -lt 0 -or $workerStart -lt $functionStart){throw 'Helper boundary missing'}
. ([scriptblock]::Create($source.Substring($functionStart,$workerStart-$functionStart)))
$checks=New-Object Collections.Generic.List[string]
$marker=Join-Path $temp 'probe_called'
$stub="`nfunction global:Get-PnpDevice { param([switch]`$PresentOnly) [IO.File]::WriteAllText('"+$marker+"','mock');return @() }`n"
function Stage-Helper([string]$Name,[string]$Original) {
 $script:driverRoot=Join-Path $temp ($Name+'\app\driver_restore')
 New-Item -ItemType Directory -Path $driverRoot -Force | Out-Null
 $text=[IO.File]::ReadAllText($Original)
 $text=$text.Replace("`$ErrorActionPreference = 'Stop'",("`$ErrorActionPreference = 'Stop'"+$stub))
 [IO.File]::WriteAllText((Join-Path $driverRoot 'restore_camera_driver.ps1'),$text,(New-Object Text.UTF8Encoding($true)))
}
function New-Operation {
 $script:Nonce=[Guid]::NewGuid().ToString('N');$script:BodyHash='b'*64
 $script:base=Join-Path $recoveryRoot $Nonce
 New-Item -ItemType Directory -Path $base -Force | Out-Null
 return Join-Path $base 'state\results'
}
Stage-Helper 'old' $OldHelper
$evidence=New-Operation
$exit=Invoke-RestoreHelper $evidence
if($exit -ne 1 -or (Test-Path -LiteralPath $marker)){throw 'Old guard did not reject before PnP'}
$errorText=Get-Content -LiteralPath (Join-Path $base 'helper_stderr.log') -Raw
if($errorText -notmatch 'Evidence must stay under a private USB research directory'){throw $errorText}
$checks.Add('old_full_helper_reproduces_shared_path_rejection_before_PnP')

Stage-Helper 'new' (Join-Path $Package 'app\driver_restore\restore_camera_driver.ps1')
$evidence=New-Operation
$exit=Invoke-RestoreHelper $evidence
$result=Get-Content -LiteralPath (Join-Path $evidence 'auto_restore_result.private.json') -Raw | ConvertFrom-Json
if($exit -ne 1 -or -not (Test-Path -LiteralPath $marker) -or $result.status -ne 'STOPPED_BEFORE_DRIVER_CHANGE' -or
   $result.device_mutation_started -ne $false -or $result.error -ne 'Expected exactly one normal-mode Sony camera.'){throw ($result|ConvertTo-Json)}
$checks.Add('new_full_helper_accepts_shared_path_then_publishes_explicit_no_device_stop')
$checks.Add('real_child_stderr_and_exit_code_are_captured')
Remove-Item -LiteralPath $marker
$evidence=Join-Path (Split-Path -Parent $driverRoot) 'state\legacy\results'
$exit=Invoke-RestoreHelper $evidence
if($exit -ne 1 -or -not (Test-Path -LiteralPath $marker)){throw 'Legacy private path was rejected'}
$checks.Add('legacy_broker_private_state_path_still_accepted')
Remove-Item -LiteralPath $marker
$outside=Join-Path $temp 'outside\state\results'
$exit=Invoke-RestoreHelper $outside
if($exit -ne 1 -or (Test-Path -LiteralPath $marker) -or (Test-Path -LiteralPath $outside)){throw 'Outside path reached preflight'}
$checks.Add('outside_state_path_rejected_before_PnP_or_writes')

# Run the real Apply body and real child-process wrapper; substitute only host
# authorization/PnP, never invoke a device or PnPUtil. Child Get-PnpDevice is stubbed above.
$evidence=New-Operation
$worker=$source.Substring($workerStart)
$worker=$worker.Replace("if(-not `$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Administrator approval required.' }",'')
$worker=$worker.Replace('$allUsers=@(Get-CimInstance Win32_PnPSignedDriver | Where-Object InfName -EQ $snapshot.normal.inf)','$allUsers=@()')
$recoverySid=$sid;$windowsRoot=$env:SystemRoot
function Probe-Connection {@{normal_count=1;service_count=0;normal=@{body_sha256=$BodyHash;service='WinUSB';reviewed_driver=$true;inf='oem99.inf'}}}
function Write-Result([string]$Path,$Value) {[IO.File]::WriteAllText($Path,($Value|ConvertTo-Json -Depth 8))}
& ([scriptblock]::Create($worker))
$result=Get-Content -LiteralPath (Join-Path $base 'worker_result.json') -Raw | ConvertFrom-Json
if($result.status -ne 'STOPPED_BEFORE_DRIVER_CHANGE' -or $result.device_mutation_started -ne $false -or
   $result.helper_exit_code -ne 1 -or $result.error -ne 'Expected exactly one normal-mode Sony camera.'){throw ($result|ConvertTo-Json)}
$checks.Add('real_worker_and_child_preserve_no_driver_change_proof_and_error')
@{passed=$true;cases=$checks.Count;tests=@($checks);device_operations=0;driver_tasks_dispatched=0;firmware_operations=0;uac_interaction_tested=$false} | ConvertTo-Json -Depth 5 -Compress
