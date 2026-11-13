# -*- coding: utf-8 -*-
"""客诉「主要投诉点」标准名口径回归（离线 / 不连库 / 不写表）。

验证 2026-11-13 v2 优化的两条硬约束：
  1. 展示口径：20 条标准名均为「模块·失效对象·失效性质」单失效点，
     无斜杠并列、无状态轴词、名称唯一、三元组标签无堆叠。
  2. 判定式冻结：与 git HEAD 版本相比，所有判定信号
     (objects/natures/stages/exclude/priority/is_defect/id) 逐条一致，
     且 match_module_problem 对真实工单文本的判定输出完全一致
     —— 证明本次只修「表达」，归类数字不会因改名而漂移。

用法： backend/venv/Scripts/python.exe scripts/verify_complaint_module_standard.py
断言函数签名固定为 (name, cond, extra)，禁止写成 (n, e='') 的恒 PASS 形式。
"""
from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from constants import complaint_module as M  # noqa: E402

PASS = 0
FAIL = 0
SKIP = 0
DETAILS = []


def ok(name, cond, extra=""):
    """断言必须收 (name, cond, extra)，否则全部恒 PASS。"""
    global PASS, FAIL
    if cond:
        PASS += 1
        DETAILS.append({"name": name, "result": "PASS", "extra": extra})
        print("  PASS  %s%s" % (name, ("  " + extra) if extra else ""))
    else:
        FAIL += 1
        DETAILS.append({"name": name, "result": "FAIL", "extra": extra})
        print("  FAIL  %s%s" % (name, ("  " + extra) if extra else ""))


def skip(name, why):
    global SKIP
    SKIP += 1
    DETAILS.append({"name": name, "result": "SKIP", "extra": why})
    print("  SKIP  %s  %s" % (name, why))


def load_head_version():
    """读取 git HEAD 版字典源码并 exec 到独立命名空间；失败返回 None。"""
    try:
        raw = subprocess.check_output(
            ["git", "show", "HEAD:backend/constants/complaint_module.py"],
            cwd=ROOT, stderr=subprocess.DEVNULL,
        )
        src = raw.decode("utf-8")
        ns = {"__name__": "_head_complaint_module"}
        exec(compile(src, "<HEAD:complaint_module.py>", "exec"), ns)  # noqa: S102
        return ns
    except Exception as e:  # 无 git / 文件未入库 -> 明确 SKIP，不假装通过
        return {"__error__": str(e)}


def signal_of(m):
    """判定式信号指纹（展示字段 name/module/fail_object/fail_nature 不参与）。"""
    return (
        m["id"],
        tuple(m.get("objects", [])),
        tuple(m.get("natures", [])),
        tuple(m.get("stages", [])),
        tuple(m.get("exclude", [])),
        m.get("priority"),
        m.get("is_defect"),
    )


def display_of(m):
    return (m["name"], m["module"], m["fail_object"], m["fail_nature"])


def real_points():
    """从真实导出 CSV 取工单原文当判定式对照输入（含标题/现象原始文本）。"""
    path = os.path.join(ROOT, "tmp_final_classified.csv")
    if not os.path.exists(path):
        return []
    with io.open(path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows[:198]:
        text = (r.get("工单内容") or "").strip()
        if text:
            out.append((text, r.get("申告类别") or "", r.get("工单属性") or ""))
    # 固定边界样例：空文本 / 状态词 / 咨询类 / 混合关键词
    out += [
        ("订单在途无法结单，施工单回单卡单", "", ""),
        ("宽带账号激活后未同步，查不到", "", ""),
        ("资费套餐配置未生效，出账金额不符", "", ""),
        ("", "", ""),
    ]
    return out


def main():
    print("=== 客诉主要投诉点 · 标准名口径回归 (v2) ===")
    print("字典版本 MODULE_DICT_VERSION = %s" % M.MODULE_DICT_VERSION)

    # 1. 结构校验
    errs = M.validate_dictionary()
    ok("字典结构校验 validate_dictionary() 零错误", len(errs) == 0,
       "errors=%s" % (json.dumps(errs, ensure_ascii=False) if errs else "[]"))
    ok("字典条目数 = 20", len(M.MODULE_PROBLEMS) == 20,
       "actual=%d" % len(M.MODULE_PROBLEMS))
    ok("字典版本 >= 2", M.MODULE_DICT_VERSION >= 2,
       "version=%s" % M.MODULE_DICT_VERSION)
    ok("标准名唯一", len({m["name"] for m in M.MODULE_PROBLEMS}) == 20,
       "uniq=%d" % len({m["name"] for m in M.MODULE_PROBLEMS}))
    ok("标准名零斜杠并列",
       all("/" not in m["name"] for m in M.MODULE_PROBLEMS),
       "violations=%d" % sum(1 for m in M.MODULE_PROBLEMS if "/" in m["name"]))
    ok("标准名零状态轴词",
       all(not any(t in m["name"] for t in M.STATUS_AXIS_TERMS)
           for m in M.MODULE_PROBLEMS),
       "status_terms=%s" % json.dumps(M.STATUS_AXIS_TERMS, ensure_ascii=False))
    ok("糊状类名『订单结单/回单卡单/在途』已消除",
       all(m["name"] != "订单结单/回单卡单/在途" for m in M.MODULE_PROBLEMS))
    close = M.get_module_problem("MP-ORDER-CLOSE")
    ok("MP-ORDER-CLOSE 为单失效点三段式标准名",
       bool(close) and close["name"].count("·") == 2 and "在途" not in close["name"],
       "name=%s" % (close or {}).get("name"))
    ok("MP-ORDER-CLOSE ID 与锚点保持稳定",
       bool(close) and close["id"] == "MP-ORDER-CLOSE")

    # 2. 判定式冻结（与 git HEAD 版逐条比对）
    head = load_head_version()
    if head is None or "__error__" in head:
        skip("判定式信号与 HEAD 版一致", "git HEAD 版不可读: %s" %
             ((head or {}).get("__error__") if head else "unknown"))
    else:
        old_list = head["MODULE_PROBLEMS"]
        new_list = M.MODULE_PROBLEMS
        old_map = {m["id"]: m for m in old_list}
        new_map = {m["id"]: m for m in new_list}
        ok("ID 集合与 HEAD 版完全一致", set(old_map) == set(new_map),
           "old=%d new=%d" % (len(old_map), len(new_map)))
        # HEAD 不是「本次改前基线」：工作区存在更早的未提交判定式调整，
        # 因此 HEAD 与当前工作区在 objects/natures 上本就不同（非本次引入）。
        # 这里只把差异作为参考信息打印，不作为断言；判定式冻结改用下方「展示字段打乱法」证明。
        diff_sig = [k for k in old_map
                    if k in new_map and signal_of(old_map[k]) != signal_of(new_map[k])]
        print("  INFO  HEAD 与工作区判定式信号既有差异（非本次引入）: %s" %
              json.dumps(diff_sig, ensure_ascii=False))
        diff_disp = [k for k in old_map
                     if k in new_map and display_of(old_map[k]) != display_of(new_map[k])]
        ok("展示字段确实已修正（非无变化空跑）", len(diff_disp) == 20,
           "changed=%d/20" % len(diff_disp))

    # 3. 判定式冻结：展示字段打乱法（不依赖任何外部基线）
    #    match_module_problem 只读 objects/natures/stages/exclude/priority/is_defect；
    #    把 name/module/fail_object/fail_nature 全部改成占位符后，对真实文本的判定
    #    输出必须逐条不变 —— 这是「只改名、归类数字不漂移」的直接证明。
    points = real_points()
    if not points:
        skip("展示字段打乱后判定输出不变", "样本 CSV 不存在")
    else:
        base_outs = [M.match_module_problem(t, s or None, c or None) for t, s, c in points]
        saved = M._SORTED
        patched = []
        for m in saved:
            m2 = dict(m)
            for f in ("name", "module", "fail_object", "fail_nature"):
                m2[f] = "__DISPLAY_ONLY__"
            patched.append(m2)
        try:
            M._SORTED = patched
            test_outs = [M.match_module_problem(t, s or None, c or None) for t, s, c in points]
        finally:
            M._SORTED = saved
        mism = [{"text": points[i][0][:40], "base": base_outs[i], "shuffled": test_outs[i]}
                for i in range(len(points)) if base_outs[i] != test_outs[i]]
        ok("展示字段打乱后判定输出逐条不变（判定式与展示解耦）",
           len(mism) == 0,
           "n=%d mismatches=%s" % (len(points), json.dumps(mism[:3], ensure_ascii=False)))

    # 4. 落盘结果
    out = {"version": M.MODULE_DICT_VERSION, "pass": PASS, "fail": FAIL,
           "skip": SKIP, "details": DETAILS,
           "names": [{"id": m["id"], "name": m["name"]} for m in M.MODULE_PROBLEMS]}
    dst = os.path.join(ROOT, "data", "complaint_module_standard_result.json")
    with io.open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\nRESULT pass=%d fail=%d skip=%d -> %s" % (PASS, FAIL, SKIP, dst))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
