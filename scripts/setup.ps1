param(
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot

function Resolve-Python {
    param([string]$Requested)
    if ($Requested) {
        if (Test-Path -LiteralPath $Requested) { return (Resolve-Path -LiteralPath $Requested).Path }
        $requestedCommand = Get-Command $Requested -ErrorAction SilentlyContinue
        if ($requestedCommand) { return $requestedCommand.Source }
        throw "找不到 Python：$Requested"
    }
    $bundled = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path -LiteralPath $bundled) { return $bundled }
    foreach ($candidate in @("python", "py")) {
        $candidateCommand = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($candidateCommand) { return $candidateCommand.Source }
    }
    throw "未找到 Python 3.11+。请安装 Python，或通过 -PythonExe 指定路径。"
}

function Resolve-Pnpm {
    $pnpmCommand = Get-Command "pnpm" -ErrorAction SilentlyContinue
    if ($pnpmCommand) { return $pnpmCommand.Source }
    $bundled = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\bin\fallback\pnpm.cmd"
    if (Test-Path -LiteralPath $bundled) { return $bundled }
    throw "未找到 pnpm。请安装 Node.js 与 pnpm 后重试。"
}

$pythonPath = Resolve-Python $PythonExe
$pnpmPath = Resolve-Pnpm

Write-Host "[1/2] 安装本地星图解算依赖…"
& $pythonPath -m pip install --upgrade --target (Join-Path $projectRoot ".deps") -r (Join-Path $projectRoot "requirements.txt")

Write-Host "[2/2] 构建网页应用…"
Push-Location (Join-Path $projectRoot "frontend")
try {
    & $pnpmPath install --frozen-lockfile
    & $pnpmPath build
}
finally {
    Pop-Location
}

Write-Host "安装完成。双击 start.cmd，或运行 scripts\run.ps1 启动。" -ForegroundColor Green
