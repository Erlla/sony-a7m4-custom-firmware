param([Parameter(Mandatory=$true)][string]$Name)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
# Import the Windows PowerShell built-in explicitly before PnP/Storage modules.
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
if ($Name -notmatch '^[a-z0-9_]+$') { throw 'Snapshot name differs.' }
$productRoot=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$folder=Join-Path (Join-Path $productRoot 'state/snapshots') $Name
if (Test-Path -LiteralPath $folder) { throw 'Snapshot already exists.' }
New-Item -ItemType Directory -Path $folder -Force | Out-Null
$camera=@(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB\VID_054C&PID_0DA5\*' })
$active=@(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB\VID_054C&PID_0336\*' })
$rows=@($camera | ForEach-Object {
 [pscustomobject]@{instance=$_.InstanceId;status=$_.Status;service=(Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName DEVPKEY_Device_Service).Data;inf=(Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName DEVPKEY_Device_DriverInfPath).Data}
})
$volumes=@(Get-Volume | Where-Object { $_.FileSystemLabel -eq 'PMHOME' } | ForEach-Object {
 $rootPath=$_.DriveLetter+':\'
 $disk=Get-Partition -DriveLetter $_.DriveLetter | Get-Disk
 $diskDevice=Get-CimInstance Win32_DiskDrive | Where-Object Index -EQ $disk.Number
 $ancestors=@();$node=$diskDevice.PNPDeviceID
 for ($depth=0;$depth -lt 8 -and $node;$depth++) {
  $ancestors+=@($node)
  $node=(Get-PnpDeviceProperty -InstanceId $node -KeyName DEVPKEY_Device_Parent -ErrorAction SilentlyContinue).Data
 }
 [pscustomobject]@{drive_letter=[string]$_.DriveLetter;accessible=(Test-Path -LiteralPath $rootPath -PathType Container);disk_number=$disk.Number;ancestors=$ancestors;belongs_to_camera=(@($camera | Where-Object { $_.InstanceId -in $ancestors }).Count -eq 1)}
})
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$base=Join-Path $env:ProgramData ('M4CameraTool\'+$sid)
$config=Get-Content -LiteralPath (Join-Path $base 'deployment.private.json') -Raw | ConvertFrom-Json
Copy-Item -LiteralPath (Join-Path $base 'deployment.private.json') -Destination $folder
foreach ($entry in $config.files) {
 $target=Join-Path $folder $entry.name
 [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target)) | Out-Null
 Copy-Item -LiteralPath (Join-Path $base $entry.name) -Destination $target
 if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $entry.sha256) { throw 'Protected dependency differs.' }
}
foreach ($mode in @('SelfTest','StageBind','Restore')) {
 $index=Join-Path $base ('latest_'+$mode+'.json')
 if (Test-Path -LiteralPath $index) {
  Copy-Item -LiteralPath $index -Destination $folder
  $state=Get-Content -LiteralPath $index -Raw | ConvertFrom-Json
  $source=Join-Path $base ('state\'+$state.run_id)
  foreach ($artifactName in @('task_result.json','auto_restore_result.private.json')) {
   $path=Join-Path $source $artifactName
   if (Test-Path -LiteralPath $path) { Copy-Item -LiteralPath $path -Destination (Join-Path $folder ($mode+'_'+$artifactName)) }
  }
 }
}
$value=[ordered]@{checked_utc=[DateTime]::UtcNow.ToString('o');normal=$rows;normal_count=$camera.Count;service_count=$active.Count;pmhome=$volumes;protected_dependencies_verified=$config.files.Count}
$value | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $folder 'windows_state.private.json') -Encoding UTF8
[pscustomobject]@{normal_count=$camera.Count;service_count=$active.Count;normal_storage=(@($rows | Where-Object { $_.service -eq 'USBSTOR' -and $_.inf -eq 'usbstor.inf' }).Count -eq 1);camera_pmhome_accessible=(@($volumes | Where-Object { $_.accessible -and $_.belongs_to_camera }).Count -eq 1);dependencies_verified=$config.files.Count;snapshot=$Name} | ConvertTo-Json
