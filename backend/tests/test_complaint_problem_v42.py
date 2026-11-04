"""方案 v4.2「分析过程不依赖人」内核回归（D0 口径 / D1 L1 / D2 类 / D3 门禁 / D4 验收）。

重点守护三条：① 全链路没有人工触点，通道不可用自动拒识而不转人工队列；
② 生成与判定分离、证据锚点强制；③ 数量闭合达标但内容闭合不达标必须不发布。
"""

from constants import complaint_problem as P
from services.complaint.problem_acceptance import (
    decide, evaluate, rewrite_negatives, run_pipeline_once,
)
from services.complaint.problem_class import (
    build_card, build_classes, canonical, compose_description,
    extract_elements, same_problem, validate_card,
)
from services.complaint.problem_gate import GATE_CHANNEL, gate_one, run_gate
from services.complaint.problem_point import (
    JUDGE_CHANNEL, anchor_hits, build_point, detect_conclusion_record,
    extract_evidence_spans, validate_point,
)

# ── §2.4 的 15 条正面示例（方案钦定，必须全部判合格）─────────────
GOOD_DESCRIPTIONS = (
    "申请市公司管理员权限查全市商机预接入工单，无申请入口",
    "施工单触发审批后无人处理，订单一直停在预受理",
    "跨地市施工单已派发至网络部，宿迁网络侧收不到",
    "缴费后账号已复机，MPLS-VPN 站点仍显示全停",
    "装维已回单，施工结果未回传订单中心，订单停在已派单待回单",
    "施工单已归档，在途状态未释放，资费变更仍报「有在途」",
    "勘察需求待办被流转至异地支撑人员，订单反复流转无法结单",
    "电视平台已开通，师傅激活时仍提示「电视未开通」",
    "系统与客户端状态不一致，系统显示正使用、客户端显示停机",
    "移机按新地址搜索组网地址无结果，无法生成移机施工单",
    "移机报文旧地址字段为空，合法性校验失败未触发施工单",
    "移机仅改地址，前台校验拦截互联网电视业务并报错",
    "集团无欠费却被高风险规则误判，提交业务被强制审批",
    "商机单为互联网专线，一网通产品无法关联，订单搜不到地址",
    "报停账户充值后未校验报停状态即复机，继续出账多月收费",
)
BAD_DESCRIPTIONS = (
    "权限-使用咨询", "订单-未归档", "竣工结果-未回写",
    "其他-规则不合理", "产品实例-使用咨询", "订单-校验拦截",
)


def _mk(no, point, anchors, status="ok", gaps=None):
    return {"ticket_no": no, "point": point, "status": status,
            "gaps": gaps or [], "anchors": anchors, "evidence": anchors,
            "generator_channel": "semantic-plugin",
            "judge_channel": JUDGE_CHANNEL,
            "old_record_conclusion": False}


def _fail(text):
    return {"kind": "failure", "text": text, "source": "content"}


def _points():
    # 类 A 两成员：同一问题点，仅单号不同（§3.1 忽略差异 → 必须并成一类）
    a1 = _mk("T1", "装维已回单，施工结果未回传订单中心，订单停在已派单待回单",
             [_fail("施工结果未回传订单中心，订单停在已派单待回单")])
    a2 = _mk("T2", "装维已回单，施工结果未回传订单中心，订单 62026091514122343888 停在已派单待回单",
             [_fail("施工结果未回传订单中心，订单停在已派单待回单")])
    # 类 B：触发条件不同必分（§3.2 E3）
    b = _mk("T3", "移机报文旧地址字段为空，合法性校验失败未触发施工单",
            [_fail("合法性校验失败未触发施工单"),
             {"kind": "field", "text": "旧地址字段为空", "source": "content"}])
    # 类 C：首现类（1 单也立类），同时充当反例池
    c = _mk("T4", "勘察需求待办被流转至异地支撑人员，订单反复流转无法结单",
            [_fail("订单反复流转无法结单")])
    return [a1, a2, b, c]


def _gen(members, elements):
    from services.complaint.problem_class import strip_user_level
    return strip_user_level(members[0]["point"])


# ── D0 口径底座 ─────────────────────────────────────────────────
def test_d0_good_and_bad_descriptions():
    for t in GOOD_DESCRIPTIONS:
        assert P.check_description(t)["ok"], t
    for t in BAD_DESCRIPTIONS:
        assert not P.check_description(t)["ok"], t


def test_d0_conclusion_and_user_level():
    assert P.conclusion_hits("施工单按流程触发审批属正常业务规则，无系统错误")
    assert P.has_user_level_info("电视账号 50051157045 激活校验返回未开通")
    assert not P.has_user_level_info("施工结果未回传订单中心")
    assert P.is_vague_fix_point("优化流程")
    assert not P.is_vague_fix_point("订单中心施工结果回传接口字段")


def test_d0_single_source_of_thresholds():
    assert len(P.VETO_KEYS) == 6
    assert P.ACCEPTANCE["no_human_touch"] == 100.0
    assert P.ACCEPTANCE["content_closure"] == 95.0
    assert P.ACCEPTANCE["gate_leak_max"] == 2.0
    assert set(P.VETO_KEYS).issubset(P.ACCEPTANCE)
    assert P.NO_CLUSTER_LIMIT is True and P.FIRST_SIGHT_MIN_MEMBERS == 1
    assert len(P.FORBIDDEN_HUMAN_TOUCHES) >= 8


# ── D1 逐单问题点 ───────────────────────────────────────────────
def test_d1_conclusion_record_is_not_a_point():
    r = detect_conclusion_record("申请管理员权限，属正常业务规则，系统无缺陷")
    assert r["is_conclusion"] and "属正常" in r["hits"]


def test_d1_evidence_spans_and_rule_block():
    spans = extract_evidence_spans(
        "移机报文旧地址字段为空，激活时仍提示「电视未开通」，订单 62026091514122343888",
        "增加管理权限请走审批流程到省工号管理员")
    kinds = {s["kind"] for s in spans}
    assert {"error_text", "failure", "field", "rule_block", "identifier"}.issubset(kinds)
    spans2 = extract_evidence_spans(
        "移机报文旧地址字段为空，激活时仍提示「电视未开通」，订单 62026091514122343888",
        "增加管理权限请走审批流程到省工号管理员")
    assert spans == spans2          # 可复现


def test_d1_channel_unavailable_auto_degrades_without_human():
    t = {"ticket_no": "X", "content": "电视平台已开通，师傅激活时仍提示「电视未开通」",
         "solution_history": "", "root_cause": "属正常业务规则，无系统错误"}
    r = build_point(t, generator=None)
    assert r["status"] == P.DEGRADED_STATUS
    assert r["gaps"][0] == P.DEGRADED_REASON_CHANNEL
    assert r["old_record_conclusion"] is True
    assert r["judge_channel"] == JUDGE_CHANNEL
    assert not any(k in r for k in P.FORBIDDEN_HUMAN_TOUCHES)


def test_d1_evidence_missing_auto_rejects():
    t = {"ticket_no": "Y", "content": "客户来电咨询", "solution_history": "", "root_cause": ""}
    r = build_point(t, generator=lambda *_: "随便编一句")
    assert r["status"] == P.UNCLASSIFIED_STATUS
    assert P.DEGRADED_REASON_EVIDENCE in r["gaps"]


def test_d1_generator_result_must_pass_independent_judge():
    t = {"ticket_no": "Z", "content": "电视平台已开通，师傅激活时仍提示「电视未开通」",
         "solution_history": "", "root_cause": ""}
    # 生成一段过短且与证据无关的结论 → 独立判定必须拦下
    bad = build_point(t, generator=lambda *_: "已处理")
    assert bad["status"] == P.UNCLASSIFIED_STATUS
    assert bad["gaps"]
    good = build_point(t, generator=lambda *_: "电视平台已开通，师傅激活时仍提示「电视未开通」")
    assert good["status"] == "ok"
    assert good["judge_channel"] != good["generator_channel"]


def test_d1_validate_point_and_anchors():
    spans = extract_evidence_spans("激活时仍提示「电视未开通」", "")
    assert anchor_hits("激活时仍提示「电视未开通」", spans)
    assert validate_point("激活时仍提示「电视未开通」，无法开通电视业务", spans)["ok"]


# ── D2 问题点类与判定卡 ─────────────────────────────────────────
def test_d2_elements_and_canonical():
    el = extract_elements(_points()[0])
    assert el["object"] and el["failure"]
    assert canonical("施工工单没生成") == canonical("施工单未生成")
    assert same_problem(el, el)


def test_d2_merge_ignore_ticket_no_split_by_trigger():
    d = build_classes(_points(), generator=_gen)
    assert d["stats"]["classes"] == 3          # A(2 单) / B / C(首现)
    assert d["stats"]["first_sight"] == 2
    a = [c for c in d["classes"] if c["ticket_cnt"] == 2]
    assert len(a) == 1
    assert set(a[0]["members"]) == {"T1", "T2"}
    assert all(c["status"] == "published" for c in d["classes"])
    assert all(validate_card(c["card"])["ok"] for c in d["classes"])
    assert not any(c["description"] in P.BANNED_STANDALONE_TERMS for c in d["classes"])


def test_d2_reject_first_merges_into_existing_class():
    built = build_classes(_points(), generator=_gen)
    existing = [built["classes"][0]]
    d = build_classes([_points()[1]], generator=_gen, existing=existing)
    assert d["stats"]["classes"] == 1             # 不另立新类
    assert "T2" in d["classes"][0]["members"]
    assert d["classes"][0]["drift_rerun"] is True  # 新增成员触发自动重核


def test_d2_card_requires_two_positive_two_negative():
    c = build_card(GOOD_DESCRIPTIONS[0], {"object": "施工单", "action": "回单",
                                          "failure": "施工结果未回传", "trigger": ""},
                   "订单中心回传接口字段", _points()[:1], [])
    v = validate_card(c)
    assert not v["ok"] and any("negatives" in m for m in v["missing"])


def test_d2_admission_three_questions():
    from services.complaint.problem_class import admission_check
    el = {"object": "施工单", "action": "生成", "failure": "未生成施工单", "trigger": ""}
    assert not admission_check(el, "优化流程", _points()[:1])["ok"]
    assert admission_check(el, "施工单生成接口字段", _points()[:1])["ok"]


def test_d2_first_sight_class_not_dropped():
    d = build_classes([_points()[3]], generator=_gen)
    assert d["stats"]["classes"] == 1
    assert d["classes"][0]["first_sight"] is True
    assert d["classes"][0]["card"]["positives"]


# ── D3 自动门禁 ─────────────────────────────────────────────────
def _published():
    return build_classes(_points(), generator=_gen)["published"]


def test_d3_gate_100_percent_coverage_no_human_touch():
    g = run_gate(_points(), _published())
    assert g["stats"]["gate_coverage"] == 100.0
    assert g["stats"]["human_touches"] == []
    assert all(p["judge_channel"] == GATE_CHANNEL for p in g["pairs"])
    assert all(p["generator_channel"] != GATE_CHANNEL for p in g["pairs"])
    assert len(g["matched"]) == 4


def test_d3_negative_short_circuit():
    cls = dict(_published()[0])
    card = dict(cls["card"])
    card["negatives"] = [{"ticket_no": "T1", "evidence": "x", "reason": "r", "exclude_code": "E3"}]
    cls["card"] = card
    p = gate_one(_points()[0], cls)
    assert p["status"] == P.UNCLASSIFIED_STATUS
    assert any("反例短路" in x for x in p["gaps"])


def test_d3_mismatch_auto_second_pass_or_unclassified():
    cls = dict(_published()[0])
    # B 型错指：该单证据与描述完全不对应
    wrong = _mk("W1", "缴费后账号已复机，MPLS-VPN 站点仍显示全停", [_fail("站点仍显示全停")])
    p = gate_one(wrong, cls)
    assert p["status"] == P.UNCLASSIFIED_STATUS
    assert p["gaps"] and p["second_channel"]
    # A 型过宽：对象不在该单，但证据片段能被描述覆盖 → 自动二次判定放行并留痕
    wide = _mk("W2", "施工结果未回传订单中心，订单停在已派单待回单",
               [_fail("施工结果未回传订单中心，订单停在已派单待回单")])
    p2 = gate_one(wide, cls)
    assert p2["status"] in ("matched", "matched_second")
    assert p2["mapped"]


def test_d3_drift_rerun_voids_description():
    classes = _published()
    classes[0]["drift_rerun"] = True
    g = run_gate(_points(), classes)
    assert g["stats"]["gate_coverage"] == 100.0
    assert isinstance(g["voided_classes"], list)
    for u in g["unclassified"]:
        assert u["gaps"]            # 未归类必须写明缺口


# ── D4 自动验收闸门 ─────────────────────────────────────────────
def test_d4_reproducible_and_publish():
    r = evaluate(_points(), generator=_gen)
    assert r["reproducible"] == 100.0
    assert r["metrics"]["no_human_touch"] == 100.0
    assert r["metrics"]["point_pass_rate"] == 100.0
    assert r["decision"]["publish"] is True, r["decision"]["failed"]


def test_d4_veto_blocks_publication():
    pts = _points()
    pts[1]["status"] = P.DEGRADED_STATUS          # 源头合格率掉到 75%
    r = evaluate(pts, generator=_gen)
    assert r["decision"]["publish"] is False
    assert "point_pass_rate" in r["decision"]["veto"]


def test_d4_count_closure_alone_is_not_enough():
    m = {k: (0.0 if k.endswith("_max") else 100.0) for k in P.ACCEPTANCE}
    m["content_closure"] = 50.0
    d = decide(m)
    assert d["publish"] is False
    assert any("数量闭合达标但内容闭合不达标" in x for x in d["failed"])


def test_d4_leak_rewrites_negatives_and_goldset_grows():
    r = evaluate(_points(), generator=_gen)
    assert r["goldset"]["core"]
    assert r["goldset"]["new_class_coverage"] == 100.0
    classes = r["classes"]
    before = len(classes[0]["card"]["negatives"])
    added = rewrite_negatives(classes, ["T1"], _points())
    assert added >= 1
    assert len(classes[0]["card"]["negatives"]) > before
