"""主动运营分析工单导入解析回归测试。

背景（2026-09-20 事故）：两份「填写说明」模板文件（列A=长描述、列B=短标签带冒号、列C=内容）
导入后正文七字段全空且无告警——解析器只匹配列A 标签，列B 标签永不命中；
同时结果区旧实现用外层行列B匹配且命中即 break，导致多行结果只落进第一项。
本文件锁定两种布局与日期容错，防复发。
"""

import io
from datetime import date

import openpyxl

from services.operation_analysis import (
    _parse_date,
    parse_analysis_workbook,
)

BODY_KEYS = [
    "background",
    "scenario",
    "biz_flow",
    "biz_rule",
    "monitoring",
    "analysis_goal",
    "data_analysis",
]


def _wb_bytes(build) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    build(ws)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _build_shuoming_layout(ws):
    """布局①「填写说明」模板：列A=长描述提示、列B=短标签带冒号、列C=内容。"""
    ws.cell(row=1, column=1, value="填写说明")
    ws.cell(row=1, column=2, value="测试课题名称")
    ws.cell(row=3, column=1, value="分析人员信息")
    ws.cell(row=3, column=2, value="分析人员信息：")
    ws.cell(row=3, column=3, value="运营团队：CRM          运营人员姓名：张三")
    rows = [
        (4, "课题背景介绍，重点说明为什么有这次分析工作", "课题背景说明：", "背景内容ABC"),
        (6, "本次课题分析的场景简单介绍下", "操作场景介绍：", "场景内容XYZ"),
        (8, "梳理确认课题涉及的业务流程", "业务流程梳理：", "流程内容"),
        (10, "梳理确认课题涉及的业务规则", "业务规则梳理：", "规则内容"),
        (12, "梳理目前已经部署的监控情况", "业务监控梳理：", "监控内容"),
        (15, "主动识别并预置分析任务", "本次分析目标：", "目标内容"),
        (17, "以生产数据为基石", "数据分析过程：", "分析内容"),
    ]
    for r, a, b, c in rows:
        ws.cell(row=r, column=1, value=a)
        ws.cell(row=r, column=2, value=b)
        ws.cell(row=r, column=3, value=c)
    # 结果区：子标题在列C、内容在列D
    ws.cell(row=19, column=1, value="基于数据分析，提炼分析结果")
    ws.cell(row=19, column=2, value="分析结果：")
    ws.cell(row=19, column=3, value="流程优化方面")
    ws.cell(row=19, column=4, value="流程结果")
    ws.cell(row=21, column=3, value="规则优化方面")
    ws.cell(row=21, column=4, value="规则结果")
    ws.cell(row=23, column=3, value="数据模型方面")  # 无内容，不应把子标题当正文
    ws.cell(row=25, column=3, value="异常用户数据方面")
    ws.cell(row=25, column=4, value="异常结果")
    ws.cell(row=27, column=3, value="监控补盲方面")
    ws.cell(row=27, column=4, value="补盲结果")
    # 遗留任务区
    ws.cell(row=29, column=1, value="如果本次课题到周五，还有未完成的任务")
    ws.cell(row=29, column=2, value="遗留任务：")
    ws.cell(row=29, column=3, value="责任人")
    ws.cell(row=29, column=4, value="任务内容")
    ws.cell(row=29, column=5, value="计划完成时间")
    ws.cell(row=30, column=3, value="李四")
    ws.cell(row=30, column=4, value="遗留任务一")
    ws.cell(row=30, column=5, value=46295)  # Excel 序列号 → 2026-09-30
    ws.cell(row=31, column=3, value="王五")
    ws.cell(row=31, column=4, value="遗留任务二")
    ws.cell(row=31, column=5, value="9.30")


def _build_meng_layout(ws):
    """布局②（孟华/顾杨豪）模板：列A=带冒号标签、列B=内容；结果区列B=子标题、列C=内容。"""
    ws.cell(row=1, column=1, value="布局二课题名称")
    ws.cell(row=3, column=1, value="分析人员信息：")
    ws.cell(row=3, column=2, value="运营团队：订单中心             运营人员姓名：孟华")
    ws.cell(row=4, column=1, value="课题背景说明：")
    ws.cell(row=4, column=2, value="背景B")
    ws.cell(row=6, column=1, value="操作场景介绍：")
    ws.cell(row=6, column=2, value="场景B")
    ws.cell(row=8, column=1, value="业务流程梳理：")
    ws.cell(row=8, column=2, value="流程B")
    ws.cell(row=10, column=1, value="业务规则梳理：")
    ws.cell(row=10, column=2, value="规则B")
    ws.cell(row=12, column=1, value="业务监控梳理：")
    ws.cell(row=12, column=2, value="监控B")
    ws.cell(row=13, column=1, value="本次分析目标：")
    ws.cell(row=13, column=2, value="目标B")
    ws.cell(row=14, column=1, value="数据分析过程：")
    ws.cell(row=14, column=2, value="分析B")
    ws.cell(row=18, column=1, value="分析结果：")
    ws.cell(row=18, column=2, value="流程优化方面")
    ws.cell(row=18, column=3, value="流程结果B")
    ws.cell(row=20, column=2, value="规则优化方面")
    ws.cell(row=20, column=3, value="规则结果B")
    ws.cell(row=22, column=2, value="数据模型方面")
    ws.cell(row=24, column=2, value="异常用户数据方面")
    ws.cell(row=26, column=2, value="监控补盲方面")
    ws.cell(row=26, column=3, value="补盲结果B")
    ws.cell(row=28, column=1, value="遗留任务：")
    ws.cell(row=28, column=2, value="责任人")
    ws.cell(row=28, column=3, value="任务内容")
    ws.cell(row=28, column=4, value="计划完成时间")
    ws.cell(row=29, column=2, value="赵六")
    ws.cell(row=29, column=3, value="遗留任务B")
    ws.cell(row=29, column=4, value="94662")  # 2026-09-24 的序列号


def test_shuoming_layout_parses_body_fields():
    """布局①：正文七字段必须全部解析出来（旧实现全丢）。"""
    res = parse_analysis_workbook(_wb_bytes(_build_shuoming_layout))
    fields = res["analysis_fields"]
    assert fields["topic_name"] == "测试课题名称"
    assert fields["analyst_team"] == "CRM"
    assert fields["analyst_name"] == "张三"
    assert fields["background"] == "背景内容ABC"
    assert fields["scenario"] == "场景内容XYZ"
    assert fields["biz_flow"] == "流程内容"
    assert fields["biz_rule"] == "规则内容"
    assert fields["monitoring"] == "监控内容"
    assert fields["analysis_goal"] == "目标内容"
    assert fields["data_analysis"] == "分析内容"
    # 结果区五项齐全
    assert fields["result_flow"] == "流程结果"
    assert fields["result_rule"] == "规则结果"
    assert not fields.get("result_model")  # 源单元格为空，不得把子标题当正文
    assert fields["result_abnormal_user"] == "异常结果"
    assert fields["result_monitor_blind"] == "补盲结果"
    # 正文齐全时不应出现「未识别到分析正文」告警
    assert not [w for w in res["warnings"] if "未识别到分析正文" in w]
    # 遗留任务：表头在列C，两行任务，序列号与「9.30」都识别为 2026-09-30
    tasks = res["legacy_tasks"]
    assert [t["handlers"] for t in tasks] == [["李四"], ["王五"]]
    assert [t["due_date"] for t in tasks] == ["2026-09-30", "2026-09-30"]


def test_shuoming_layout_strips_duplicated_label_prefix():
    """布局①：列C 常把标签再抄一遍，入库前须去掉重复前缀。"""
    def build(ws):
        ws.cell(row=1, column=2, value="前缀课题")
        ws.cell(row=4, column=2, value="课题背景说明：")
        ws.cell(row=4, column=3, value="课题背景说明：\n只有这段是正文")

    fields = parse_analysis_workbook(_wb_bytes(build))["analysis_fields"]
    assert fields["background"] == "只有这段是正文"


def test_meng_layout_all_result_items_parsed():
    """布局②：结果区四项/五项须逐行解析，旧实现只落第一项。"""
    res = parse_analysis_workbook(_wb_bytes(_build_meng_layout))
    fields = res["analysis_fields"]
    assert fields["topic_name"] == "布局二课题名称"
    assert fields["analyst_name"] == "孟华"
    assert fields["analyst_team"] == "订单中心"
    for key in BODY_KEYS:
        assert fields[key], f"{key} 未解析到内容"
    assert fields["result_flow"] == "流程结果B"
    assert fields["result_rule"] == "规则结果B"
    assert not fields.get("result_model")
    assert not fields.get("result_abnormal_user")
    assert fields["result_monitor_blind"] == "补盲结果B"
    tasks = res["legacy_tasks"]
    assert [t["handlers"] for t in tasks] == [["赵六"]]


def test_missing_body_triggers_explicit_warning():
    """正文全空时必须显式告警，避免再次静默丢字段。"""
    def build(ws):
        ws.cell(row=1, column=2, value="只有标题的文件")

    res = parse_analysis_workbook(_wb_bytes(build))
    assert any("未识别到分析正文" in w for w in res["warnings"])


def test_parse_date_tolerates_short_forms():
    """日期容错：「9.24」「9月22号」等短写法不得变成 1900 年脏数据。"""
    assert _parse_date(9.24) == date(2026, 9, 24)
    assert _parse_date("9.24") == date(2026, 9, 24)
    assert _parse_date("9月24日") == date(2026, 9, 24)
    assert _parse_date("9月22号") == date(2026, 9, 22)
    assert _parse_date(46295) == date(2026, 9, 30)  # 真实 Excel 序列号仍照常解析
    for bad in ("待定", "/", "", None, 8, 13.5):
        assert _parse_date(bad) is None
