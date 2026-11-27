$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
New-Item -ItemType Directory -Force '.tools','.cache\downloads','.cache\python-bin' | Out-Null
$taskUv = Join-Path $taskRoot '.tools\uv.exe'
if (-not (Test-Path -LiteralPath $taskUv)) {
    $taskRelease = Invoke-RestMethod 'https://api.github.com/repos/astral-sh/uv/releases/tags/0.13.5'
    $taskAsset = $taskRelease.assets | Where-Object { $_.name -eq 'uv-x86_64-pc-windows-msvc.zip' }
    $taskZip = Join-Path $taskRoot '.cache\downloads\uv.zip'
    Invoke-WebRequest -Uri $taskAsset.browser_download_url -OutFile $taskZip
    if (-not $taskAsset.digest -or (Get-FileHash -LiteralPath $taskZip -Algorithm SHA256).Hash.ToLower() -ne $taskAsset.digest.Substring(7)) { throw 'uv archive checksum failed' }
    Expand-Archive -LiteralPath $taskZip -DestinationPath (Join-Path $taskRoot '.tools\uv-bootstrap') -Force
    $taskBinary = Get-ChildItem -LiteralPath (Join-Path $taskRoot '.tools\uv-bootstrap') -Filter uv.exe -Recurse | Select-Object -First 1
    Copy-Item -LiteralPath $taskBinary.FullName -Destination $taskUv
}
$env:UV_PYTHON_INSTALL_DIR = Join-Path $taskRoot '.tools\python'
$env:UV_PYTHON_BIN_DIR = Join-Path $taskRoot '.cache\python-bin'
$env:UV_CACHE_DIR = Join-Path $taskRoot '.cache\uv'
& $taskUv python install 3.12.15
if ($LASTEXITCODE -ne 0) { throw 'Local Python installation failed' }
& $taskUv sync --frozen --python 3.12.15
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& '.\.venv\Scripts\python.exe' 'scripts\install_tools.py'
if ($LASTEXITCODE -ne 0) { throw 'Unity installation failed' }
& '.\.venv\Scripts\python.exe' 'scripts\repair_urp_metadata.py'
Write-Host 'Local setup complete. Use Activate Unity.cmd if a license is not active, then Build Simulator.cmd.'
