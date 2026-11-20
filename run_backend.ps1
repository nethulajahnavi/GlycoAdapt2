$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ProjectRoot 'backend'
$VenvDir = Join-Path $env:LOCALAPPDATA 'GLYCOADAPT\backend-venv'
$PythonExe = Join-Path $VenvDir 'Scripts\python.exe'

# Keep the virtual environment outside OneDrive to avoid file-lock/sync issues.
if (-not (Test-Path (Join-Path $VenvDir 'pyvenv.cfg'))) {
    if (Test-Path $VenvDir) {
        Remove-Item -Recurse -Force $VenvDir
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3.12 -m venv $VenvDir
    } else {
        python -m venv $VenvDir
    }
}

if (-not (Test-Path $PythonExe)) {
    throw "Python virtual environment was not created correctly at $VenvDir. Check that Python 3.12 is installed."
}

Set-Location $BackendDir
& $PythonExe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Could not upgrade pip.' }
& $PythonExe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed. Fix the pip error above, then run this script again.' }
& $PythonExe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
