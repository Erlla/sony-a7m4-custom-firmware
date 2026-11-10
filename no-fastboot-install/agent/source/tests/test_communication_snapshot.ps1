param([Parameter(Mandatory=$true)][string]$Package)
$ErrorActionPreference='Stop'
$taskOldData=$env:ProgramData
$taskOldState=$env:M4_TOOL_DATA_ROOT
$taskFixture=Join-Path $env:TEMP ('m4-snapshot-test-'+[Guid]::NewGuid().ToString('N'))
$taskRoot=Join-Path $taskFixture 'data'
[IO.Directory]::CreateDirectory($taskRoot) | Out-Null
try {
 $env:ProgramData=$taskRoot
 $env:M4_TOOL_DATA_ROOT=Join-Path $taskFixture 'state'
 $taskSid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
 $taskBase=Join-Path $taskRoot ('M4CameraTool\'+$taskSid)
 [IO.Directory]::CreateDirectory($taskBase) | Out-Null
 '{"files":[]}' | Set-Content -LiteralPath (Join-Path $taskBase 'deployment.private.json') -Encoding UTF8
 $taskRun='a'*32
 $taskRunFolder=Join-Path $taskBase ('state\'+$taskRun)
 [IO.Directory]::CreateDirectory($taskRunFolder)|Out-Null
 '{"run_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","status":"NEEDS_REVIEW"}'|Set-Content -LiteralPath (Join-Path $taskBase 'latest_StageBind.json') -Encoding UTF8
 'fixture signing refusal'|Set-Content -LiteralPath (Join-Path $taskRunFolder 'stage.log') -Encoding UTF8
 $global:m4SnapshotVolumeCalls=0
 $global:m4SnapshotForbidStorage=$true
 function Get-PnpDevice { [pscustomobject]@{InstanceId='USB\VID_054C&PID_0DA5\FIXTURE';Status='OK'} }
 function Get-PnpDeviceProperty {
  param($InstanceId,$KeyName)
  [pscustomobject]@{Data=$(if($KeyName -eq 'DEVPKEY_Device_Service'){'WinUSB'}else{'oem42.inf'})}
 }
 function Get-Volume {
  $global:m4SnapshotVolumeCalls++
  if($global:m4SnapshotForbidStorage){throw 'Storage enumeration is forbidden for communication readiness'}
  return @()
 }
 function Get-Partition {throw 'No disk operations allowed'}
 function Get-Disk {throw 'No disk operations allowed'}
 function Get-CimInstance {throw 'No WMI operations allowed'}
 $taskScript=Join-Path $Package 'app/workflow/windows_snapshot.ps1'
 $taskName='reuse_'+[Guid]::NewGuid().ToString('N')
 $taskResult=(& $taskScript -Name $taskName -CommunicationOnly) | ConvertFrom-Json
 $taskSnapshot=Join-Path $env:M4_TOOL_DATA_ROOT ('snapshots/'+$taskName)
 $taskState=Get-Content -LiteralPath (Join-Path $taskSnapshot 'windows_state.private.json') -Raw | ConvertFrom-Json
 if($global:m4SnapshotVolumeCalls -ne 0 -or $taskState.storage_checked -or $taskResult.normal_count -ne 1){throw 'Communication snapshot enumerated storage or missed camera'}
 if((Get-Content -LiteralPath (Join-Path $taskSnapshot 'StageBind_stage.log') -Raw).Trim() -ne 'fixture signing refusal'){throw 'Driver signing diagnostic was not captured'}
 $global:m4SnapshotForbidStorage=$false
 $taskName='storage_'+[Guid]::NewGuid().ToString('N')
 $null=& $taskScript -Name $taskName
 $taskState=Get-Content -LiteralPath (Join-Path $env:M4_TOOL_DATA_ROOT ('snapshots/'+$taskName+'/windows_state.private.json')) -Raw | ConvertFrom-Json
 if($global:m4SnapshotVolumeCalls -ne 1 -or -not $taskState.storage_checked){throw 'Explicit storage snapshot was disabled'}
 [pscustomobject]@{passed=$true;cases=3;device_operations=0;driver_tasks_dispatched=0;communication_volume_calls=0;explicit_storage_volume_calls=1;stage_log_captured=$true}|ConvertTo-Json -Compress
} finally {
 Remove-Variable -Name m4SnapshotVolumeCalls,m4SnapshotForbidStorage -Scope Global -ErrorAction SilentlyContinue
 $env:ProgramData=$taskOldData
 $env:M4_TOOL_DATA_ROOT=$taskOldState
 # Remove only this verified, newly created temporary fixture directory.
 $taskResolved=[IO.Path]::GetFullPath($taskFixture)
 $taskTemp=[IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')+'\'
 if($taskResolved.StartsWith($taskTemp,[StringComparison]::OrdinalIgnoreCase) -and
    [IO.Path]::GetFileName($taskResolved) -match '^m4-snapshot-test-[a-f0-9]{32}$'){
  Remove-Item -LiteralPath $taskResolved -Recurse -Force
 }
}
