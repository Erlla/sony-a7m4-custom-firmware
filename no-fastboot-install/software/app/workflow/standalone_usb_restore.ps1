param(
 [Parameter(Mandatory=$true)][ValidateSet('Probe','Launch','Apply')][string]$Mode,
 [string]$Folder,
 [ValidatePattern('^[a-f0-9]{64}$')][string]$BodyHash,
 [ValidatePattern('^[a-f0-9]{32}$')][string]$Nonce
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version 2
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$knownInf='501b7c682e1ef7f378353350f51e66e033962b91357e9136f9e4a9b42a8da487'
$knownSvcInf='9455d90c562916277590bb9a8bc333379b86913e680d1e9176face6b44923e25'
$windowsRoot=[IO.Path]::GetDirectoryName([Environment]::SystemDirectory)

function Write-Result([string]$Path,$Value) {
 $temp=$Path+'.'+[Guid]::NewGuid().ToString('N')+'.tmp'
 [IO.File]::WriteAllText($temp,($Value | ConvertTo-Json -Depth 10),(New-Object Text.UTF8Encoding($false)))
 [IO.File]::Move($temp,$Path)
}
function Body-Digest([string]$Id) {
 $hash=[Security.Cryptography.SHA256]::Create()
 try { return [BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($Id.ToUpperInvariant()))).Replace('-','').ToLowerInvariant() }
 finally { $hash.Dispose() }
}
function Probe-Connection {
 $devices=@(Get-PnpDevice -PresentOnly)
 $normal=@($devices | Where-Object { $_.InstanceId -like 'USB\VID_054C&PID_0DA5\*' })
 $service=@($devices | Where-Object { $_.InstanceId -like 'USB\VID_054C&PID_0336\*' })
 $camera=$null;$accessible=$false;$pmhomeAccessible=$false
 if($normal.Count -eq 1) {
  $id=$normal[0].InstanceId
  $inf=[string](Get-PnpDeviceProperty -InstanceId $id -KeyName DEVPKEY_Device_DriverInfPath).Data
  $driver=[string](Get-PnpDeviceProperty -InstanceId $id -KeyName DEVPKEY_Device_Service).Data
  $reviewed=$false
  if($inf -match '^oem[0-9]+\.inf$') {
   $reviewed=((Get-FileHash -LiteralPath (Join-Path (Join-Path $windowsRoot 'INF') $inf) -Algorithm SHA256).Hash -eq $knownInf)
  }
  $camera=[ordered]@{body_sha256=(Body-Digest $id);service=$driver;inf=$inf;status=[string]$normal[0].Status;reviewed_driver=$reviewed}
  if($driver -eq 'USBSTOR') {
   . (Join-Path (Split-Path -Parent $PSScriptRoot) 'driver_restore\camera_storage.ps1')
   $volumes=@(Get-CameraStorageVolumes -InstanceId $id)
   $accessible=@($volumes | Where-Object root_accessible -EQ $true).Count -gt 0
   $pmhomeAccessible=@($volumes | Where-Object { $_.root_accessible -and $_.label -eq 'PMHOME' }).Count -gt 0
  }
 }
 $packages=@(Get-ChildItem -LiteralPath (Join-Path $windowsRoot 'INF') -Filter 'oem*.inf' -File | Where-Object {
  $hash=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
  $hash -eq $knownInf -or $hash -eq $knownSvcInf
 })
 [ordered]@{normal_count=$normal.Count;service_count=$service.Count;normal=$camera;
  camera_storage_accessible=$accessible;camera_pmhome_accessible=$pmhomeAccessible;
  reviewed_package_absent=($packages.Count -eq 0);firmware_operations=0;camera_commands=0}
}
if($Mode -eq 'Probe') { Probe-Connection | ConvertTo-Json -Depth 8 -Compress;exit 0 }
if(-not $Folder -or -not $BodyHash -or -not $Nonce) { throw 'Recovery parameters missing.' }
$base=[IO.Path]::GetFullPath($Folder)
if((Split-Path -Leaf $base) -ne $Nonce) { throw 'Recovery folder differs.' }
$record=Get-Content -LiteralPath (Join-Path $base 'recovery.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($record.recovery -ne $Nonce -or $record.body_sha256 -ne $BodyHash) { throw 'Recovery record differs.' }
$driverRoot=Join-Path (Split-Path -Parent $PSScriptRoot) 'driver_restore'
$recoverySid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$recoveryRoot=Join-Path $env:ProgramData ('M4CameraToolRecovery\'+$recoverySid+'\operations')
if([IO.Path]::GetFullPath((Split-Path -Parent $base)) -ne [IO.Path]::GetFullPath($recoveryRoot)){throw 'Recovery must use the shared protected registry.'}
if($Mode -eq 'Launch') {
 try {
  $shell=Join-Path $PSHOME 'powershell.exe'
  $arguments='-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+$PSCommandPath+'" -Mode Apply -Folder "'+$base+'" -BodyHash '+$BodyHash+' -Nonce '+$Nonce
  $process=Start-Process -FilePath $shell -ArgumentList $arguments -Verb RunAs -WindowStyle Hidden -PassThru
  @{nonce=$Nonce;dispatched=$true;process_id=$process.Id;process_start_utc=$process.StartTime.ToUniversalTime().ToString('o')} | ConvertTo-Json -Compress
 } catch {
  $native=$_.Exception
  while($native.InnerException) { $native=$native.InnerException }
  if($native -is [ComponentModel.Win32Exception] -and $native.NativeErrorCode -eq 1223) { @{nonce=$Nonce;cancelled_before_change=$true;dispatched=$false} | ConvertTo-Json -Compress }
  else { throw }
 }
 exit 0
}
function Invoke-RestoreHelper([string]$Evidence) {
 $start=New-Object Diagnostics.ProcessStartInfo
 $start.FileName=Join-Path $PSHOME 'powershell.exe'
 $start.Arguments='-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+(Join-Path $driverRoot 'restore_camera_driver.ps1')+'" -EvidenceDirectory "'+$Evidence+'" -Apply'
 $start.UseShellExecute=$false;$start.CreateNoWindow=$true
 $start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true
 $process=New-Object Diagnostics.Process;$process.StartInfo=$start
 try {
  if(-not $process.Start()){throw 'Could not start USB restore helper.'}
  $stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync()
  $process.WaitForExit()
  [IO.File]::WriteAllText((Join-Path $base 'helper_stdout.log'),$stdout.GetAwaiter().GetResult())
  [IO.File]::WriteAllText((Join-Path $base 'helper_stderr.log'),$stderr.GetAwaiter().GetResult())
  return $process.ExitCode
 } finally {$process.Dispose()}
}
$workerGuard=$null;$brokerGuard=$null
$result=[ordered]@{nonce=$Nonce;body_sha256=$BodyHash;firmware_operations=0;camera_commands=0;error=$null;status='RUNNING'}
try {
 $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
 $principal=New-Object Security.Principal.WindowsPrincipal($identity)
 if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Administrator approval required.' }
 $workerGuard=[IO.File]::Open((Join-Path $recoveryRoot 'worker.lock'),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
 $brokerPath=Join-Path $env:ProgramData ('M4CameraTool\'+$recoverySid+'\operation.lock')
 if(Test-Path -LiteralPath (Split-Path -Parent $brokerPath)){$brokerGuard=[IO.File]::Open($brokerPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)}
 $result.process_id=$PID
 $result.process_start_utc=(Get-Process -Id $PID).StartTime.ToUniversalTime().ToString('o')
 $snapshot=Probe-Connection
 if($snapshot.normal_count -ne 1 -or $snapshot.service_count -ne 0 -or $snapshot.normal.body_sha256 -ne $BodyHash -or
    $snapshot.normal.service -ne 'WinUSB' -or -not $snapshot.normal.reviewed_driver) { throw 'Camera or reviewed driver changed before recovery.' }
 $allUsers=@(Get-CimInstance Win32_PnPSignedDriver | Where-Object InfName -EQ $snapshot.normal.inf)
 foreach($user in $allUsers) { if((Body-Digest $user.DeviceID) -ne $BodyHash) { throw 'Driver is also used by another device.' } }
 $evidence=Join-Path $base 'state/results'
 New-Item -ItemType Directory -Path $evidence | Out-Null
 $env:SystemRoot=$windowsRoot
 $result.helper_exit_code=Invoke-RestoreHelper $evidence
 $result.status=if($result.helper_exit_code -eq 0) {'HELPER_COMPLETE'} else {'HELPER_NEEDS_CHECK'}
 $detailPath=Join-Path $evidence 'auto_restore_result.private.json'
 if(Test-Path -LiteralPath $detailPath){
  $detail=Get-Content -LiteralPath $detailPath -Raw -Encoding UTF8 | ConvertFrom-Json
  if($detail.status -eq 'STOPPED_BEFORE_DRIVER_CHANGE' -and $detail.device_mutation_started -eq $false){
   $result.status='STOPPED_BEFORE_DRIVER_CHANGE';$result.device_mutation_started=$false;$result.error=$detail.error
  }
 }
 if($result.helper_exit_code -ne 0 -and -not $result.error){
  $result.error=Get-Content -LiteralPath (Join-Path $base 'helper_stderr.log') -Raw -Encoding UTF8
 }
} catch { $result.status='NEEDS_CHECK';$result.error=$_.Exception.Message }
finally {
 try{$result.finished_utc=[DateTime]::UtcNow.ToString('o');Write-Result (Join-Path $base 'worker_result.json') $result}
 finally{if($brokerGuard){$brokerGuard.Dispose()};if($workerGuard){$workerGuard.Dispose()}}
}
