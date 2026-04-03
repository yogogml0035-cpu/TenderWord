#!/usr/bin/env bash

set -euo pipefail

fail() {
  printf '[start-dev-wsl] ERROR: %s\n' "$1" >&2
  exit 1
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "未找到必需命令: $1"
  fi
}

is_wsl() {
  [[ -n "${WSL_DISTRO_NAME:-}" ]] || grep -qi 'microsoft' /proc/sys/kernel/osrelease 2>/dev/null
}

select_powershell_host() {
  if command -v pwsh.exe >/dev/null 2>&1; then
    printf '%s\n' "pwsh.exe"
    return 0
  fi

  if command -v powershell.exe >/dev/null 2>&1; then
    printf '%s\n' "powershell.exe"
    return 0
  fi

  return 1
}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$script_dir"
script_path="$repo_root/start-dev.ps1"

is_wsl || fail "该脚本只能在 WSL 中使用。"
require_command wslpath
ps_host="$(select_powershell_host)" || fail "未找到可用的 Windows PowerShell 宿主（powershell.exe 或 pwsh.exe）。"

[[ -f "$script_path" ]] || fail "未找到 $script_path"
[[ -f "$repo_root/backend/main.py" ]] || fail "未找到 backend/main.py"
[[ -f "$repo_root/backend/.venv/Scripts/python.exe" ]] || fail "缺少 backend/.venv/Scripts/python.exe"
[[ -f "$repo_root/backend/.env" ]] || fail "缺少 backend/.env"
[[ -f "$repo_root/frontend/package.json" ]] || fail "未找到 frontend/package.json"
[[ -f "$repo_root/frontend/.env.local" ]] || fail "缺少 frontend/.env.local"
[[ -d "$repo_root/frontend/node_modules" ]] || fail "缺少 frontend/node_modules"
require_command npm

repo_root_windows="$(wslpath -w "$repo_root")" || fail "无法将仓库根目录转换为 Windows 路径。"
windows_script_path="$(wslpath -w "$script_path")" || fail "无法将脚本路径转换为 Windows 路径。"

[[ -n "$repo_root_windows" ]] || fail "仓库根目录的 Windows 路径为空。"

cd "$repo_root"
printf '[start-dev-wsl] 在 Windows 侧启动后端窗口...\n'
"$ps_host" -NoProfile -ExecutionPolicy Bypass -File "$windows_script_path" -BackendOnly

printf '[start-dev-wsl] 在当前 WSL 终端启动前端 npm run dev...\n'
cd "$repo_root/frontend"
exec npm run dev
