param([Parameter(Mandatory=$true)][string]$Name,[switch]$CommunicationOnly)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
# Import the Windows PowerShell built-in explicitly before PnP/Storage modules.
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
if ($Name -notmatch '^[a-z0-9_]+$') { throw 'Snapshot name differs.' }
$productRoot=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$dataRoot=if($env:M4_TOOL_DATA_ROOT){$env:M4_TOOL_DATA_ROOT}else{Join-Path $productRoot 'state'}
$folder=Join-Path (Join-Path $dataRoot 'snapshots') $Name
if (Test-Path -LiteralPath $folder) { throw 'Snapshot already exists.' }
New-Item -ItemType Directory -Path $folder -Force | Out-Null
$camera=@(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB\VID_054C&PID_0DA5\*' })
$active=@(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB\VID_054C&PID_0336\*' })
$rows=@($camera | ForEach-Object {
 [pscustomobject]@{instance=$_.InstanceId;status=$_.Status;service=(Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName DEVPKEY_Device_Service).Data;inf=(Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName DEVPKEY_Device_DriverInfPath).Data}
})
$volumes=@()
if (-not $CommunicationOnly -and $camera.Count -eq 1 -and $active.Count -eq 0) {
 . (Join-Path (Split-Path -Parent $PSScriptRoot) 'driver_restore\camera_storage.ps1')
 $volumes=@(Get-CameraStorageVolumes -InstanceId $camera[0].InstanceId)
}
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
  foreach ($artifactName in @('task_result.json','auto_restore_result.private.json','stage.log','stage_error.log','stage_svc.log')) {
   $path=Join-Path $source $artifactName
   if (Test-Path -LiteralPath $path) { Copy-Item -LiteralPath $path -Destination (Join-Path $folder ($mode+'_'+$artifactName)) }
  }
 }
}
$pmhome=@($volumes | Where-Object label -EQ 'PMHOME')
$value=[ordered]@{checked_utc=[DateTime]::UtcNow.ToString('o');normal=$rows;normal_count=$camera.Count;service_count=$active.Count;storage=$volumes;pmhome=$pmhome;storage_checked=(-not $CommunicationOnly);protected_dependencies_verified=$config.files.Count}
$value | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $folder 'windows_state.private.json') -Encoding UTF8
[pscustomobject]@{normal_count=$camera.Count;service_count=$active.Count;normal_storage=(@($rows | Where-Object { $_.service -eq 'USBSTOR' -and $_.inf -eq 'usbstor.inf' }).Count -eq 1);camera_storage_accessible=(@($volumes | Where-Object accessible -EQ $true).Count -gt 0);camera_pmhome_accessible=(@($pmhome | Where-Object accessible -EQ $true).Count -gt 0);dependencies_verified=$config.files.Count;snapshot=$Name} | ConvertTo-Json
