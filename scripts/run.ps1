param(
    [string]$PythonExe = "",
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot

if ($PythonExe) {
    $pythonPath = $PythonExe
} else {
    $bundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    $pythonPath = if (Test-Path -LiteralPath $bundledPython) { $bundledPython } else { $null }
    if (-not $pythonPath) {
        foreach ($candidate in @("python", "py")) {
            $candidateCommand = Get-Command $candidate -ErrorAction SilentlyContinue
            if ($candidateCommand) {
                $pythonPath = $candidateCommand.Source
                break
            }
        }
    }
}

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "未找到 Python。请先运行 setup.cmd，或使用 -PythonExe 指定 Python。"
}
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot ".deps\tetra3"))) {
    throw "本地解算依赖尚未安装，请先运行 setup.cmd。"
}
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot "frontend\dist\index.html"))) {
    throw "网页应用尚未构建，请先运行 setup.cmd。"
}

Push-Location $projectRoot
try {
    & $pythonPath -m backend.server --port $Port --open
}
finally {
    Pop-Location
}
