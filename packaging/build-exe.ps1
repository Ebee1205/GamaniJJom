param([string]$Python = "")
$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
if (-not $Python) {
    $projectPython = Join-Path $projectPath '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $projectPython) { $Python = $projectPython }
    else { $Python = (Get-Command python -ErrorAction Stop).Source }
}
$buildEnvironment = Join-Path $PSScriptRoot '.venv-build'
$buildPython = Join-Path $buildEnvironment 'Scripts\python.exe'
$requirements = Join-Path $PSScriptRoot 'requirements-build.txt'
$spec = Join-Path $PSScriptRoot 'GamaniJJom.spec'
$workPath = Join-Path $PSScriptRoot 'build'
$distPath = Join-Path $projectPath 'dist'
$prodConfig = Join-Path $projectPath 'src\config\gamani-jjom.prod.cfg.json'
if (-not (Test-Path -LiteralPath $prodConfig -PathType Leaf)) {
    throw "Production configuration not found: $prodConfig"
}
if (-not (Test-Path -LiteralPath $buildPython)) {
    & $Python -m venv --system-site-packages $buildEnvironment
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the build environment.' }
}

# Use pip's CA bundle rather than a stale PostgreSQL certificate environment.
$previousCert = $env:PIP_CERT
$previousRequestsCert = $env:REQUESTS_CA_BUNDLE
$previousSslCert = $env:SSL_CERT_FILE
$previousLocalAppData = $env:LOCALAPPDATA
$previousGamaniConfig = $env:GAMANI_CONFIG
Push-Location -LiteralPath $projectPath
try {
    $cert = & $buildPython -c 'from pip._vendor.certifi import where; print(where())'
    if ($LASTEXITCODE -ne 0) { throw 'Could not locate the certificate bundle.' }
    $env:PIP_CERT = $cert
    $env:REQUESTS_CA_BUNDLE = $cert
    $env:SSL_CERT_FILE = $cert
    & $buildPython -m pip install --disable-pip-version-check -r $requirements
    if ($LASTEXITCODE -ne 0) { throw 'Build dependencies could not be installed.' }
    & $buildPython -B src/main.py --check --cfg $prodConfig
    if ($LASTEXITCODE -ne 0) { throw 'Source startup check failed.' }
    & $buildPython -m PyInstaller --noconfirm --clean --workpath $workPath --distpath $distPath $spec
    if ($LASTEXITCODE -ne 0) { throw 'EXE build failed.' }
    $executable = Join-Path $distPath 'GamaniJJom.exe'
    # Verify the bundled production template with fresh, isolated user data.
    $checkData = Join-Path $workPath ("frozen-check-" + [guid]::NewGuid().ToString('N'))
    $env:LOCALAPPDATA = $checkData
    $env:GAMANI_CONFIG = $null
    $check = Start-Process -FilePath $executable -ArgumentList '--check' -PassThru -Wait -WindowStyle Hidden
    if ($check.ExitCode -ne 0) { throw "Frozen startup check failed. See $checkData\GamaniJJom\startup.log." }
    $smoke = Start-Process -FilePath $executable -ArgumentList '--smoke-test' -PassThru -Wait -WindowStyle Hidden
    if ($smoke.ExitCode -ne 0) { throw "Frozen GUI smoke test failed. See $checkData\GamaniJJom\logs." }
    Get-FileHash -LiteralPath $executable -Algorithm SHA256
    Write-Host "Built and checked: $executable"
}
finally {
    Pop-Location
    $env:PIP_CERT = $previousCert
    $env:REQUESTS_CA_BUNDLE = $previousRequestsCert
    $env:SSL_CERT_FILE = $previousSslCert
    $env:LOCALAPPDATA = $previousLocalAppData
    $env:GAMANI_CONFIG = $previousGamaniConfig
}
