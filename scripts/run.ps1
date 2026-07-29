$ErrorActionPreference = "Stop"
$projectDirectory = Split-Path -Parent $PSScriptRoot
$pythonExecutable = Join-Path $projectDirectory ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    throw "Virtual environment not found. Follow the installation steps in README.md."
}

$env:PYTHONPYCACHEPREFIX = Join-Path $projectDirectory "runtime\pycache"
& $pythonExecutable -m persistent_tracker
