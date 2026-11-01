param(
 [Parameter(Mandatory=$true)][string]$BundlePath,
 [Parameter(Mandatory=$true)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$ManifestSha256,
 [switch]$Repair
)
function Get-SetupContext {
 $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
 $principal=New-Object Security.Principal.WindowsPrincipal($identity)
 return @{sid=$identity.User.Value;administrator=$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator);
  common=(Join-Path ([Environment]::GetFolderPath('CommonApplicationData')) 'M4CameraTool')}
}
function New-SetupScheduler {
 $service=New-Object -ComObject 'Schedule.Service';$service.Connect();return $service
}
function New-SetupDirectory([string]$Path,$Security) {
 [IO.Directory]::CreateDirectory($Path,$Security)|Out-Null
}
function Get-SetupTaskFolder($Service,[string]$Path) {
 try{return $Service.GetFolder($Path)}catch{
  $failure=$_.Exception
  while($failure.InnerException){$failure=$failure.InnerException}
  if ($failure.HResult -notin @(-2147024894,-2147024893)) {throw}
  return $null
 }
}
function Resolve-SetupUserSid([string]$Identifier) {
 if ([string]::IsNullOrWhiteSpace($Identifier)) {return $null}
 try {
  if ($Identifier -match '^S-\d-') {return ([Security.Principal.SecurityIdentifier]::new($Identifier)).Value}
  return ([Security.Principal.NTAccount]::new($Identifier)).Translate([Security.Principal.SecurityIdentifier]).Value
 } catch {return $null}
}
function Get-SetupTasks($Folder,[string]$Base,[string]$Sid,[string]$PowerShell,$Diagnostics=$null) {
 if (-not $Folder) {return}
 $tasks=@($Folder.GetTasks(1))
 foreach($task in $tasks){
  $facts=[ordered]@{task=$task.Name;state=[int]$task.State;failed_fields=@()}
  if($task.State -eq 4){
   $facts.failed_fields=@('running');if($null -ne $Diagnostics){[void]$Diagnostics.Add($facts)}
   throw 'An existing M4 task is running; wait for it to finish before setup.'
  }
  if($task.Name -notin @('SelfTest','StageBind','Restore')){
   $facts.failed_fields=@('task_name');if($null -ne $Diagnostics){[void]$Diagnostics.Add($facts)}
   throw 'Unexpected task definition prevents setup; no tasks were removed.'
  }
  $definition=$task.Definition
  $identifier=[string]$definition.Principal.UserId
  $resolvedSid=Resolve-SetupUserSid $identifier
  $facts.principal_kind=if([string]::IsNullOrWhiteSpace($identifier)){'empty'}elseif($identifier -match '^S-\d-'){'sid'}else{'account_name'}
  $facts.principal_resolved=($null -ne $resolvedSid)
  $facts.actions_count=[int]$definition.Actions.Count;$facts.triggers_count=[int]$definition.Triggers.Count
  $facts.logon_type=[int]$definition.Principal.LogonType;$facts.run_level=[int]$definition.Principal.RunLevel
  $arguments='-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "'+(Join-Path $Base 'worker.ps1')+'" -Mode '+$task.Name
  $checks=[ordered]@{user_sid=($resolvedSid -eq $Sid);action_count=($definition.Actions.Count -eq 1);
   trigger_count=($definition.Triggers.Count -eq 0);logon_type=($definition.Principal.LogonType -eq 3);
   run_level=($definition.Principal.RunLevel -eq 1);action_type=$false;action_path=$false;working_directory=$false;arguments=$false}
  if($definition.Actions.Count -eq 1){
   $action=$definition.Actions.Item(1)
   $checks.action_type=($action.Type -eq 0);$checks.action_path=($action.Path -eq $PowerShell)
   $checks.working_directory=($action.WorkingDirectory -eq $Base);$checks.arguments=($action.Arguments -eq $arguments)
  }
  $facts.checks=$checks;$facts.failed_fields=@($checks.Keys|Where-Object{-not $checks[$_]})
  if($null -ne $Diagnostics){[void]$Diagnostics.Add($facts)}
  if($facts.failed_fields.Count){throw 'Unexpected task definition prevents setup; no tasks were removed.'}
 }
 return $tasks
}
function Install-M4Broker {
 param([string]$BundlePath,[string]$ManifestSha256,[switch]$Repair)
$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
$context=Get-SetupContext
if (-not $context.administrator) { throw 'One-time administrator authorization is required to register the fixed tasks.' }
$sid=$context.sid
$bundle=(Resolve-Path -LiteralPath $BundlePath).Path
$receipt=Join-Path $bundle 'installation.private.json'
if (Test-Path -LiteralPath $receipt) { throw 'Refusing to overwrite an installation receipt.' }
$outcome=[ordered]@{status='RUNNING';started_utc=[DateTime]::UtcNow.ToString('o');user_sid=$sid;error=$null}
$repairLock=$null;$setupLock=$null
try {
 $manifestPath=Join-Path $bundle 'bundle_manifest.json'
 if ((Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash -ne $ManifestSha256) { throw 'Reviewed installation manifest changed.' }
 $manifest=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
 $names=@('worker.ps1','restore_camera_driver.ps1','camera_port.cs','driver\ilce-7m4.inf','driver\ILCE-7M4.cat','driver\ilce-7m4-svc.inf','driver\ILCE-7M4-SVC.cat','driver\amd64\WdfCoInstaller01011.dll','driver\amd64\WinUSBCoInstaller2.dll')
 if (@($manifest.files).Count -ne 9 -or @($manifest.triggers).Count -ne 0 -or
     (($manifest.allowed_modes -join ',') -ne 'SelfTest,StageBind,Restore')) { throw 'Installation scope differs.' }
 foreach ($file in $manifest.files) {
  if ($file.name -notin $names -or (Get-FileHash -LiteralPath (Join-Path $bundle $file.name) -Algorithm SHA256).Hash -ne $file.sha256) { throw 'Installation dependency differs.' }
 }
 if ((Get-FileHash -LiteralPath (Join-Path $bundle 'driver\ilce-7m4.inf') -Algorithm SHA256).Hash -ne '501B7C682E1EF7F378353350F51E66E033962B91357E9136F9E4A9B42A8DA487' -or
     (Get-FileHash -LiteralPath (Join-Path $bundle 'driver\ILCE-7M4.cat') -Algorithm SHA256).Hash -ne 'D923980763E6CAA1151F8854905565878CAC1367DBE24307CC103C8B88FAE933' -or
     (Get-FileHash -LiteralPath (Join-Path $bundle 'driver\ilce-7m4-svc.inf') -Algorithm SHA256).Hash -ne '9455D90C562916277590BB9A8BC333379B86913E680D1E9176FACE6B44923E25' -or
     (Get-FileHash -LiteralPath (Join-Path $bundle 'driver\ILCE-7M4-SVC.cat') -Algorithm SHA256).Hash -ne 'FA1B38929210C1423104F1C71B488FC3E3BA6456A3478BE03659DF4E6456C886' -or
     (Get-FileHash -LiteralPath (Join-Path $bundle 'driver\amd64\WdfCoInstaller01011.dll') -Algorithm SHA256).Hash -ne 'F6FB39A8578F19616570D5A3DC7212C84A9DA232B30A03376BBF08F4264FEDF2' -or
     (Get-FileHash -LiteralPath (Join-Path $bundle 'driver\amd64\WinUSBCoInstaller2.dll') -Algorithm SHA256).Hash -ne '981A17EFFDDBC20377512DDAEC9F22C2B7067E17A3E2A8CCF82BB7BB7B2420B6') { throw 'Signed driver source differs.' }
 $common=$context.common
 $base=Join-Path $common $sid
 $oldConfig=$null
 $reviewedPrecheck=$null
 # Establish the required body before disabling tasks or copying any code.
 # Wait briefly for a just-replugged or waking camera before refusing.
 $camera=@()
 $waitDeadline=[DateTime]::UtcNow.AddSeconds(20)
 while ($true) {
  $camera=@(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB\VID_054C&PID_0DA5\*' })
  $active=@(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB\VID_054C&PID_0336\*' })
  if ($camera.Count -eq 1 -and $active.Count -eq 0) { break }
  if ([DateTime]::UtcNow -ge $waitDeadline) {
   if ($active.Count) { throw 'The camera is still in its service identity; let it return to normal mode and retry.' }
   throw ('Installation requires exactly one connected normal camera for body binding (detected ' + $camera.Count + '). Connect the powered-on camera in normal USB mode and retry.')
  }
  Start-Sleep -Milliseconds 500
 }
 $digest=[Security.Cryptography.SHA256]::Create()
 try { $bodyHash=[BitConverter]::ToString($digest.ComputeHash([Text.Encoding]::UTF8.GetBytes($camera[0].InstanceId.ToUpperInvariant()))).Replace('-','') } finally { $digest.Dispose() }
 # The per-user setup lock serializes retries before touching files or tasks.
 $directorySecurity=New-Object Security.AccessControl.DirectorySecurity
 $directorySecurity.SetSecurityDescriptorSddlForm(('O:BAG:SYD:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;GRGX;;;'+$sid+')'))
 if (-not (Test-Path -LiteralPath $common)) {
  $commonSecurity=New-Object Security.AccessControl.DirectorySecurity
  $commonSecurity.SetSecurityDescriptorSddlForm('O:BAG:SYD:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;GRGX;;;BU)')
  New-SetupDirectory $common $commonSecurity
 } elseif ((Get-Item -LiteralPath $common).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked installation parent refused.' }
 if ((Get-Acl -LiteralPath $common).GetOwner([Security.Principal.SecurityIdentifier]).Value -ne 'S-1-5-32-544') { throw 'Installation parent must be owned by Administrators.' }
 $setupLock=[IO.File]::Open((Join-Path $common ('setup_'+$sid+'.lock')),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
 $service=New-SetupScheduler
 $taskPath='\M4CameraTool\'+$sid
 $folder=Get-SetupTaskFolder $service $taskPath
 $powershell=Join-Path ([Environment]::SystemDirectory) 'WindowsPowerShell\v1.0\powershell.exe'
 $outcome.task_checks=New-Object Collections.Generic.List[object]
 $existingTasks=@(Get-SetupTasks $folder $base $sid $powershell -Diagnostics $outcome.task_checks)
 $reuseInstalled=$false;$orphanRelocated=$false
 if (Test-Path -LiteralPath $base) {
  if ((Get-Item -LiteralPath $base).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked installation refused.' }
  $configPath=Join-Path $base 'deployment.private.json'
  if (-not (Test-Path -LiteralPath $configPath)) {
   # Only an idle, evidence-free partial installation can be restarted.
   if (@(Get-ChildItem -LiteralPath $base -Filter 'latest_*.json' -File).Count -or
       ((Test-Path -LiteralPath (Join-Path $base 'state')) -and @(Get-ChildItem -LiteralPath (Join-Path $base 'state') -Force).Count)) {
    throw 'Incomplete installation has operation records; preserve them for review.'
   }
   $operationPath=Join-Path $base 'operation.lock'
   if (Test-Path -LiteralPath $operationPath) {
    $probeLock=[IO.File]::Open($operationPath,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None);$probeLock.Dispose()
   }
   $failedInstall=Join-Path $common ('failed_install_'+[Guid]::NewGuid().ToString('N'))
   if ([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($base)) -ne [IO.Path]::GetFullPath($common) -or
       [IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($failedInstall)) -ne [IO.Path]::GetFullPath($common)) { throw 'Partial installation must stay in its protected parent.' }
   [IO.Directory]::Move($base,$failedInstall)
   $outcome.relocated_failed_install=$failedInstall;$orphanRelocated=$true
  } elseif (-not $Repair) {
   $configuration=Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
   if ($configuration.user_sid -ne $sid -or $configuration.task_folder -ne $taskPath -or
       $configuration.camera_instance_sha256 -ne $bodyHash) { throw 'Existing setup belongs to a different user or camera.' }
   $expected=@($manifest.files.name)+@('camera_driver_native.dll')
   if ((@($configuration.files.name | Sort-Object) -join ',') -ne (@($expected | Sort-Object) -join ',')) { throw 'Existing driver setup differs; no replacement was made.' }
   foreach ($entry in $configuration.files) {
    $reviewed=@($manifest.files | Where-Object name -EQ $entry.name)
    if (($entry.name -ne 'camera_driver_native.dll' -and ($reviewed.Count -ne 1 -or $reviewed[0].sha256 -ne $entry.sha256)) -or
        (Get-FileHash -LiteralPath (Join-Path $base $entry.name) -Algorithm SHA256).Hash -ne $entry.sha256) { throw 'Existing driver setup differs; no replacement was made.' }
   }
   $repairLock=[IO.File]::Open((Join-Path $base 'operation.lock'),[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
   $reuseInstalled=$true;$outcome.reused_installation=$true
  }
 }
 if ((Test-Path -LiteralPath $base) -and -not $reuseInstalled) {
  if (-not $Repair) { throw 'An installation already exists; inspect or uninstall it before replacing code.' }
  if ((Get-Item -LiteralPath $base).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked installation refused.' }
  $oldConfig=Get-Content -LiteralPath (Join-Path $base 'deployment.private.json') -Raw | ConvertFrom-Json
  if ($oldConfig.user_sid -ne $sid -or $oldConfig.task_folder -ne ('\M4CameraTool\'+$sid)) { throw 'Repair target differs.' }
  if ($oldConfig.camera_instance_sha256 -ne $bodyHash) { throw 'Camera body differs from the original authorization.' }
  $repairLock=[IO.File]::Open((Join-Path $base 'operation.lock'),[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
  $oldService=New-Object -ComObject 'Schedule.Service'; $oldService.Connect(); $oldFolder=$oldService.GetFolder($oldConfig.task_folder)
  $oldTasks=@($oldFolder.GetTasks(1))
  if ($oldTasks.Count -ne 3 -or @($oldTasks | Where-Object { $_.Name -notin @('SelfTest','StageBind','Restore') -or $_.State -eq 4 }).Count) { throw 'Unexpected or running task prevents repair.' }
  foreach ($oldMode in @('StageBind','Restore')) {
   $oldIndex=Join-Path $base ('latest_'+$oldMode+'.json')
   if (Test-Path -LiteralPath $oldIndex) {
    $oldState=Get-Content -LiteralPath $oldIndex -Raw | ConvertFrom-Json
    if ($oldState.status -in @('RUNNING','NEEDS_REVIEW')) {
     # One observed, source-reviewed refusal occurred before Get-BrokerCamera
     # returned, before any driver utility call. Preserve the exact original;
     # no other unknown operation may be cleared by this repair path.
     $knownHash='74BD86C3036B0FD21C8A7EA9F9184099C7E06F7C2DF611278AD0E880FAB63AF9'
     $knownWorker='00DC343D40D8DDAFCC2DC31E29E2605612EBB2DB8522C54D8E82240D6ACC52DD'
     $record=Join-Path (Join-Path (Join-Path $base 'state') 'eb0ba202bd894fa38cea6fc3bbc6ff2b') 'task_result.json'
     $workerBinding=@($oldConfig.files | Where-Object name -EQ 'worker.ps1')
     $known=($oldMode -eq 'StageBind' -and $oldState.status -eq 'NEEDS_REVIEW' -and
       $oldState.run_id -eq 'eb0ba202bd894fa38cea6fc3bbc6ff2b' -and
       $oldState.error -eq 'Expected one normal camera and no active service session.' -and
       $workerBinding.Count -eq 1 -and $workerBinding[0].sha256 -eq $knownWorker -and
       (Get-FileHash -LiteralPath $oldIndex -Algorithm SHA256).Hash -eq $knownHash -and
       (Get-FileHash -LiteralPath $record -Algorithm SHA256).Hash -eq $knownHash -and
       @(Get-ChildItem -LiteralPath ([IO.Path]::GetDirectoryName($record)) -Force).Count -eq 1)
     $volumeRecoveryCases=@{
      '2B9091BF175E660AB380A4D7563A0F28E01B381DC8DB40A1152383ECB5B43F30'=@{run='4edcec7cb9c542648f0073622c8ed83c';detail='9FAA47EA8A4603DE5B282E60627920DD86B4FF5532250CD68A0DD6847AA92BC3'}
      '29A7C709C5CD9D0A3D87D807AE291A11CD83E71AFAE9187A4F520352DE8463F5'=@{run='3acd174b56804af58b38fe5aa5809801';detail='5621F6FDEC386FCBD6EDAF9DC0D3BDD417A14C1A2E059FCF977920E1A2A03F8D'}
      'F79BB3E7CA6E90C1FBF8633BA9DB0D5F36E7F307732180477007D1B7E4053784'=@{run='19bf920499d6402bbb4ecbde751b6162';detail='814D829E17104F14D5871DA7098F01BBD546C547847B29BB1D9BDD1F985D280F'}
     }
     $indexHash=(Get-FileHash -LiteralPath $oldIndex -Algorithm SHA256).Hash
     if (-not $known -and $oldMode -eq 'Restore' -and $volumeRecoveryCases.ContainsKey($indexHash) -and
         $workerBinding.Count -eq 1 -and $workerBinding[0].sha256 -eq '860B8063FFB49B1CC61F5683D56CCFD15559E3687C6B3D9DCD649D14FC69BD2F') {
      # This exact completed uninstall/cycle missed only the volume deadline.
      # User subsequently restored normal USB. Resolve only with fresh postconditions;
      # the original failed run remains immutable in its protected evidence folder.
      $reviewedCase=$volumeRecoveryCases[$indexHash]
      $detailPath=Join-Path $base ('state\'+$reviewedCase.run+'\auto_restore_result.private.json')
      $recordPath=Join-Path $base ('state\'+$reviewedCase.run+'\task_result.json')
      if ($oldState.status -eq 'NEEDS_REVIEW' -and $oldState.run_id -eq $reviewedCase.run -and
          (Get-FileHash -LiteralPath $recordPath -Algorithm SHA256).Hash -eq $indexHash -and
          (Get-FileHash -LiteralPath $detailPath -Algorithm SHA256).Hash -eq $reviewedCase.detail) {
       $detail=Get-Content -LiteralPath $detailPath -Raw | ConvertFrom-Json
       $currentService=(Get-PnpDeviceProperty -InstanceId $camera[0].InstanceId -KeyName DEVPKEY_Device_Service).Data
       $currentInf=(Get-PnpDeviceProperty -InstanceId $camera[0].InstanceId -KeyName DEVPKEY_Device_DriverInfPath).Data
       $pmhome=@(Get-Volume | Where-Object { $_.FileSystemLabel -eq 'PMHOME' -and $_.DriveLetter -and (Test-Path -LiteralPath ($_.DriveLetter+':\')) })
       $packageGone=($detail.package -match '^oem[0-9]+\.inf$' -and -not (Test-Path -LiteralPath (Join-Path (Join-Path ([IO.Path]::GetDirectoryName([Environment]::SystemDirectory)) 'INF') $detail.package)))
       $known=($detail.status -eq 'failed' -and $detail.uninstall_exit_code -eq 0 -and $detail.port_cycle_count -eq 1 -and
         $detail.error -eq 'USBSTOR/PMHOME did not become accessible within the postcondition deadline.' -and
         $camera[0].InstanceId -eq $detail.before.instance -and $currentService -eq 'USBSTOR' -and $currentInf -eq 'usbstor.inf' -and $pmhome.Count -gt 0 -and $packageGone)
       if ($known) {
        $knownHash=(Get-FileHash -LiteralPath $oldIndex -Algorithm SHA256).Hash
        $outcome.reviewed_volume_recovery=[ordered]@{original_failed_run=$reviewedCase.run;original_failure_preserved=$true;fresh_driver='USBSTOR/usbstor.inf';pmhome_accessible=$true;package_absent=$true;user_restored_normal_usb=$true;additional_driver_mutations=0}
       }
      }
     }
     if (-not $known) { throw 'Unresolved device operation prevents code repair.' }
     $reviewedPrecheck=$oldIndex
     $outcome.reviewed_precheck_sha256=$knownHash
     $outcome.reviewed_precheck_driver_mutations=0
    }
   }
  }
  foreach ($oldTask in $oldTasks) { $oldTask.Enabled=$false }
  $backup=Join-Path (Join-Path $base 'state') ('pre_repair_'+[Guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Path $backup | Out-Null
  Copy-Item -LiteralPath (Join-Path $base 'deployment.private.json') -Destination $backup
  foreach ($oldFile in $oldConfig.files) {
   if ($oldFile.name -notin @('worker.ps1','restore_camera_driver.ps1','camera_port.cs','camera_driver_native.dll','driver\ilce-7m4.inf','driver\ILCE-7M4.cat','driver\ilce-7m4-svc.inf','driver\ILCE-7M4-SVC.cat','driver\amd64\WdfCoInstaller01011.dll','driver\amd64\WinUSBCoInstaller2.dll')) { throw 'Unexpected installed dependency prevents repair.' }
   $oldPath=Join-Path $base $oldFile.name
   if ((Get-FileHash -LiteralPath $oldPath -Algorithm SHA256).Hash -ne $oldFile.sha256) { throw 'Installed code differs; preserve it for review.' }
   $backupPath=Join-Path $backup $oldFile.name
   [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($backupPath)) | Out-Null
   [IO.File]::Copy($oldPath,$backupPath,$false)
  }
  $selfIndex=Join-Path $base 'latest_SelfTest.json'
  if (Test-Path -LiteralPath $selfIndex) { Move-Item -LiteralPath $selfIndex -Destination (Join-Path $backup 'latest_SelfTest.json') }
  if ($reviewedPrecheck) { Move-Item -LiteralPath $reviewedPrecheck -Destination (Join-Path $backup ([IO.Path]::GetFileName($reviewedPrecheck))) }
  $outcome.repair_backup=$backup
 } elseif ($Repair -and -not $orphanRelocated -and -not $reuseInstalled) { throw 'No matching installation exists for repair.' }
 if (-not $reuseInstalled) {
 New-SetupDirectory $base $directorySecurity
 New-SetupDirectory (Join-Path $base 'driver') $directorySecurity
 New-SetupDirectory (Join-Path $base 'state') $directorySecurity
 if (-not $Repair -or $orphanRelocated) {
  [IO.File]::WriteAllBytes((Join-Path $base 'operation.lock'),[byte[]]@())
  $repairLock=[IO.File]::Open((Join-Path $base 'operation.lock'),[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
 }
 $owner=New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')
 foreach ($file in $manifest.files) {
  $destination=Join-Path $base $file.name
  New-SetupDirectory ([IO.Path]::GetDirectoryName($destination)) $directorySecurity
  [IO.File]::Copy((Join-Path $bundle $file.name),$destination,[bool]$Repair)
  $acl=Get-Acl -LiteralPath $destination; $acl.SetOwner($owner); Set-Acl -LiteralPath $destination -AclObject $acl
 }
 $assembly=Join-Path $base 'camera_driver_native.dll'
 if ($Repair -and (Test-Path -LiteralPath $assembly)) { Remove-Item -LiteralPath $assembly -Force }
 Add-Type -Path (Join-Path $base 'camera_port.cs') -OutputAssembly $assembly -OutputType Library
 $allFiles=@($manifest.files)+@([pscustomobject]@{name='camera_driver_native.dll';bytes=(Get-Item -LiteralPath $assembly).Length;sha256=(Get-FileHash -LiteralPath $assembly -Algorithm SHA256).Hash})
 $configuration=[ordered]@{schema=1;user_sid=$sid;camera_instance_sha256=$bodyHash;files=$allFiles;task_folder=('\M4CameraTool\'+$sid);modes=@('SelfTest','StageBind','Restore');triggers=@()}
 $configPath=Join-Path $base 'deployment.private.json'
 $configuration | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $configPath -Encoding UTF8
 foreach ($path in @($assembly,$configPath,(Join-Path $base 'operation.lock'))) {
  $acl=Get-Acl -LiteralPath $path; $acl.SetOwner($owner); Set-Acl -LiteralPath $path -AclObject $acl
 }
 }
 # Reuse a matching task directory and register only missing tasks. Its name
 # alone is never evidence that deleting tasks is safe.
 $rootFolder=$service.GetFolder('\')
 $parentFolder=Get-SetupTaskFolder $service '\M4CameraTool'
 if (-not $parentFolder) { $parentFolder=$rootFolder.CreateFolder('M4CameraTool','O:BAG:SYD:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;GRGX;;;BU)') }
 $sddl='O:BAG:SYD:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;GRGX;;;'+$sid+')'
 if (-not $folder) { $folder=$parentFolder.CreateFolder($sid,$sddl) }
 foreach ($mode in @('SelfTest','StageBind','Restore')) {
  $present=@($existingTasks | Where-Object Name -EQ $mode)
  if (-not $Repair -and $present.Count) { $present[0].Enabled=$true;continue }
  $task=$service.NewTask(0)
  $task.RegistrationInfo.Description='User-authorized fixed Sony camera driver maintenance; no schedule or arbitrary commands.'
  $task.Principal.UserId=$sid; $task.Principal.LogonType=3; $task.Principal.RunLevel=1
  $task.Settings.Enabled=$true; $task.Settings.AllowDemandStart=$true; $task.Settings.Hidden=$false
  $task.Settings.DisallowStartIfOnBatteries=$false; $task.Settings.StopIfGoingOnBatteries=$false
  $task.Settings.StartWhenAvailable=$false; $task.Settings.WakeToRun=$false
  $task.Settings.MultipleInstances=2; $task.Settings.ExecutionTimeLimit='PT10M'
  $action=$task.Actions.Create(0); $action.Path=$powershell; $action.WorkingDirectory=$base
  $action.Arguments='-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "'+(Join-Path $base 'worker.ps1')+'" -Mode '+$mode
  $registrationFlags=if ($Repair) { 0x16 } else { 0x12 }
  $registered=$folder.RegisterTaskDefinition($mode,$task,$registrationFlags,$sid,$null,3,$sddl)
  $registered.SetSecurityDescriptor($sddl,0x10)
 }
 $outcome.status='INSTALLED'; $outcome.base=$base; $outcome.task_folder=$configuration.task_folder
 $outcome.modes=$configuration.modes; $outcome.no_triggers=$true
} catch { $outcome.status='FAILED'; $outcome.error=$_.Exception.Message }
finally {
 if ($repairLock) { $repairLock.Dispose() }
 if ($setupLock) { $setupLock.Dispose() }
 $outcome.finished_utc=[DateTime]::UtcNow.ToString('o'); $outcome | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $receipt -Encoding UTF8
}
return [pscustomobject]$outcome

}
$result=Install-M4Broker -BundlePath $BundlePath -ManifestSha256 $ManifestSha256 -Repair:$Repair
if($result.status -eq 'FAILED'){exit 1}
