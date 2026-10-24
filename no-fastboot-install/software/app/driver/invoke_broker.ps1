param([Parameter(Mandatory=$true)][ValidateSet('SelfTest','StageBind','Restore')][string]$Mode)
$ErrorActionPreference='Stop'
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$base=Join-Path (Join-Path ([Environment]::GetFolderPath('CommonApplicationData')) 'M4CameraTool') $sid
$configuration=Get-Content -LiteralPath (Join-Path $base 'deployment.private.json') -Raw | ConvertFrom-Json
if ($configuration.user_sid -ne $sid -or $configuration.task_folder -ne ('\M4CameraTool\'+$sid)) { throw 'Deployment identity differs.' }
if ($Mode -ne 'SelfTest') {
 $normal=@(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB\VID_054C&PID_0DA5\*' })
 $active=@(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB\VID_054C&PID_0336\*' })
 if ($normal.Count -ne 1 -or $active.Count) { throw 'No unique normal camera; no privileged task was dispatched.' }
 foreach ($other in @('SelfTest','StageBind','Restore')) {
  $priorPath=Join-Path $base ('latest_'+$other+'.json')
  if (Test-Path -LiteralPath $priorPath) {
   $prior=Get-Content -LiteralPath $priorPath -Raw | ConvertFrom-Json
   if ($prior.status -in @('RUNNING','NEEDS_REVIEW')) {
    $recoveryCandidate=($Mode -eq 'Restore' -and $other -eq 'Restore' -and $prior.status -eq 'NEEDS_REVIEW' -and
        $prior.mode -eq 'Restore' -and $prior.error -eq 'Restore helper returned 1' -and $prior.device_mutation_started -eq $true)
    if ($recoveryCandidate) {
     $currentService=(Get-PnpDeviceProperty -InstanceId $normal[0].InstanceId -KeyName DEVPKEY_Device_Service).Data
     $currentInf=(Get-PnpDeviceProperty -InstanceId $normal[0].InstanceId -KeyName DEVPKEY_Device_DriverInfPath).Data
     $visiblePmhome=@(Get-Volume | Where-Object { $_.FileSystemLabel -eq 'PMHOME' -and $_.DriveLetter -and (Test-Path -LiteralPath ($_.DriveLetter+':\') -PathType Container) })
     $recoveryCandidate=($currentService -eq 'USBSTOR' -and $currentInf -eq 'usbstor.inf' -and $visiblePmhome.Count -gt 0)
    }
    if (-not $recoveryCandidate) { throw 'Prior outcome needs review; no privileged task was dispatched.' }
   }
  }
 }
}
$service=New-Object -ComObject 'Schedule.Service'; $service.Connect()
$folder=$service.GetFolder($configuration.task_folder); $task=$folder.GetTask($Mode)
if ($task.State -eq 4) { throw 'This maintenance task is already running; no repeat was dispatched.' }
$index=Join-Path $base ('latest_'+$Mode+'.json')
$previous=$null
if (Test-Path -LiteralPath $index) { $previous=(Get-Content -LiteralPath $index -Raw | ConvertFrom-Json).run_id }
$instance=$task.Run($null)
$deadline=[DateTime]::UtcNow.AddSeconds(120)
do {
 if (Test-Path -LiteralPath $index) {
  try { $result=Get-Content -LiteralPath $index -Raw | ConvertFrom-Json } catch { $result=$null }
  if ($result -and $result.run_id -ne $previous -and $result.status -ne 'RUNNING') {
   [pscustomobject]@{mode=$Mode;run_id=$result.run_id;status=$result.status;elevated=$result.elevated;
       error=$result.error;result_path=(Join-Path (Join-Path (Join-Path $base 'state') $result.run_id) 'task_result.json')} | ConvertTo-Json
   if ($result.status -in @('FAILED','NEEDS_REVIEW','REFUSED_BEFORE_CHANGE')) { exit 1 }; exit 0
  }
  if ($result -and $result.run_id -ne $previous -and $task.State -eq 3 -and $result.status -eq 'RUNNING') {
   throw ('Worker exited before committing its final index; inspect run '+$result.run_id+' without repeating the operation.')
  }
 }
 Start-Sleep -Milliseconds 500
} while ([DateTime]::UtcNow -lt $deadline)
throw 'Task outcome is pending; inspect the protected task result before another request.'
