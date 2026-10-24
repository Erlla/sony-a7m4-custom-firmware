param(
 [Parameter(Mandatory=$true)][string]$Bundle,
 [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{64}$')][string]$BundleHash,
 [Parameter(Mandatory=$true)][string]$Installer,
 [Parameter(Mandatory=$true)][string]$Output
)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$base=Join-Path $env:ProgramData ('M4CameraTool\'+$sid)
$configPath=Join-Path $base 'deployment.private.json'
$bundleRoot=(Resolve-Path -LiteralPath $Bundle).Path
$installFile=(Resolve-Path -LiteralPath $Installer).Path
$manifestPath=Join-Path $bundleRoot 'bundle_manifest.json'
if ((Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash -ne $BundleHash) { throw 'Setup bundle changed.' }
$manifest=Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not (Test-Path -LiteralPath $configPath)) {
 $shell=Join-Path $PSHOME 'powershell.exe'
 $arguments='-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+$installFile+'" -BundlePath "'+$bundleRoot+'" -ManifestSha256 '+$BundleHash
 $process=Start-Process -FilePath $shell -ArgumentList $arguments -Verb RunAs -WindowStyle Hidden -PassThru -Wait
 if ($process.ExitCode -ne 0) { throw 'Windows setup was not completed; keep the setup record.' }
}
$config=Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($config.user_sid -ne $sid -or $config.task_folder -ne ('\M4CameraTool\'+$sid)) { throw 'Windows user differs.' }
foreach ($file in $manifest.files) {
 $installed=@($config.files | Where-Object name -EQ $file.name)
 if ($installed.Count -ne 1 -or $installed[0].sha256 -ne $file.sha256 -or
     (Get-FileHash -LiteralPath (Join-Path $base $file.name) -Algorithm SHA256).Hash -ne $file.sha256) { throw 'Existing driver setup differs; no replacement was made.' }
}
$camera=@(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB\VID_054C&PID_0DA5\*' })
$service=@(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB\VID_054C&PID_0336\*' })
if ($camera.Count -ne 1 -or $service.Count) { throw 'Connect exactly one normal ILCE-7M4.' }
$hash=[Security.Cryptography.SHA256]::Create()
try { $bodyHash=[BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($camera[0].InstanceId.ToUpperInvariant()))).Replace('-','').ToLowerInvariant() } finally { $hash.Dispose() }
if ($bodyHash -ne $config.camera_instance_sha256.ToLowerInvariant()) { throw 'Connected body differs from the Windows driver enrollment.' }
if ((Get-PnpDeviceProperty -InstanceId $camera[0].InstanceId -KeyName DEVPKEY_Device_Service).Data -ne 'USBSTOR') { throw 'Restore ordinary USB before setup.' }
$record=[ordered]@{schema='m4-user-enrollment/1';model='ILCE-7M4';identity=$null;user_sid=$sid;camera_instance_sha256=$bodyHash;
 deployment_sha256=(Get-FileHash -LiteralPath $configPath -Algorithm SHA256).Hash.ToLowerInvariant();created_utc=[DateTime]::UtcNow.ToString('o');firmware_operations=0}
if (Test-Path -LiteralPath $Output) { throw 'Setup output already exists.' }
$record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Output -Encoding UTF8
@{passed=$true;firmware_operations=0} | ConvertTo-Json
