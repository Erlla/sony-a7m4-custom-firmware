param([Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$expectedSigners=@{
 normal='974B181DF467547DD9A51B461F0BD962E74D5D0B'
 service='7B02E48E8167C8C8844A0C0FDC04C87CB988E2D5'
}
$expectedWorkers=@('FA301416BA19C41F6C6BBD2AB9A313BC61847EA9B1B6B1C0ACA2B4912BE2E0C8','1AEF8514B6A5BE2ED7E8E5F39810B04F0568951AB725491C6E324519989DA2DD')

function Confirm-DriverSigner($Certificates) {
 Add-Type -AssemblyName System.Windows.Forms
 $listed=($Certificates|ForEach-Object{$_.Subject}) -join "`n  "
 $text="此电脑首次使用需要信任相机 USB 驱动的签名证书。`n`n继续将把 libwdi 自动生成的驱动证书（普通连接与服务连接各一张）加入 Windows 的「受信任的根证书」和「受信任的发布者」存储。这些证书不是索尼或微软的发布者证书。`n`n签名者：`n  "+$listed+"`n`n是否继续？"
 return [Windows.Forms.MessageBox]::Show($text,'安装相机 USB 驱动',[Windows.Forms.MessageBoxButtons]::YesNo,
   [Windows.Forms.MessageBoxIcon]::Warning,[Windows.Forms.MessageBoxDefaultButton]::Button2) -eq [Windows.Forms.DialogResult]::Yes
}

function Get-DriverSignerFacts([string]$Base) {
 $packages=@(
  @{inf='driver\ilce-7m4.inf';cat='driver\ILCE-7M4.cat';infHash='501B7C682E1EF7F378353350F51E66E033962B91357E9136F9E4A9B42A8DA487';catHash='D923980763E6CAA1151F8854905565878CAC1367DBE24307CC103C8B88FAE933';signer=$expectedSigners.normal},
  @{inf='driver\ilce-7m4-svc.inf';cat='driver\ILCE-7M4-SVC.cat';infHash='9455D90C562916277590BB9A8BC333379B86913E680D1E9176FACE6B44923E25';catHash='FA1B38929210C1423104F1C71B488FC3E3BA6456A3478BE03659DF4E6456C886';signer=$expectedSigners.service}
 )
 $certificates=@();$catalogs=@();$signaturesValid=$true
 foreach($package in $packages){
  if((Get-FileHash -LiteralPath (Join-Path $Base $package.inf) -Algorithm SHA256).Hash -ne $package.infHash -or
     (Get-FileHash -LiteralPath (Join-Path $Base $package.cat) -Algorithm SHA256).Hash -ne $package.catHash){throw 'Driver package differs from the reviewed source.'}
  $signature=Get-AuthenticodeSignature -LiteralPath (Join-Path $Base $package.cat)
  $certificate=$signature.SignerCertificate
  if(-not $certificate -or $certificate.Thumbprint -ne $package.signer){throw 'Driver signer differs from the reviewed source.'}
  if([DateTime]::UtcNow -lt $certificate.NotBefore.ToUniversalTime() -or [DateTime]::UtcNow -gt $certificate.NotAfter.ToUniversalTime()){
   throw 'Driver signer validity does not include the current date. Check the computer clock.'
  }
  if($signature.Status -ne 'Valid'){$signaturesValid=$false}
  $certificates+=@($certificate);$catalogs+=@((Join-Path $Base $package.cat))
 }
 $present=@{}
 foreach($name in @('Root','TrustedPublisher')){
  $store=New-Object Security.Cryptography.X509Certificates.X509Store($name,'LocalMachine')
  try{$store.Open('ReadOnly');$present[$name]=@{};foreach($thumbprint in $expectedSigners.Values){$present[$name][$thumbprint]=@($store.Certificates|Where-Object Thumbprint -EQ $thumbprint).Count -gt 0}}
  finally{$store.Close()}
 }
 return @{certificates=$certificates;root=$present.Root;publisher=$present.TrustedPublisher;signature_valid=$signaturesValid;catalogs=$catalogs}
}

function Open-DriverSignerStore([string]$Name,[string]$Access) {
 $store=New-Object Security.Cryptography.X509Certificates.X509Store($Name,'LocalMachine')
 $store.Open($Access);return $store
}

function Install-DriverSigner($Facts) {
 # Export the public certificates only. No private signing key is copied or created.
 $publics=@($Facts.certificates|ForEach-Object{[Security.Cryptography.X509Certificates.X509Certificate2]::new($_.Export([Security.Cryptography.X509Certificates.X509ContentType]::Cert))})
 $added=New-Object Collections.Generic.List[string]
 try {
  foreach($public in $publics){
   foreach($name in @('Root','TrustedPublisher')){
    $store=Open-DriverSignerStore $name 'ReadWrite'
    try{
     if(@($store.Certificates|Where-Object Thumbprint -EQ $public.Thumbprint).Count -eq 0){$store.Add($public);$added.Add($name+':'+$public.Thumbprint)}
    } finally{$store.Close()}
   }
  }
  foreach($catalog in $Facts.catalogs){
   if((Get-AuthenticodeSignature -LiteralPath $catalog).Status -ne 'Valid'){throw 'Windows still does not trust the driver signature.'}
  }
 } catch {
  foreach($entry in $added){
   $parts=$entry -split ':',2;$store=Open-DriverSignerStore $parts[0] 'ReadWrite'
   $match=@($publics|Where-Object Thumbprint -EQ $parts[1])
   try{if($match.Count){$store.Remove($match[0])}}finally{$store.Close()}
  }
  throw
 } finally{foreach($public in $publics){$public.Dispose()}}
 return @($added.ToArray())
}

function Test-DriverSignerStores($Facts) {
 foreach($thumbprint in @($expectedSigners.Values)){
  if(-not $Facts.root[$thumbprint] -or -not $Facts.publisher[$thumbprint]){return $false}
 }
 return $true
}

function Ensure-DriverSigner($Facts) {
 if((Test-DriverSignerStores $Facts) -and $Facts.signature_valid){return @{phase='DRIVER_TRUST_READY';stores_added=@();consent_required=$false}}
 if(-not (Confirm-DriverSigner $Facts.certificates)){return @{phase='DRIVER_TRUST_CANCELLED';stores_added=@();consent_required=$true;consent_granted=$false}}
 $added=@(Install-DriverSigner $Facts)
 return @{phase='DRIVER_TRUST_READY';stores_added=$added;consent_required=$true;consent_granted=$true;signers=@($expectedSigners.Values)}
}

function Test-StageSignatureRefusal($Record,$Camera,[string]$WorkerHash) {
 return ($WorkerHash -in $expectedWorkers -and $Record.mode -eq 'StageBind' -and $Record.status -eq 'NEEDS_REVIEW' -and
   $Record.error -eq 'Driver staging failed: -2146762487' -and $Record.device_mutation_started -eq $true -and
   $Record.before.instance -eq $Camera.instance -and $Record.before.service -eq 'USBSTOR' -and $Record.before.inf -eq 'usbstor.inf' -and
   $Camera.service -eq 'USBSTOR' -and $Camera.inf -eq 'usbstor.inf' -and $Camera.status -eq 'OK')
}

function Write-SetupJson([string]$Path,$Value,[switch]$Protected) {
 $temporary=$Path+'.'+[Guid]::NewGuid().ToString('N')+'.tmp'
 if($Protected){
  $security=New-Object Security.AccessControl.FileSecurity
  $security.SetSecurityDescriptorSddlForm(('O:BAG:SYD:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;GR;;;'+$sid+')'))
  $stream=New-Object IO.FileStream($temporary,[IO.FileMode]::CreateNew,[Security.AccessControl.FileSystemRights]::FullControl,[IO.FileShare]::Read,4096,[IO.FileOptions]::None,$security)
  try{$raw=(New-Object Text.UTF8Encoding($false)).GetBytes(($Value|ConvertTo-Json -Depth 10));$stream.Write($raw,0,$raw.Length);$stream.Flush($true)}finally{$stream.Dispose()}
 }else{[IO.File]::WriteAllText($temporary,($Value|ConvertTo-Json -Depth 10),(New-Object Text.UTF8Encoding($false)))}
 if([IO.File]::Exists($Path)){[IO.File]::Replace($temporary,$Path,[NullString]::Value)}else{[IO.File]::Move($temporary,$Path)}
}

function Review-StageSignatureRefusal([string]$Base,$Camera) {
 $index=Join-Path $Base 'latest_StageBind.json'
 if(-not (Test-Path -LiteralPath $index)){return $false}
 $prior=Get-Content -LiteralPath $index -Raw -Encoding UTF8|ConvertFrom-Json
 if($prior.status -notin @('RUNNING','NEEDS_REVIEW','FAILED','REFUSED_BEFORE_CHANGE')){return $false}
 if($prior.run_id -notmatch '^[a-f0-9]{32}$'){throw 'Invalid previous driver run.'}
 $workerHash=(Get-FileHash -LiteralPath (Join-Path $Base 'worker.ps1') -Algorithm SHA256).Hash
 if(-not (Test-StageSignatureRefusal $prior $Camera $workerHash)){throw ('Previous driver task requires review: '+$prior.error)}
 $original=Join-Path $Base ('state\'+$prior.run_id+'\task_result.json')
 if((Get-FileHash -LiteralPath $index -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $original -Algorithm SHA256).Hash){throw 'Driver index does not match its final task result.'}
 $reviewId=[Guid]::NewGuid().ToString('N');$folder=Join-Path $Base ('state\'+$reviewId)
 $security=New-Object Security.AccessControl.DirectorySecurity
 $security.SetSecurityDescriptorSddlForm(('O:BAG:SYD:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;GRGX;;;'+$sid+')'))
 [IO.Directory]::CreateDirectory($folder,$security)|Out-Null
 $confirmation=[ordered]@{schema=1;run_id=$reviewId;mode='StageBind';status='STAGE_SIGNATURE_REFUSAL_REVIEWED';
  original_failed_run=$prior.run_id;original_failure_preserved=$true;error=$null;device_mutation_started=$false;
  reason='CERT_E_UNTRUSTEDROOT';device_binding_changed=$false;package_staging_may_have_been_attempted=$true;
  after=$Camera;finished_utc=[DateTime]::UtcNow.ToString('o')}
 Write-SetupJson (Join-Path $folder 'task_result.json') $confirmation -Protected
 Write-SetupJson $index $confirmation -Protected
 return $true
}

$report=@{phase='DRIVER_TRUST_FAILED';firmware_operations=0;camera_commands=0;error=$null};$guard=$null
try {
 $principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
 if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Administrator authorization is required.'}
 $sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
 $base=Join-Path $env:ProgramData ('M4CameraTool\'+$sid)
 $guard=[IO.File]::Open((Join-Path $base 'operation.lock'),[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
 $config=Get-Content -LiteralPath (Join-Path $base 'deployment.private.json') -Raw -Encoding UTF8|ConvertFrom-Json
 $devices=@(Get-PnpDevice -PresentOnly|Where-Object InstanceId -Like 'USB\VID_054C&PID_0DA5\*')
 if($devices.Count -ne 1 -or @(Get-PnpDevice -PresentOnly|Where-Object InstanceId -Like 'USB\VID_054C&PID_0336\*').Count){throw 'Connect one normal camera before preparing its driver.'}
 $id=$devices[0].InstanceId;$digest=[Security.Cryptography.SHA256]::Create()
 try{$body=[BitConverter]::ToString($digest.ComputeHash([Text.Encoding]::UTF8.GetBytes($id.ToUpperInvariant()))).Replace('-','')}finally{$digest.Dispose()}
 if($config.user_sid -ne $sid -or $body -ne $config.camera_instance_sha256){throw 'Camera or Windows user differs from the enrollment.'}
 $camera=@{instance=$id;service=(Get-PnpDeviceProperty -InstanceId $id -KeyName DEVPKEY_Device_Service).Data;
  inf=(Get-PnpDeviceProperty -InstanceId $id -KeyName DEVPKEY_Device_DriverInfPath).Data;status=[string]$devices[0].Status}
 if($camera.service -eq 'USBSTOR' -and $camera.inf -eq 'usbstor.inf'){}else{
  # A camera already bound to the reviewed package may still be missing the
  # service signer trust; preparing it there avoids an untrusted staging.
  $reviewedBound=($camera.service -eq 'WinUSB' -and $camera.inf -match '^oem[0-9]+\.inf$' -and
   ((Get-FileHash -LiteralPath (Join-Path (Join-Path $env:SystemRoot 'INF') $camera.inf) -Algorithm SHA256).Hash -eq '501B7C682E1EF7F378353350F51E66E033962B91357E9136F9E4A9B42A8DA487'))
  if(-not $reviewedBound){throw 'Driver preparation requires the current storage connection.'}
 }
 $report=Ensure-DriverSigner (Get-DriverSignerFacts $base)
 $report.firmware_operations=0;$report.camera_commands=0
 if($report.phase -eq 'DRIVER_TRUST_READY'){$report.prior_signature_failure_reviewed=Review-StageSignatureRefusal $base $camera}
}catch{$report.phase='DRIVER_TRUST_FAILED';$report.error=$_.Exception.Message}
finally{if($guard){$guard.Dispose()}}
$outputPath=[IO.Path]::GetFullPath($Output)
$dataPrefix=[IO.Path]::GetFullPath($env:M4_TOOL_DATA_ROOT).TrimEnd('\')+'\'
if(-not $outputPath.StartsWith($dataPrefix,[StringComparison]::OrdinalIgnoreCase)){throw 'Driver setup output must stay in the current data directory.'}
Write-SetupJson ('\\?\'+$outputPath) $report
$report|ConvertTo-Json -Depth 6 -Compress
if($report.phase -ne 'DRIVER_TRUST_READY'){exit 1}
