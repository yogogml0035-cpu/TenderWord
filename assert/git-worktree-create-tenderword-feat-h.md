# TenderWord worktree（feat-wsq-h -> TenderWord-feat-h）

## 创建

```powershell
cd D:\CompanyProject\TenderWord
git fetch --prune --all
git worktree add "D:\CompanyProject\TenderWord-feat-h" -b feat-wsq-h origin/feat-wsq-h
git worktree list
```

## 进入与更新

```powershell
cd D:\CompanyProject\TenderWord-feat-h
git status
git pull
```

## 删除（可选）

```powershell
cd D:\CompanyProject\TenderWord
git worktree remove "D:\CompanyProject\TenderWord-feat-h"
git branch -D feat-wsq-h
git worktree prune
git fetch --prune origin
```
