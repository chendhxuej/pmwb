"""用户故事拆分规则引擎 v2 —— 合并优先策略。

依据公司最新管理要求：
- 核心原则：独立业务价值 / 角色不变 / 场景隔离 / 可独立上线 / 差异显性化
- 允许拆分：角色不同 / 场景不同 / 上线节奏不同 / 业务目标不同
- 禁止拆分：同角色操作步骤切分 / 按技术维度拆分 / 虚增工作量 / 成套强依赖仍拆分

本模块提供纯规则版本的拆分逻辑，作为 LLM 不可用时的降级策略。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 角色关键词提取
# ---------------------------------------------------------------------------
_ROLE_KEYWORDS = [
    "操作员", "管理员", "审核员", "业务员", "客户经理",
    "营业员", "系统管理员", "配置员", "运维人员", "客服",
    "财务", "稽核", "审批人", "受理人", "派单员",
]


def _extract_roles(text: str) -> List[str]:
    """从澄清内容中提取涉及的角色列表（去重）。"""
    found = []
    for kw in _ROLE_KEYWORDS:
        if kw in text:
            found.append(kw)
    if not found:
        found = ["业务负责人员"]
    return list(dict.fromkeys(found))  # 去重保序


# ---------------------------------------------------------------------------
# 场景边界检测
# ---------------------------------------------------------------------------
def _detect_scenario_boundaries(text: str) -> List[Tuple[int, int, str]]:
    """检测场景/章节边界，返回 (start_offset, end_offset, label)。

    触发条件（仅限明确的章节级边界，不包含步骤级编号）：
    - Markdown 标题行（##/###）
    - 中文数字编号章节（一、二、三、）
    - 场景关键词行（"场景"/"流程"/"功能" 开头）
    - 分隔行（---）

    不会将步骤级编号（1、2、3、或 (1)(2)(3)）视为场景边界。
    """
    lines = text.replace("\r", "\n").split("\n")
    boundaries: List[Tuple[int, int, str]] = []
    current_start = 0
    current_label = ""

    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue

        is_boundary = False
        label = ""

        # Markdown 标题
        m = re.match(r"^#{2,4}\s+(.+)", line)
        if m:
            is_boundary, label = True, m.group(1).strip()

        # 中文数字编号（章节级：一、二、三、...）
        m = re.match(r"^[一二三四五六七八九十]、(.+)", line)
        if m:
            is_boundary, label = True, m.group(1).strip()

        # 分隔线
        if re.match(r"^[-=*_]{3,}$", line):
            is_boundary, label = True, ""

        # 场景关键词行（明确标注的新场景/流程/功能模块）
        if re.match(r"^(场景|业务流程|流程说明|功能模块|模块)[：:]\s*", line):
            is_boundary, label = True, line

        if is_boundary:
            # 保存前一个场景
            if i > current_start:
                prev_text = "\n".join(lines[current_start:i]).strip()
                if prev_text:
                    boundaries.append((current_start, i, current_label or "默认场景"))
            current_start = i
            current_label = label

    # 最后一个场景
    if current_start < len(lines):
        rest = "\n".join(lines[current_start:]).strip()
        if rest:
            boundaries.append((current_start, len(lines), current_label or "默认场景"))

    return boundaries


# ---------------------------------------------------------------------------
# 闭环操作检测（同角色完成流程合并）
# ---------------------------------------------------------------------------
_CLOSED_LOOP_PATTERNS = [
    # 填写-提交-同步 类
    re.compile(r"(填写|录入|输入).*(提交|保存|确认)", re.IGNORECASE),
    re.compile(r"(提交|保存).*(同步|推送|通知|触发)", re.IGNORECASE),
    # 查询-处理-反馈 类
    re.compile(r"(查询|检索|搜索).*(处理|操作|执行)", re.IGNORECASE),
    re.compile(r"(处理|操作).*(反馈|回复|通知)", re.IGNORECASE),
    # 创建-审核-生效 类
    re.compile(r"(创建|新建|生成).*(审核|审批|复核)", re.IGNORECASE),
    re.compile(r"(审核|审批).*(生效|发布|上线)", re.IGNORECASE),
    # 导入-校验-入库 类
    re.compile(r"(导入|上传).*(校验|验证|检查)", re.IGNORECASE),
    re.compile(r"(校验|验证).*(入库|存储|保存)", re.IGNORECASE),
]


def _detect_closed_loops(features: List[str], text: str) -> List[List[int]]:
    """检测应合并的闭环操作组，返回每组在 features 中的索引列表。

    规则：若连续多行中存在"步骤A→步骤B"的闭环关系，合并为一组。
    """
    if len(features) <= 1:
        return []

    merged_groups: List[List[int]] = []
    used: set = set()
    full_text = "\n".join(features)

    for pattern in _CLOSED_LOOP_PATTERNS:
        if pattern.search(full_text):
            # 找到整个闭环 → 尝试将连续特征合并
            # 简化策略：如果总特征数 <= 5 且检测到闭环模式 → 合并为 1 条
            # 否则按现有分组保留
            pass

    # 更实用的启发式：若所有特征属于同一角色，且检测到闭环关键词 → 合并
    roles = _extract_roles(full_text)
    if len(roles) == 1 and len(features) <= 6:
        # 单一角色 + 功能块不超过6个 → 极有可能是完整闭环
        has_loop = any(p.search(full_text) for p in _CLOSED_LOOP_PATTERNS)
        if has_loop:
            return [list(range(len(features)))]

    return merged_groups


# ---------------------------------------------------------------------------
# 核心拆分逻辑
# ---------------------------------------------------------------------------

def split_into_user_stories(
    content: str,
    ddd: Dict[str, str],
    *,
    max_stories: int = 5,
) -> List[Dict[str, Any]]:
    """按合并优先策略拆分用户故事。

    算法：
    1. 检测场景边界（按场景隔离原则）
    2. 每个场景内检测角色（按角色不变原则）
    3. 同场景同角色 → 合并为 1 条（独立业务价值原则）
    4. 不同角色 → 各 1 条
    5. 输出中写明差异化边界声明
    """
    if not content or not content.strip():
        return []

    # Step 1: 检测场景边界
    boundaries = _detect_scenario_boundaries(content)
    if not boundaries:
        # 无明确场景边界，整段作为一个场景
        boundaries = [(0, len(content.split("\n")), "默认场景")]

    lines = content.replace("\r", "\n").split("\n")

    # Step 2: 每个场景内提取角色和功能块
    scenario_groups: List[Tuple[str, List[str], List[str]]] = []  # (label, roles, features)

    for start, end, label in boundaries:
        scene_lines = lines[start:end]
        scene_text = "\n".join(scene_lines).strip()
        if not scene_text:
            continue

        # 提取该场景内的功能行
        feats = []
        for l in scene_text.split("\n"):
            l = re.sub(r"^[（(]?\d+[.、)）]?\s*", "", l).strip()
            l = re.sub(r"^[一二三四五六七八九十]、\s*", "", l).strip()
            # 去掉 Markdown 列表前缀
            l = re.sub(r"^[-*+]\s+", "", l).strip()
            if len(l) >= 8:  # 至少有实际内容
                feats.append(l)

        if not feats:
            continue

        roles = _extract_roles(scene_text)

        # Step 3: 按角色分组（同一场景内不同角色 → 各自独立故事）
        role_to_feats: Dict[str, List[str]] = {}
        for r in roles:
            role_to_feats[r] = feats  # 简化：同场景内所有功能块归每个角色

        # Step 4: 同一角色只有一个故事（合并该场景所有功能块）
        if len(roles) == 1:
            scenario_groups.append((label, roles, feats))
        else:
            # 不同角色，各自一条
            for r in roles:
                scenario_groups.append((f"{label}（{r}）", [r], feats))

    # Step 5: 限制总条数
    if len(scenario_groups) > max_stories:
        # 如果超出上限，合并总功能块数最少的场景
        scenario_groups = _merge_smallest_scenarios(scenario_groups, max_stories)

    # Step 6: 构建输出
    stories = []
    for i, (label, roles, feats) in enumerate(scenario_groups, start=1):
        role = roles[0] if roles else "业务负责人员"
        func_summary = _build_function_summary(feats)
        boundary_note = _build_boundary_note(i, len(scenario_groups), label, roles, feats)

        title = f"US{i}：作为「{role}」，希望{func_summary}，以便支撑业务运营"
        desc = (
            f"【故事描述】\n"
            f"本故事聚焦「{label}」场景，由「{role}」角色完成。\n"
            f"核心功能：{'；'.join(feats)}。\n\n"
            f"【差异化说明】{boundary_note}\n\n"
            f"【DDD 领域】{ddd.get('domain', '政企需求交付')} / {ddd.get('subdomain', '需求评估与履约')}"
        )
        scene = (
            f"【故事场景】\n"
            f"当「{role}」处理「{label}」相关业务时，系统应提供完整的功能支撑，"
            f"使其能在一个操作闭环内完成目标，获得明确的结果反馈。"
        )
        acceptance = _build_acceptance(feats, label)

        stories.append({
            "seq": i,
            "title": title,
            "desc": desc,
            "scene": scene,
            "acceptance": acceptance,
            "rules": [],
            "finalized": False,
        })

    return stories


def _build_function_summary(feats: List[str]) -> str:
    """构建功能摘要（用于标题，限制长度）。"""
    if len(feats) == 1:
        return feats[0][:50]
    first = feats[0][:40]
    return f"{first}等 {len(feats)} 项功能"


def _build_boundary_note(
    seq: int,
    total: int,
    label: str,
    roles: List[str],
    feats: List[str],
) -> str:
    """构建差异化边界声明（满足差异显性化原则）。"""
    if total == 1:
        return f"本需求仅包含 1 条用户故事，覆盖「{label}」场景的完整业务闭环。"
    return (
        f"本故事（US{seq}/{total}）聚焦「{label}」场景，"
        f"操作角色为「{roles[0] if roles else '业务负责人员'}」，"
        f"涵盖 {len(feats)} 项关联功能。"
        f"与同需求其他故事的差异在于业务场景{'和操作角色' if len(roles) > 1 else ''}不同。"
    )


def _build_acceptance(feats: List[str], label: str) -> List[str]:
    """构建验收标准列表。"""
    acceptance = []
    # 1. 场景级验收
    acceptance.append(f"验证「{label}」场景下整体业务流程可完整走通，无阻断")
    # 2. 功能级验收（每项至少 1 条）
    for f in feats[:8]:  # 最多 8 项验收
        # 提取核心动作
        core = re.sub(r"[，,。.].*$", "", f)[:60]
        acceptance.append(f"验证「{core}」功能是否成功实现")
    return acceptance


def _merge_smallest_scenarios(
    groups: List[Tuple[str, List[str], List[str]]],
    max_stories: int,
) -> List[Tuple[str, List[str], List[str]]]:
    """将功能块最少的小场景合并到大场景中，直到总数 <= max_stories。"""
    # 按功能块数升序排，优先合并最小的
    indexed = [(i, g) for i, g in enumerate(groups)]
    indexed.sort(key=lambda x: len(x[1][2]))  # 按 feats 长度

    while len(indexed) > max_stories and len(indexed) > 1:
        # 合并最小的两个
        _, (_, roles1, feats1) = indexed.pop(0)  # smallest
        i2, (label2, roles2, feats2) = indexed.pop(0)  # second smallest
        merged_label = f"{label2}（含关联功能）"
        merged_roles = list(dict.fromkeys(roles1 + roles2))
        merged_feats = list(dict.fromkeys(feats1 + feats2))
        indexed.append((i2, (merged_label, merged_roles, merged_feats)))
        indexed.sort(key=lambda x: len(x[1][2]))

    # 恢复原顺序
    result = [g for _, g in sorted(indexed, key=lambda x: x[0])]
    return result
