param(
    [Parameter(Mandatory=$true)][string]$EvidenceDirectory,
    [switch]$Apply,
    [ValidateRange(3,20)][int]$CycleAfterSeconds = 5
)
$ErrorActionPreference = 'Stop'
$taskResearchRoot = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent)).TrimEnd('\') + '\'
$taskEvidence = [IO.Path]::GetFullPath($EvidenceDirectory)
if (-not $taskEvidence.StartsWith($taskResearchRoot,[StringComparison]::OrdinalIgnoreCase) -or
    $taskEvidence -notmatch '\\state\\') { throw 'Evidence must stay under a private USB research directory.' }
$taskResultPath = Join-Path $taskEvidence 'auto_restore_result.private.json'
if (Test-Path -LiteralPath $taskResultPath) { throw 'Refusing to replace an existing restoration record.' }
$taskExpectedInf = '501B7C682E1EF7F378353350F51E66E033962B91357E9136F9E4A9B42A8DA487'
$taskPattern = 'USB\VID_054C&PID_0DA5\*'

function Get-OneCamera {
    $devices = @(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like $taskPattern })
    if ($devices.Count -ne 1) { throw 'Expected exactly one normal-mode Sony camera.' }
    if (@(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB\VID_054C&PID_0336\*' }).Count) {
        throw 'A research service identity is active; close the session before restoring.'
    }
    $id = $devices[0].InstanceId
    $parent = (Get-PnpDeviceProperty -InstanceId $id -KeyName DEVPKEY_Device_Parent).Data
    $address = [uint32](Get-PnpDeviceProperty -InstanceId $id -KeyName DEVPKEY_Device_Address).Data
    $locations = @((Get-PnpDeviceProperty -InstanceId $id -KeyName DEVPKEY_Device_LocationPaths).Data)
    $usbLocation = @($locations | Where-Object { $_ -match '#USB\((\d+)\)$' })
    if ($usbLocation.Count -ne 1 -or $usbLocation[0] -notmatch '#USB\((\d+)\)$' -or
        [uint32]$Matches[1] -ne $address -or $address -lt 1 -or $address -gt 255) {
        throw 'USB port cannot be cross-checked between Address and LocationPaths.'
    }
    [pscustomobject]@{instance=$id; parent=$parent; port=$address; location=$usbLocation[0];
        service=(Get-PnpDeviceProperty -InstanceId $id -KeyName DEVPKEY_Device_Service).Data;
        inf=(Get-PnpDeviceProperty -InstanceId $id -KeyName DEVPKEY_Device_DriverInfPath).Data;
        status=$devices[0].Status}
}

function Get-Pmhome {
    @((Get-Volume -ErrorAction Stop | Where-Object FileSystemLabel -EQ 'PMHOME') | ForEach-Object {
        $rootPath = '{0}:\' -f $_.DriveLetter
        [pscustomobject]@{drive_letter=[string]$_.DriveLetter;label=$_.FileSystemLabel;
            health=[string]$_.HealthStatus;root_accessible=(Test-Path -LiteralPath $rootPath -PathType Container)}
    })
}

$taskBefore = Get-OneCamera
$taskPackages = @(Get-ChildItem -LiteralPath (Join-Path $env:SystemRoot 'INF') -Filter 'oem*.inf' -File | Where-Object {
    (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash -eq $taskExpectedInf
})
if ($taskPackages.Count -ne 1 -or $taskBefore.inf -notin @($taskPackages[0].Name,'usbstor.inf')) {
    throw 'Expected one reviewed package and its camera or USBSTOR binding.'
}
$taskPackage = $taskPackages[0].Name
$taskUsers = @(Get-CimInstance Win32_PnPSignedDriver | Where-Object InfName -EQ $taskPackage)
if (@($taskUsers | Where-Object { $_.DeviceID -notlike $taskPattern }).Count) { throw 'Driver package is used outside this camera.' }
$taskPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $taskPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run from an elevated Windows PowerShell host.' }
Add-Type -Path (Join-Path $PSScriptRoot 'camera_port.cs')
$taskPortInspection = [SonyCameraPortRecovery]::InspectOrCycle($taskBefore.parent,$taskBefore.port,$false)
if (-not $Apply) {
    New-Item -ItemType Directory -Path $taskEvidence -Force | Out-Null
    [pscustomobject]@{apply=$false;before=$taskBefore;package=$taskPackage;port_inspection=$taskPortInspection} |
        ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $taskEvidence 'inspection.private.json') -Encoding UTF8
    exit 0
}
New-Item -ItemType Directory -Path $taskEvidence -Force | Out-Null
$taskResult = [ordered]@{status='running';started_utc=[DateTime]::UtcNow.ToString('o');before=$taskBefore;
    package=$taskPackage;port_inspection=$taskPortInspection;port_cycle_attempts=0;port_cycle_count=0;error=$null}
function Save-Result { $taskResult | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $taskResultPath -Encoding UTF8 }
function Invoke-OnePortCycle {
    $taskCurrent = Get-OneCamera
    if ($taskCurrent.instance -ne $taskBefore.instance -or $taskCurrent.parent -ne $taskBefore.parent -or
        $taskCurrent.port -ne $taskBefore.port -or $taskCurrent.location -ne $taskBefore.location) { throw 'Camera topology changed; refusing port cycle.' }
    if ($taskCurrent.service -ne 'USBSTOR' -or $taskCurrent.inf -ne 'usbstor.inf') { throw 'Port cycle requires the restored USBSTOR binding.' }
    if ($taskResult.port_cycle_attempts -ne 0) { throw 'Only one port cycle attempt is permitted.' }
    $taskResult.port_cycle_attempts = 1
    Save-Result
    $taskResult.port_cycle = [SonyCameraPortRecovery]::InspectOrCycle($taskCurrent.parent,$taskCurrent.port,$true)
    $taskResult.port_cycle_count = 1
    $taskResult.cycle_elapsed_seconds = $taskWatch.Elapsed.TotalSeconds
    Save-Result
}
Save-Result
$taskUtility = Join-Path $env:SystemRoot 'System32\pnputil.exe'
try {
    $taskExport = Join-Path $taskEvidence 'recovery_package'
    New-Item -ItemType Directory -Path $taskExport -Force | Out-Null
    & $taskUtility /export-driver $taskPackage $taskExport 2>&1 | Out-File -LiteralPath (Join-Path $taskEvidence 'export.log') -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw "Driver recovery export failed: $LASTEXITCODE" }
    $taskWatch = [Diagnostics.Stopwatch]::StartNew()
    # Keep the native Process handle from Start through WaitForExit. Windows
    # PowerShell Start-Process -PassThru can otherwise leave ExitCode null.
    $taskStartInfo = New-Object Diagnostics.ProcessStartInfo
    $taskStartInfo.FileName = $taskUtility
    $taskStartInfo.Arguments = '/delete-driver ' + $taskPackage + ' /uninstall'
    $taskStartInfo.UseShellExecute = $false
    $taskStartInfo.CreateNoWindow = $true
    $taskStartInfo.RedirectStandardOutput = $true
    $taskStartInfo.RedirectStandardError = $true
    $taskStartInfo.StandardOutputEncoding = [Text.Encoding]::GetEncoding([Globalization.CultureInfo]::CurrentCulture.TextInfo.OEMCodePage)
    $taskStartInfo.StandardErrorEncoding = $taskStartInfo.StandardOutputEncoding
    $taskUninstall = New-Object Diagnostics.Process
    $taskUninstall.StartInfo = $taskStartInfo
    if (-not $taskUninstall.Start()) { throw 'Could not start the bounded driver uninstall.' }
    $taskStdout = $taskUninstall.StandardOutput.ReadToEndAsync()
    $taskStderr = $taskUninstall.StandardError.ReadToEndAsync()
    $taskResult.uninstall_process = $taskUninstall.Id
    Save-Result
    while (-not $taskUninstall.HasExited -and $taskWatch.Elapsed.TotalSeconds -lt 70) {
        if ($taskWatch.Elapsed.TotalSeconds -ge $CycleAfterSeconds -and $taskResult.port_cycle_count -eq 0) {
            $taskCurrent = Get-OneCamera
            if ($taskCurrent.instance -ne $taskBefore.instance -or $taskCurrent.parent -ne $taskBefore.parent -or
                $taskCurrent.port -ne $taskBefore.port -or $taskCurrent.location -ne $taskBefore.location) { throw 'Camera topology changed; refusing port cycle.' }
            if ($taskCurrent.service -eq 'USBSTOR' -and $taskCurrent.inf -eq 'usbstor.inf') {
                Invoke-OnePortCycle
            }
        }
        Start-Sleep -Milliseconds 500
        $taskUninstall.Refresh()
    }
    if (-not $taskUninstall.HasExited) { throw 'Driver uninstall outcome is still pending; no automatic repeat or forced deletion.' }
    $taskUninstall.WaitForExit()
    $taskStdout.GetAwaiter().GetResult() | Set-Content -LiteralPath (Join-Path $taskEvidence 'uninstall.log') -Encoding UTF8
    $taskStderr.GetAwaiter().GetResult() | Set-Content -LiteralPath (Join-Path $taskEvidence 'uninstall_error.log') -Encoding UTF8
    $taskResult.uninstall_exit_code = $taskUninstall.ExitCode
    if ($taskUninstall.ExitCode -ne 0) { throw "Driver uninstall returned $($taskUninstall.ExitCode)." }
    # Re-enumerate once even after a fast uninstall, so volumes get the same
    # fresh connection as the former manual unplug/replug step.
    if ($taskResult.port_cycle_count -eq 0) { Invoke-OnePortCycle }
    $taskDeadline = [DateTime]::UtcNow.AddSeconds(30)
    do {
        try { $taskAfter = Get-OneCamera; $taskPmhome = @(Get-Pmhome) } catch { $taskAfter=$null; $taskPmhome=@() }
        $taskReady = ($taskAfter -and $taskAfter.instance -eq $taskBefore.instance -and
            $taskAfter.service -eq 'USBSTOR' -and $taskAfter.inf -eq 'usbstor.inf' -and
            @($taskPmhome | Where-Object root_accessible -EQ $true).Count -gt 0)
        if ($taskReady) { break }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $taskDeadline)
    if (-not $taskReady) { throw 'USBSTOR/PMHOME did not become accessible within the postcondition deadline.' }
    if (Test-Path -LiteralPath (Join-Path (Join-Path $env:SystemRoot 'INF') $taskPackage)) { throw 'Reviewed OEM package still remains in INF after deletion.' }
    $taskResult.after = $taskAfter
    $taskResult.pmhome = $taskPmhome
    $taskResult.elapsed_seconds = $taskWatch.Elapsed.TotalSeconds
    $taskResult.status = 'USBSTOR_PMHOME_AND_PACKAGE_REMOVAL_VERIFIED'
} catch {
    $taskResult.status = 'failed'
    $taskResult.error = $_.Exception.Message
} finally {
    $taskResult.finished_utc = [DateTime]::UtcNow.ToString('o')
    Save-Result
}
if ($taskResult.status -eq 'failed') { exit 1 }
