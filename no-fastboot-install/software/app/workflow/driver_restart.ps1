param([ValidateSet('Inspect','Confirm')][string]$Mode='Inspect')
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$sid=$identity.User.Value
$base=Join-Path $env:ProgramData ('M4CameraTool\'+$sid)
$boot=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime()
function Reply($phase,$fields=@{}) {
 $value=@{phase=$phase;boot_utc=$boot.ToString('o');firmware_operations=0;camera_commands=0;driver_changes=0}
 foreach($key in $fields.Keys){$value[$key]=$fields[$key]}
 $value | ConvertTo-Json -Depth 8 -Compress
}
function Hash-Body([string]$instance) {
 $hash=[Security.Cryptography.SHA256]::Create()
 try{return [BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($instance.ToUpperInvariant()))).Replace('-','').ToLowerInvariant()}
 finally{$hash.Dispose()}
}
function Publish-Json([string]$path,$value) {
 $temporary=$path+'.'+[Guid]::NewGuid().ToString('N')+'.next'
 [IO.File]::WriteAllText($temporary,($value|ConvertTo-Json -Depth 12)+"`n",(New-Object Text.UTF8Encoding($false)))
 if(Test-Path -LiteralPath $path){[IO.File]::Replace($temporary,$path,[NullString]::Value)}else{[IO.File]::Move($temporary,$path)}
}
$index=Join-Path $base 'latest_Restore.json'
if(-not(Test-Path -LiteralPath $index)){Reply 'CLEAR';exit 0}
$prior=Get-Content -LiteralPath $index -Raw | ConvertFrom-Json
if($prior.status -notin @('NEEDS_REVIEW','WINDOWS_RESTART_REQUIRED') -or $prior.mode -ne 'Restore' -or $prior.run_id -notmatch '^[0-9a-f]{32}$'){
 Reply 'CLEAR';exit 0
}
$oldFolder=Join-Path (Join-Path $base 'state') $prior.run_id
$original=Join-Path $oldFolder 'task_result.json'
$detailPath=Join-Path $oldFolder 'auto_restore_result.private.json'
if(-not(Test-Path -LiteralPath $detailPath)){Reply 'CLEAR';exit 0}
$detail=Get-Content -LiteralPath $detailPath -Raw | ConvertFrom-Json
if($detail.uninstall_exit_code -ne 3010){Reply 'CLEAR';exit 0}
$config=Get-Content -LiteralPath (Join-Path $base 'deployment.private.json') -Raw | ConvertFrom-Json
$originalHash=(Get-FileHash -LiteralPath $original -Algorithm SHA256).Hash
$indexHash=(Get-FileHash -LiteralPath $index -Algorithm SHA256).Hash
if($config.user_sid -ne $sid -or $originalHash -ne $indexHash -or $prior.device_mutation_started -ne $true -or
 (Hash-Body $detail.before.instance) -ne $config.camera_instance_sha256.ToLowerInvariant() -or
 $prior.before.instance -ne $detail.before.instance -or $detail.package -notmatch '^oem[0-9]+\.inf$'){
 throw 'The saved 3010 restoration does not match its protected task and authorized body.'
}
$finished=[DateTimeOffset]::Parse($prior.finished_utc).UtcDateTime
$facts=@{source_run=$prior.run_id;uninstall_exit_code=3010;boot_utc=$boot.ToString('o');finished_utc=$finished.ToString('o')}
if($boot -le $finished){Reply 'WINDOWS_RESTART_REQUIRED' $facts;exit 0}
if($Mode -eq 'Inspect'){Reply 'RESTARTED_CONFIRMATION_NEEDED' $facts;exit 0}
$principal=New-Object Security.Principal.WindowsPrincipal($identity)
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Open M4 Camera Tool with administrator privileges to confirm the restored connection.'}
$guard=[IO.File]::Open((Join-Path $base 'operation.lock'),[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
try {
 if((Get-FileHash -LiteralPath $index -Algorithm SHA256).Hash -ne $indexHash){throw 'Restore index changed before confirmation.'}
 $devices=@(Get-PnpDevice -PresentOnly)
 $camera=@($devices|Where-Object{$_.InstanceId -like 'USB\VID_054C&PID_0DA5\*'})
 $service=@($devices|Where-Object{$_.InstanceId -like 'USB\VID_054C&PID_0336\*'})
 if($camera.Count -ne 1 -or $service.Count -ne 0){Reply 'RESTARTED_CONNECTION_PENDING' $facts;exit 0}
 $instance=$camera[0].InstanceId
 if((Hash-Body $instance) -ne $config.camera_instance_sha256.ToLowerInvariant()){throw 'The connected camera differs from the protected restoration.'}
 $driver=(Get-PnpDeviceProperty -InstanceId $instance -KeyName DEVPKEY_Device_Service).Data
 $inf=(Get-PnpDeviceProperty -InstanceId $instance -KeyName DEVPKEY_Device_DriverInfPath).Data
 $packageAbsent=-not(Test-Path -LiteralPath (Join-Path (Join-Path $env:SystemRoot 'INF') $detail.package))
 # Records from the service-package era also verify the service INF removal.
 if(@($detail.PSObject.Properties|Where-Object Name -EQ 'svc_package').Count -and $detail.svc_package){
  $packageAbsent=$packageAbsent -and -not(Test-Path -LiteralPath (Join-Path (Join-Path $env:SystemRoot 'INF') $detail.svc_package))
 }
 $pmhome=@(Get-Volume | Where-Object{$_.FileSystemLabel -eq 'PMHOME' -and $_.DriveLetter} | ForEach-Object {
  $volume=$_;$parts=@(Get-Partition -DriveLetter $volume.DriveLetter)
  if($parts.Count -eq 1 -and (Test-Path -LiteralPath ($volume.DriveLetter+':\') -PathType Container)){
   $disk=$parts[0]|Get-Disk;$rows=@(Get-CimInstance Win32_DiskDrive|Where-Object Index -EQ $disk.Number)
   if($rows.Count -eq 1){
    $node=$rows[0].PNPDeviceID
    for($depth=0;$depth -lt 10 -and $node;$depth++){
     if($node -eq $instance){[pscustomobject]@{drive_letter=[string]$volume.DriveLetter;accessible=$true;belongs_to_camera=$true};break}
     $parent=Get-PnpDeviceProperty -InstanceId $node -KeyName DEVPKEY_Device_Parent -ErrorAction SilentlyContinue
     if($parent){$node=$parent.Data}else{$node=$null}
    }
   }
  }
 })
 if($driver -ne 'USBSTOR' -or $inf -ne 'usbstor.inf' -or $camera[0].Status -ne 'OK' -or -not $packageAbsent -or $pmhome.Count -ne 1){
  Reply 'RESTARTED_CONNECTION_PENDING' $facts;exit 0
 }
 $run=[Guid]::NewGuid().ToString('N')
 $folder=Join-Path (Join-Path $base 'state') $run
 $security=New-Object Security.AccessControl.DirectorySecurity
 $security.SetSecurityDescriptorSddlForm(('O:BAG:SYD:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;GRGX;;;'+$sid+')'))
 [IO.Directory]::CreateDirectory($folder,$security)|Out-Null
 Copy-Item -LiteralPath $index -Destination (Join-Path $folder 'original_index.private.json')
 $now=[DateTime]::UtcNow.ToString('o')
 $result=[ordered]@{schema=1;run_id=$run;mode='Restore';status='RECOVERY_CONFIRMED';elevated=$true;
  started_utc=$now;finished_utc=$now;observation_source='m4_tool_post_reboot_confirmation';error=$null;device_mutation_started=$false;
  device_operations=0;firmware_operations=0;camera_commands=0;
  recovery_confirmation=@{source_run=$prior.run_id;source_task_sha256=$originalHash;
   source_detail_sha256=(Get-FileHash -LiteralPath $detailPath -Algorithm SHA256).Hash;
   original_failure_preserved=$true;windows_restarted=$true;boot_utc=$boot.ToString('o');package_absent=$true;pmhome=$pmhome}}
 Publish-Json (Join-Path $folder 'task_result.json') $result
 Publish-Json $index $result
 $facts.confirmation_run=$run
 Reply 'DRIVER_RESTART_RECOVERY_VERIFIED' $facts
} finally {$guard.Dispose()}
