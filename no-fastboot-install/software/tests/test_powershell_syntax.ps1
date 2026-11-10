param([Parameter(Mandatory=$true)][string]$Source,[string]$Downloader)
$ErrorActionPreference='Stop'
$paths=@(Get-ChildItem -LiteralPath $Source -Filter '*.ps1' -File -Recurse | Select-Object -ExpandProperty FullName)
if($Downloader){$paths += [IO.Path]::GetFullPath($Downloader)}
$failures=@()
foreach($path in $paths){
 $tokens=$null
 $parseErrors=$null
 $null=[System.Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$parseErrors)
 if($parseErrors.Count){$failures += @($parseErrors | ForEach-Object { "$path : $($_.Message)" })}
}
if($failures.Count){throw ($failures -join "`n")}
[pscustomobject]@{passed=$true;parsed_files=$paths.Count;powershell=$PSVersionTable.PSVersion.ToString();device_operations=0;script_execution=$false}|ConvertTo-Json -Compress
