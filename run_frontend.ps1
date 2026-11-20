$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $ProjectRoot 'frontend')
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw 'Node.js/npm is not installed. Install Node.js 20.19+ or 22.12+ and reopen PowerShell.' }
if (-not (Test-Path 'node_modules')) { npm install }
npm run dev
