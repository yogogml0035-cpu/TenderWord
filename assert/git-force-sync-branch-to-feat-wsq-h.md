# Git：将当前分支强制替换为 `feat-wsq-h` 最新节点（Hard Reset 同步）

适用场景：
- 当前分支与 `feat-wsq-h` 框架差异过大，无法通过 merge/rebase 平滑更新
- 目标是让“当前分支指针”直接对齐 `origin/feat-wsq-h`（代码整体以 `feat-wsq-h` 为准）

前置条件（必须）：
- 当前目录在目标仓库的 worktree 内
- 工作区必须干净（无未提交改动）
- 远端分支 `origin/feat-wsq-h` 存在

注意：
- 如果 `feat-wsq-h` 已在其它 worktree 中被检出，本 worktree 不建议/也可能无法直接 `git switch feat-wsq-h`；本指南采用“保留当前分支名，但把内容强制对齐到 `origin/feat-wsq-h`”的方式。
- 本仓库曾出现 `git fetch --tags` 导致 OOM 的情况；同步时优先使用 `--no-tags` 的定向 fetch。

---

## 一键执行（PowerShell，带断言）

把下面整段粘贴执行即可：

```powershell
$ErrorActionPreference = 'Stop'

function Assert($cond, $msg) {
  if (-not $cond) { throw "ASSERT FAIL: $msg" }
}

$inRepo = (git rev-parse --is-inside-work-tree 2>$null).Trim()
Assert ($inRepo -eq 'true') 'Not inside a git work tree.'

$porcelain = git status --porcelain
Assert (-not $porcelain) ("Working tree is not clean.`n$porcelain")

$branch  = (git branch --show-current).Trim()
$target  = 'refs/remotes/origin/feat-wsq-h'

git fetch --no-tags origin feat-wsq-h --prune
Assert ($LASTEXITCODE -eq 0) 'git fetch failed.'

$targetHead = (git rev-parse $target).Trim()
Assert ($LASTEXITCODE -eq 0) 'origin/feat-wsq-h does not exist locally.'

git reset --hard $target
Assert ($LASTEXITCODE -eq 0) 'git reset --hard failed.'

git branch --set-upstream-to=("origin/" + $branch)
Assert ($LASTEXITCODE -eq 0) 'set upstream failed.'

$newHead = (git rev-parse HEAD).Trim()
Assert ($newHead -eq $targetHead) "HEAD($newHead) != origin/feat-wsq-h($targetHead)"

"OK: $branch is now aligned to origin/feat-wsq-h @ $newHead"
git status -sb
git log --oneline --decorate -n 5
```

---

## 命令行执行（纯 Git 命令）

说明：
- 这组命令在 Git Bash / PowerShell / CMD 都可执行
- 不包含脚本级断言；请结合下方“验证点”核对结果

```bash
git status --porcelain
git fetch --no-tags origin feat-wsq-h --prune
git reset --hard origin/feat-wsq-h
git branch --set-upstream-to=origin/<current-branch>
git status -sb
```

---

## 验证点（手工检查）

```bash
git status -sb
git rev-parse HEAD
git rev-parse origin/feat-wsq-h
```

预期：
- `git status -sb` 显示形如：`## <current-branch>...origin/<current-branch> [ahead N]`
- `HEAD` 与 `origin/feat-wsq-h` 的 commit id 完全一致

---

## 可选：断言（Git Bash / WSL）

如果你在类 bash 环境（Git Bash、WSL）里想“一行断言”：

```bash
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/feat-wsq-h)"
```

---

## 可选：删除备份分支（不保留回滚点）

如果之前手动创建过备份分支（例如 `backup/<branch>-before-force-sync-to-feat-wsq-h-<timestamp>`），可直接删除：

```bash
git branch -D backup/<your-branch-before-force-sync-to-feat-wsq-h-*>
```

