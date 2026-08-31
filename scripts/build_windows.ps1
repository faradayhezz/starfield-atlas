param(
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$buildVenv = Join-Path $projectRoot ".build-venv"
$releaseRoot = Join-Path $projectRoot "release"
$portableRoot = Join-Path $releaseRoot "星图寻迹-Windows-x64"
$pyInstallerWork = Join-Path ([System.IO.Path]::GetTempPath()) "starfield-atlas-pyi-work"
$pyInstallerDist = Join-Path ([System.IO.Path]::GetTempPath()) "starfield-atlas-pyi-dist"
$resolvedProjectRoot = [System.IO.Path]::GetFullPath($projectRoot).TrimEnd('\')
$resolvedReleaseRoot = [System.IO.Path]::GetFullPath($releaseRoot)
if (-not $resolvedReleaseRoot.StartsWith($resolvedProjectRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "发布目录必须位于项目目录内。"
}

function Assert-LastExitCode {
    param([string]$Step)
    if ($LASTEXITCODE -ne 0) {
        throw "$Step 失败，退出代码：$LASTEXITCODE"
    }
}

if (-not $PythonExe) {
    $bundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path -LiteralPath $bundledPython) {
        $PythonExe = $bundledPython
    } else {
        $PythonExe = (Get-Command python -ErrorAction Stop).Source
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $projectRoot "frontend\dist\index.html"))) {
    throw "前端尚未构建。请先运行 setup.cmd。"
}

if (-not (Test-Path -LiteralPath (Join-Path $buildVenv "Scripts\python.exe"))) {
    & $PythonExe -m venv $buildVenv
    Assert-LastExitCode "创建独立构建环境"
}

$venvPython = Join-Path $buildVenv "Scripts\python.exe"
& $venvPython -m pip install --disable-pip-version-check --upgrade pip
Assert-LastExitCode "更新构建工具"
& $venvPython -m pip install --disable-pip-version-check -r (Join-Path $projectRoot "packaging-requirements.txt")
Assert-LastExitCode "安装桌面版构建依赖"

$localTetra3 = Join-Path $projectRoot ".deps\tetra3"
if (Test-Path -LiteralPath (Join-Path $localTetra3 "data\default_database.npz")) {
    $sitePackages = Join-Path $buildVenv "Lib\site-packages"
    $tetra3Target = Join-Path $sitePackages "tetra3"
    $resolvedBuildVenv = [System.IO.Path]::GetFullPath($buildVenv).TrimEnd('\')
    $resolvedTetra3Target = [System.IO.Path]::GetFullPath($tetra3Target)
    if (-not $resolvedTetra3Target.StartsWith($resolvedBuildVenv + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "tetra3 构建目标必须位于独立构建环境内。"
    }
    if (Test-Path -LiteralPath $tetra3Target) {
        Remove-Item -LiteralPath $tetra3Target -Recurse -Force
    }
    Copy-Item -LiteralPath $localTetra3 -Destination $tetra3Target -Recurse -Force
} else {
    & $venvPython -m pip install --disable-pip-version-check "tetra3 @ git+https://github.com/esa/tetra3.git@f9fa2eb9a32a5efc529e2d86f0b59f35b1e9028d"
    Assert-LastExitCode "安装 tetra3"
}
& $venvPython (Join-Path $projectRoot "scripts\create_app_icon.py") (Join-Path $projectRoot "packaging\starfield-atlas.ico")
Assert-LastExitCode "生成 Windows 应用图标"

$resolvedTempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\')
foreach ($temporaryPath in @($pyInstallerWork, $pyInstallerDist)) {
    $resolvedTemporaryPath = [System.IO.Path]::GetFullPath($temporaryPath)
    if (-not $resolvedTemporaryPath.StartsWith($resolvedTempRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "PyInstaller 临时目录必须位于系统临时目录内。"
    }
    if (Test-Path -LiteralPath $temporaryPath) {
        Remove-Item -LiteralPath $temporaryPath -Recurse -Force
    }
}

Push-Location $projectRoot
try {
    & $venvPython -m PyInstaller --noconfirm --clean --workpath $pyInstallerWork --distpath $pyInstallerDist (Join-Path $projectRoot "StarfieldAtlas.spec")
    Assert-LastExitCode "冻结 Windows 桌面程序"
} finally {
    Pop-Location
}

if (Test-Path -LiteralPath $portableRoot) {
    Remove-Item -LiteralPath $portableRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $portableRoot -Force | Out-Null
Copy-Item -Path (Join-Path $pyInstallerDist "星图寻迹\*") -Destination $portableRoot -Recurse -Force
Copy-Item -LiteralPath (Join-Path $projectRoot "README.md") -Destination (Join-Path $portableRoot "README.md") -Force

# Keep licence and attribution material next to the portable executable. The
# frontend bundle contains Aladin Lite, so its GPL texts must travel with every
# redistributable build. We also preserve licence files exposed by the pinned
# frontend packages and the installed Python distributions.
$thirdPartyNotice = Join-Path $projectRoot "THIRD_PARTY_NOTICES.md"
if (-not (Test-Path -LiteralPath $thirdPartyNotice)) {
    throw "缺少 THIRD_PARTY_NOTICES.md，不能生成可分发软件包。"
}
Copy-Item -LiteralPath $thirdPartyNotice -Destination (Join-Path $portableRoot "THIRD_PARTY_NOTICES.md") -Force

$projectLicense = Join-Path $projectRoot "LICENSE"
if (-not (Test-Path -LiteralPath $projectLicense)) {
    throw "缺少根目录 LICENSE，不能生成可分发软件包。"
}
Copy-Item -LiteralPath $projectLicense -Destination (Join-Path $portableRoot "LICENSE") -Force

$portableLicenses = Join-Path $portableRoot "licenses"
New-Item -ItemType Directory -Path $portableLicenses -Force | Out-Null
$frontendLicenseSets = @(
    @{ Package = "aladin-lite-3.8.1"; Root = "frontend\node_modules\aladin-lite"; Files = @("LICENSE", "COPYING", "COPYING.LESSER") },
    @{ Package = "react-19.2.8"; Root = "frontend\node_modules\react"; Files = @("LICENSE") },
    @{ Package = "react-dom-19.2.8"; Root = "frontend\node_modules\react-dom"; Files = @("LICENSE") },
    @{ Package = "leaflet-1.9.4"; Root = "frontend\node_modules\leaflet"; Files = @("LICENSE") },
    @{ Package = "vite-8.2.2"; Root = "frontend\node_modules\vite"; Files = @("LICENSE.md") },
    @{ Package = "vite-plugin-react-6.1.1"; Root = "frontend\node_modules\@vitejs\plugin-react"; Files = @("LICENSE") },
    @{ Package = "typescript-7.0.2"; Root = "frontend\node_modules\typescript"; Files = @("LICENSE", "NOTICE.txt") }
)
foreach ($licenseSet in $frontendLicenseSets) {
    $packageRoot = Join-Path $projectRoot $licenseSet.Root
    $packageTarget = Join-Path $portableLicenses $licenseSet.Package
    New-Item -ItemType Directory -Path $packageTarget -Force | Out-Null
    foreach ($licenseName in $licenseSet.Files) {
        $licenseSource = Join-Path $packageRoot $licenseName
        if (-not (Test-Path -LiteralPath $licenseSource)) {
            throw "缺少前端依赖许可证：$licenseSource"
        }
        Copy-Item -LiteralPath $licenseSource -Destination (Join-Path $packageTarget $licenseName) -Force
    }
}

$pythonSitePackages = Join-Path $buildVenv "Lib\site-packages"
$pythonLicenseRoot = Join-Path $portableLicenses "python-packages"
New-Item -ItemType Directory -Path $pythonLicenseRoot -Force | Out-Null
foreach ($distInfo in Get-ChildItem -LiteralPath $pythonSitePackages -Directory -Filter "*.dist-info") {
    $licenseFiles = Get-ChildItem -LiteralPath $distInfo.FullName -Recurse -File | Where-Object {
        $_.Name -match '^(LICENSE|LICENCE|COPYING|NOTICE|AUTHORS)(\..*)?$' -or
        $_.DirectoryName -match '[\\/]licenses([\\/]|$)'
    }
    if (-not $licenseFiles) {
        continue
    }
    $distTarget = Join-Path $pythonLicenseRoot $distInfo.Name
    $distInfoPrefix = [System.IO.Path]::GetFullPath($distInfo.FullName).TrimEnd('\') + '\'
    foreach ($licenseFile in $licenseFiles) {
        $licenseFullPath = [System.IO.Path]::GetFullPath($licenseFile.FullName)
        if (-not $licenseFullPath.StartsWith($distInfoPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "依赖许可证路径超出预期目录：$licenseFullPath"
        }
        $relativeLicensePath = $licenseFullPath.Substring($distInfoPrefix.Length)
        $licenseTarget = Join-Path $distTarget $relativeLicensePath
        New-Item -ItemType Directory -Path (Split-Path -Parent $licenseTarget) -Force | Out-Null
        Copy-Item -LiteralPath $licenseFile.FullName -Destination $licenseTarget -Force
    }
}

$instructions = @"
星图寻迹 Windows x64 便携版

1. 双击“星图寻迹.exe”即可运行，无需安装 Python 或 Node.js。
2. 可点击上传，也可把资源管理器或微信中的照片直接拖入软件窗口；微信虚拟图片可复制后按 Ctrl+V。
3. 识别期间显示真实进度、耗时和接收字节，可随时取消；失败或取消后可直接重试。
4. 照片与识别结果只保存在本机：%LOCALAPPDATA%\星图寻迹\jobs。
5. 高清星图瓦片会按需联网读取并缓存在：%LOCALAPPDATA%\星图寻迹。
6. 软件窗口关闭后，本地识别服务会自动退出。
7. 需要 Windows 10/11 x64 和 Microsoft Edge WebView2 Runtime。

项目与第三方许可证、目录和影像来源详见 LICENSE（若存在）、THIRD_PARTY_NOTICES.md、licenses、_internal\backend\data\LICENSES、各 SOURCES.md 与 README.md。
"@
Set-Content -LiteralPath (Join-Path $portableRoot "使用说明.txt") -Value $instructions -Encoding UTF8

$zipPath = Join-Path $releaseRoot "Starfield-Atlas-Windows-x64-v1.1.0.zip"
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -LiteralPath $portableRoot -DestinationPath $zipPath -CompressionLevel Optimal

$exePath = Join-Path $portableRoot "星图寻迹.exe"
$exeHash = (Get-FileHash -LiteralPath $exePath -Algorithm SHA256).Hash
$zipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash
$hashes = @(
    "星图寻迹.exe  SHA256  $exeHash"
    "$(Split-Path -Leaf $zipPath)  SHA256  $zipHash"
)
$aladinSourceArchive = Join-Path $releaseRoot "aladin-lite-v3.8.1-source.zip"
if (Test-Path -LiteralPath $aladinSourceArchive) {
    $aladinSourceHash = (Get-FileHash -LiteralPath $aladinSourceArchive -Algorithm SHA256).Hash
    $hashes += "$(Split-Path -Leaf $aladinSourceArchive)  SHA256  $aladinSourceHash"
}
Set-Content -LiteralPath (Join-Path $releaseRoot "SHA256SUMS.txt") -Value $hashes -Encoding UTF8

Write-Host "便携版已生成：$portableRoot" -ForegroundColor Green
Write-Host "压缩包已生成：$zipPath" -ForegroundColor Green
