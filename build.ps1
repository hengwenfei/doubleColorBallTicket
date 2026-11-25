param(
    [switch]$ExeOnly
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BuildEnvironment = Join-Path $ProjectRoot ".build-venv"
$Python = Join-Path $BuildEnvironment "Scripts\python.exe"
$InnoSetupScript = Join-Path $ProjectRoot "installer.iss"
$AppName = "双色球选号工具"

Set-Location $ProjectRoot

if (-not (Test-Path $Python)) {
    $PythonLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($PythonLauncher) {
        & $PythonLauncher.Source -3 -m venv $BuildEnvironment
    }
    else {
        $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if (-not $PythonCommand) {
            throw "未找到 Python 3。请先安装 Python 3 并重新运行。"
        }
        & $PythonCommand.Source -m venv $BuildEnvironment
    }
    if ($LASTEXITCODE -ne 0) {
        throw "创建打包用 Python 虚拟环境失败。"
    }
}

& $Python -m pip install --upgrade pyinstaller
if ($LASTEXITCODE -ne 0) {
    throw "安装 PyInstaller 失败。请检查网络或 Python 环境。"
}

& $Python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name $AppName --distpath (Join-Path $ProjectRoot "dist") `
    --workpath (Join-Path $ProjectRoot "build") `
    --specpath (Join-Path $ProjectRoot "build") `
    (Join-Path $ProjectRoot "ssq_tool.py")
if ($LASTEXITCODE -ne 0) {
    throw "生成 exe 失败。"
}

$ExePath = Join-Path $ProjectRoot "dist\$AppName.exe"
Write-Host "已生成：$ExePath"

if ($ExeOnly) {
    return
}

$IsccCommand = Get-Command ISCC.exe -ErrorAction SilentlyContinue
$IsccPath = $null
if ($IsccCommand) {
    $IsccPath = $IsccCommand.Source
}
else {
    $InnoCandidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    )
    foreach ($Candidate in $InnoCandidates) {
        if (Test-Path $Candidate) {
            $IsccPath = $Candidate
            break
        }
    }
}

if (-not $IsccPath) {
    throw "已生成 exe，但未找到 Inno Setup 6 编译器 (ISCC.exe)。安装 Inno Setup 6，或使用 -ExeOnly 仅生成 exe。"
}

& $IsccPath "/DSourceDir=$ProjectRoot" $InnoSetupScript
if ($LASTEXITCODE -ne 0) {
    throw "编译安装程序失败。"
}

Write-Host "安装程序已生成于：$(Join-Path $ProjectRoot 'dist')"
