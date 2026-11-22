$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
if (Test-Path -LiteralPath (Join-Path $PSScriptRoot '.deps')) {
    $env:PYTHONPATH = (Join-Path $PSScriptRoot '.deps') + [IO.Path]::PathSeparator + $env:PYTHONPATH
}
$env:PYTHONUTF8 = '1'
$env:OPENBLAS_NUM_THREADS = '1'
$env:MPLCONFIGDIR = Join-Path $PSScriptRoot '.mplcache'
python -m chladni.labor_web @args
exit $LASTEXITCODE
