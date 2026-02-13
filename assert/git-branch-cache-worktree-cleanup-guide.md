# Git 分支缓存（远端跟踪分支/失效引用）与 Worktree 清理指南

适用场景：
- 远端分支已删除，但本地仍显示 `origin/xxx` 等远端跟踪分支（stale remote-tracking refs）
- `git branch -a` / `git branch -r` 里有“幽灵分支”
- 需要删除某个 worktree 目录，并同时删除对应的本地分支记录

> 说明：下文以远端名 `origin`、分支名 `feat-wsq-c`、worktree 路径 `D:\PythonProject\TenderWord-worktrees\feat-wsq-c` 为例。按需替换。

---

## 1) 清除“分支缓存”（远端跟踪分支/失效引用）

### 1.1 同步远端并清理已删除的远端分支引用（推荐）

```bash
git fetch --all --prune
```

预期现象（示例）：
- 输出中出现类似：
  - `- [deleted]         (none)     -> origin/xxx`
  - 或 `- [deleted]         origin/xxx`
- 表示本地的 `refs/remotes/origin/xxx`（远端跟踪引用）已被清掉

### 1.2 进一步清理本地记录的失效远端引用（可选补充）

```bash
git remote prune origin
```

### 1.3 验证是否清干净

```bash
git branch -r
git branch -a
git show-ref --heads --dereference
git show-ref --remotes --dereference
```

你关注的是：
- `origin/xxx` 是否还存在
- `refs/remotes/origin/xxx` 是否还存在

---

## 2) 本地分支记录怎么处理（常见实际操作）

### 2.1 本地已存在同名分支：删除再重建

```bash
git branch -d feat-wsq
git switch -c feat-wsq
```

如果 `-d` 删除失败（有未合并提交），说明该分支相对当前分支有独立提交：
- 确认后再强制删除：

```bash
git branch -D feat-wsq
```

### 2.2 重命名当前分支

```bash
git branch -m feat-wsq-c
```

---

## 3) 删除 worktree + 删除本地分支记录（正确做法）

目标：
- 移除 worktree 目录（会删除 `D:\...\feat-wsq-c` 这整个目录）
- 移除与之关联的本地分支引用（`refs/heads/feat-wsq-c`）

### 3.1 删除 worktree

1) 确认 worktree 列表与路径：

```bash
git worktree list
```

2) 移除指定 worktree：

```bash
git worktree remove "D:\PythonProject\TenderWord-worktrees\feat-wsq-c"
```

3) 可选：清理残留元数据（当你曾经强删目录或出现残留记录时很有用）

```bash
git worktree prune
```

### 3.2 删除本地分支记录（确保不在该分支上）

1) 先切到其它分支（示例用 `master`，以你的仓库默认分支为准）：

```bash
git switch master
```

2) 删除分支：

```bash
git branch -d feat-wsq-c
```

如果删除失败（未合并提交），确认后强删：

```bash
git branch -D feat-wsq-c
```

---

## 4) 常见问题与排查

### 4.1 `git worktree remove` 失败：目录被占用

表现：
- Windows 下常见报错：目录无法删除 / 文件被占用

处理：
- 关闭该 worktree 目录下打开的 IDE、终端、运行中的进程
- 再执行 `git worktree remove ...`

### 4.2 分支删不掉：提示未合并

原因：
- 该分支存在未合并到目标分支的提交

处理：
- 不想保留：用 `git branch -D <branch>`
- 想保留：先合并/变基/打补丁保存，再删除

### 4.3 远端分支已删除但本地还显示

优先处理：

```bash
git fetch --all --prune
git remote prune origin
```

然后用 `git branch -r` 验证。

