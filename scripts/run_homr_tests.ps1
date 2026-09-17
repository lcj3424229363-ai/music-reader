$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$HomrRoot = Join-Path $ProjectRoot "data\omr-benchmark\homr-source"
$VenvPython = Join-Path $ProjectRoot ".venv-homr\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    throw "HOMR test environment is missing. Run .\scripts\setup_homr_test_env.ps1 first."
}

# The downloaded source is a benchmark snapshot, not a nested Git checkout.
# Its pre-commit hook test is repository hygiene rather than HOMR behavior.
& $VenvPython -m pytest $HomrRoot\tests -q -k "not isset_precommit_hooks"
if ($LASTEXITCODE -ne 0) {
    throw "HOMR tests failed."
}
