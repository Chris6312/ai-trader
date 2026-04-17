param(
    [string]$SourceDir = "C:\dev\ai-trader",
    [string]$TargetDir = "C:\dev\ai-trader\backups",
    [int]$MaxBackups = 10
)

# Ensure target dir exists
if (-not (Test-Path -Path $TargetDir)) { New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null }

# Get git tracked files list
$gitFiles = git -C $SourceDir ls-files
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to get git tracked files from $SourceDir"; exit 1 }

# Create a temporary folder
$temp = Join-Path -Path $env:TEMP -ChildPath ([System.Guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $temp | Out-Null

try {
    foreach ($f in $gitFiles) {
        $src = Join-Path -Path $SourceDir -ChildPath $f
        $dstDir = Split-Path -Path (Join-Path $temp $f) -Parent
        if (-not (Test-Path -Path $dstDir)) { New-Item -ItemType Directory -Path $dstDir -Force | Out-Null }
        if (Test-Path -Path $src) {
            Copy-Item -Path $src -Destination (Join-Path $temp $f) -Force
        }
    }

    $timestamp = (Get-Date).ToString('yyyyMMdd_HHmmss')
    $zipName = "ai-trader_$timestamp.zip"
    $zipPath = Join-Path -Path $TargetDir -ChildPath $zipName

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory($temp, $zipPath)

    # Manage old backups
    $zips = Get-ChildItem -Path $TargetDir -Filter "ai-trader_*.zip" | Sort-Object CreationTime
    while ($zips.Count -gt $MaxBackups) {
        $old = $zips[0]
        Remove-Item -Path $old.FullName -Force
        $zips = Get-ChildItem -Path $TargetDir -Filter "ai_trading_bot_*.zip" | Sort-Object CreationTime
    }

    Write-Output "Backup created: $zipPath"
} finally {
    # Cleanup temp
    Remove-Item -Path $temp -Recurse -Force
}