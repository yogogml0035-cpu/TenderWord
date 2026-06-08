param(
    [switch]$BackendOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$script:LauncherName = "start-dev"
$script:LauncherFileName = "start-dev.ps1"
$script:LauncherRelativePath = "scripts\start-dev.ps1"

function Write-Info {
    param([string]$Message)

    Write-Host "[$script:LauncherName] $Message" -ForegroundColor Cyan
}

function Fail {
    param([string]$Message)

    Write-Host "[$script:LauncherName] ERROR: $Message" -ForegroundColor Red
    exit 1
}

function Assert-PathExists {
    param(
        [string]$Path,
        [string]$FailureMessage
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        Fail $FailureMessage
    }
}

function Test-WindowsVenvCompatible {
    param([string]$PyVenvConfigPath)

    if (-not (Test-Path -LiteralPath $PyVenvConfigPath)) {
        return $false
    }

    $configContent = Get-Content -LiteralPath $PyVenvConfigPath -Raw -ErrorAction Stop
    return ($configContent -notmatch "(?m)^(home|executable|command)\s*=\s*/")
}

function Assert-PathWithinDirectory {
    param(
        [string]$Path,
        [string]$Directory
    )

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $fullDirectory = [System.IO.Path]::GetFullPath($Directory).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar

    if (-not $fullPath.StartsWith($fullDirectory, [System.StringComparison]::OrdinalIgnoreCase)) {
        Fail "拒绝清理目录外路径：$fullPath"
    }
}

function Remove-DirectoryIfPresent {
    param(
        [string]$Path,
        [string]$ContainingDirectory
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    Assert-PathWithinDirectory -Path $Path -Directory $ContainingDirectory
    Remove-Item -LiteralPath $Path -Recurse -Force
}

function Move-BackendVenvAside {
    param(
        [string]$VenvDir,
        [string]$BackendDir,
        [string]$BaseName,
        [string]$Reason
    )

    if (-not (Test-Path -LiteralPath $VenvDir)) {
        return
    }

    Assert-PathWithinDirectory -Path $VenvDir -Directory $BackendDir

    $targetName = $BaseName
    if (Test-Path -LiteralPath (Join-Path $BackendDir $targetName)) {
        $targetName = "$BaseName-$(Get-Date -Format yyyyMMddHHmmss)"
    }

    Write-Info "检测到 $Reason，已保留为 backend\$targetName。"
    Rename-Item -LiteralPath $VenvDir -NewName $targetName
}

function Test-PythonCommand {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    $testArgs = @()
    if ($Arguments) {
        $testArgs += $Arguments
    }
    $testArgs += @("-c", "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)")

    & $FilePath @testArgs *> $null
    return ($LASTEXITCODE -eq 0)
}

function Get-WindowsPythonCommand {
    $py = Get-Command py.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($py) {
        foreach ($versionArg in @("-3.12", "-3.11", "-3")) {
            if (Test-PythonCommand -FilePath $py.Source -Arguments @($versionArg)) {
                return [pscustomobject]@{
                    FilePath = $py.Source
                    Arguments = @($versionArg)
                }
            }
        }
    }

    $python = Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($python -and (Test-PythonCommand -FilePath $python.Source -Arguments @())) {
        return [pscustomobject]@{
            FilePath = $python.Source
            Arguments = @()
        }
    }

    Fail "未找到可创建后端虚拟环境的 Windows Python 3.11+。请先安装 Python 3.11 或 3.12，并确保 py.exe 或 python.exe 在 PATH 中。"
}

function New-WindowsBackendVenv {
    param(
        [string]$VenvDir
    )

    $pythonCommand = Get-WindowsPythonCommand
    $createArgs = @()
    if ($pythonCommand.Arguments) {
        $createArgs += $pythonCommand.Arguments
    }
    $createArgs += @("-m", "venv", $VenvDir)

    Write-Info "正在创建 Windows 后端虚拟环境 backend\.venv..."
    & $pythonCommand.FilePath @createArgs
    if ($LASTEXITCODE -ne 0) {
        Fail "创建 backend\.venv 失败。"
    }
}

function Install-WindowsBackendRequirements {
    param(
        [string]$PythonExe,
        [string]$RequirementsPath
    )

    Assert-PathExists -Path $PythonExe -FailureMessage "缺少 backend\.venv\Scripts\python.exe，无法安装后端依赖。"
    Assert-PathExists -Path $RequirementsPath -FailureMessage "缺少 backend\requirements.txt，无法安装后端依赖。"

    Write-Info "正在安装 Windows 后端依赖 backend\requirements.txt..."
    & $PythonExe -m pip install -r $RequirementsPath
    if ($LASTEXITCODE -ne 0) {
        Fail "安装 Windows 后端依赖失败。"
    }
}

function Ensure-WindowsBackendVenv {
    param(
        [string]$BackendDir,
        [string]$RequirementsPath
    )

    $venvDir = Join-Path $BackendDir ".venv"
    $pythonExe = Join-Path $venvDir "Scripts\python.exe"
    $pyVenvConfig = Join-Path $venvDir "pyvenv.cfg"

    if ((Test-Path -LiteralPath $pyVenvConfig) -and
        -not (Test-WindowsVenvCompatible -PyVenvConfigPath $pyVenvConfig)) {
        Move-BackendVenvAside -VenvDir $venvDir -BackendDir $BackendDir -BaseName ".venv-linux" -Reason "backend\.venv 是 WSL/Linux Python 环境"
    } elseif ((Test-Path -LiteralPath $venvDir) -and
        (-not (Test-Path -LiteralPath $pythonExe) -or -not (Test-Path -LiteralPath $pyVenvConfig))) {
        Move-BackendVenvAside -VenvDir $venvDir -BackendDir $BackendDir -BaseName ".venv-backup" -Reason "backend\.venv 不完整"
    }

    if (-not (Test-Path -LiteralPath $pythonExe)) {
        New-WindowsBackendVenv -VenvDir $venvDir
        Install-WindowsBackendRequirements -PythonExe $pythonExe -RequirementsPath $RequirementsPath
    }
}

function Get-CommandPath {
    param(
        [string]$Name,
        [string]$FailureMessage
    )

    $command = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $command) {
        Fail $FailureMessage
    }

    return $command.Source
}

function Get-PowerShellHostPath {
    if ($PSVersionTable.PSEdition -eq "Core") {
        $pwsh = Get-Command pwsh -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($pwsh) {
            return $pwsh.Source
        }
    }

    $powershell = Get-Command powershell -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($powershell) {
        return $powershell.Source
    }

    $selfPath = (Get-Process -Id $PID -ErrorAction SilentlyContinue).Path
    if ($selfPath) {
        return $selfPath
    }

    Fail "未找到可用的 PowerShell 可执行文件。"
}

function Test-WindowsFrontendDependenciesReady {
    param(
        [string]$FrontendDir,
        [string]$NodeExe
    )

    $nextCmd = Join-Path $FrontendDir "node_modules\.bin\next.cmd"
    if (-not (Test-Path -LiteralPath $nextCmd)) {
        return $false
    }

    Push-Location $FrontendDir
    try {
        & $NodeExe -e "require('lightningcss')" *> $null
        return ($LASTEXITCODE -eq 0)
    } finally {
        Pop-Location
    }
}

function Test-ReparsePoint {
    param([Parameter(Mandatory = $true)]$Item)

    return (($Item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)
}

function Get-NodeModulesPlatform {
    param([string]$Path)

    if (Test-Path -LiteralPath (Join-Path $Path "lightningcss-win32-x64-msvc")) {
        return "win"
    }

    if ((Test-Path -LiteralPath (Join-Path $Path "lightningcss-linux-x64-gnu")) -or
        (Test-Path -LiteralPath (Join-Path $Path "lightningcss-linux-x64-musl"))) {
        return "wsl"
    }

    return ""
}

function Remove-NodeModulesForRepair {
    param([string]$FrontendDir)

    $nodeModules = Join-Path $FrontendDir "node_modules"
    if (-not (Test-Path -LiteralPath $nodeModules)) {
        return
    }

    $item = Get-Item -LiteralPath $nodeModules -Force
    if ($item.LinkType -in @("Junction", "SymbolicLink") -or (Test-ReparsePoint $item)) {
        [System.IO.Directory]::Delete($nodeModules)
        return
    }

    $platform = Get-NodeModulesPlatform -Path $nodeModules
    if ($platform -and $platform -ne "win") {
        $preservePath = Join-Path $FrontendDir "node_modules-$platform"
        if (Test-Path -LiteralPath $preservePath) {
            Fail "frontend\node_modules 是 $platform 依赖目录，且 frontend\node_modules-$platform 已存在。请先手动确认后移走其中一个目录。"
        }

        Rename-Item -LiteralPath $nodeModules -NewName "node_modules-$platform"
        return
    }

    Remove-DirectoryIfPresent -Path $nodeModules -ContainingDirectory $FrontendDir
}

function Repair-WindowsFrontendDependencies {
    param(
        [string]$RepoRoot,
        [string]$FrontendDir,
        [string]$NpmCmd
    )

    $nodeModulesWin = Join-Path $FrontendDir "node_modules-win"
    $nodeModules = Join-Path $FrontendDir "node_modules"

    Write-Info "正在安装 Windows 前端依赖到 frontend\node_modules..."
    Remove-NodeModulesForRepair -FrontendDir $FrontendDir
    Remove-DirectoryIfPresent -Path $nodeModulesWin -ContainingDirectory $FrontendDir
    Remove-DirectoryIfPresent -Path (Join-Path $FrontendDir ".next") -ContainingDirectory $FrontendDir

    Push-Location $FrontendDir
    try {
        & $NpmCmd ci
        if ($LASTEXITCODE -ne 0) {
            Fail "npm ci 失败，无法安装 Windows 前端依赖。"
        }

        if (-not (Test-Path -LiteralPath $nodeModules)) {
            Fail "npm ci 完成后未生成 frontend\node_modules。"
        }

        if (Test-Path -LiteralPath $nodeModulesWin) {
            Remove-DirectoryIfPresent -Path $nodeModulesWin -ContainingDirectory $FrontendDir
        }
    } finally {
        Pop-Location
    }

    Write-Info "Windows 前端依赖已安装到 frontend\node_modules。"
}

function Get-PortOccupant {
    param([int]$Port)

    if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
        $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if (-not $listener) {
            return $null
        }

        $processName = ""
        try {
            $processName = (Get-Process -Id $listener.OwningProcess -ErrorAction Stop).ProcessName
        } catch {
        }

        return [pscustomobject]@{
            Port = $Port
            Pid = $listener.OwningProcess
            ProcessName = $processName
        }
    }

    $line = netstat -ano -p tcp |
        Select-String -Pattern "[:.]$Port\s+.*LISTENING\s+(\d+)" |
        Select-Object -First 1

    if (-not $line) {
        return $null
    }

    $pid = [int]$line.Matches[0].Groups[1].Value
    $processName = ""
    try {
        $processName = (Get-Process -Id $pid -ErrorAction Stop).ProcessName
    } catch {
    }

    return [pscustomobject]@{
        Port = $Port
        Pid = $pid
        ProcessName = $processName
    }
}

function Assert-PortFree {
    param([int]$Port)

    $occupant = Get-PortOccupant -Port $Port
    if (-not $occupant) {
        return
    }

    $suffix = if ($occupant.ProcessName) {
        "（进程: $($occupant.ProcessName), PID: $($occupant.Pid)）"
    } else {
        "（PID: $($occupant.Pid)）"
    }

    Fail "端口 $Port 已被占用$suffix。请先释放端口后再运行 .\$script:LauncherRelativePath。"
}

function Escape-SingleQuotedText {
    param([string]$Text)

    return $Text -replace "'", "''"
}

function Test-IsUncPath {
    param([string]$Path)

    return $Path.StartsWith("\\")
}

function Start-ServiceWindow {
    param(
        [string]$ShellPath,
        [string]$Title,
        [string]$WorkingDirectory,
        [string]$Banner,
        [string]$CommandText
    )

    $escapedTitle = Escape-SingleQuotedText -Text $Title
    $escapedDir = Escape-SingleQuotedText -Text $WorkingDirectory
    $escapedBanner = Escape-SingleQuotedText -Text $Banner
    $scriptBlock = @(
        "& { "
        "`$host.UI.RawUI.WindowTitle = '$escapedTitle'; "
        "Set-Location -LiteralPath '$escapedDir'; "
        "Write-Host '$escapedBanner' -ForegroundColor Cyan; "
        "$CommandText }"
    ) -join ""

    $startProcessArgs = @{
        FilePath = $ShellPath
        ArgumentList = @("-NoExit", "-Command", $scriptBlock)
        PassThru = $true
    }

    if (-not (Test-IsUncPath -Path $WorkingDirectory)) {
        $startProcessArgs.WorkingDirectory = $WorkingDirectory
    }

    return Start-Process @startProcessArgs
}

function Start-CmdServiceWindow {
    param(
        [string]$CmdPath,
        [string]$Title,
        [string]$WorkingDirectory,
        [string]$Banner,
        [string]$CommandText
    )

    $cmdCommand = 'title ' + $Title + ' & pushd "' + $WorkingDirectory + '" && echo ' + $Banner + ' && ' + $CommandText

    $startProcessArgs = @{
        FilePath = $CmdPath
        ArgumentList = @("/d", "/k", $cmdCommand)
        PassThru = $true
    }

    if ($env:SystemRoot -and -not (Test-IsUncPath -Path $env:SystemRoot) -and (Test-Path -LiteralPath $env:SystemRoot)) {
        $startProcessArgs.WorkingDirectory = $env:SystemRoot
    }

    return Start-Process @startProcessArgs
}

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$currentDir = [System.IO.Path]::GetFullPath((Get-Location).Path)
$launchFrontend = -not $BackendOnly

if ($currentDir -ne $repoRoot) {
    Write-Info "检测到当前目录不是仓库根目录，已自动切换到仓库根目录：$repoRoot"
    Set-Location -LiteralPath $repoRoot
}

$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"

$backendEntry = Join-Path $backendDir "main.py"
$backendPython = Join-Path $backendDir ".venv\Scripts\python.exe"
$backendRequirements = Join-Path $backendDir "requirements.txt"
$frontendPackage = Join-Path $frontendDir "package.json"
$backendEnv = Join-Path $backendDir ".env"
$frontendEnv = Join-Path $frontendDir ".env.local"
$frontendDepsLinkScript = Join-Path $repoRoot "scripts\set-frontend-deps-link-win.ps1"

Assert-PathExists -Path $backendEntry -FailureMessage "未找到 backend\main.py。请确认当前目录是项目根目录。"
Assert-PathExists -Path $backendRequirements -FailureMessage "缺少 backend\requirements.txt，无法安装后端依赖。"
Ensure-WindowsBackendVenv -BackendDir $backendDir -RequirementsPath $backendRequirements
Assert-PathExists -Path $backendEnv -FailureMessage "缺少 backend\.env。请先参考 backend\.env.example 创建环境文件。"

$shellPath = Get-PowerShellHostPath
$frontendNodeExe = $null
$frontendNpmCmd = $null

if ($launchFrontend) {
    Assert-PathExists -Path $frontendPackage -FailureMessage "未找到 frontend\package.json。请确认当前目录是项目根目录。"
    Assert-PathExists -Path $frontendEnv -FailureMessage "缺少 frontend\.env.local。请先参考 frontend\.env.local.example 创建环境文件。"
    Assert-PathExists -Path $frontendDepsLinkScript -FailureMessage "缺少 scripts\set-frontend-deps-link-win.ps1。"
    $frontendNodeExe = Get-CommandPath -Name "node.exe" -FailureMessage "未找到 node.exe 命令。请先安装 Windows Node.js 或确保 node.exe 在 PATH 中。"
    $frontendNpmCmd = Get-CommandPath -Name "npm.cmd" -FailureMessage "未找到 npm.cmd 命令。请先安装 Windows Node.js 或确保 npm.cmd 在 PATH 中。"
}

Assert-PortFree -Port 8000
if ($launchFrontend) {
    Assert-PortFree -Port 8502
}

if ($launchFrontend) {
    Write-Info "切换前端依赖到 Windows 模式..."
    & $frontendDepsLinkScript -Target win -RepoRoot $repoRoot
    if ($LASTEXITCODE -ne 0) {
        Fail "无法切换 frontend\node_modules 到 node_modules-win。"
    }

    if (-not (Test-WindowsFrontendDependenciesReady -FrontendDir $frontendDir -NodeExe $frontendNodeExe)) {
        Write-Info "检测到 Windows 原生前端依赖缺失或平台不匹配，将执行 npm ci 修复。"
        Repair-WindowsFrontendDependencies -RepoRoot $repoRoot -FrontendDir $frontendDir -NpmCmd $frontendNpmCmd
    }
}

$frontendNpmCmdLiteral = "'" + (Escape-SingleQuotedText -Text $frontendNpmCmd) + "'"
$frontendCommandText = @"
if (Test-Path -LiteralPath ".next") {
    Write-Host "[frontend] 正在清理 Next.js 缓存..." -ForegroundColor Yellow
    Remove-Item -LiteralPath ".next" -Recurse -Force
}
& $frontendNpmCmdLiteral run dev
"@
$frontendBanner = "[frontend] 正在执行 npm run dev"
$frontendTitle = "TenderWord Frontend Dev (8502)"
$frontendSummary = "dev (npm run dev)"

Write-Info "运行后端预检查..."
$backendCheckOutput = & $backendPython -c "import asyncio; import fastapi; import uvicorn; import pydantic_settings; import backend.main" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Info "后端预检查失败，尝试重新安装 Windows 后端依赖..."
    Install-WindowsBackendRequirements -PythonExe $backendPython -RequirementsPath $backendRequirements
    $backendCheckOutput = & $backendPython -c "import asyncio; import fastapi; import uvicorn; import pydantic_settings; import backend.main" 2>&1
    if ($LASTEXITCODE -ne 0) {
        $details = ($backendCheckOutput | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
        Fail "后端预检查失败。请先修复 Python/依赖/本机环境问题后再启动。`n$details"
    }
}

if ($launchFrontend) {
    Write-Info "预检查通过，正在启动前后端窗口..."
} else {
    Write-Info "预检查通过，正在启动后端窗口..."
}
$backendProcess = $null
$frontendProcess = $null

try {
    $backendPythonLiteral = "'" + (Escape-SingleQuotedText -Text $backendPython) + "'"
    # 只监听实际源码子目录，避免 watchfiles 扫到 .venv-linux 等开发环境目录。
    $backendReloadArgsText = @(
        "--reload"
        "--reload-dir agents"
        "--reload-dir api"
        "--reload-dir config"
        "--reload-dir core"
        "--reload-dir graphs"
        "--reload-dir helper"
        "--reload-dir models"
        "--reload-dir nodes"
        "--reload-dir prompts"
        "--reload-dir services"
        "--reload-dir skills"
        "--reload-dir states"
        "--reload-dir task"
        "--reload-dir util"
    ) -join " "
    $backendCommandText = @(
        "`$env:WATCHFILES_FORCE_POLLING='true'; "
        "`$env:WATCHFILES_POLL_DELAY_MS='300'; "
        "& $backendPythonLiteral -m uvicorn main:app --host 0.0.0.0 --port 8000 $backendReloadArgsText"
    ) -join ""
    $backendProcess = Start-ServiceWindow `
        -ShellPath $shellPath `
        -Title "TenderWord Backend (8000)" `
        -WorkingDirectory $backendDir `
        -Banner "[backend] 正在执行 uvicorn main:app --reload (热加载模式, watchfiles 轮询)" `
        -CommandText $backendCommandText

    if ($launchFrontend) {
        Start-Sleep -Seconds 1

        $frontendProcess = Start-ServiceWindow `
            -ShellPath $shellPath `
            -Title $frontendTitle `
            -WorkingDirectory $frontendDir `
            -Banner $frontendBanner `
            -CommandText $frontendCommandText
    }
} catch {
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    }

    throw
}

Write-Host ""
if ($launchFrontend) {
    Write-Host "TenderWord 开发环境已拉起：" -ForegroundColor Green
} else {
    Write-Host "TenderWord 后端开发环境已拉起：" -ForegroundColor Green
}
Write-Host "  Backend PID : $($backendProcess.Id)" -ForegroundColor Green
if ($launchFrontend) {
    Write-Host "  Frontend PID: $($frontendProcess.Id)" -ForegroundColor Green
    Write-Host "  Frontend Run: $frontendSummary" -ForegroundColor Green
    Write-Host "  Frontend URL: http://localhost:8502/tender" -ForegroundColor Green
}
Write-Host "  Backend URL : http://localhost:8000" -ForegroundColor Green
Write-Host "  Health URL  : http://localhost:8000/health" -ForegroundColor Green
Write-Host ""
if ($launchFrontend) {
    Write-Host "停止方式：在两个子窗口中按 Ctrl+C，或直接关闭子窗口。" -ForegroundColor Yellow
} else {
    Write-Host "停止方式：在后端子窗口中按 Ctrl+C，或直接关闭子窗口。" -ForegroundColor Yellow
}
