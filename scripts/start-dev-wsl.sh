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

detect_node_modules_platform() {
  local path="$1"

  if [[ -d "$path/lightningcss-win32-x64-msvc" ]]; then
    printf 'win\n'
    return
  fi

  if [[ -d "$path/lightningcss-linux-x64-gnu" || -d "$path/lightningcss-linux-x64-musl" ]]; then
    printf 'wsl\n'
    return
  fi

  printf '\n'
}

remove_frontend_dir() {
  local path="$1"
  local frontend_dir="$repo_root/frontend"

  case "$path" in
    "$frontend_dir"/node_modules-wsl|"$frontend_dir"/.next)
      rm -rf "$path"
      ;;
    *)
      fail "拒绝清理 frontend 目录外或非固定目标路径：$path"
      ;;
  esac
}

remove_active_node_modules_for_wsl_install() {
  local frontend_dir="$repo_root/frontend"
  local link_path="$frontend_dir/node_modules"

  if [[ -L "$link_path" ]]; then
    rm "$link_path"
    return
  fi

  if [[ -d "$link_path" ]]; then
    local detected_platform
    detected_platform="$(detect_node_modules_platform "$link_path")"
    if [[ -n "$detected_platform" && "$detected_platform" != "wsl" ]]; then
      fail "frontend/node_modules 是 $detected_platform 依赖目录，拒绝在 WSL 安装流程中直接覆盖。"
    fi

    rm -rf "$link_path"
  fi
}

link_wsl_frontend_dependencies() {
  local frontend_dir="$repo_root/frontend"
  local link_path="$frontend_dir/node_modules"
  local target_name="node_modules-wsl"
  local target_path="$frontend_dir/$target_name"

  if [[ -L "$link_path" ]]; then
    rm "$link_path"
  elif [[ -d "$link_path" ]]; then
    local detected_platform
    detected_platform="$(detect_node_modules_platform "$link_path")"
    if [[ "$detected_platform" == "wsl" ]]; then
      printf '[start-dev-wsl] frontend/node_modules 已是 WSL 依赖目录。\n'
      return
    fi

    local preserve_name="${target_name}"
    if [[ -n "$detected_platform" ]]; then
      preserve_name="node_modules-$detected_platform"
    fi

    if [[ ! -e "$frontend_dir/$preserve_name" ]]; then
      printf '[start-dev-wsl] 保留现有 frontend/node_modules 为 %s...\n' "$preserve_name"
      mv "$link_path" "$frontend_dir/$preserve_name"
    elif [[ -n "$detected_platform" && "$detected_platform" != "wsl" ]]; then
      printf '[start-dev-wsl] frontend/%s 已存在，移除当前 %s 依赖目录以切换到 WSL。\n' "$preserve_name" "$detected_platform"
      rm -rf "$link_path"
    else
      fail "frontend/node_modules 是真实目录，且 frontend/$preserve_name 已存在；请先手动确认后移走其中一个目录。"
    fi
  fi

  mkdir -p "$target_path"
  ln -s "$target_name" "$link_path"
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
repo_root="$(cd "$script_dir/.." && pwd)"
script_path="$repo_root/scripts/start-dev.ps1"
deps_link_script="$repo_root/scripts/set-frontend-deps-link-win.ps1"

is_wsl || fail "该脚本只能在 WSL 中使用。"
require_command wslpath
ps_host="$(select_powershell_host)" || fail "未找到可用的 Windows PowerShell 宿主（powershell.exe 或 pwsh.exe）。"

[[ -f "$script_path" ]] || fail "未找到 $script_path"
[[ -f "$deps_link_script" ]] || fail "未找到 $deps_link_script"
[[ -f "$repo_root/backend/main.py" ]] || fail "未找到 backend/main.py"
[[ -f "$repo_root/backend/.env" ]] || fail "缺少 backend/.env"
[[ -f "$repo_root/frontend/package.json" ]] || fail "未找到 frontend/package.json"
[[ -f "$repo_root/frontend/.env.local" ]] || fail "缺少 frontend/.env.local"
require_command node
require_command npm

repo_root_windows="$(wslpath -w "$repo_root")" || fail "无法将仓库根目录转换为 Windows 路径。"
windows_script_path="$(wslpath -w "$script_path")" || fail "无法将脚本路径转换为 Windows 路径。"
windows_deps_link_script="$(wslpath -w "$deps_link_script")" || fail "无法将依赖链接脚本路径转换为 Windows 路径。"

[[ -n "$repo_root_windows" ]] || fail "仓库根目录的 Windows 路径为空。"

cd "$repo_root"
printf '[start-dev-wsl] 切换前端依赖到 WSL 模式...\n'
if ! "$ps_host" -NoProfile -ExecutionPolicy Bypass -File "$windows_deps_link_script" -Target wsl -RepoRoot "$repo_root_windows"; then
  printf '[start-dev-wsl] Windows 侧依赖链接失败，改用 WSL 符号链接。\n'
  link_wsl_frontend_dependencies
fi

if [[ ! -f "$repo_root/frontend/node_modules/.bin/next" ]] || ! (cd "$repo_root/frontend" && node -e "require('lightningcss')") >/dev/null 2>&1; then
  printf '[start-dev-wsl] 检测到 WSL 原生前端依赖缺失或平台不匹配，正在执行 npm ci...\n'
  link_wsl_frontend_dependencies
  remove_active_node_modules_for_wsl_install
  remove_frontend_dir "$repo_root/frontend/node_modules-wsl"
  remove_frontend_dir "$repo_root/frontend/.next"
  (cd "$repo_root/frontend" && npm ci && mv node_modules node_modules-wsl)
  if ! "$ps_host" -NoProfile -ExecutionPolicy Bypass -File "$windows_deps_link_script" -Target wsl -RepoRoot "$repo_root_windows"; then
    link_wsl_frontend_dependencies
  fi
fi

printf '[start-dev-wsl] 在 Windows 侧启动后端窗口...\n'
"$ps_host" -NoProfile -ExecutionPolicy Bypass -File "$windows_script_path" -BackendOnly

printf '[start-dev-wsl] 在当前 WSL 终端启动前端 npm run dev...\n'
cd "$repo_root/frontend"
exec npm run dev
