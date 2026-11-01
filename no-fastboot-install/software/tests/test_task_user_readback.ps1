param([Parameter(Mandatory=$true)][string]$Source)
$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
# Read only the current user's existing fixed M4 task definitions. This is an
# API representation check, not a fresh-machine installation test.
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $Source 'app/driver/install_broker.ps1'),[ref]$tokens,[ref]$errors)
if($errors.Count){throw ($errors|Out-String)}
foreach($definition in $ast.FindAll({param($n)$n -is [Management.Automation.Language.FunctionDefinitionAst]},$false)){
 . ([scriptblock]::Create($definition.Extent.Text))
}
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$base=Join-Path ([Environment]::GetFolderPath('CommonApplicationData')) ('M4CameraTool\'+$sid)
$service=New-Object -ComObject 'Schedule.Service';$service.Connect()
$folder=$service.GetFolder('\M4CameraTool\'+$sid)
$before=@($folder.GetTasks(1))
$literalMismatches=@($before|Where-Object{$_.Definition.Principal.UserId -ne $sid}).Count
$diagnostics=New-Object Collections.Generic.List[object]
$shell=Join-Path ([Environment]::SystemDirectory) 'WindowsPowerShell\v1.0\powershell.exe'
$accepted=@(Get-SetupTasks $folder $base $sid $shell -Diagnostics $diagnostics)
if($accepted.Count -ne $before.Count -or $accepted.Count -ne 3 -or $literalMismatches -eq 0){throw 'Real Windows representation regression did not exercise the expected case'}
@{passed=$true;cases=1;scope='read_only_real_windows_task_service';accepted_tasks=$accepted.Count;
 literal_sid_string_mismatches=$literalMismatches;diagnostics=@($diagnostics.ToArray());
 task_changes=0;device_operations=0;fresh_installation_test=$false}|ConvertTo-Json -Depth 8 -Compress
