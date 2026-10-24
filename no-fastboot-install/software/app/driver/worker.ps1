param([Parameter(Mandatory=$true)][ValidateSet('SelfTest','StageBind','Restore')][string]$Mode)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2
$brokerIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$brokerSid = $brokerIdentity.User.Value
$brokerPrincipal = New-Object Security.Principal.WindowsPrincipal($brokerIdentity)
if (-not $brokerPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'The registered administrator task is required.' }
$brokerBase = Join-Path (Join-Path ([Environment]::GetFolderPath('CommonApplicationData')) 'M4CameraTool') $brokerSid
if ([IO.Path]::GetFullPath($PSScriptRoot) -ne [IO.Path]::GetFullPath($brokerBase)) { throw 'Worker must execute from its protected installation.' }
$brokerConfig = Get-Content -LiteralPath (Join-Path $brokerBase 'deployment.private.json') -Raw | ConvertFrom-Json
if ($brokerConfig.user_sid -ne $brokerSid) { throw 'Registered user differs.' }
$brokerExpectedNames = @('worker.ps1','restore_camera_driver.ps1','camera_port.cs','camera_driver_native.dll','driver\ilce-7m4.inf','driver\ILCE-7M4.cat')
if (@($brokerConfig.files).Count -ne $brokerExpectedNames.Count) { throw 'Unexpected trusted file set.' }
foreach ($brokerFile in $brokerConfig.files) {
    if ($brokerFile.name -notin $brokerExpectedNames) { throw 'Unexpected executable dependency.' }
    $brokerPath = Join-Path $brokerBase $brokerFile.name
    if ((Get-Item -LiteralPath $brokerPath).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked executable dependency refused.' }
    if ((Get-FileHash -LiteralPath $brokerPath -Algorithm SHA256).Hash -ne $brokerFile.sha256) { throw 'Installed executable/driver hash differs.' }
}

function New-BrokerDirectory([string]$Path) {
    $security = New-Object Security.AccessControl.DirectorySecurity
    $security.SetSecurityDescriptorSddlForm(('O:BAG:SYD:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;GRGX;;;'+$brokerSid+')'))
    [IO.Directory]::CreateDirectory($Path,$security) | Out-Null
}

function Write-BrokerJson([string]$Path,$Value) {
    $temporary = $Path + '.' + [Guid]::NewGuid().ToString('N') + '.next'
    $security = New-Object Security.AccessControl.FileSecurity
    $security.SetSecurityDescriptorSddlForm(('O:BAG:SYD:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;GR;;;'+$brokerSid+')'))
    $stream = New-Object IO.FileStream($temporary,[IO.FileMode]::CreateNew,[Security.AccessControl.FileSystemRights]::FullControl,[IO.FileShare]::Read,4096,[IO.FileOptions]::None,$security)
    try {
        $bytes = (New-Object Text.UTF8Encoding($false)).GetBytes(($Value | ConvertTo-Json -Depth 12)+"`n")
        $stream.Write($bytes,0,$bytes.Length); $stream.Flush($true)
    } finally { $stream.Dispose() }
    if (Test-Path -LiteralPath $Path) { [IO.File]::Replace($temporary,$Path,[NullString]::Value) } else { [IO.File]::Move($temporary,$Path) }
}

function Get-BrokerCamera {
    $devices = @(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB\VID_054C&PID_0DA5\*' })
    if ($devices.Count -ne 1 -or @(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB\VID_054C&PID_0336\*' }).Count) { throw 'Expected one normal camera and no active service session.' }
    $id=$devices[0].InstanceId
    $digest=[Security.Cryptography.SHA256]::Create()
    try { $bodyHash=[BitConverter]::ToString($digest.ComputeHash([Text.Encoding]::UTF8.GetBytes($id.ToUpperInvariant()))).Replace('-','') } finally { $digest.Dispose() }
    if ($bodyHash -ne $brokerConfig.camera_instance_sha256) { throw 'Connected camera differs from the authorized body.' }
    [pscustomobject]@{instance=$id;service=(Get-PnpDeviceProperty -InstanceId $id -KeyName DEVPKEY_Device_Service).Data;
        inf=(Get-PnpDeviceProperty -InstanceId $id -KeyName DEVPKEY_Device_DriverInfPath).Data;status=$devices[0].Status}
}

function Get-BrokerFailureStatus([string]$Operation,[bool]$MutationStarted,[bool]$PriorUnresolved) {
    if ($Operation -eq 'SelfTest') { return 'FAILED' }
    if ($MutationStarted -or $PriorUnresolved) { return 'NEEDS_REVIEW' }
    return 'REFUSED_BEFORE_CHANGE'
}

function Test-BrokerRecoveredFacts($Facts) {
    return ($Facts.original_task_matches_index -and $Facts.original_status -eq 'NEEDS_REVIEW' -and
        $Facts.original_mode -eq 'Restore' -and $Facts.original_error -eq 'Restore helper returned 1' -and
        $Facts.original_mutation_started -eq $true -and $Facts.detail_status -eq 'failed' -and
        $Facts.detail_error -eq 'USBSTOR/PMHOME did not become accessible within the postcondition deadline.' -and
        $Facts.uninstall_exit_code -eq 0 -and $Facts.port_cycle_attempts -eq 1 -and $Facts.port_cycle_count -eq 1 -and
        $Facts.same_body -and $Facts.current_storage -and $Facts.package_absent -and $Facts.camera_pmhome_count -eq 1)
}

function Get-BrokerRecoveredRestore($Previous,[string]$IndexPath) {
    if ($Previous.run_id -notmatch '^[a-f0-9]{32}$') { throw 'Invalid failed-run identity.' }
    $originalDirectory=Join-Path (Join-Path $brokerBase 'state') $Previous.run_id
    $originalPath=Join-Path $originalDirectory 'task_result.json'
    $detailPath=Join-Path $originalDirectory 'auto_restore_result.private.json'
    $originalHash=(Get-FileHash -LiteralPath $originalPath -Algorithm SHA256).Hash
    $detailHash=(Get-FileHash -LiteralPath $detailPath -Algorithm SHA256).Hash
    if ($originalHash -notmatch '^[A-F0-9]{64}$' -or $detailHash -notmatch '^[A-F0-9]{64}$') { throw 'Original restoration records are not hashed files.' }
    $detail=Get-Content -LiteralPath $detailPath -Raw | ConvertFrom-Json
    $camera=Get-BrokerCamera
    $pmhome=@(Get-Volume | Where-Object { $_.FileSystemLabel -eq 'PMHOME' -and $_.DriveLetter } | ForEach-Object {
        $volume=$_
        $partitions=@(Get-Partition -DriveLetter $volume.DriveLetter)
        if ($partitions.Count -eq 1 -and (Test-Path -LiteralPath ($volume.DriveLetter+':\') -PathType Container)) {
            $disk=$partitions[0] | Get-Disk
            $diskDevice=@(Get-CimInstance Win32_DiskDrive | Where-Object Index -EQ $disk.Number)
            if ($diskDevice.Count -eq 1) {
                $node=$diskDevice[0].PNPDeviceID;$belongs=$false
                for ($depth=0;$depth -lt 8 -and $node;$depth++) {
                    if ($node -eq $camera.instance) { $belongs=$true;break }
                    $node=(Get-PnpDeviceProperty -InstanceId $node -KeyName DEVPKEY_Device_Parent -ErrorAction SilentlyContinue).Data
                }
                if ($belongs) { [pscustomobject]@{drive_letter=[string]$volume.DriveLetter;root_accessible=$true;belongs_to_camera=$true} }
            }
        }
    })
    $windowsDirectory=[IO.Path]::GetDirectoryName([Environment]::SystemDirectory)
    $packageAbsent=($detail.package -match '^oem[0-9]+\.inf$' -and -not (Test-Path -LiteralPath (Join-Path (Join-Path $windowsDirectory 'INF') $detail.package)))
    $facts=[pscustomobject]@{
        original_task_matches_index=($originalHash -eq (Get-FileHash -LiteralPath $IndexPath -Algorithm SHA256).Hash)
        original_status=$Previous.status;original_mode=$Previous.mode;original_error=$Previous.error
        original_mutation_started=$Previous.device_mutation_started;detail_status=$detail.status;detail_error=$detail.error
        uninstall_exit_code=$detail.uninstall_exit_code;port_cycle_attempts=$detail.port_cycle_attempts;port_cycle_count=$detail.port_cycle_count
        same_body=($detail.before.instance -eq $camera.instance -and $Previous.before.instance -eq $camera.instance)
        current_storage=($camera.service -eq 'USBSTOR' -and $camera.inf -eq 'usbstor.inf' -and $camera.status -eq 'OK')
        package_absent=$packageAbsent;camera_pmhome_count=$pmhome.Count
    }
    if (-not (Test-BrokerRecoveredFacts $facts)) { throw 'Failed restoration is not a completed uninstall/cycle with freshly verified camera storage.' }
    return [ordered]@{original_failed_run=$Previous.run_id;original_task_sha256=$originalHash;original_detail_sha256=$detailHash
        original_failure_preserved=$true;after=$camera;pmhome=$pmhome;package_absent=$true;device_mutations=0;externally_restored=$true}
}

$brokerRunId = [Guid]::NewGuid().ToString('N')
$brokerOutput = Join-Path (Join-Path $brokerBase 'state') $brokerRunId
New-BrokerDirectory $brokerOutput
$brokerIndex = Join-Path $brokerBase ('latest_'+$Mode+'.json')
$brokerResult = [ordered]@{schema=1;run_id=$brokerRunId;mode=$Mode;status='RUNNING';elevated=$true;
    started_utc=[DateTime]::UtcNow.ToString('o');script_integrity_verified=$true;error=$null;device_mutation_started=$false}
$brokerLock = $null
$brokerPriorUnresolved = $false
$brokerRecoveredRestore = $null
try {
    $brokerLock = [IO.File]::Open((Join-Path $brokerBase 'operation.lock'),[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    foreach ($otherMode in @('SelfTest','StageBind','Restore')) {
        $otherIndex = Join-Path $brokerBase ('latest_'+$otherMode+'.json')
        if (Test-Path -LiteralPath $otherIndex) {
            $previous = Get-Content -LiteralPath $otherIndex -Raw | ConvertFrom-Json
            if ($Mode -ne 'SelfTest' -and $previous.status -in @('RUNNING','NEEDS_REVIEW')) {
                $brokerPriorUnresolved=$true
                if ($Mode -eq 'Restore' -and $otherMode -eq 'Restore' -and $previous.status -eq 'NEEDS_REVIEW') {
                    $brokerRecoveredRestore=Get-BrokerRecoveredRestore $previous $otherIndex
                } else { throw 'A previous operation has unknown outcome; inspect it before another mutation.' }
            }
        }
    }
    Write-BrokerJson $brokerIndex $brokerResult
    if ($Mode -ne 'SelfTest') { Add-Type -Path (Join-Path $brokerBase 'camera_driver_native.dll') }
    if ($Mode -eq 'SelfTest') {
        $brokerResult.device_operations=0
        $brokerResult.allowed_modes=@('SelfTest','StageBind','Restore')
        $brokerResult.status='SELFTEST_OK'
    } elseif ($Mode -eq 'Restore' -and $brokerRecoveredRestore) {
        $brokerResult.recovery_confirmation=$brokerRecoveredRestore
        $brokerResult.device_operations=0
        $brokerResult.status='RECOVERY_CONFIRMED'
    } elseif ($Mode -eq 'StageBind') {
        $before = Get-BrokerCamera
        if ($before.service -ne 'USBSTOR' -or $before.inf -ne 'usbstor.inf') { throw 'StageBind requires the normal storage driver.' }
        $inf = Join-Path $brokerBase 'driver\ilce-7m4.inf'
        $cat = Join-Path $brokerBase 'driver\ILCE-7M4.cat'
        $infHash='501B7C682E1EF7F378353350F51E66E033962B91357E9136F9E4A9B42A8DA487'
        if ((Get-FileHash -LiteralPath $inf -Algorithm SHA256).Hash -ne $infHash -or
            (Get-FileHash -LiteralPath $cat -Algorithm SHA256).Hash -ne 'D923980763E6CAA1151F8854905565878CAC1367DBE24307CC103C8B88FAE933') { throw 'Reviewed driver package differs.' }
        $utility = Join-Path ([Environment]::SystemDirectory) 'pnputil.exe'
        $brokerResult.before=$before
        $brokerResult.device_mutation_started=$true
        Write-BrokerJson $brokerIndex $brokerResult
        & $utility /add-driver $inf 2>&1 | Out-File -LiteralPath (Join-Path $brokerOutput 'stage.log') -Encoding UTF8
        if ($LASTEXITCODE -notin @(0,3010)) { throw "Driver staging failed: $LASTEXITCODE" }
        $packages = @(Get-ChildItem -LiteralPath (Join-Path ([IO.Path]::GetDirectoryName([Environment]::SystemDirectory)) 'INF') -Filter 'oem*.inf' -File | Where-Object { (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash -eq $infHash })
        if ($packages.Count -ne 1) { throw 'Expected one reviewed staged package.' }
        $reboot=$false
        if (-not [M4CameraToolBind]::UpdateDriverForPlugAndPlayDevicesW([IntPtr]::Zero,'USB\VID_054C&PID_0DA5',$inf,1,[ref]$reboot)) {
            throw (New-Object ComponentModel.Win32Exception([Runtime.InteropServices.Marshal]::GetLastWin32Error()))
        }
        $after = Get-BrokerCamera
        if ($after.instance -ne $before.instance -or $after.service -ne 'WinUSB' -or $after.inf -ne $packages[0].Name) { throw 'WinUSB binding postcondition failed.' }
        $brokerResult.before=$before; $brokerResult.after=$after; $brokerResult.reboot_required=$reboot
        $brokerResult.status='WINUSB_BOUND'
    } else {
        $authorizedCamera = Get-BrokerCamera
        $brokerResult.before=$authorizedCamera
        $brokerResult.device_mutation_started=$true
        Write-BrokerJson $brokerIndex $brokerResult
        & (Join-Path $brokerBase 'restore_camera_driver.ps1') -EvidenceDirectory $brokerOutput -Apply
        if ($LASTEXITCODE -ne 0) { throw "Restore helper returned $LASTEXITCODE" }
        $restored = Get-Content -LiteralPath (Join-Path $brokerOutput 'auto_restore_result.private.json') -Raw | ConvertFrom-Json
        if ($restored.status -ne 'USBSTOR_PMHOME_AND_PACKAGE_REMOVAL_VERIFIED') { throw 'Restoration postcondition failed.' }
        $brokerResult.restoration=$restored
        $brokerResult.status='USBSTOR_RESTORED'
    }
} catch {
    $brokerResult.status=Get-BrokerFailureStatus $Mode $brokerResult.device_mutation_started $brokerPriorUnresolved
    $brokerResult.error=$_.Exception.Message
} finally {
    $brokerResult.finished_utc=[DateTime]::UtcNow.ToString('o')
    Write-BrokerJson (Join-Path $brokerOutput 'task_result.json') $brokerResult
    Write-BrokerJson $brokerIndex $brokerResult
    # External utility logs are never parsed as commands or reused as package input.
    if ($brokerLock) { $brokerLock.Dispose() }
}
if ($brokerResult.status -in @('FAILED','NEEDS_REVIEW','REFUSED_BEFORE_CHANGE')) { exit 1 }
