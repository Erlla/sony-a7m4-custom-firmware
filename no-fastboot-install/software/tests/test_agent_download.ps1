param([string]$Downloader=(Join-Path $PSScriptRoot '../../agent/Get-M4Agent.ps1'))
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.IO.Compression
$script:area=Join-Path ([IO.Path]::GetTempPath()) ('m4-agent-download-test-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $script:area | Out-Null
$script:archive=Join-Path $script:area 'fixture.zip'
$global:M4AgentDownloadTestContext=@{Archive=$script:archive;Calls=0;Failures=0}
function Invoke-WebRequest {
    param([switch]$UseBasicParsing,$Uri,$OutFile,$TimeoutSec)
    $global:M4AgentDownloadTestContext.Calls++
    if ($global:M4AgentDownloadTestContext.Calls -le $global:M4AgentDownloadTestContext.Failures) { throw 'injected interrupted download' }
    Copy-Item -LiteralPath $global:M4AgentDownloadTestContext.Archive -Destination $OutFile
}
function NewFixture($names) {
    if (Test-Path -LiteralPath $script:archive) { Remove-Item -LiteralPath $script:archive }
    $zip=[IO.Compression.ZipFile]::Open($script:archive,[IO.Compression.ZipArchiveMode]::Create)
    try { foreach($name in $names){$entry=$zip.CreateEntry($name);$writer=[IO.StreamWriter]::new($entry.Open());$writer.Write('INERT');$writer.Dispose()} }
    finally {$zip.Dispose()}
}
function Manifest($published=$true) {
    $value=@{schema='m4-agent-resources/1';published=$published;version='1.03';build_id='test-build';source_commit=('a'*40);
      platforms=@{'windows-x64'=@{url='https://github.com/Erlla/sony-a7m4-custom-firmware/releases/download/test/test.zip';
      sha256=(Get-FileHash -LiteralPath $script:archive -Algorithm SHA256).Hash.ToLowerInvariant();bytes=(Get-Item -LiteralPath $script:archive).Length;
      root='M4Agent_1.03';entry='M4相机工具.exe';status='validated'}}}
    $path=Join-Path $script:area 'manifest.json';$value|ConvertTo-Json -Depth 5|Set-Content -LiteralPath $path -Encoding UTF8
    return $path
}
function MustFail($body) { $failed=$false;try { & $body | Out-Null }catch {$failed=$true};if(-not $failed){throw 'expected rejection'} }
$rows=@()
try {
    NewFixture @('M4Agent_1.03/M4相机工具.exe')
    $manifest=Manifest $false
    MustFail { & $Downloader -Manifest $manifest -Destination (Join-Path $script:area 'unpublished') }
    if($global:M4AgentDownloadTestContext.Calls -ne 0){throw 'unpublished manifest downloaded'};$rows+='unpublished-refused'
    $manifest=Manifest
    $bad=Get-Content -LiteralPath $manifest -Raw|ConvertFrom-Json;$bad.platforms.'windows-x64'.sha256='0'*64
    $bad|ConvertTo-Json -Depth 5|Set-Content -LiteralPath $manifest -Encoding UTF8
    MustFail { & $Downloader -Manifest $manifest -Destination (Join-Path $script:area 'bad-hash') };$rows+='digest-mismatch'
    $manifest=Manifest;$global:M4AgentDownloadTestContext.Calls=0;$global:M4AgentDownloadTestContext.Failures=1
    & $Downloader -Manifest $manifest -Destination (Join-Path $script:area 'good') | Out-Null
    if($global:M4AgentDownloadTestContext.Calls -ne 2){throw 'retry count'};$rows+='bounded-download-retry'
    $saved=Join-Path $script:area 'good/M4Agent_1.03/user-record.txt';'keep'|Set-Content -LiteralPath $saved
    & $Downloader -Manifest $manifest -Destination (Join-Path $script:area 'good') | Out-Null
    if($global:M4AgentDownloadTestContext.Calls -ne 2 -or -not (Test-Path -LiteralPath $saved)){throw 'existing state overwritten'};$rows+='reuse-preserves-state'
    $global:M4AgentDownloadTestContext.Calls=0;$global:M4AgentDownloadTestContext.Failures=5
    MustFail { & $Downloader -Manifest $manifest -Destination (Join-Path $script:area 'offline') }
    if($global:M4AgentDownloadTestContext.Calls -ne 3){throw 'unbounded retry'};$rows+='download-fails-after-three-attempts'
    $global:M4AgentDownloadTestContext.Failures=0
    NewFixture @('M4Agent_1.03/readme.txt');$manifest=Manifest
    MustFail { & $Downloader -Manifest $manifest -Destination (Join-Path $script:area 'missing-entry') };$rows+='missing-entry-refused'
    NewFixture @('M4Agent_1.03/../escape.txt');$manifest=Manifest
    MustFail { & $Downloader -Manifest $manifest -Destination (Join-Path $script:area 'traversal') };$rows+='traversal-refused'
    NewFixture @('M4Agent_1.03/a.txt','M4Agent_1.03/A.txt');$manifest=Manifest
    MustFail { & $Downloader -Manifest $manifest -Destination (Join-Path $script:area 'alias') };$rows+='case-alias-refused'
    [pscustomobject]@{passed=$true;tests=$rows;network_requests=0;device_operations=0} | ConvertTo-Json -Compress
} finally {
    Remove-Variable -Name M4AgentDownloadTestContext -Scope Global -ErrorAction SilentlyContinue
    $resolved=[IO.Path]::GetFullPath($script:area)
    if([IO.Path]::GetDirectoryName($resolved).TrimEnd('\') -eq [IO.Path]::GetTempPath().TrimEnd('\') -and
       [IO.Path]::GetFileName($resolved) -match '^m4-agent-download-test-[0-9a-f]{32}$') {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
