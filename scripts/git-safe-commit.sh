#!/usr/bin/env bash
# git-safe-commit.sh — PMWB 安全提交封装（规避沙箱 git 孤儿分支怪象）
#
# 用法:
#   bash scripts/git-safe-commit.sh -m "feat: xxx" [--push] [--skip-gate] [--no-backup] <file1> [file2 ...]
#
# 设计要点（对应 8/15 故障整改报告 P0）:
#   1) 绝不执行 git checkout -b / git branch（那是触发孤儿分支的元凶）。
#   2) 提交前先把待提交文件 cp 到 /d/fixbk_<时间戳>/ 作为仓库外最后防线。
#   3) 用单命令法重锚到 main（symbolic-ref + reset --mixed），保留工作树，避免切换分支清空 refs。
#   4) 仅 git add 显式列出的文件 —— 不贪多，避免一次丢一整片。
#   5) 提交前跑 commit-gate.sh（import 烟雾 + pytest 收集）；WIP/紧急可用 --skip-gate。
#   6) commit 时导出 PMWB_SKIP_GATE=1，避免 pre-commit hook 重复跑门禁。
#
# 注意：本脚本只在 main 上产生提交。如需 feature 分支，由集成者用
#   git push origin HEAD:refs/heads/feature/xxx 后再 merge，但绝不在脚本里 checkout -b。
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

MSG=""; PUSH=0; SKIP_GATE=0; BACKUP=1; FILES=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -m) MSG="$2"; shift 2;;
    --push) PUSH=1; shift;;
    --skip-gate) SKIP_GATE=1; shift;;
    --no-backup) BACKUP=0; shift;;
    -*) echo "unknown flag: $1" >&2; exit 2;;
    *) FILES+=("$1"); shift;;
  esac
done

[[ -z "$MSG" ]] && { echo "[git-safe] 缺少 -m <message>" >&2; exit 2; }
[[ ${#FILES[@]} -eq 0 ]] && { echo "[git-safe] 未指定任何文件" >&2; exit 2; }

# 0) 仓库外备份（最后防线）
if [[ $BACKUP -eq 1 ]]; then
  TS="$(date +%Y%m%d-%H%M%S)"
  BK="/d/fixbk_${TS}"
  mkdir -p "$BK"
  for f in "${FILES[@]}"; do
    if [[ -f "$f" ]]; then
      mkdir -p "$BK/$(dirname "$f")"
      cp "$f" "$BK/$f"
    fi
  done
  echo "[git-safe] 仓库外备份 -> $BK"
fi

# 1) 提交前门禁（除非显式跳过）
if [[ $SKIP_GATE -eq 0 && -z "${PMWB_SKIP_GATE:-}" ]]; then
  "$REPO_ROOT/scripts/commit-gate.sh" || { echo "[git-safe] 门禁未通过，已中止提交"; exit 4; }
fi

# 2) 重锚到 main（规避孤儿分支），保留工作树
git symbolic-ref HEAD refs/heads/main 2>/dev/null || true
git reset --mixed main 2>/dev/null || git reset --mixed HEAD

# 3) 仅暂存显式列出的文件
git add "${FILES[@]}"

# 4) 误加检查：任何不在已知目录前缀下的文件被暂存都视为异常
STRAY="$(git diff --cached --name-only | grep -vE '^(backend/|frontend/|services/|scripts/|docs/|.workbuddy/)' || true)"
if [[ -n "$STRAY" ]]; then
  echo "[git-safe] 发现非预期文件被暂存，已中止：" >&2
  echo "$STRAY" >&2
  git reset --mixed HEAD >/dev/null 2>&1 || true
  exit 3
fi

# 5) 提交（导出 PMWB_SKIP_GATE 防止 pre-commit hook 重复跑门禁）
export PMWB_SKIP_GATE=1
git commit -m "$MSG"

if [[ $PUSH -eq 1 ]]; then
  git push origin main
fi
echo "[git-safe] done"
