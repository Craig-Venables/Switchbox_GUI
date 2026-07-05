<#
.SYNOPSIS
    Copy classification snapshot from Switchbox_GUI to memristive-iv-classifier repo.

.DESCRIPTION
    Mirrors analysis/, tools/data_consolidation/, and tools/classification_validation/
    into the sibling classifier repo. Does not overwrite docs/ or examples/ in target.

.PARAMETER TargetRepo
    Path to memristive-iv-classifier repo (default: sibling folder).

.EXAMPLE
    .\tools\sync_to_classifier_repo.ps1
    .\tools\sync_to_classifier_repo.ps1 -TargetRepo "D:\repos\memristive-iv-classifier"
#>
param(
    [string]$TargetRepo = (Join-Path (Split-Path $PSScriptRoot -Parent) "..\memristive-iv-classifier")
)

$ErrorActionPreference = "Stop"
$SourceRoot = Split-Path $PSScriptRoot -Parent

if ($TargetRepo) {
    $TargetRepo = [System.IO.Path]::GetFullPath($TargetRepo)
} else {
    $TargetRepo = [System.IO.Path]::GetFullPath((Join-Path $SourceRoot "..\memristive-iv-classifier"))
}

if (-not (Test-Path $TargetRepo)) {
    Write-Error "Target repo not found: $TargetRepo. Create memristive-iv-classifier first."
}

Write-Host "Syncing Switchbox_GUI -> $TargetRepo" -ForegroundColor Cyan

$pairs = @(
    @("analysis", "analysis"),
    @("tools\data_consolidation", "tools\data_consolidation"),
    @("tools\classification_validation", "tools\classification_validation")
)

foreach ($pair in $pairs) {
    $src = Join-Path $SourceRoot $pair[0]
    $dst = Join-Path $TargetRepo $pair[1]
    if (-not (Test-Path $src)) {
        Write-Warning "Skip missing source: $src"
        continue
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $dst -Parent) | Out-Null
    robocopy $src $dst /MIR /XD __pycache__ .pytest_cache /XF *.pyc *.log /NFL /NDL
    if ($LASTEXITCODE -ge 8) {
        Write-Error "robocopy failed for $src (exit $LASTEXITCODE)"
    }
    Write-Host "  OK: $($pair[0])" -ForegroundColor Green
}

$patchScript = Join-Path $TargetRepo "tools\apply_standalone_patch.ps1"
if (Test-Path $patchScript) {
    & $patchScript
}

Write-Host "`nDone. Commit in target repo:" -ForegroundColor Cyan
Write-Host "  cd `"$TargetRepo`""
Write-Host "  git add -A"
Write-Host "  git commit -m `"Sync from Switchbox_GUI`""
