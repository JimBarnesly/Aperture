#requires -Version 5.1
<#
Non-destructive Windows preparation only. No image writing, formatting, elevation,
execution-policy changes, downloads, network services, or Kodi setting changes.
Review README.md first. Run only where your organisation permits scripts.
#>
[CmdletBinding()]
param(
    [string]$KitPath = (Split-Path -Parent $PSScriptRoot),
    [string]$OutputPath = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Aperture-ready'),
    [ValidatePattern('^[D-Zd-z]$')][string]$UsbDriveLetter,
    [switch]$ShowDisks,
    [switch]$OpenOfficialDownloads
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-PlainDirectory([string]$Path) {
    $item = Get-Item -LiteralPath $Path
    if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "Not an ordinary directory: $Path"
    }
}
function Assert-NoReparseAncestors([string]$Path) {
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Refusing a symbolic link/junction in destination: $cursor"
            }
        }
        $cursor = Split-Path -Parent $cursor
    }
}
function Get-SafeUsbDisk([string]$Letter) {
    $partitions = @(Get-Partition -DriveLetter $Letter)
    if ($partitions.Count -ne 1) { throw 'Ambiguous volume-to-disk mapping; stop.' }
    $disks = @($partitions[0] | Get-Disk)
    if ($disks.Count -ne 1) { throw 'Ambiguous physical disk; stop.' }
    $disk = $disks[0]
    if ($disk.IsBoot -or $disk.IsSystem -or $disk.IsOffline -or $disk.IsReadOnly) {
        throw 'Refusing boot/system/offline/read-only disk.'
    }
    if ([string]$disk.BusType -notin @('USB', 'SD', 'MMC')) {
        throw 'Only positively identified USB/SD/MMC media is accepted. No internal/unknown bus.'
    }
    if ([string]::IsNullOrWhiteSpace([string]$disk.UniqueId)) { throw 'Disk has no stable identity; stop.' }
    $volume = Get-Volume -DriveLetter $Letter
    if ($volume.FileSystem -notin @('FAT', 'FAT32', 'exFAT', 'NTFS')) { throw 'Unsupported data-volume filesystem.' }
    $root = "${Letter}:\"
    if ((Test-Path -LiteralPath (Join-Path $root 'KERNEL')) -or
        (Test-Path -LiteralPath (Join-Path $root 'SYSTEM'))) {
        throw 'This looks like the LibreELEC boot card. Use a separate USB data stick.'
    }
    return $disk
}
function Assert-LocalOutput([string]$Path) {
    # Do not let -OutputPath bypass the explicit removable-media flow.
    $root = [IO.Path]::GetPathRoot($Path)
    if ($root -ine ($env:SystemDrive + '\')) {
        throw 'OutputPath must be on the Windows system drive. Use -UsbDriveLetter for removable media.'
    }
    $parts = @(Get-Partition -DriveLetter $root.Substring(0, 1))
    if ($parts.Count -ne 1) { throw 'Cannot positively identify local output volume.' }
    $disks = @($parts[0] | Get-Disk)
    if ($disks.Count -ne 1 -or [string]$disks[0].BusType -notin @('SATA', 'NVMe', 'RAID', 'ATA', 'SAS', 'SCSI', 'Spaces')) {
        throw 'Local output is not on a positively identified internal disk; stop.'
    }
}
function Assert-DestinationFiles([string]$Directory, [object[]]$Files) {
    if (-not (Test-Path -LiteralPath $Directory)) { return }
    Assert-PlainDirectory $Directory
    foreach ($existing in @(Get-ChildItem -LiteralPath $Directory -Force)) {
        $match = @($Files | Where-Object { $_.Name -ceq $existing.Name })
        if ($match.Count -ne 1 -or $existing.PSIsContainer -or
            ($existing.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Output contains unexpected files or old versions. Choose a fresh output folder.'
        }
        if ((Get-FileHash -LiteralPath $existing.FullName -Algorithm SHA256).Hash -ne $match[0].Hash) {
            throw 'Output contains a conflicting or partial file. Choose a fresh output folder.'
        }
    }
}
function Copy-VerifiedFile([string]$Source, [string]$Destination, [string]$Sha256) {
    if (Test-Path -LiteralPath $Destination) {
        $item = Get-Item -LiteralPath $Destination
        if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Unsafe existing destination: $Destination"
        }
        if ((Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash -ne $Sha256) {
            throw "Refusing to overwrite different file: $Destination. Choose a new output folder."
        }
        return
    }
    # File.Copy with overwrite=false also refuses a file created after the check.
    [IO.File]::Copy($Source, $Destination, $false)
    if ((Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash -ne $Sha256) {
        throw "Copy verification failed: $Destination. Do not install this file."
    }
}

if ($env:OS -ne 'Windows_NT') { throw 'This helper requires Windows PowerShell 5.1 or PowerShell on Windows.' }
if ($ShowDisks) {
    Get-Disk | Select-Object Number, FriendlyName, SerialNumber, BusType, Size, IsBoot, IsSystem | Format-Table -AutoSize
    Get-Volume | Select-Object DriveLetter, FileSystemLabel, FileSystem, Size, SizeRemaining | Format-Table -AutoSize
    return
}
$KitPath = (Resolve-Path -LiteralPath $KitPath).Path
Assert-PlainDirectory $KitPath
$manifestPath = Join-Path $KitPath 'checksums.json'
$entries = @(Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json)
$required = @('plugin.games.apeture', 'script.apeture.music', 'skin.apeture')
if ($entries.Count -ne 3) { throw 'Expected exactly three add-ons in checksums.json.' }
$sources = @()
foreach ($id in $required) {
    $matches = @($entries | Where-Object { $_.addon -eq $id })
    if ($matches.Count -ne 1) { throw "Missing or duplicate add-on: $id" }
    $entry = $matches[0]
    if ($entry.version -notmatch '^[0-9][0-9A-Za-z.~+_-]*$' -or
        $entry.file -cne ($id + '-' + $entry.version + '.zip') -or
        $entry.sha256 -notmatch '^[0-9a-fA-F]{64}$') { throw "Invalid manifest entry: $id" }
    $source = Join-Path $KitPath $entry.file
    $item = Get-Item -LiteralPath $source
    if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Unsafe source: $source" }
    if ($item.Length -ne $entry.bytes -or
        (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $entry.sha256) {
        throw "Checksum/size mismatch: $source. Obtain the original complete release kit."
    }
    $sources += [PSCustomObject]@{ Path = $source; Name = $entry.file; Hash = $entry.sha256 }
}
$sources += [PSCustomObject]@{ Path = $manifestPath; Name = 'checksums.json'; Hash = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash }

$instructionsPath = Join-Path $PSScriptRoot 'README.md'
$instructions = Get-Item -LiteralPath $instructionsPath
if ($instructions.PSIsContainer -or ($instructions.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw 'Missing or unsafe installer instructions.'
}
$sources += [PSCustomObject]@{ Path = $instructionsPath; Name = 'INSTALL-WINDOWS.md'; Hash = (Get-FileHash -LiteralPath $instructionsPath -Algorithm SHA256).Hash }

if ($UsbDriveLetter) {
    $UsbDriveLetter = $UsbDriveLetter.ToUpperInvariant()
    $disk = Get-SafeUsbDisk $UsbDriveLetter
    $identity = [string]$disk.UniqueId
    $diskNumber = $disk.Number
    $diskSize = $disk.Size
    Write-Host "COPY ONLY to $UsbDriveLetter`: on disk $diskNumber, $($disk.FriendlyName), $diskSize bytes."
    Write-Host 'Use a separate USB DATA stick, not the microSD to be erased for LibreELEC.'
    $answer = Read-Host "Type COPY $UsbDriveLetter to confirm (anything else cancels)"
    if ($answer -cne "COPY $UsbDriveLetter") { throw 'Cancelled; no files copied.' }
    $again = Get-SafeUsbDisk $UsbDriveLetter
    if ([string]$again.UniqueId -cne $identity -or $again.Number -ne $diskNumber -or $again.Size -ne $diskSize) {
        throw 'Media identity changed; stop and rerun.'
    }
    $OutputPath = "${UsbDriveLetter}:\Aperture-ready"
    $needed = ($sources | ForEach-Object { (Get-Item -LiteralPath $_.Path).Length } | Measure-Object -Sum).Sum
    if ((Get-Volume -DriveLetter $UsbDriveLetter).SizeRemaining -lt $needed) { throw 'Insufficient free space.' }
}
$OutputPath = [IO.Path]::GetFullPath($OutputPath)
if ($OutputPath.StartsWith('\\') -or ([IO.Path]::GetPathRoot($OutputPath) -eq $OutputPath)) {
    throw 'Use a local subfolder, not a network share or drive root.'
}
Assert-NoReparseAncestors $OutputPath
if (-not $UsbDriveLetter) { Assert-LocalOutput $OutputPath }
# Check every existing file before copying any file; reject leftover versions too.
Assert-DestinationFiles $OutputPath $sources
if (-not (Test-Path -LiteralPath $OutputPath)) { New-Item -ItemType Directory -Path $OutputPath | Out-Null }
Assert-PlainDirectory $OutputPath
foreach ($file in $sources) { Copy-VerifiedFile $file.Path (Join-Path $OutputPath $file.Name) $file.Hash }
Write-Host "Verified add-ons prepared at: $OutputPath"
Write-Host 'No operating system has been written. Nothing has been installed on the Pi.'
Write-Host 'Next: follow INSTALL-WINDOWS.md in the prepared folder. Imaging erases the ENTIRE selected card.'
if ($OpenOfficialDownloads) {
    Start-Process 'https://libreelec.tv/downloads/raspberry/'
    Start-Process 'https://www.raspberrypi.com/software/'
}
