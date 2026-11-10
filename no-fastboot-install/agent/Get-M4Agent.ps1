param([Parameter(Mandatory=$true)][string]$Manifest,
      [string]$Destination)
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
    throw '此入口仅支持 Windows x64；macOS 尚未完成实机适配。'
}
$resource = Get-Content -LiteralPath $Manifest -Raw -Encoding UTF8 | ConvertFrom-Json
if ($resource.schema -ne 'm4-agent-resources/1' -or $resource.published -ne $true) {
    throw '此清单尚未发布。请使用维护者提供的本地审阅包，不要猜测下载地址。'
}
if ($resource.source_commit -notmatch '^[0-9a-f]{40}$' -or $resource.build_id -notmatch '^[a-zA-Z0-9._-]{1,80}$') { throw '资源身份不完整。' }
$asset = $resource.platforms.'windows-x64'
if ($asset.status -ne 'validated' -or $asset.sha256 -notmatch '^[0-9a-f]{64}$' -or $asset.bytes -le 0 -or
    $asset.url -notmatch '^https://github\.com/Erlla/sony-a7m4-custom-firmware/releases/download/[^/]+/[^/]+$' -or
    $asset.root -ne 'M4Agent_1.01' -or $asset.entry -ne 'M4相机工具.exe') { throw '没有适用且已验收的 Agent 包。' }
if (-not $Destination) { $Destination = Join-Path $env:LOCALAPPDATA ('M4CameraToolAgent\' + $resource.build_id) }
$target = [IO.Path]::GetFullPath($Destination)
$parent = [IO.Path]::GetDirectoryName($target)
New-Item -ItemType Directory -Path $parent -Force | Out-Null
if (Test-Path -LiteralPath $target) {
    $receipt = Get-Content -LiteralPath (Join-Path $target 'download.json') -Raw | ConvertFrom-Json
    if ($receipt.sha256 -ne $asset.sha256 -or $receipt.build_id -ne $resource.build_id) { throw '目标目录属于其他构建，未覆盖原文件。' }
    $entry = Join-Path (Join-Path $target $asset.root) $asset.entry
    [pscustomobject]@{status='EXISTING';entry=$entry;next='先调用 --agent status，不能直接重发 start。'} | ConvertTo-Json -Compress
    exit 0
}
$stage = Join-Path $parent ('.m4-agent-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
$archive = Join-Path $stage 'download.zip'
try {
    for ($attempt=1; $attempt -le 3; $attempt++) {
        try { Invoke-WebRequest -UseBasicParsing -Uri $asset.url -OutFile $archive -TimeoutSec 120; break }
        catch { if ($attempt -eq 3) { throw }; Start-Sleep -Seconds 2 }
    }
    if ((Get-Item -LiteralPath $archive).Length -ne $asset.bytes -or
        (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $asset.sha256) { throw '下载大小或 SHA-256 不匹配，已停止。' }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($archive)
    try {
        $seen = @{}
        foreach ($item in $zip.Entries) {
            $name = $item.FullName
            if (-not $name.StartsWith($asset.root + '/', [StringComparison]::Ordinal) -or
                $name -match '\\|:|(^|/)\.\.?(/|$)' -or $seen.ContainsKey($name.ToLowerInvariant()) -or
                (($item.ExternalAttributes -shr 16) -band 0xF000) -eq 0xA000) { throw '压缩包目录无效。' }
            $seen[$name.ToLowerInvariant()] = $true
            $resolved = [IO.Path]::GetFullPath((Join-Path $stage $name))
            if (-not $resolved.StartsWith($stage + '\', [StringComparison]::OrdinalIgnoreCase)) { throw '压缩包路径越界。' }
        }
    } finally { $zip.Dispose() }
    [IO.Compression.ZipFile]::ExtractToDirectory($archive, $stage)
    $executable = Join-Path (Join-Path $stage $asset.root) $asset.entry
    if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) { throw '下载包缺少正式启动入口，未安装。' }
    Remove-Item -LiteralPath $archive
    @{schema='m4-agent-download/1';build_id=$resource.build_id;sha256=$asset.sha256;source_commit=$resource.source_commit} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $stage 'download.json') -Encoding UTF8
    Move-Item -LiteralPath $stage -Destination $target
    [pscustomobject]@{status='DOWNLOADED';entry=(Join-Path (Join-Path $target $asset.root) $asset.entry);
        next='先调用 --agent status；按操作目的进入安装检查或 recover-usb，并向用户转述当前待办。'} | ConvertTo-Json -Compress
} finally {
    $resolvedStage = [IO.Path]::GetFullPath($stage)
    if ((Test-Path -LiteralPath $stage) -and [IO.Path]::GetDirectoryName($resolvedStage) -eq $parent -and
        [IO.Path]::GetFileName($resolvedStage) -match '^\.m4-agent-[0-9a-f]{32}$') {
        Remove-Item -LiteralPath $resolvedStage -Recurse -Force
    }
}
