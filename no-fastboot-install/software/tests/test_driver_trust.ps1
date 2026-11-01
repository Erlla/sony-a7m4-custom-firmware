param([Parameter(Mandatory=$true)][string]$Package)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$path=Join-Path $Package 'app\workflow\driver_trust.ps1'
$tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$errors)
if($errors.Count){throw ($errors|Out-String)}
# Load function definitions only. The script entry point, PnP, store writes,
# and authorization dialog are never invoked in this test.
foreach($function in $ast.FindAll({param($node)$node -is [Management.Automation.Language.FunctionDefinitionAst]},$false)){
 . ([scriptblock]::Create($function.Extent.Text))
}
$scriptText=[IO.File]::ReadAllText($path)
if($scriptText -notmatch '\$expectedSigners=@\{\s*normal=''([0-9A-F]{40})''\s*service=''([0-9A-F]{40})''\s*\}'){throw 'Signer constants not found'}
$normalSigner=$Matches[1];$serviceSigner=$Matches[2]
if($scriptText -notmatch '\$expectedWorkers=@\(''([0-9A-F]{64})'',''([0-9A-F]{64})''\)'){throw 'Worker constants not found'}
$expectedWorkers=@($Matches[1],$Matches[2])
# Loaded functions reference these script-scope constants; mirror them here.
$expectedSigners=@{normal=$normalSigner;service=$serviceSigner}
$checks=New-Object Collections.Generic.List[string]
$script:consent=$false;$script:dialogs=0;$script:installs=0
function Confirm-DriverSigner($Certificates){$script:dialogs++;return $script:consent}
function Install-DriverSigner($Facts){$script:installs++;return @('Root','TrustedPublisher')}
$storesReady={param($Thumbprints) @{root=@{};publisher=@{};signature_valid=$true}}
$thumbprints=@($normalSigner,$serviceSigner)
$ready=@{root=@{};publisher=@{};signature_valid=$true}
foreach($t in $thumbprints){$ready.root[$t]=$true;$ready.publisher[$t]=$true}
$result=Ensure-DriverSigner $ready
if($result.phase -ne 'DRIVER_TRUST_READY' -or $script:dialogs -ne 0 -or $script:installs -ne 0){throw 'Trusted machine unnecessarily prompted or changed stores'}
$checks.Add('already_trusted_machine_has_no_prompt_or_store_change')
$missing=@{root=@{};publisher=@{};signature_valid=$false}
foreach($t in $thumbprints){$missing.root[$t]=$false;$missing.publisher[$t]=$false}
$result=Ensure-DriverSigner $missing
if($result.phase -ne 'DRIVER_TRUST_CANCELLED' -or $script:installs -ne 0){throw 'Cancellation did not prevent store changes'}
$checks.Add('explicit_cancellation_prevents_certificate_installation')
$halfReady=@{root=@{};publisher=@{};signature_valid=$true}
foreach($t in $thumbprints){$halfReady.root[$t]=$true;$halfReady.publisher[$t]=($t -eq $normalSigner)}
$script:consent=$true
$result=Ensure-DriverSigner $halfReady
if($result.phase -ne 'DRIVER_TRUST_READY' -or $script:installs -ne 1 -or -not $result.consent_granted){throw 'Partial trust did not reach the fixed certificate install boundary'}
$checks.Add('partially_trusted_machine_still_prompts_once_and_installs')
$untrusted=@{root=@{};publisher=@{};signature_valid=$false}
foreach($t in $thumbprints){$untrusted.root[$t]=$false;$untrusted.publisher[$t]=$false}
$result=Ensure-DriverSigner $untrusted
if($result.phase -ne 'DRIVER_TRUST_READY' -or $script:installs -ne 2){throw 'Untrusted machine did not reach the install boundary exactly once per prompt'}
$checks.Add('consent_reaches_certificate_install_boundary_once_per_prompt')

$camera=@{instance='USB\VID_054C&PID_0DA5\FIXTURE';service='USBSTOR';inf='usbstor.inf';status='OK'}
$record=@{mode='StageBind';status='NEEDS_REVIEW';error='Driver staging failed: -2146762487';device_mutation_started=$true;before=@{instance=$camera.instance;service='USBSTOR';inf='usbstor.inf'}}
$knownAccepted=$false
foreach($worker in $expectedWorkers){if(Test-StageSignatureRefusal $record $camera $worker){$knownAccepted=$true}}
if(-not $knownAccepted){throw 'Known refusal was not recognized for any reviewed worker'}
$checks.Add('known_signature_refusal_with_unchanged_storage_is_recognized_for_reviewed_workers')
foreach($field in @('mode','status','error')){
 $old=$record[$field];$record[$field]='unrelated'
 if(Test-StageSignatureRefusal $record $camera $expectedWorkers[0]){throw ('Unknown failure accepted: '+$field)}
 $record[$field]=$old
}
$checks.Add('unrelated_operation_status_or_error_is_not_retired')
$old=$camera.instance;$camera.instance+='OTHER'
if(Test-StageSignatureRefusal $record $camera $expectedWorkers[0]){throw 'Another body accepted'}
$camera.instance=$old
$checks.Add('body_identity_must_match_original_refusal')
$camera.service='WinUSB'
if(Test-StageSignatureRefusal $record $camera $expectedWorkers[0]){throw 'Changed binding accepted'}
$camera.service='USBSTOR'
$checks.Add('changed_driver_binding_is_not_retired')
if(Test-StageSignatureRefusal $record $camera ('0'*64)){throw 'Unknown worker accepted'}
$checks.Add('worker_implementation_is_pinned_for_old_failure_review')

# The existing private keys are neither requested nor exported. Certificate reads
# and public re-export below use both fixed known catalogs; no store modifications.
$signatures=@()
$signatures+=Get-AuthenticodeSignature -LiteralPath (Join-Path $Package 'tools\driver\ILCE-7M4.cat')
$signatures+=Get-AuthenticodeSignature -LiteralPath (Join-Path $Package 'tools\driver\ILCE-7M4-SVC.cat')
if($signatures[0].SignerCertificate.Thumbprint -ne $normalSigner -or $signatures[1].SignerCertificate.Thumbprint -ne $serviceSigner){throw 'Unexpected catalog signers'}
$publics=@($signatures|ForEach-Object{[Security.Cryptography.X509Certificates.X509Certificate2]::new($_.SignerCertificate.Export([Security.Cryptography.X509Certificates.X509ContentType]::Cert))})
try{
 foreach($public in $publics){if($public.HasPrivateKey -or ($public.Thumbprint -notin @($normalSigner,$serviceSigner))){throw 'Public certificate extraction differs'}}
}finally{foreach($public in $publics){$public.Dispose()}}
$checks.Add('both_catalog_certificates_export_contain_no_private_key')

$installer=$ast.FindAll({param($node)$node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Install-DriverSigner'},$false)[0].Extent.Text
. ([scriptblock]::Create($installer))
$facts=@{certificates=@($signatures[0].SignerCertificate,$signatures[1].SignerCertificate);catalogs=@('fixture-normal.cat','fixture-service.cat')}
$script:stores=@{};$script:storeFailure=$null;$script:signatureStatus='Valid';$script:privateKeySeen=$false
function Reset-FakeStores {
 $script:stores=@{Root=(New-Object Collections.ArrayList);TrustedPublisher=(New-Object Collections.ArrayList)}
 $script:storeFailure=$null;$script:signatureStatus='Valid';$script:privateKeySeen=$false
}
function Open-DriverSignerStore([string]$Name,[string]$Access){
 if($Name -eq $script:storeFailure){throw 'Fixture store failure'}
 $fake=[pscustomobject]@{Certificates=$script:stores[$Name]}
 $fake|Add-Member ScriptMethod Add {param($Certificate)
  if($Certificate.HasPrivateKey){$script:privateKeySeen=$true}
  [void]$this.Certificates.Add([pscustomobject]@{Thumbprint=$Certificate.Thumbprint})
 }
 $fake|Add-Member ScriptMethod Remove {param($Certificate)
  foreach($entry in @($this.Certificates|Where-Object Thumbprint -EQ $Certificate.Thumbprint)){$this.Certificates.Remove($entry)}
 }
 $fake|Add-Member ScriptMethod Close {}
 return $fake
}
function Get-AuthenticodeSignature {param([string]$LiteralPath)
 return [pscustomobject]@{Status=$script:signatureStatus}
}
Reset-FakeStores
$added=@(Install-DriverSigner $facts)
if($added.Count -ne 4 -or $script:privateKeySeen -or $script:stores.Root.Count -ne 2 -or $script:stores.TrustedPublisher.Count -ne 2){throw 'Public-only install did not update both fake stores for both certificates'}
$added=@(Install-DriverSigner $facts)
if($added.Count -ne 0 -or $script:stores.Root.Count -ne 2 -or $script:stores.TrustedPublisher.Count -ne 2){throw 'Already-present signers were duplicated'}
$checks.Add('actual_installer_adds_both_public_certificates_once_to_each_fake_store')
Reset-FakeStores
[void]$script:stores.Root.Add([pscustomobject]@{Thumbprint='UNRELATED'})
$script:storeFailure='TrustedPublisher';$failed=$false
try{Install-DriverSigner $facts|Out-Null}catch{$failed=$true}
if(-not $failed -or $script:stores.Root.Count -ne 1 -or $script:stores.Root[0].Thumbprint -ne 'UNRELATED'){throw 'Partial failure did not roll back only its own certificates'}
$checks.Add('second_store_failure_rolls_back_new_roots_and_preserves_unrelated_certificate')
Reset-FakeStores
[void]$script:stores.Root.Add([pscustomobject]@{Thumbprint=$normalSigner})
$script:signatureStatus='NotTrusted';$failed=$false
try{Install-DriverSigner $facts|Out-Null}catch{$failed=$true}
if(-not $failed -or $script:stores.Root.Count -ne 1 -or $script:stores.TrustedPublisher.Count -ne 0){throw 'Signature failure removed a preexisting certificate or kept new trust'}
$checks.Add('signature_failure_preserves_preexisting_root_and_removes_new_publishers')
@{passed=$true;cases=$checks.Count;tests=@($checks);certificate_stores_modified=0;driver_tasks_dispatched=0;device_operations=0;firmware_operations=0;authorization_dialog_shown=$false} | ConvertTo-Json -Depth 5 -Compress
