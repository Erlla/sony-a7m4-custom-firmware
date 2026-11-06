# Read-only Windows storage queries. A volume is accepted only when its disk's
# PnP ancestry reaches the exact inspected normal-mode camera, never by label.
function Get-CameraStorageVolumes {
    param([Parameter(Mandatory=$true)][string]$InstanceId)
    if ($InstanceId -notlike 'USB\VID_054C&PID_0DA5\*') { throw 'Expected a normal-mode camera instance.' }
    foreach ($volume in @(Get-Volume | Where-Object DriveLetter)) {
        $parts = @(Get-Partition -DriveLetter $volume.DriveLetter -ErrorAction SilentlyContinue)
        if ($parts.Count -ne 1) { continue }
        $disk = $parts[0] | Get-Disk -ErrorAction SilentlyContinue
        if (-not $disk -or [string]$disk.BusType -ne 'USB') { continue }
        $rows = @(Get-CimInstance Win32_DiskDrive | Where-Object Index -EQ $disk.Number)
        if ($rows.Count -ne 1) { continue }
        $node = [string]$rows[0].PNPDeviceID
        $seen = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
        for ($depth=0; $depth -lt 10 -and $node; $depth++) {
            if (-not $seen.Add($node)) { break }
            if ($node -eq $InstanceId) {
                $accessible = [bool](Test-Path -LiteralPath ($volume.DriveLetter.ToString()+':\') -PathType Container)
                [pscustomobject]@{drive_letter=[string]$volume.DriveLetter; label=[string]$volume.FileSystemLabel;
                    disk_number=$disk.Number; root_accessible=$accessible; accessible=$accessible;
                    belongs_to_camera=$true}
                break
            }
            $parent = Get-PnpDeviceProperty -InstanceId $node -KeyName DEVPKEY_Device_Parent -ErrorAction SilentlyContinue
            $node = if ($parent) { [string]$parent.Data } else { $null }
        }
    }
}
