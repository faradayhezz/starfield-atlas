param(
    [switch]$Slow
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
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
if ($Slow) { $env:RUN_SLOW_TESTS = "1" }
Push-Location $projectRoot
try {
    & $pythonPath -m unittest discover -s tests -v
}
finally {
    Pop-Location
}
