# Pull the daily reports that GitHub Actions generated in the cloud and copy them
# into the iCloud Obsidian vault. Runs at logon + daily 09:00 KST (after the 08:00 cloud run).
# Existing files in Obsidian are never overwritten (preserves manual edits).
# NOTE: kept ASCII-only so Windows PowerShell 5.1 parses it without a UTF-8 BOM.
#       The Korean folder name is read from the UTF-8 config file at runtime.

$ErrorActionPreference = "Continue"
$repo = "C:\Users\User\Documents\github-projects-commandcenter\90_stock-monitor"
$vaultRoot = "C:\Users\User\iCloudDrive\iCloud~md~obsidian\hkyu_note"
$log = Join-Path $repo "reports\sync.log"

$stamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
"[$stamp] sync start" | Out-File $log -Append -Encoding utf8

# Read the (Korean) report folder name from the UTF-8 config so this script stays ASCII.
$cfg = Get-Content (Join-Path $repo "config\strategy.yaml") -Encoding UTF8 -Raw
$folder = ([regex]'obsidian_folder:\s*"([^"]+)"').Match($cfg).Groups[1].Value -replace '/', '\'
if (-not $folder) { $folder = "05_" + [char]0xAC1C + [char]0xC778 + "\" }  # safety fallback

$src = Join-Path $repo (Join-Path "vault" $folder)
$dst = Join-Path $vaultRoot $folder

# 1) Fetch the latest reports
Set-Location $repo
(git pull 2>&1) | Out-File $log -Append -Encoding utf8

# 2) Copy only reports that are missing in Obsidian (never overwrite existing)
if (Test-Path $src) {
    if (-not (Test-Path $dst)) { New-Item -ItemType Directory -Path $dst -Force | Out-Null }
    $copied = 0
    Get-ChildItem $src -Filter *.md | ForEach-Object {
        $target = Join-Path $dst $_.Name
        if (-not (Test-Path $target)) {
            Copy-Item $_.FullName $target -Force
            "  + copied: $($_.Name)" | Out-File $log -Append -Encoding utf8
            $copied++
        }
    }
    "[$stamp] sync done - new $copied file(s)" | Out-File $log -Append -Encoding utf8
} else {
    "[$stamp] WARN: source folder missing ($src)" | Out-File $log -Append -Encoding utf8
}
