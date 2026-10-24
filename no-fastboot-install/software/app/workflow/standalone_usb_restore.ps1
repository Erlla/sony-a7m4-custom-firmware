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
 $camera=$null;$accessible=$false
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
   foreach($volume in @(Get-Volume | Where-Object { $_.FileSystemLabel -eq 'PMHOME' -and $_.DriveLetter })) {
    $parts=@(Get-Partition -DriveLetter $volume.DriveLetter)
    if($parts.Count -ne 1) { continue }
    $disk=$parts[0] | Get-Disk
    $rows=@(Get-CimInstance Win32_DiskDrive | Where-Object Index -EQ $disk.Number)
    if($rows.Count -ne 1) { continue }
    $node=$rows[0].PNPDeviceID
    for($depth=0;$depth -lt 10 -and $node;$depth++) {
     if($node -eq $id) { $accessible=(Test-Path -LiteralPath ($volume.DriveLetter+':\') -PathType Container);break }
     $parent=Get-PnpDeviceProperty -InstanceId $node -KeyName DEVPKEY_Device_Parent -ErrorAction SilentlyContinue
     if($parent) { $node=$parent.Data } else { $node=$null }
    }
    if($accessible) { break }
   }
  }
 }
 $packages=@(Get-ChildItem -LiteralPath (Join-Path $windowsRoot 'INF') -Filter 'oem*.inf' -File | Where-Object {
  (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash -eq $knownInf
 })
 [ordered]@{normal_count=$normal.Count;service_count=$service.Count;normal=$camera;
  camera_pmhome_accessible=$accessible;reviewed_package_absent=($packages.Count -eq 0);firmware_operations=0;camera_commands=0}
}
if($Mode -eq 'Probe') { Probe-Connection | ConvertTo-Json -Depth 8 -Compress;exit 0 }
if(-not $Folder -or -not $BodyHash -or -not $Nonce) { throw 'Recovery parameters missing.' }
$base=[IO.Path]::GetFullPath($Folder)
if($base -ne [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot)) -or (Split-Path -Leaf $base) -ne $Nonce) { throw 'Recovery folder differs.' }
$record=Get-Content -LiteralPath (Join-Path $base 'recovery.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($record.recovery -ne $Nonce -or $record.body_sha256 -ne $BodyHash) { throw 'Recovery record differs.' }
$hashes=Get-Content -LiteralPath (Join-Path $base 'helper_hashes.json') -Raw -Encoding UTF8 | ConvertFrom-Json
foreach($name in @('standalone_usb_restore.ps1','restore_camera_driver.ps1','camera_port.cs')) {
 if((Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $name) -Algorithm SHA256).Hash -ne $hashes.$name) { throw 'Recovery helper changed.' }
}
if($Mode -eq 'Launch') {
 try {
  $shell=Join-Path $PSHOME 'powershell.exe'
  $arguments='-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+$PSCommandPath+'" -Mode Apply -Folder "'+$base+'" -BodyHash '+$BodyHash+' -Nonce '+$Nonce
  $process=Start-Process -FilePath $shell -ArgumentList $arguments -Verb RunAs -WindowStyle Hidden -PassThru
  @{nonce=$Nonce;dispatched=$true;process_id=$process.Id} | ConvertTo-Json -Compress
 } catch {
  $native=$_.Exception
  while($native.InnerException) { $native=$native.InnerException }
  if($native -is [ComponentModel.Win32Exception] -and $native.NativeErrorCode -eq 1223) { @{nonce=$Nonce;cancelled_before_change=$true;dispatched=$false} | ConvertTo-Json -Compress }
  else { throw }
 }
 exit 0
}
$result=[ordered]@{nonce=$Nonce;body_sha256=$BodyHash;firmware_operations=0;camera_commands=0;error=$null;status='RUNNING'}
try {
 $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
 $principal=New-Object Security.Principal.WindowsPrincipal($identity)
 if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Administrator approval required.' }
 $snapshot=Probe-Connection
 if($snapshot.normal_count -ne 1 -or $snapshot.service_count -ne 0 -or $snapshot.normal.body_sha256 -ne $BodyHash -or
    $snapshot.normal.service -ne 'WinUSB' -or -not $snapshot.normal.reviewed_driver) { throw 'Camera or reviewed driver changed before recovery.' }
 $allUsers=@(Get-CimInstance Win32_PnPSignedDriver | Where-Object InfName -EQ $snapshot.normal.inf)
 foreach($user in $allUsers) { if((Body-Digest $user.DeviceID) -ne $BodyHash) { throw 'Driver is also used by another device.' } }
 $evidence=Join-Path $base 'state/results'
 New-Item -ItemType Directory -Path $evidence | Out-Null
 $env:SystemRoot=$windowsRoot
 & (Join-Path $PSHOME 'powershell.exe') -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'restore_camera_driver.ps1') -EvidenceDirectory $evidence -Apply
 $result.helper_exit_code=$LASTEXITCODE
 $result.status=if($LASTEXITCODE -eq 0) {'HELPER_COMPLETE'} else {'HELPER_NEEDS_CHECK'}
} catch { $result.status='NEEDS_CHECK';$result.error=$_.Exception.Message }
finally { $result.finished_utc=[DateTime]::UtcNow.ToString('o');Write-Result (Join-Path $base 'worker_result.json') $result }
