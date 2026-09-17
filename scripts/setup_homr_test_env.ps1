param(
    [string]$Python = "python",
    [string]$IndexUrl = "https://pypi.org/simple",
    [string]$TorchIndexUrl = "https://download.pytorch.org/whl/cpu",
    [switch]$Benchmark,
    [switch]$Recreate
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$HomrRoot = Join-Path $ProjectRoot "data\omr-benchmark\homr-source"
$VenvRoot = Join-Path $ProjectRoot ".venv-homr"
$VenvPython = Join-Path $VenvRoot "Scripts\python.exe"

if (-not (Test-Path $HomrRoot)) {
    throw "HOMR source was not found at $HomrRoot"
}

if ($Recreate -and (Test-Path $VenvRoot)) {
    $resolved = (Resolve-Path $VenvRoot).Path
    if (-not $resolved.StartsWith($ProjectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a virtual environment outside the project."
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}

if (-not (Test-Path $VenvPython)) {
    & $Python -m venv $VenvRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create the HOMR virtual environment."
    }
}

function Invoke-VenvPip {
    param([string[]]$PipArgs)
    & $VenvPython -m pip install --disable-pip-version-check --index-url $IndexUrl @PipArgs
    if ($LASTEXITCODE -ne 0) {
        throw "pip failed while preparing the HOMR test environment."
    }
}

Invoke-VenvPip -PipArgs @("--upgrade", "pip")
Invoke-VenvPip -PipArgs @(
    "--editable", $HomrRoot, "pytest", "editdistance", "onnxruntime"
)
if ($Benchmark) {
    Invoke-VenvPip -PipArgs @("datasets>=5,<6")
}
& $VenvPython -m pip install --disable-pip-version-check --index-url $TorchIndexUrl torch
if ($LASTEXITCODE -ne 0) {
    throw "pip failed while installing CPU-only Torch for HOMR tests."
}

Write-Host "HOMR test environment is ready."
Write-Host "Run: .\scripts\run_homr_tests.ps1"
