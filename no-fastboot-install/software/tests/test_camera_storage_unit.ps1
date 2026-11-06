param([Parameter(Mandatory=$true)][string]$Source)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
. $Source
$camera='USB\VID_054C&PID_0DA5\INERT-CAMERA'
$script:volumes=@([pscustomobject]@{DriveLetter='I';FileSystemLabel=''},[pscustomobject]@{DriveLetter='J';FileSystemLabel='PMHOME'})
$script:parents=@{'USBSTOR\CAMERA\INERT'=$camera;'USBSTOR\OTHER\INERT'='USB\VID_0000&PID_0001\OTHER'}
$script:accessible=@{'I:\'=$true;'J:\'=$true}
$script:ambiguous=$false
function Get-Volume { $script:volumes }
function Get-Partition {
    [CmdletBinding()]param([string]$DriveLetter)
    [pscustomobject]@{DiskNumber=if($DriveLetter -eq 'I'){2}else{3}}
}
function Get-Disk {
    [CmdletBinding()]param([Parameter(ValueFromPipeline=$true)]$InputObject)
    process { [pscustomobject]@{Number=$InputObject.DiskNumber;BusType='USB'} }
}
function Get-CimInstance {
    param([string]$ClassName)
    if($ClassName -ne 'Win32_DiskDrive'){throw 'Unexpected Windows query in fixture'}
    [pscustomobject]@{Index=2;PNPDeviceID='USBSTOR\CAMERA\INERT'}
    [pscustomobject]@{Index=3;PNPDeviceID='USBSTOR\OTHER\INERT'}
    if($script:ambiguous){[pscustomobject]@{Index=2;PNPDeviceID='USBSTOR\AMBIGUOUS\INERT'}}
}
function Get-PnpDeviceProperty {
    [CmdletBinding()]param([string]$InstanceId,[string]$KeyName)
    if($KeyName -ne 'DEVPKEY_Device_Parent'){throw 'Unexpected PnP property in fixture'}
    if($script:parents.ContainsKey($InstanceId)){[pscustomobject]@{Data=$script:parents[$InstanceId]}}
}
function Test-Path {
    param([string]$LiteralPath,[string]$PathType)
    if($PathType -ne 'Container'){throw 'Unexpected path query'}
    [bool]$script:accessible[$LiteralPath]
}
$checks=New-Object Collections.Generic.List[string]
$rows=@(Get-CameraStorageVolumes -InstanceId $camera)
if($rows.Count -ne 1 -or $rows[0].drive_letter -ne 'I' -or -not $rows[0].root_accessible){throw 'Unlabelled camera card was not accepted'}
$checks.Add('unlabelled_exfat_camera_card_is_accepted')
if(@($rows | Where-Object label -EQ 'PMHOME').Count){throw 'Unrelated PMHOME was accepted'}
$checks.Add('foreign_pmhome_is_not_camera_evidence')
$script:accessible['I:\']=$false
$rows=@(Get-CameraStorageVolumes -InstanceId $camera)
if($rows.Count -ne 1 -or $rows[0].root_accessible){throw 'Unreadable root was accepted'}
$checks.Add('unreadable_camera_root_remains_unready')
$script:accessible['I:\']=$true
$script:parents['USBSTOR\CAMERA\INERT']='USBSTOR\CAMERA\INERT'
if(@(Get-CameraStorageVolumes -InstanceId $camera).Count){throw 'Cyclic ancestry was accepted'}
$checks.Add('cyclic_ancestry_terminates_without_acceptance')
$script:parents['USBSTOR\CAMERA\INERT']=$camera.ToLowerInvariant()
if(@(Get-CameraStorageVolumes -InstanceId $camera).Count -ne 1){throw 'Windows case-insensitive identity failed'}
$checks.Add('pnp_identity_comparison_is_case_insensitive')
$script:ambiguous=$true
if(@(Get-CameraStorageVolumes -InstanceId $camera).Count){throw 'Ambiguous disks were accepted'}
$checks.Add('ambiguous_disk_mapping_is_rejected')
$rejected=$false
try {Get-CameraStorageVolumes -InstanceId 'USB\VID_054C&PID_0336\INERT'}catch{$rejected=$true}
if(-not $rejected){throw 'Service identity was accepted'}
$checks.Add('service_mode_is_not_normal_storage')
# Load only this pure predicate from the worker AST; never execute its privileged
# entry point, scheduler, native assembly, storage query or driver operations.
$worker=Join-Path (Split-Path -Parent (Split-Path -Parent $Source)) 'driver\worker.ps1'
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($worker,[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Worker parse failed'}
$definition=@($ast.FindAll({param($n)$n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Test-BrokerRecoveredFacts'},$true))
if($definition.Count -ne 1){throw 'Recovery predicate missing'}
. ([scriptblock]::Create($definition[0].Extent.Text))
$facts=@{original_task_matches_index=$true;original_status='NEEDS_REVIEW';original_mode='Restore';original_error='Restore helper returned 1';
 original_mutation_started=$true;detail_status='failed';detail_error='USBSTOR/camera storage did not become accessible within the postcondition deadline.';
 uninstall_exit_code=0;port_cycle_attempts=1;port_cycle_count=1;same_body=$true;current_storage=$true;package_absent=$true;camera_storage_count=2}
if(-not (Test-BrokerRecoveredFacts $facts)){throw 'Two accessible card volumes were refused'}
$facts.detail_error='USBSTOR/PMHOME did not become accessible within the postcondition deadline.'
if(-not (Test-BrokerRecoveredFacts $facts)){throw 'Legacy failed-run evidence was refused'}
$checks.Add('broker_confirms_same_body_cards_with_legacy_or_new_deadline_evidence')
foreach($field in @('same_body','package_absent','current_storage','original_task_matches_index','original_mutation_started')){
 $facts[$field]=$false
 if(Test-BrokerRecoveredFacts $facts){throw ('Unsafe recovery confirmation accepted: '+$field)}
 $facts[$field]=$true
}
$facts.camera_storage_count=0
if(Test-BrokerRecoveredFacts $facts){throw 'Missing camera storage accepted'}
$facts.camera_storage_count=1;$facts.detail_error='unrelated failure'
if(Test-BrokerRecoveredFacts $facts){throw 'Unrelated failure accepted'}
$checks.Add('broker_preserves_identity_package_original_evidence_and_failure_guards')
$restart=Join-Path (Split-Path -Parent (Split-Path -Parent $Source)) 'workflow\driver_restart.ps1'
$restartAst=[Management.Automation.Language.Parser]::ParseFile($restart,[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Restart helper parse failed'}
$assignment=@($restartAst.FindAll({param($n)$n -is [Management.Automation.Language.AssignmentStatementAst] -and $n.Left.Extent.Text -eq '$storage'},$true))
$condition=@($restartAst.FindAll({param($n)$n -is [Management.Automation.Language.IfStatementAst] -and $n.Clauses[0].Item1.Extent.Text -like '*$storage.Count -eq 0*'},$true))
if($assignment.Count -ne 1 -or $condition.Count -ne 1){throw 'Restart storage check missing'}
$instance=$camera;$camera=@([pscustomobject]@{Status='OK'})
$driver='USBSTOR';$inf='usbstor.inf';$packageAbsent=$true;$script:ambiguous=$false
$script:parents['USBSTOR\CAMERA\INERT']=$instance
foreach($label in @('PMHOME','','MY-CARD')){
 $script:volumes=@([pscustomobject]@{DriveLetter='I';FileSystemLabel=$label})
 . ([scriptblock]::Create($assignment[0].Extent.Text))
 if(& ([scriptblock]::Create($condition[0].Clauses[0].Item1.Extent.Text))){throw 'Restart refused readable same-body card'}
}
$script:accessible['I:\']=$false
. ([scriptblock]::Create($assignment[0].Extent.Text))
if(-not (& ([scriptblock]::Create($condition[0].Clauses[0].Item1.Extent.Text)))){throw 'Restart accepted unreadable card'}
$checks.Add('post_restart_accepts_camera_storage_without_label_and_rejects_unreadable_root')
$stagePredicate=@($restartAst.FindAll({param($n)$n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Test-StageBindRestartRequired'},$true))
if($stagePredicate.Count -ne 1){throw 'StageBind restart predicate missing'}
. ([scriptblock]::Create($stagePredicate[0].Extent.Text))
$stage=@{mode='StageBind';status='WINUSB_BOUND';reboot_required=$true;finished_utc='2026-01-02T12:00:00Z'}
if(-not (Test-StageBindRestartRequired $stage ([datetime]'2026-01-02T10:00:00Z'))){throw 'Pending StageBind restart ignored'}
if(Test-StageBindRestartRequired $stage ([datetime]'2026-01-02T13:00:00Z')){throw 'Completed Windows restart ignored'}
$stage.reboot_required=$false
if(Test-StageBindRestartRequired $stage ([datetime]'2026-01-02T10:00:00Z')){throw 'Unneeded restart requested'}
$checks.Add('stagebind_restart_wait_survives_reopen_and_clears_after_windows_boot')
@{passed=$true;cases=$checks.Count;tests=@($checks);device_operations=0;driver_tasks_dispatched=0} | ConvertTo-Json -Compress
