param([Parameter(Mandatory=$true)][string]$Package,[Parameter(Mandatory=$true)][string]$Bundle)
$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$taskRoot=Join-Path $env:TEMP ('m4-fresh-'+[Guid]::NewGuid().ToString('N').Substring(0,8))
[IO.Directory]::CreateDirectory($taskRoot)|Out-Null
$taskOldProgramData=$env:ProgramData
$taskSid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$global:m4Clean_sid=$taskSid
$global:m4Clean_principalName=[Security.Principal.WindowsIdentity]::GetCurrent().Name
$taskChecks=New-Object Collections.Generic.List[string]
# Load the entire installer entry function. Only Windows API boundaries below
# are substituted; manifest validation, file copies, locks, retry decisions,
# configuration writes, task construction and enrollment run unchanged.
$taskTokens=$null;$taskErrors=$null
$taskAst=[Management.Automation.Language.Parser]::ParseFile((Join-Path $Package 'app/driver/install_broker.ps1'),[ref]$taskTokens,[ref]$taskErrors)
if($taskErrors.Count){throw ($taskErrors|Out-String)}
foreach($definition in $taskAst.FindAll({param($n)$n -is [Management.Automation.Language.FunctionDefinitionAst]},$false)){
 . ([scriptblock]::Create($definition.Extent.Text))
}
function New-FakeActions {
 $a=[pscustomobject]@{Count=0;Items=(New-Object Collections.ArrayList)}
 $a|Add-Member ScriptMethod Create {param($Type)
  $v=[pscustomobject]@{Type=$Type;Path='';WorkingDirectory='';Arguments=''}
  [void]$this.Items.Add($v);$this.Count++;return $v
 }
 $a|Add-Member ScriptMethod Item {param($Index)return $this.Items[$Index-1]}
 return $a
}
function New-FakeDefinition {
 return [pscustomobject]@{
  RegistrationInfo=[pscustomobject]@{Description=''}
  Principal=[pscustomobject]@{UserId='';LogonType=0;RunLevel=0}
  Settings=[pscustomobject]@{Enabled=$true;AllowDemandStart=$true;Hidden=$false;DisallowStartIfOnBatteries=$false;
   StopIfGoingOnBatteries=$false;StartWhenAvailable=$false;WakeToRun=$false;MultipleInstances=2;ExecutionTimeLimit=''}
  Actions=(New-FakeActions);Triggers=[pscustomobject]@{Count=0}
 }
}
function New-FakeFolder([string]$Path) {
 $f=[pscustomobject]@{Path=$Path;Tasks=@{}}
 $f|Add-Member ScriptMethod GetTasks {param($Flags)return @($this.Tasks.Values)}
 $f|Add-Member ScriptMethod CreateFolder {param($Name,$Security)
  $p=if($this.Path -eq '\'){'\'+$Name}else{$this.Path+'\'+$Name}
  if($global:m4Clean_folders.ContainsKey($p)){throw 'Fixture folder already exists'}
  $global:m4Clean_folderCreates++;return New-FakeFolder $p
 }
 $f|Add-Member ScriptMethod RegisterTaskDefinition {param($Name,$Definition,$Flags,$User,$Password,$Logon,$Security)
  if($Name -eq $global:m4Clean_failTask){throw 'Fixture interrupted registration'}
  if($this.Tasks.ContainsKey($Name) -and $Flags -eq 0x12){throw 'Fixture duplicate task registration'}
  $global:m4Clean_registrations++
  # Windows Task Scheduler reads a SID registration back as an account name.
  $Definition.Principal.UserId=$global:m4Clean_principalName
  $t=[pscustomobject]@{Name=$Name;State=3;Enabled=$true;Definition=$Definition}
  $t|Add-Member ScriptMethod SetSecurityDescriptor {param($Security,$Flags)}
  $this.Tasks[$Name]=$t;return $t
 }
 # Deleting a task/folder is not an allowed recovery mechanism in these tests.
 $f|Add-Member ScriptMethod DeleteTask {throw 'Task deletion is forbidden'}
 $f|Add-Member ScriptMethod DeleteFolder {throw 'Folder deletion is forbidden'}
 $global:m4Clean_folders[$Path]=$f;return $f
}
function Get-SetupContext {return @{sid=$global:m4Clean_sid;administrator=$true;common=(Join-Path $env:ProgramData 'M4CameraTool')}}
function New-SetupScheduler {return $global:m4Clean_scheduler}
function New-SetupDirectory([string]$Path,$Security){[IO.Directory]::CreateDirectory($Path)|Out-Null}
function Get-Acl {param($LiteralPath)
 $acl=[pscustomobject]@{}
 $acl|Add-Member ScriptMethod GetOwner {param($Type)return [pscustomobject]@{Value='S-1-5-32-544'}}
 $acl|Add-Member ScriptMethod SetOwner {param($Owner)}
 return $acl
}
function Set-Acl {param($LiteralPath,$AclObject)
 if(-not ([IO.Path]::GetFullPath($LiteralPath)).StartsWith($taskRoot,[StringComparison]::OrdinalIgnoreCase)){throw 'Host ACL change forbidden'}
}
function Add-Type {param($Path,$OutputAssembly,$OutputType)
 if(-not $OutputAssembly -or -not $OutputAssembly.StartsWith($taskRoot,[StringComparison]::OrdinalIgnoreCase)){throw 'Host assembly operation forbidden'}
 [IO.File]::WriteAllBytes($OutputAssembly,[byte[]]@(1,2,3,4));$global:m4Clean_compilations++
}
function Get-PnpDevice {param([switch]$PresentOnly)
 $global:m4Clean_pnpReads++
 if($global:m4Clean_pnpReads -lt $global:m4Clean_appearAfter){return @()}
 return [pscustomobject]@{InstanceId=$global:m4Clean_camera;Status='OK'}
}
function Get-PnpDeviceProperty {param($InstanceId,$KeyName)
 return [pscustomobject]@{Data=$(if($KeyName -eq 'DEVPKEY_Device_Service'){'USBSTOR'}else{'usbstor.inf'})}
}
function Start-Process {param($FilePath,$ArgumentList,$Verb,$WindowStyle,[switch]$PassThru,[switch]$Wait)
 if($WindowStyle -ne 'Hidden' -or $ArgumentList -notmatch '-BundlePath "([^"]+)" -ManifestSha256 ([0-9a-fA-F]{64})'){throw 'Unexpected enrollment process'}
 $r=Install-M4Broker -BundlePath $Matches[1] -ManifestSha256 $Matches[2]
 return [pscustomobject]@{ExitCode=$(if($r.status -eq 'INSTALLED'){0}else{1})}
}
function Get-Volume {throw 'Host storage query forbidden'}
function Reset-Fixture([string]$Name){
 $env:ProgramData=Join-Path $taskRoot $Name
 $global:m4Clean_folders=@{};$global:m4Clean_registrations=0;$global:m4Clean_compilations=0;$global:m4Clean_folderCreates=0
 $global:m4Clean_failTask='';$global:m4Clean_camera='USB\VID_054C&PID_0DA5\FIXTURE';$global:m4Clean_pnpReads=0;$global:m4Clean_appearAfter=0
 $global:m4Clean_driverStore=@{};$global:m4Clean_certificateStores=@{Root=@{};TrustedPublisher=@{}}
 $global:m4Clean_scheduler=[pscustomobject]@{}
 $global:m4Clean_scheduler|Add-Member ScriptMethod GetFolder {param($Path)
  if(-not $global:m4Clean_folders.ContainsKey($Path)){throw [Runtime.InteropServices.COMException]::new('Fixture missing folder',-2147024894)}
  return $global:m4Clean_folders[$Path]
 }
 $global:m4Clean_scheduler|Add-Member ScriptMethod NewTask {param($Flags)return New-FakeDefinition}
 $null=New-FakeFolder '\'
 if((Test-Path -LiteralPath $env:ProgramData) -or $global:m4Clean_driverStore.Count -ne 0 -or $global:m4Clean_certificateStores.Root.Count -ne 0){throw 'Fixture did not start as a clean machine'}
}
function Invoke-Attempt([switch]$Repair) {
 $attempt=Join-Path $taskRoot ('bundle_'+[Guid]::NewGuid().ToString('N').Substring(0,8))
 [IO.Directory]::CreateDirectory($attempt)|Out-Null
 Copy-Item -Path (Join-Path $Bundle '*') -Destination $attempt -Recurse
 $h=(Get-FileHash -LiteralPath (Join-Path $attempt 'bundle_manifest.json') -Algorithm SHA256).Hash
 $result=Install-M4Broker -BundlePath $attempt -ManifestSha256 $h -Repair:$Repair
 $global:m4Clean_lastReceipt=Join-Path $attempt 'installation.private.json'
 return $result
}
function Require-Installed($Result){if($Result.status -ne 'INSTALLED'){throw ('Setup failed: '+$Result.error)}}
try {
 Reset-Fixture 'clean'
 $r=Invoke-Attempt;Require-Installed $r
 if($global:m4Clean_registrations -ne 3 -or $global:m4Clean_compilations -ne 1 -or $global:m4Clean_driverStore.Count -or $global:m4Clean_certificateStores.Root.Count){throw 'Clean setup depends on prior tasks/drivers/certificates'}
 $taskChecks.Add('complete_installer_from_no_data_no_tasks_no_driver_packages_no_certificates')
 $base=Join-Path (Get-SetupContext).common $taskSid
 $cfg=Join-Path $base 'deployment.private.json';$before=(Get-FileHash -LiteralPath $cfg).Hash
 $config=Get-Content -LiteralPath $cfg -Raw | ConvertFrom-Json
 $storageFiles=@($config.files | Where-Object name -EQ 'camera_storage.ps1')
 if($storageFiles.Count -ne 1 -or
    (Get-FileHash -LiteralPath (Join-Path $base 'camera_storage.ps1')).Hash -ne $storageFiles[0].sha256 -or
    (Get-FileHash -LiteralPath (Join-Path $base 'camera_storage.ps1')).Hash -ne
    (Get-FileHash -LiteralPath (Join-Path $Package 'app/driver_restore/camera_storage.ps1')).Hash){throw 'Storage helper was not copied and pinned in the protected bundle'}
 $taskChecks.Add('storage_helper_is_included_hashed_and_installed_before_restore')
 $cleanTasks=$global:m4Clean_folders['\M4CameraTool\'+$taskSid].Tasks
 if($cleanTasks.SelfTest.Definition.Principal.UserId -eq $taskSid){throw 'Fixture failed to emulate real Windows account-name readback'}
 $r=Invoke-Attempt;Require-Installed $r
 if(-not $r.reused_installation -or $global:m4Clean_registrations -ne 3 -or $global:m4Clean_compilations -ne 1 -or (Get-FileHash -LiteralPath $cfg).Hash -ne $before){throw 'Repeat setup replaced known configuration or tasks'}
 $taskChecks.Add('repeat_setup_accepts_scheduler_account_name_and_preserves_installation')
 $cleanTasks.SelfTest.Definition.Principal.UserId=$taskSid
 $r=Invoke-Attempt;Require-Installed $r
 if(@($r.task_checks|Where-Object{$_.failed_fields.Count}).Count){throw 'SID-form readback was rejected'}
 $taskChecks.Add('sid_form_and_account_name_form_identify_the_same_authorized_user')
 $cleanTasks.SelfTest.Definition.Principal.UserId='S-1-5-32-544'
 $r=Invoke-Attempt
 $mismatch=@($r.task_checks|Where-Object task -EQ 'SelfTest')[0]
 if($r.status -ne 'FAILED' -or $mismatch.failed_fields -notcontains 'user_sid' -or -not $mismatch.principal_resolved){throw 'Different resolved principal was accepted or not diagnosed'}
 $saved=Get-Content -LiteralPath $global:m4Clean_lastReceipt -Raw|ConvertFrom-Json
 if(@($saved.task_checks|Where-Object task -EQ 'SelfTest')[0].failed_fields -notcontains 'user_sid'){throw 'Mismatch details were not persisted in the installation receipt'}
 if((Get-FileHash -LiteralPath $cfg).Hash -ne $before){throw 'Rejected principal changed configuration'}
 $taskChecks.Add('different_resolved_principal_is_rejected_with_user_sid_difference')
 $cleanTasks.SelfTest.Definition.Principal.UserId=''
 $r=Invoke-Attempt
 $mismatch=@($r.task_checks|Where-Object task -EQ 'SelfTest')[0]
 if($r.status -ne 'FAILED' -or $mismatch.principal_resolved -or $mismatch.failed_fields -notcontains 'user_sid'){throw 'Missing principal was accepted or not diagnosed'}
 $taskChecks.Add('unresolved_principal_is_rejected_without_weakening_user_binding')
 $cleanTasks.SelfTest.Definition.Principal.UserId=$global:m4Clean_principalName
 $operation=Join-Path $base 'operation.lock'
 $held=[IO.File]::Open($operation,'Open','ReadWrite','None')
 try{$r=Invoke-Attempt;if($r.status -ne 'FAILED'){throw 'Running operation was ignored'}}finally{$held.Dispose()}
 if((Get-FileHash -LiteralPath $cfg).Hash -ne $before){throw 'Busy operation changed configuration'}
 $taskChecks.Add('held_operation_lock_prevents_setup_changes')

 Reset-Fixture 'folder'
 $null=New-FakeFolder '\M4CameraTool';$null=New-FakeFolder ('\M4CameraTool\'+$taskSid)
 $r=Invoke-Attempt;Require-Installed $r
 if($global:m4Clean_folderCreates -ne 0 -or $global:m4Clean_registrations -ne 3){throw 'Empty existing task folder was deleted or rejected'}
 $taskChecks.Add('existing_empty_task_folder_is_reused_without_deletion')

 Reset-Fixture 'partial'
 $base=Join-Path (Get-SetupContext).common $taskSid
 [IO.Directory]::CreateDirectory((Join-Path $base 'driver'))|Out-Null
 [IO.File]::WriteAllText((Join-Path $base 'driver/partial.txt'),'preserve partial installation')
 $r=Invoke-Attempt;Require-Installed $r
 if(-not (Test-Path -LiteralPath (Join-Path $r.relocated_failed_install 'driver/partial.txt'))){throw 'Incomplete files were not preserved'}
 $taskChecks.Add('copy_interrupted_before_configuration_is_preserved_and_restarted')

 Reset-Fixture 'repair'
 $base=Join-Path (Get-SetupContext).common $taskSid
 [IO.Directory]::CreateDirectory((Join-Path $base 'driver'))|Out-Null
 $r=Invoke-Attempt -Repair;Require-Installed $r
 if(-not (Test-Path -LiteralPath (Join-Path $base 'operation.lock'))){throw 'Explicit repair of an incomplete setup omitted its lock'}
 $taskChecks.Add('explicit_repair_of_partial_installation_creates_and_holds_operation_lock')

 Reset-Fixture 'tasks'
 $global:m4Clean_failTask='StageBind';$r=Invoke-Attempt
 if($r.status -ne 'FAILED' -or $global:m4Clean_registrations -ne 1){throw 'Fixture did not stop after first task'}
 $base=Join-Path (Get-SetupContext).common $taskSid
 $cfg=Join-Path $base 'deployment.private.json';$before=(Get-FileHash -LiteralPath $cfg).Hash
 $global:m4Clean_failTask='';$r=Invoke-Attempt;Require-Installed $r
 if($global:m4Clean_registrations -ne 3 -or $global:m4Clean_compilations -ne 1 -or (Get-FileHash -LiteralPath $cfg).Hash -ne $before){throw 'Partial task registration did not resume precisely'}
 $taskChecks.Add('registration_interrupted_after_selftest_resumes_only_missing_tasks')
 $folder=$global:m4Clean_folders['\M4CameraTool\'+$taskSid]
 $folder.Tasks.SelfTest.State=4;$r=Invoke-Attempt
 if($r.status -ne 'FAILED' -or $r.error -notlike '*task is running*' -or (Get-FileHash -LiteralPath $cfg).Hash -ne $before){throw 'Running task treated as an orphan'}
 $folder.Tasks.SelfTest.State=3
 $taskChecks.Add('running_task_never_relocates_configuration_or_removes_tasks')
 $folder.Tasks.SelfTest.Definition.Actions.Item(1).Path='C:\Windows\notepad.exe'
 $r=Invoke-Attempt
 if($r.status -ne 'FAILED' -or $r.error -notlike '*Unexpected task definition*'){throw 'Task names alone were trusted'}
 $mismatch=@($r.task_checks|Where-Object task -EQ 'SelfTest')[0]
 if($mismatch.failed_fields -notcontains 'action_path'){throw 'Wrong executable path was not diagnosed'}
 $taskChecks.Add('same_name_with_different_action_is_preserved_and_rejected')

 Reset-Fixture 'records'
 $base=Join-Path (Get-SetupContext).common $taskSid
 [IO.Directory]::CreateDirectory((Join-Path $base 'state'))|Out-Null
 $record=Join-Path $base 'latest_StageBind.json';[IO.File]::WriteAllText($record,'{"status":"RUNNING"}')
 $r=Invoke-Attempt
 if($r.status -ne 'FAILED' -or -not (Test-Path -LiteralPath $record) -or $global:m4Clean_registrations){throw 'Unknown operation was reset as partial setup'}
 $taskChecks.Add('configuration_missing_with_operation_evidence_is_not_erased')

 Reset-Fixture 'delayed'
 $global:m4Clean_appearAfter=3;$r=Invoke-Attempt;Require-Installed $r
 if($global:m4Clean_pnpReads -le 2){throw 'Delayed first enumeration was not waited for'}
 $taskChecks.Add('first_camera_enumeration_can_arrive_after_initial_scan')

 Reset-Fixture 'enroll'
 $r=Invoke-Attempt;Require-Installed $r
 $folder=$global:m4Clean_folders['\M4CameraTool\'+$taskSid];$folder.Tasks.Remove('Restore')
 $before=$global:m4Clean_registrations
 $attempt=Join-Path $taskRoot 'enroll_bundle';[IO.Directory]::CreateDirectory($attempt)|Out-Null
 Copy-Item -Path (Join-Path $Bundle '*') -Destination $attempt -Recurse
 $h=(Get-FileHash -LiteralPath (Join-Path $attempt 'bundle_manifest.json') -Algorithm SHA256).Hash.ToLowerInvariant()
 $out=Join-Path $taskRoot 'enrollment.json'
 $null=& (Join-Path $Package 'app/workflow/enroll.ps1') -Bundle $attempt -BundleHash $h -Installer (Join-Path $Package 'app/driver/install_broker.ps1') -Output $out
 $binding=Get-Content -LiteralPath $out -Raw|ConvertFrom-Json
 if($binding.schema -ne 'm4-user-enrollment/1' -or $global:m4Clean_registrations -ne $before+1 -or $folder.Tasks.Count -ne 3){throw 'Enrollment skipped incomplete task setup because config existed'}
 $taskChecks.Add('complete_enrollment_repairs_missing_task_even_when_configuration_exists')

 @{passed=$true;cases=$taskChecks.Count;tests=@($taskChecks);fixture_start='no_tool_data_no_tasks_no_related_drivers_no_certificates';
  full_installer_exercised=$true;full_enrollment_exercised=$true;real_windows_acl_tested=$false;real_scheduler_tested=$false;
  device_operations=0;driver_tasks_dispatched=0;host_certificate_changes=0;host_task_changes=0;fixture_root=$taskRoot}|ConvertTo-Json -Depth 6 -Compress
}finally{$env:ProgramData=$taskOldProgramData;Remove-Variable -Name 'm4Clean_*' -Scope Global -ErrorAction SilentlyContinue}
