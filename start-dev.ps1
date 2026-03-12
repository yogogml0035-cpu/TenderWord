Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$script:LauncherName = "start-dev"
$script:LauncherFileName = "start-dev.ps1"

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

    Fail "端口 $Port 已被占用$suffix。请先释放端口后再运行 .\$script:LauncherFileName。"
}

function Escape-SingleQuotedText {
    param([string]$Text)

    return $Text -replace "'", "''"
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
    $scriptBlock = "& { " +
        "`$host.UI.RawUI.WindowTitle = '$escapedTitle'; " +
        "Set-Location -LiteralPath '$escapedDir'; " +
        "Write-Host '$escapedBanner' -ForegroundColor Cyan; " +
        "$CommandText }"

    return Start-Process `
        -FilePath $ShellPath `
        -WorkingDirectory $WorkingDirectory `
        -ArgumentList @("-NoExit", "-Command", $scriptBlock) `
        -PassThru
}

$repoRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$currentDir = [System.IO.Path]::GetFullPath((Get-Location).Path)

if ($currentDir -ne $repoRoot) {
    Fail "请先进入仓库根目录后再运行：`ncd $repoRoot`n.\$script:LauncherFileName"
}

$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"

$backendEntry = Join-Path $backendDir "main.py"
$backendPython = Join-Path $backendDir ".venv\Scripts\python.exe"
$frontendPackage = Join-Path $frontendDir "package.json"
$backendEnv = Join-Path $backendDir ".env"
$frontendEnv = Join-Path $frontendDir ".env.local"
$frontendNodeModules = Join-Path $frontendDir "node_modules"

Assert-PathExists -Path $backendEntry -FailureMessage "未找到 backend\main.py。请确认当前目录是项目根目录。"
Assert-PathExists -Path $backendPython -FailureMessage "缺少 backend\.venv\Scripts\python.exe。请先在 backend 目录创建并安装虚拟环境。"
Assert-PathExists -Path $frontendPackage -FailureMessage "未找到 frontend\package.json。请确认当前目录是项目根目录。"
Assert-PathExists -Path $backendEnv -FailureMessage "缺少 backend\.env。请先参考 backend\.env.example 创建环境文件。"
Assert-PathExists -Path $frontendEnv -FailureMessage "缺少 frontend\.env.local。请先参考 frontend\.env.local.example 创建环境文件。"
Assert-PathExists -Path $frontendNodeModules -FailureMessage "缺少 frontend\node_modules。请先进入 frontend 执行 npm install。"

$null = Get-CommandPath -Name "npm" -FailureMessage "未找到 npm 命令。请先安装 Node.js 或确保 npm 在 PATH 中。"
$shellPath = Get-PowerShellHostPath

Assert-PortFree -Port 8000
Assert-PortFree -Port 8502

$frontendCommandText = "npm run dev"
$frontendBanner = "[frontend] 正在执行 npm run dev"
$frontendTitle = "TenderWord Frontend Dev (8502)"
$frontendSummary = "dev (npm run dev)"

Write-Info "运行后端预检查..."
$backendCheckOutput = & $backendPython -c "import asyncio; import fastapi; import uvicorn; import pydantic_settings; import backend.main" 2>&1
if ($LASTEXITCODE -ne 0) {
    $details = ($backendCheckOutput | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    Fail "后端预检查失败。请先修复 Python/依赖/本机环境问题后再启动。`n$details"
}

Write-Info "预检查通过，正在启动前后端窗口..."
$backendProcess = $null
$frontendProcess = $null

try {
    $backendPythonLiteral = "'" + (Escape-SingleQuotedText -Text $backendPython) + "'"
    $backendProcess = Start-ServiceWindow `
        -ShellPath $shellPath `
        -Title "TenderWord Backend (8000)" `
        -WorkingDirectory $backendDir `
        -Banner "[backend] 正在执行 backend\\.venv\\Scripts\\python.exe main.py" `
        -CommandText "& $backendPythonLiteral main.py"

    Start-Sleep -Seconds 1

    $frontendProcess = Start-ServiceWindow `
        -ShellPath $shellPath `
        -Title $frontendTitle `
        -WorkingDirectory $frontendDir `
        -Banner $frontendBanner `
        -CommandText $frontendCommandText
} catch {
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    }

    throw
}

Write-Host ""
Write-Host "TenderWord 开发环境已拉起：" -ForegroundColor Green
Write-Host "  Backend PID : $($backendProcess.Id)" -ForegroundColor Green
Write-Host "  Frontend PID: $($frontendProcess.Id)" -ForegroundColor Green
Write-Host "  Frontend Run: $frontendSummary" -ForegroundColor Green
Write-Host "  Frontend URL: http://localhost:8502" -ForegroundColor Green
Write-Host "  Backend URL : http://localhost:8000" -ForegroundColor Green
Write-Host "  Health URL  : http://localhost:8000/health" -ForegroundColor Green
Write-Host ""
Write-Host "停止方式：在两个子窗口中按 Ctrl+C，或直接关闭子窗口。" -ForegroundColor Yellow
