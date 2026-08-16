#!/usr/bin/env bash
# commit-gate.sh — PMWB 提交前门禁（防整路由 NameError / 功能蒸发）
# 由 git-safe-commit.sh 与 .git/hooks/pre-commit 调用。
# 退出码 0 = 通过；非 0 = 拦截（commit 应中止）。
set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

# 可用 PMWB_PYTHON 环境变量覆盖 python 路径；默认取项目 venv
PY="${PMWB_PYTHON:-$REPO_ROOT/backend/venv/Scripts/python.exe}"

if [[ ! -f "$PY" ]]; then
  echo "[gate] WARN: python 未找到 ($PY)，跳过门禁"
  exit 0
fi

echo "[gate] 1/2 后端 import 烟雾测试 (import main，工作目录=backend/)..."
cd "$REPO_ROOT/backend"
if ! "$PY" -c "import main; print('  import main OK')" >/tmp/pmwb_import.log 2>&1; then
  echo "[gate] FAIL: backend 入口导入失败（很可能是某路由少了 import，如 requirement_service）："
  cat /tmp/pmwb_import.log
  exit 1
fi

echo "[gate] 2/2 pytest --collect-only（捕获测试引用了已蒸发/不存在的符号）..."
cd "$REPO_ROOT/backend"
if "$PY" -m pytest --collect-only -q >/tmp/pmwb_collect.log 2>&1; then
  echo "[gate] collect OK"
else
  echo "[gate] FAIL: 收集阶段报错（功能蒸发/符号缺失）："
  grep -iE "error|ModuleNotFound|ImportError|cannot import|not found" /tmp/pmwb_collect.log | head -20
  exit 1
fi

echo "[gate] PASS"
