param([Parameter(Mandatory=$true)][string]$Package)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
$target=Join-Path $Package 'app/workflow/driver_restart.ps1'
$testRoot=Join-Path ([IO.Path]::GetTempPath()) ('m4_restart_test_'+[Guid]::NewGuid().ToString('N'))
$oldProgramData=$env:ProgramData
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$instance='USB\VID_054C&PID_0DA5\offline'
$sha=[Security.Cryptography.SHA256]::Create()
try{$body=[BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($instance.ToUpperInvariant()))).Replace('-','').ToLowerInvariant()}finally{$sha.Dispose()}
$global:m4FixtureBoot=[DateTime]::Parse('2020-01-01T00:00:00Z').ToUniversalTime()
$global:m4FixtureReady=$true
function Get-CimInstance {
 param($ClassName)
 if($ClassName -eq 'Win32_OperatingSystem'){return [pscustomobject]@{LastBootUpTime=$global:m4FixtureBoot}}
 if($ClassName -eq 'Win32_DiskDrive'){return [pscustomobject]@{Index=7;PNPDeviceID=$instance}}
 throw 'Offline fixture cannot query another WMI class.'
}
function Get-PnpDevice {param([switch]$PresentOnly);[pscustomobject]@{InstanceId=$instance;Status='OK'}}
function Get-PnpDeviceProperty {
 param($InstanceId,$KeyName,$ErrorAction)
 if($KeyName -eq 'DEVPKEY_Device_Service'){return [pscustomobject]@{Data=$(if($global:m4FixtureReady){'USBSTOR'}else{'WinUSB'})}}
 if($KeyName -eq 'DEVPKEY_Device_DriverInfPath'){return [pscustomobject]@{Data=$(if($global:m4FixtureReady){'usbstor.inf'}else{'oem88.inf'})}}
 throw 'Offline fixture cannot query another PnP property.'
}
function Get-Volume {[pscustomobject]@{FileSystemLabel='PMHOME';DriveLetter='M4Fixture'}}
function Get-Partition {param($DriveLetter);[pscustomobject]@{DiskNumber=7}}
function Get-Disk {param([Parameter(ValueFromPipeline=$true)]$InputObject);process{[pscustomobject]@{Number=7}}}
function Write-Fixture($path,$value){[IO.File]::WriteAllText($path,($value|ConvertTo-Json -Depth 8),(New-Object Text.UTF8Encoding($false)))}
try {
 New-Item -ItemType Directory -Path $testRoot|Out-Null
 $env:ProgramData=Join-Path $testRoot 'ProgramData'
 New-PSDrive -Name M4Fixture -PSProvider FileSystem -Root $testRoot|Out-Null
 $base=Join-Path $env:ProgramData ('M4CameraTool\'+$sid)
 $sourceRun='11223344556677889900aabbccddeeff'
 $folder=Join-Path $base ('state\'+$sourceRun)
 New-Item -ItemType Directory -Path $folder -Force|Out-Null
 [IO.File]::WriteAllText((Join-Path $base 'operation.lock'),'lock')
 Write-Fixture (Join-Path $base 'deployment.private.json') @{user_sid=$sid;camera_instance_sha256=$body}
 $record=@{schema=1;run_id=$sourceRun;mode='Restore';status='NEEDS_REVIEW';device_mutation_started=$true;
  before=@{instance=$instance};error='Restore helper returned 1';finished_utc='2020-01-02T00:00:00Z'}
 $detail=@{status='failed';uninstall_exit_code=3010;before=@{instance=$instance};package='oem99999999.inf';error='Driver uninstall returned 3010.'}
 $index=Join-Path $base 'latest_Restore.json';$original=Join-Path $folder 'task_result.json';$detailPath=Join-Path $folder 'auto_restore_result.private.json'
 Write-Fixture $original $record;Copy-Item -LiteralPath $original -Destination $index
 Write-Fixture $detailPath $detail
 $originalHash=(Get-FileHash -LiteralPath $original).Hash
 $result=& $target -Mode Inspect|ConvertFrom-Json
 if($result.phase -ne 'WINDOWS_RESTART_REQUIRED'){throw '3010 before reboot was not retained as a restart wait.'}
 $result=& $target -Mode Confirm|ConvertFrom-Json
 if($result.phase -ne 'WINDOWS_RESTART_REQUIRED' -or (Get-FileHash -LiteralPath $index).Hash -ne $originalHash){throw 'Pre-reboot confirmation changed the protected outcome.'}
 $global:m4FixtureBoot=[DateTime]::Parse('2020-01-03T00:00:00Z').ToUniversalTime()
 $result=& $target -Mode Inspect|ConvertFrom-Json
 if($result.phase -ne 'RESTARTED_CONFIRMATION_NEEDED'){throw 'A real boot boundary was ignored.'}
 # Test the post-reboot file transition in a fixture copy: only the administrator/ACL
 # setup is replaced. All writable ProgramData paths stay under this temporary root.
 $fixtureTarget=Join-Path $testRoot 'confirm_fixture.ps1'
 $source=Get-Content -LiteralPath $target -Raw
 $source=$source.Replace("if(-not `$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Open M4 Camera Tool with administrator privileges to confirm the restored connection.'}",'')
 $source=$source.Replace('[IO.Directory]::CreateDirectory($folder,$security)|Out-Null','[IO.Directory]::CreateDirectory($folder)|Out-Null')
 [IO.File]::WriteAllText($fixtureTarget,$source,(New-Object Text.UTF8Encoding($false)))
 $global:m4FixtureReady=$false
 $result=& $fixtureTarget -Mode Confirm|ConvertFrom-Json
 if($result.phase -ne 'RESTARTED_CONNECTION_PENDING' -or (Get-FileHash -LiteralPath $index).Hash -ne $originalHash){throw 'A non-storage connection was confirmed.'}
 $global:m4FixtureReady=$true
 $result=& $fixtureTarget -Mode Confirm|ConvertFrom-Json
 if($result.phase -ne 'DRIVER_RESTART_RECOVERY_VERIFIED'){throw 'Fresh matching storage was not confirmed after reboot.'}
 $current=Get-Content -LiteralPath $index -Raw|ConvertFrom-Json
 if($current.status -ne 'RECOVERY_CONFIRMED' -or $current.device_mutation_started -ne $false -or $current.recovery_confirmation.source_run -ne $sourceRun){throw 'Confirmation was not recorded as a new read-only observation.'}
 if((Get-FileHash -LiteralPath $original).Hash -ne $originalHash){throw 'Original failed task was rewritten.'}
 Copy-Item -LiteralPath $original -Destination $index -Force
 $detail.uninstall_exit_code=5;Write-Fixture $detailPath $detail
 $result=& $target -Mode Inspect|ConvertFrom-Json
 if($result.phase -ne 'CLEAR'){throw 'An unrelated uninstall failure was accepted as 3010.'}
 $detail.uninstall_exit_code=3010;Write-Fixture $detailPath $detail
 Write-Fixture (Join-Path $base 'deployment.private.json') @{user_sid=$sid;camera_instance_sha256=('0'*64)}
 $refused=$false;try{& $target -Mode Inspect|Out-Null}catch{$refused=$true}
 if(-not $refused){throw 'A restoration for another body was accepted.'}
 @{passed=$true;cases=7;device_operations=0;driver_tasks_dispatched=0;fixture_only=$true;real_admin_acl_tested=$false}|ConvertTo-Json -Compress
} finally {
 $env:ProgramData=$oldProgramData
 Remove-PSDrive -Name M4Fixture -ErrorAction SilentlyContinue
 $resolved=[IO.Path]::GetFullPath($testRoot)
 $temp=[IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')+'\'
 if($resolved.StartsWith($temp,[StringComparison]::OrdinalIgnoreCase) -and (Split-Path -Leaf $resolved) -like 'm4_restart_test_*'){
  Remove-Item -LiteralPath $resolved -Recurse -Force
 }
}
