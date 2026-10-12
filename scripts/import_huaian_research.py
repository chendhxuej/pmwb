# -*- coding: utf-8 -*-
"""淮安订单中心调研明细导入（一线调研模块 · 子类 huaian_order_center）

数据来源（老大桌面）：
  8 月：C:/Users/chend/Desktop/运营问题汇总/淮安订单中心/8月优化建议/
        【汇总】【8月份】淮安订单中心系统优化需求清单.xlsx（37 条，1 个 sheet）
  10 月：C:/Users/chend/Desktop/运营问题汇总/淮安订单中心/10月优化建议/
        【10月份】系统优化需求信息分析与汇总.xlsx（需求汇总明细 sheet，19 条）

映射规则（2026-10-12 老大确认）：
  · 粒度：逐条录入（每条问题 = 一条调研工单）
  · 子类：huaian_order_center「淮安订单中心调研」；地市 city=huaian
  · 状态：按原表「是否采纳 / 评审结果」回填
  · 特有列：按现有工单模板落位，不新增数据库字段

用法：
  python backend/venv/Scripts/python.exe scripts/import_huaian_research.py --dry-run
  python backend/venv/Scripts/python.exe scripts/import_huaian_research.py            # 跳过已存在
  python backend/venv/Scripts/python.exe scripts/import_huaian_research.py --force    # 覆盖更新
"""
from __future__ import annotations

import argparse
import os
import sys

BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

# 坑：OS 级环境变量会覆盖 backend/.env，导致 1045 Access denied。
# 显式以 .env 为准重建连接串，再加载 db.base（settings 读取 os.environ）。
from dotenv import dotenv_values  # noqa: E402

_env = dotenv_values(os.path.join(BACKEND, ".env"))
if _env.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = _env["DATABASE_URL"]

from db.base import SessionLocal  # noqa: E402
from db.models import PmwbResearchIssue  # noqa: E402

SUB_TYPE = "huaian_order_center"
CITY = "huaian"
SOURCE_2608 = "淮安订单中心8月调研 · 【汇总】【8月份】淮安订单中心系统优化需求清单.xlsx"
SOURCE_2610 = "淮安订单中心10月调研 · 【10月份】系统优化需求信息分析与汇总.xlsx"

# 8 月「是否采纳」→ 工单状态
STATUS_MAP_8 = {
    "已解决": "resolved",
    "已优化": "resolved",
    "优化中": "processing",
    "部分解决": "processing",
    "建议采纳": "pending",
    "是": "pending",
    "待业务部门评估": "pending",
    "暂不采纳": "closed",
    "": "pending",
}

# ---------------------------------------------------------------- 8 月（37 条）
HUAIAN_2608 = [
    dict(no=1, cat="一网通", biz="一网通/组网业务资费录入", system="CRM系统",
         name="一网通/组网业务资费录入问题",
         desc="资费系统设置最低金额门槛（如最低5元/月），低于此金额的资费无法在订单中心填写提交。客户经理与客户谈判后合同约定低于系统最低金额的资费（如3元/月），合同经合规审批后生效，但因系统限制无法录入实际金额，导致订单无法正常流转，需退回修改合同或发起特殊整改流程，增加沟通成本和业务开通周期。",
         expect="系统和合同系统最低限制需与可实现操作保持一致。", biz_owner="", di_owner="陈大海",
         adopt="已解决", assess="此问题目前已经有需求安排优化",
         solution="已安排下调crm侧商客产品的最低售价包含规则约束，下调到0.1元",
         need_flow="", plan_date="9月初版本", sa=""),
    dict(no=2, cat="一网通", biz="批量开通一网通", system="CRM系统",
         name="批量开通一网通——地址选择数量提示",
         desc="批量开通一网通时，需从地址列表选择多个目标地址，当前页面未提供已选数量实时反馈，只能凭记忆或自行计数确认。单个批量任务涉及数十甚至上百个地址，需反复核对是否漏选、多选或重复选择，操作效率低下且极易出错。",
         expect="1.增加实时计数展示，在地址选择页面固定位置实时显示已勾选地址数量；2.同步展示总地址数，以已选X/总数Y格式呈现。",
         biz_owner="", di_owner="陈大海", adopt="优化中",
         assess="已有需求在改造，目前前台系统各业务的地址选址方式不一，此问题目前已经有需求安排优化",
         solution="统一选址公共服务组件，一套服务，支持按业务个性化屏蔽。",
         need_flow="", plan_date="9月初版本", sa=""),
    dict(no=3, cat="一网通", biz="一网通免施工地址提醒", system="CRM系统",
         name="一网通免施工地址提醒",
         desc="是否免施工属性参数随勾选地址代入确认，因各地市对免施工地址发单有严格要求，受理人员会漏看是否为免施工地址导致错误发单。",
         expect="建议电子协议起草时，客户经理勾选地址为免施工地址时，系统弹窗提醒当前地址为免施工地址并请谨慎发单，减少发单错误问题。业务侧修正，系统判定是什么就是什么参数，无需受理人员介入调整",
         biz_owner="杨凯", di_owner="陈大海", adopt="建议采纳",
         assess="建议有效，我们会沟通业务部门评估调整服务规则",
         solution="不需要操作员前台个性化设置是否免施工，这个信息直接采集gims选择的地址配置（标准地址都有这个是否免施工的参数信息）",
         need_flow="待提需求工单", plan_date="", sa=""),
    dict(no=4, cat="一网通", biz="手机看店销户失效时间选择", system="CRM系统",
         name="手机看店销户失效时间选择问题",
         desc="手机看店业务通过集团业务批量销户时可选立即失效；但商品中心单次操作仅能选次月1号失效。客户经理如需立即销户1条产品，受理人员需制作表格进行批量操作。",
         expect="建议商品中心销户的失效时间都可以手动选择立即或次月。统一销户规则",
         biz_owner="范伟", di_owner="陈大海", adopt="建议采纳",
         assess="建议有效，我们会沟通业务部门评估调整服务规则",
         solution="统一业务销户场景的失效时间业务规则，不要分场景差异化",
         need_flow="待提需求工单", plan_date="", sa=""),
    dict(no=5, cat="一网通", biz="组网批量发单", system="CRM系统",
         name="组网批量发单问题（不同宽带不同地址）",
         desc="一网通智能组网批量开户页面，系统无法实现不同宽带不同地址的批量发单。即使导入的模板表中为不同的宽带账号及地址，提交后结果依然显示为同一个宽带账号及地址。受理人员只能手动单个办理，极大浪费效能。",
         expect="一网通智能组网批量开户操作时可读取导入的对应宽带账号及地址进行对应开通。基于附件支持组网的批开对应不同宽带账号及地址，实现个性化派单",
         biz_owner="范伟", di_owner="陈大海", adopt="暂不采纳",
         assess="功能具备，建议淮安订单中心按此场景提供实际操作录屏（明确操作步骤）",
         solution="", need_flow="", plan_date="", sa=""),
    dict(no=6, cat="一网通", biz="单点版一网通智能组网设备选择", system="CRM系统",
         name="单点版一网通业务智能组网设备选择",
         desc="单点版一网通加开智能组网时，光猫类型、FTTO设备类型虽为必填项，但因系统默认填充值（普通光猫/FTTO-B），无强提醒，导致员工漏选、错选，引发后续业务关联失败或退撤单。",
         expect="建议同商务版实现无需手动选择光猫类型，由工维按实际需求携带设备安装。商务快线拟计划下线，待确认具体下线时间，先取消隐藏折叠，默认展开",
         biz_owner="杨凯", di_owner="陈大海", adopt="建议采纳",
         assess="建议有效，我们会沟通业务部门，推动产品下线，",
         solution="同业务管理员沟通结果，会在10月份前完成此产品下线。", need_flow="", plan_date="", sa=""),
    dict(no=7, cat="一网通", biz="移动宽带企业版/商务快线同步办理", system="CRM系统",
         name="移动宽带企业版/商务快线同步办理业务",
         desc="移动政企宽带、单点版一网通开通业务，同一集团多个人同时办理，会有业务开通失败的情况。",
         expect="系统能否实现同一集团可以同时多人办理业务。",
         biz_owner="杨凯", di_owner="陈大海", adopt="建议采纳",
         assess="建议有效，我们会沟通业务部门，重新评估宽带账号生成规则",
         solution="方案一（建议优先采纳）：\n恢复操作规则，维持一个集团一个操作员的要求。\n同步优化批量操作便捷性，支持大批量任务一次导入，由后台按性能自动拆分多任务，并串行逐一执行。",
         need_flow="待提需求工单", plan_date="", sa=""),
    dict(no=8, cat="一网通", biz="一网通发单地址问题", system="订单中心",
         name="一网通发单地址问题（前端地址与回传地址不一致）",
         desc="受理人员按协议地址进行业务办理，实际工维施工后，后台回传同步的地址与前端地址不一致，引起合规性问题。",
         expect="触发的施工单中体现前端发单地址与实际安装地址信息，便于稽核复核业务办理准确性。",
         biz_owner="李能禾", di_owner="陈大海", adopt="已解决",
         assess="在稽核界面展示施工派单地址+实际施工地址+地址不一致原因说明(网络侧地址调整)",
         solution="", need_flow="", plan_date="", sa=""),
    dict(no=9, cat="一网通", biz="商务快线改资费触发施工单", system="CRM系统",
         name="商务快线改资费触发施工单", desc="", expect="",
         biz_owner="童振彦", di_owner="陈大海", adopt="建议采纳",
         assess="方案：\n1、前台操作页面优化，区分短流程业务操作和长流程操作\n2、协同网络部，针对改密、改带宽、停复机由现在的长流程机制改为实时通知（短流程通知）；",
         solution="", need_flow="", plan_date="", sa=""),
    dict(no=10, cat="专线类", biz="工维施工单退单流程", system="集客订单系统",
         name="工维施工单退单流程优化", desc="", expect="",
         biz_owner="李能禾", di_owner="陈大海", adopt="暂不采纳",
         assess="集客部、网络部协同商定新流程", solution="", need_flow="是", plan_date="", sa="王辅松"),
    dict(no=11, cat="专线类", biz="专线停复机/改资费施工单自动归档", system="CRM系统",
         name="专线停复机/改资费施工单触发后需额外通知",
         desc="互联网专线（含商务专线）、VPN专线停复机会触发施工单，受理人员需逐单通知客户经理/网络部进行归档。未及时归档会导致产品次月继续出账。",
         expect="针对停复机、改资费等无需施工的施工单，能实现即时自动归档，无需网络部或工维人员手动归档。",
         biz_owner="", di_owner="帅敏", adopt="部分解决",
         assess="已解决：\n1、改资费操作不在触发施工单流程；\n待管理沟通：\n2、目前专线停复机流程是需要等待网络部反馈，如果反馈不及时，存在跨月未及时更新状态，需要业务部门和网络部沟通停复机流程；",
         solution="", need_flow="是", plan_date="", sa="王辅松/郑文东"),
    dict(no=12, cat="专线类", biz="专线新增与存量变更区县错误", system="集客订单系统",
         name="专线新增与存量变更：区县错误且未同步",
         desc="专线业务新增需关联商机接入单，但频繁出现区县错误。客户经理发起商机单时区县选择错误（系统未对区县、网格进行校验）。网络部后续修改正确区县后未同步至订单中心（无反馈机制），导致受理人员仍使用错误区县发起订单。",
         expect="建议客户经理发起商机单时，系统对区县与地址比对后做强校验限制，直接将地址信息准确后回填到目标区县处，无需受理人员手动修正。",
         biz_owner="张舒明", di_owner="帅敏", adopt="优化中",
         assess="待优化", solution="商机预接入流程施工反馈增加施工区县信息反向更新",
         need_flow="是", plan_date="9.10版本", sa="王辅松"),
    dict(no=13, cat="专线类", biz="VPN专线大项目选择默认值", system="CRM系统",
         name="VPN专线大项目选择默认值导致遗漏",
         desc="系统是否大项目选项默认否，受理人员容易忘记选择。",
         expect="建议系统将是否大项目调成空白，且设置为必选项，办理时必须手动选择。",
         biz_owner="邵建", di_owner="帅敏", adopt="已解决", assess="已解决",
         solution="大项目标识根据专线数量自动初始化：根据合同号查合同下的签约的专线数量，大于20算大项目",
         need_flow="否", plan_date="已完成", sa="王辅松"),
    dict(no=14, cat="专线类", biz="数据专线多Z端地址办理卡单", system="集客订单系统",
         name="数据专线多Z端地址办理卡单",
         desc="数据专线新开或变更时，若Z端地址数量较多（如1个A端对应10个以上Z端），系统卡单严重，每次需提交小信工单，厂家优化后才能处理。",
         expect="建议数据专线的协议、订单，1A对多Z的地址限制上限数量10条。",
         biz_owner="邵建", di_owner="帅敏", adopt="已优化", assess="已优化",
         solution="数据专线C2C/OTN实例变更界面查询加载逻辑优化",
         need_flow="否", plan_date="已完成", sa="王辅松"),
    dict(no=15, cat="专线类", biz="数据专线选址地址覆盖类型不一致", system="集客订单系统",
         name="数据专线选址地址覆盖类型不一致",
         desc="前台选址时，若安装地址手填处未删除，施工单与网络部收到的地址覆盖类型不一致（实际为厚覆盖，系统识别有误），网络部多次反馈覆盖类型不一致导致面临考核。",
         expect="安装地址手填处应默认为空白；实际地址应根据商机接入单或选址，系统侧自动准确识别地址覆盖类型。",
         biz_owner="邵建", di_owner="帅敏", adopt="已优化", assess="已优化",
         solution="安装地址手填处应默认为空白；实际地址应根据商机接入单或选址，系统侧自动准确识别地址覆盖类型。",
         need_flow="否", plan_date="已完成", sa="王辅松"),
    dict(no=16, cat="专线类", biz="政务随心配存量业务变更", system="CRM系统",
         name="政务随心配存量业务变更能力缺失",
         desc="存量业务中IP个数、FTTO（专线版）光猫数量、资费等无法操作变更。若客户需新增从光猫10个，目前只能另外开通1主10从，然后通过CRM后台处理（小信工单）。",
         expect="针对前期已开通的业务，系统应支持增加IP数量、FTTO数量等变更操作，具有操作按钮。",
         biz_owner="张舒明", di_owner="帅敏", adopt="已解决", assess="已优化解决",
         solution="", need_flow="", plan_date="", sa=""),
    dict(no=17, cat="专线类", biz="政务随心配设备型号问题", system="CRM系统",
         name="政务随心配设备型号问题",
         desc="CRM系统受理政务随心配专线卫士时，设备型号默认为华为增强版，字段为非必填项。受理人员因惯性操作易忽略下拉切换，造成订单设备与实际需求不符。",
         expect="将设备型号设为必填项，默认值由华为增强版改为空；若某项无需配置，后面增加是否为必选项。",
         biz_owner="张舒明", di_owner="帅敏", adopt="优化中", assess="已有需求在优化改造",
         solution="", need_flow="", plan_date="9.10版本", sa=""),
    dict(no=18, cat="专线类", biz="极速上网专线移机问题", system="CRM系统",
         name="极速上网专线移机问题（未触发施工单）",
         desc="进行移机操作后系统地址信息已变更，但工维反馈未接到施工单，无法进行移机施工。经提交小信核实，受理人员仅修改了地址名称及地区，再次发起移机操作依然未触发施工单。",
         expect="优化极速上网专线进行移机操作时可以同步触发施工单。",
         biz_owner="", di_owner="", adopt="暂不采纳", assess="建议采用变通方案操作",
         solution="建议通过相近地址，通过备注标记移机地址，完成移机",
         need_flow="", plan_date="", sa=""),
    dict(no=19, cat="专线类", biz="移动400业务代付功能", system="CRM系统",
         name="移动400业务代付功能问题",
         desc="移动400业务存在最低消费要求且不支持第三方代付。即使用户发起代付申请，系统后端也无法完成真实扣款。但当前系统在受理环节未做限制，代付订单仍可正常提交办理成功，最终因无法代付导致费用无人承担。",
         expect="前置限制：在移动400业务资费确认环节，系统自动判断是否支持代付。不支持则直接屏蔽代付选项或提交时给出明确阻断提示。",
         biz_owner="", di_owner="帅敏", adopt="", assess="", solution="",
         need_flow="", plan_date="", sa="张茜"),
    dict(no=20, cat="专线类", biz="400业务最低消费生效时间", system="CRM系统",
         name="400业务最低消费生效时间与协议不一致",
         desc="业务协议可选择次月生效，但系统目前仅支持立即生效，无法满足协议约定。",
         expect="将系统设置与协议中的增值商品生效时间保持一致，避免因协议与系统不匹配引发客户争议。",
         biz_owner="", di_owner="帅敏", adopt="", assess="", solution="",
         need_flow="", plan_date="", sa="张茜"),
    dict(no=21, cat="专线类", biz="语音专线号码开通与密码重置", system="CRM系统",
         name="语音专线号码开通与密码重置存在障碍",
         desc="（1）号码单无法正常推送：固话成员号码添加后，工维反馈未收到号码单，需在多媒体桌面电话中二次删除并重新添加；（2）密码重置困难：2020年4月前加入的语音专线成员需重置密码，系统缺失信息，需先退后加方式重置，易引发投诉且存在退出后无法重新加入的风险。",
         expect="（1）实现语音专线成员添加后准确同步至多媒体桌面电话并自动推送号码单；（2）支持直接对历史成员进行密码重置，避免先退后加的操作风险。",
         biz_owner="", di_owner="帅敏", adopt="", assess="", solution="",
         need_flow="", plan_date="", sa="张茜"),
    dict(no=22, cat="电子协议", biz="协议合同总金额为0或计算错误", system="电子协议系统",
         name="协议合同总金额为0或与实际不符",
         desc="多份电子协议第一页合同总金额处为0或与实际资费不符（如FTTO正确金额应为3600元显示为1200元；移动宽带企业版正确8640元显示为2880元），接入点详情页有对应单价/折后价及数量信息，应按单价x数量x业务期限=合同总金额。",
         expect="在协议起草时内置自动计算公式（资费x数量x协议期）并强校验，若总金额为0或与系统计算结果不一致，应限制转单，确保金额准确。",
         biz_owner="方舟", di_owner="陈大海", adopt="是", assess="当前购物车流程算费不准",
         solution="已经专项跟踪，crm会标准化资费属性", need_flow="", plan_date="", sa="秦新/吴雨霜"),
    dict(no=23, cat="电子协议", biz="协议资费变更金额展示", system="电子协议系统",
         name="资费变更订单协议金额展示问题",
         desc="客户经理实际需求为变更原开通的8条专线中一条的IP个数，协议自动抓取原协议总金额合计，易造成受理人员计算误差，业务办理错误。",
         expect="在协议中新增单条资费变更明细展示，独立计算该专线的原资费与新资费，按差值调整总金额，增加变更前后费用对比校验。",
         biz_owner="方舟", di_owner="陈大海", adopt="是",
         assess="展示在变更协议的字段支持勾选，建议合同总金额的变更项，就不展示给客户了（存在履约中变更的场景）",
         solution="客户经理取消合同总金额的展示勾选，不在变更协议中展示合同总金额",
         need_flow="", plan_date="", sa="秦新"),
    dict(no=24, cat="电子协议", biz="人工智能产品协议资费不一致", system="电子协议系统/CRM系统",
         name="人工智能产品协议资费与系统不一致",
         desc="客户经理协议起草时产品资费填写5000/6000元不等，但系统里默认产品资费的单价为1000元，与协议不符，造成沟通困难。",
         expect="协议起草时资费价格应与系统可实现价格一致，确保协议与系统侧一致，避免歧义与业务差错。",
         biz_owner="徐煜", di_owner="谢张", adopt="是",
         assess="现在协议资费填写是通过审批阈值来控制，没有在协议系统里做取值限制",
         solution="电子协议资费填写控制与crm保持一致", need_flow="", plan_date="", sa="秦新/吴雨霜"),
    dict(no=25, cat="电子协议", biz="易甩办订单协议线上签字", system="电子协议系统",
         name="易甩办订单协议线上签字问题",
         desc="通过易甩办起草电子协议，经经办人线上签名或法人线上签名授权流转，甲方签章仅首页显示，其他需签字盖章页面未同步，影响协议完整性。",
         expect="在协议模板中预设所有页面的签章占位符，签署时系统自动将电子签章同步至各指定位置。",
         biz_owner="方舟", di_owner="陈大海", adopt="优化中",
         assess="当前是因为反诈承诺书只有一套版本，用来做客户线下盖章，客户签名无法自动带入；",
         solution="业务部门已提单改造，做两套协议模板，签字版本和盖章版本",
         need_flow="", plan_date="", sa="秦新"),
    dict(no=26, cat="其他优化", biz="集团客户关联功能", system="CRM系统",
         name="集团客户关联功能（增加检索条件）",
         desc="在ICT集团客户注册流程中，关联母集团时仅支持通过母集团名称模糊搜索。因集团名称可能存在重名、记忆偏差或录入不规范，导致检索效率低且易选错。",
         expect="在搜索条件中新增集团编号字段，支持精确匹配检索，提升操作准确性与效率。",
         biz_owner="孔婷", di_owner="杨帆", adopt="建议采纳", assess="可以支撑",
         solution="母集团选择支持根据集团省内编码进行搜索查询", need_flow="", plan_date="", sa=""),
    dict(no=27, cat="其他优化", biz="移动云新增业务生效时间", system="电子协议系统",
         name="移动云新增业务生效时间问题",
         desc="客户经理与客户约定次月生效（如月底签约次月1日起计费），但当前系统仅支持立即生效，导致必须违背协议约定或被迫修改协议条款，影响客户感知。",
         expect="新增次月生效或指定生效日期选项，支持客户经理根据协议约定灵活选择。",
         biz_owner="方舟", di_owner="陈大海", adopt="建议采纳", assess="可以支撑",
         solution="业务部门确认后it改造", need_flow="", plan_date="", sa="秦新"),
    dict(no=28, cat="其他优化", biz="集团商品购物车", system="CRM系统",
         name="集团商品购物车默认筛选问题",
         desc="集团商品购物车查询界面中，仅查我的筛选条件默认为勾选状态，导致每次进入页面或刷新后，系统仅展示当前操作人本人添加的商品。",
         expect="取消仅查我的默认勾选，默认展示当前有权限查看的全部集团商品。",
         biz_owner="李能禾", di_owner="陈大海", adopt="优化中",
         assess="基于菜单+角色的组合判断，个性化放开这个默认选择配置。",
         solution="修改集团商品购物车菜单的仅查我的选项，默认去勾选，政企甩办一体和商客专区一键订购保持勾选。",
         need_flow="敏捷需求（2026）第（090700429）号", plan_date="", sa="黄长春"),
    dict(no=29, cat="其他优化", biz="集团客户资料批量业务监控", system="CRM系统",
         name="集团客户资料批量业务监控导出上限",
         desc="批量业务监控中导出失败记录设置了条数上限（如最多5000条），当单次批量任务失败记录总数超过上限时，用户无法一次性完整导出全部失败数据。",
         expect="1.取消导出条数上限；2.对超大数据量采用异步导出模式，后台生成文件后通过系统消息或邮件通知下载。",
         biz_owner="李能禾", di_owner="杨帆", adopt="优化中", assess="可以支撑",
         solution="修改集团客户资料批量业务监控的导出数量限制，放开5000条最大上限，在超过5000条时，提示跳转后台任务结果查询菜单下载导出结果。新增集团客户资料异步导出任务查询界面，支持查询异步任务执行进展和结果，并支持下载导出文件。",
         need_flow="敏捷需求（2026）第（090700429）号", plan_date="", sa="黄长春"),
    dict(no=30, cat="其他优化", biz="批量修改商客联系人信息", system="CRM系统",
         name="批量修改商客联系人信息字段缺失",
         desc="部分商客集团需完善联系人信息（添加有效商客联系人），但集团客户资料批量业务菜单中缺少相应字段，员工只能通过集团客户资料菜单逐个手动完善。",
         expect="在集团客户资料批量业务菜单中新增商客联系人字段，支持批量完善集团资料信息。",
         biz_owner="童振彦", di_owner="杨帆", adopt="建议采纳", assess="可以支撑",
         solution="业务部门确认后it改造", need_flow="", plan_date="", sa=""),
    dict(no=31, cat="其他优化", biz="跨集团业务受理提醒前置", system="CRM系统",
         name="跨集团业务受理提醒前置",
         desc="已办理过跨集团过户的集团，业务规则不能再办理其他业务，此类集团无显著提醒，往往在业务受理到最后一步提交时才会报错。",
         expect="报错提醒前置，在业务发起时就提醒报错。",
         biz_owner="杨凯", di_owner="陈大海", adopt="建议采纳",
         assess="前期已通杨凯专题讨论，解决方案已定，待走需求流程启动开发",
         solution="优化当前跨集团过户的操作规则，取消对老集团后续继续办理商客业务的校验规则限制",
         need_flow="待提需求流程", plan_date="", sa=""),
    dict(no=32, cat="其他优化", biz="人工智能产品系统填写要求与协议不一致", system="电子协议系统/CRM系统",
         name="人工智能产品系统侧填写要求与协议不一致",
         desc="（1）AI智能体系统必须填客户联系人姓名和电话，当前协议中未体现，需单单沟通客户经理增加沟通成本；（2）多账号要求时需导入对应数量姓名/服务号码，增加操作步骤。",
         expect="（1）同步协议及受理侧需求，在电子协议起草时即要求客户经理准确填写并提取至订单；（2）非业务规则必须的建议取消，必要信息从电子协议起草时管控填写。",
         biz_owner="徐煜", di_owner="谢张", adopt="建议采纳", assess="可以支撑",
         solution="业务部门确认后it改造", need_flow="待提需求流程", plan_date="", sa="秦新"),
    dict(no=33, cat="其他优化", biz="省内云安全重保服务生效时间", system="电子协议系统/CRM系统",
         name="省内云安全重保服务生效时间问题",
         desc="业务规则限制省内云安全重保服务仅能办理立即生效，但协议起草不同步，可勾选次月生效。",
         expect="建议协议与业务实际办理情况同步，仅能勾选立即方式。",
         biz_owner="方舟", di_owner="陈大海", adopt="建议采纳", assess="可以支撑",
         solution="业务部门确认后it改造", need_flow="", plan_date="", sa="秦新"),
    dict(no=34, cat="其他优化", biz="集团主联系人/工商状态异常/高风险集团", system="CRM系统",
         name="缺少集团主联系人/工商状态为注销/高风险集团",
         desc="因集团主联系人缺失、工商状态异常或高风险标识，导致业务受理时需联系客户经理反复沟通补录，影响效率。",
         expect="在订单提交前增加集团状态预校验，异常时自动拦截并提示补录或变更路径。",
         biz_owner="方舟", di_owner="杨帆", adopt="部分解决",
         assess="已解决：\n集团状态预校验功能目前已经具备\n\n待优化：\n1、按一线建议，在合同起草环节，增加业务校验规则，如果集团确实主联系人，则校验报错（建议针对指定业务合同）；\n2、支持电子协议系统直接维护目标集团的主联系人信息。",
         solution="明确具体业务场景，以及需要提示的规则。业务部门确认后it改造",
         need_flow="", plan_date="", sa="秦新、黄长春"),
    dict(no=35, cat="其他优化", biz="集团账户付费类型/缴费期变更", system="电子协议系统/CRM系统",
         name="集团账户付费类型/缴费期变更结果跟踪",
         desc="受理人员执行订单通过操作后，后续账号情况是否变更成功无法即刻关注到。此单因集团欠费未变更成功，引发客户经理投诉。",
         expect="在协议起草提交前增加集团欠费等关键状态预校验；变更操作完成后自动推送变更结果通知给客户经理。",
         biz_owner="方舟", di_owner="陈大海", adopt="已解决",
         assess="1，当前协议起草界面已经有欠费提醒和校验；\n2，订单提交，增加了账户变更是否成功的结果同志",
         solution="已解决", need_flow="", plan_date="", sa="秦新/张茜"),
    dict(no=36, cat="其他优化", biz="稽核失败原因说明", system="订单中心系统",
         name="增加稽核失败原因说明",
         desc="订单中心导出的订单明细中，对于稽核失败或支撑人员补录状态的订单，无法直接定位问题，需通过订单编码逐单查询并进入相应环节方可查看具体原因。",
         expect="在导出明细中增加稽核失败原因列，以便快速核实凭证或业务差错。",
         biz_owner="李能禾", di_owner="陈大海", adopt="优化中", assess="可以支撑",
         solution="优化在导出明细中增加“稽核失败原因”字段，便于快速定位问题、核实凭证或业务差错。",
         need_flow="敏捷需求（2026）第（090700429）号", plan_date="", sa="陈山"),
    dict(no=37, cat="其他优化", biz="购物车关联账户问题", system="CRM系统",
         name="购物车关联账户问题",
         desc="（1）同一集团不同合同不同业务的订单关联账户全是同一个名字，不符合各地市建账户要求；（2）购物车建出的账户与协议缴费期不符，提交时报错。",
         expect="按业务类型-建立日期-个性化标识生成唯一账户名称，确保每笔订单独立建户，并同步校验协议缴费期。",
         biz_owner="方舟", di_owner="", adopt="待业务部门评估",
         assess="目前共用账户是新建的账户名称，如果需要按照业务需要考虑多业务场景下以那个业务名称为准",
         solution="", need_flow="", plan_date="", sa=""),
]

# ---------------------------------------------------------------- 10 月（19 条）
HUAIAN_2610 = [
    dict(no=1, batch="第一批(9月)", belong="大数据产品-和洞察", system="电子协议系统/CRM系统",
         name="定制化开发科目协议与购物车数据不一致",
         desc="购物车显示议价后单价1570元/套、数量6套、总价9420元；协议首页仅显示总金额，详情页显示资费9420元数量1，缺少单价和套数",
         expect="协议内容与购物车数据同步，合同直接引用购物车明细字段(单价、数量、合计总价)，确保总价=单价x数量",
         case="订单62026081899999135951, 合同HT20260818092144001",
         result="采纳（谢张）", next_step="业务评估安排", remark=""),
    dict(no=2, batch="第一批(9月)", belong="专线卫士", system="电子协议系统/OA审批系统/订单中心系统",
         name="资费审批阈值表未同步至订单中心",
         desc="专线卫士新增资费审批要求，但阈值表尚未同步至订单中心，无法判断是否需要审批及对应层级",
         expect="将最新的资费审批阈值表同步至订单中心，明确审批规则(套餐包、产品型号、办理年限)，各系统统一标准",
         case="", result="采纳（陈大海）", next_step="修复页面展示", remark="枚举值转译"),
    dict(no=3, batch="第一批(9月)", belong="专线卫士", system="电子协议系统/OA审批系统",
         name='资费审批单"总资费"字段显示0元',
         desc='电子协议生成的专线卫士资费审批单上"总资费"字段显示为0元，而实际协议已约定资费金额',
         expect='审批单"总资费"应从协议读取正确资费，禁止默认填充0或空值',
         case="订单62026082111200316036, 合同HT20260818173711001",
         result="采纳（陈大海）", next_step="修复同步生产运营平台参数信息", remark="信息组装策略调整解决问题"),
    dict(no=4, batch="第一批(9月)", belong="专线卫士", system="电子协议系统/订单中心系统",
         name="协议未带出设备类型、转发能力字段，缺少必填校验",
         desc="协议详情中未带出设备类型及转发能力字段，客户经理漏选设备类型时系统无强制校验，允许直接提交转单",
         expect="电子协议中将设备类型设为必填项(红色*号)，提交时非空校验；或在转单入口增加二次校验",
         case="订单62026082711390498219, 合同HT20260827180427301",
         result="采纳（陈大海）", next_step="优化中", remark="已有优化安排，近期上线"),
    dict(no=5, batch="第一批(9月)", belong="集团V网", system="CRM系统",
         name="批量添加入口不支持外地网内号码",
         desc='批量添加V网成员仅支持"本地网内号码"，无法选"外地网内号码"；单个新增入口支持手动选择外地号码',
         expect="将单个新增入口中外地号码选择能力同步扩展至批量添加功能",
         case="订单编码62026082819123508307", result="采纳（杨帆）", next_step="业务评估安排", remark=""),
    dict(no=6, batch="第一批(9月)", belong="互联网电视-新", system="CRM系统",
         name="批量办理仅生成单个产品编码，无法独立销户",
         desc="批量办理仅生成一个产品编码，销户时只能全量销户，无法针对单个用户或产品独立销户",
         expect="统一批量与单个办理底层能力，批量办理时也生成独立编码，支持逐个销户",
         case="", result="待定", next_step="", remark="待业务管理员评估安排"),
    dict(no=7, batch="第一批(9月)", belong="RPA流程", system="磐匠系统",
         name="RPA销户仅支持立即生效，不支持次月失效",
         desc="RPA一网通销户仅支持立即生效，无法选次月失效；模板虽支撑次月选项但实际销户失败",
         expect="修复次月销户底层执行逻辑，使实际执行能力与模板选项一致",
         case="", result="不采纳", next_step="", remark=""),
    dict(no=8, batch="第一批(9月)", belong="订单流转", system="集客订单中心系统",
         name="挂起订单非本人可解挂问题",
         desc="员工挂起的订单，客户经理可自行解挂非本人挂起的订单，可能导致跳过核查等环节造成差错",
         expect="关闭非本人挂起订单的解挂权限，仅挂起人本人可操作；授权组长接管权限",
         case="订单编号62026032418140159491", result="采纳（陈大海）",
         next_step="订单中心专题分析，输出分析报告和后续解决方案", remark=""),
    dict(no=9, batch="第一批(9月)", belong="大额出账业务", system="集客订单中心系统/CRM系统/集客大厅系统",
         name="大额出账系统刚性复核流程缺失",
         desc="大额出账订单缺乏系统级强制复核，未设置班组长二次复核刚性拦截，风险依赖人工自觉",
         expect='建立"员工提交--订单中心组长复核--地市审核--省公司审批"闭环；阈值金额可后台自主配置',
         case="", result="待定", next_step="", remark="待业务管理员评估安排"),
    dict(no=10, batch="第一批(9月)", belong="批量业务(集团菜单)", system="CRM系统",
         name="集团业务菜单展示页面及搜索问题",
         desc="批量业务选择界面展示区域偏小，业务名称显示不全，查找效率低、易误选",
         expect="扩大展示区域，增加关键词搜索功能，支持按关键词过滤快速定位目标功能",
         case="", result="采纳（陈大海）", next_step="业务评估安排", remark=""),
    dict(no=11, batch="第一批(9月)", belong="批量业务(一网通复机)", system="CRM系统",
         name="一网通批量复机仅支持全量复机",
         desc="对同一账户编码下的停机产品复机时，默认全量复机(含欠费停机)，不支持选择性办理",
         expect="参考专线业务批量复机，通过集团编码及产品编码锁定需复机的具体产品，提交前进行状态校验",
         case="", result="不采纳", next_step="", remark=""),
    dict(no=12, batch="第一批(9月)", belong="MPLS-VPN专线业务", system="电子协议系统/OA审批系统",
         name="购物车订单协议及资费审批单信息展示不准确",
         desc="协议首页无合同总金额；资费审批单中网络使用费未按条数合计计算，总金额缺失",
         expect="统一购物车订单与普通订单协议首页总金额及资费审批表中产品条数、资费、协议期等关键信息的计算与展示",
         case="购物车订单62026091599999349207", result="采纳（帅敏）", next_step="业务评估安排", remark=""),
    dict(no=13, batch="第二批(10月)", belong="一网通多地址发单(宽带选址)", system="CRM系统",
         name="多小区选址已选地址错漏无法即时修正",
         desc="勾选多条地址后返回属性填写界面，发现地址错漏只能重新全量选址，操作重复效率低",
         expect='增加"修正地址"入口，支持删除错误地址或重新选择，确认返回仅更新对应地址，其他信息不变',
         case="", result="不采纳", next_step="", remark="不要用gims选址页面，用crm只有标准选址能力"),
    dict(no=14, batch="第二批(10月)", belong="一网通多地址发单(宽带开户)", system="CRM系统",
         name="多条宽带无法分别新建独立账户并逐条关联",
         desc='"是否产生新账户"选"是"仅能新建一个账户，多条宽带默认关联至同一账户，无法按条新建对应账户',
         expect="参考企业版批量开户逻辑：支持按宽带条数自动新建同等数量账户并逐条关联；或关联已有账户两种模式",
         case="", result="采纳（陈大海）", next_step="已有需求安排", remark="支持地址组详情下末级地址对象的个性化选择删除能力"),
    dict(no=15, batch="第二批(10月)", belong="集中化人员角色配置", system="集客订单中心系统",
         name="临时人员调配无批量入口，大屏人数统计不准确",
         desc="临时调动只能逐个工号配置，操作重复耗时；大屏按工号统计人数，同员工多工号被重复计数",
         expect="增加批量配置入口；以4A账号/手机号作为唯一标识统计人数，不再按工号数量统计",
         case="", result="不采纳", next_step="", remark=""),
    dict(no=16, batch="第二批(10月)", belong="购物车订单转单(协议转单)", system="电子协议系统/集客订单中心系统",
         name="协议转单环节无法带出笔记及基础信息",
         desc="协议盖章上传后，转单环节无法带出协议基础信息，也无法添加备注或特殊要求",
         expect='协议转单时增加"转单备注"栏，自动抓取协议信息及备注，支持补充特殊要求随单流转',
         case="", result="不采纳", next_step="", remark=""),
    dict(no=17, batch="第二批(10月)", belong="统付营销案办理", system="CRM系统",
         name='"充值方式"字段非必填且有默认值',
         desc='"充值方式"非必填、默认选中"直接充值"，受理人员未修改即按默认提交，与实际营销案要求不一致',
         expect="后台已配置则受理侧只读展示；需手动选择则设为必填、取消默认值、提交前强校验",
         case="", result="采纳（谢张）", next_step="业务评估安排", remark="改默认值方案"),
    dict(no=18, batch="第二批(10月)", belong="出账计费科目办理", system="CRM系统",
         name="数量字段无强校验，金额易误填进数量栏",
         desc="受理人员将金额37240误填入数量栏(正确数量应为28)，系统无校验导致订单总额放大1330倍",
         expect="数量字段设为正整数强校验；设数量上限与阈值提醒；实时展示总金额=单价x数量；智能体校验",
         case="订单编码62026092813195731886", result="采纳（谢张）", next_step="业务评估安排", remark=""),
    dict(no=19, batch="第二批(10月)", belong="业务产品包订购选择", system="CRM系统",
         name="同类不同资费套餐列表排序无序",
         desc="同类套餐存在多个资费档次，名称接近、金额尾数差异小，列表无固定排序导致容易误选",
         expect="默认按金额升序排列，金额相同时按套餐名称/产品编码/业务条数次级排序",
         case="", result="不采纳", next_step="", remark=""),
]


def status_from_result_10(result: str) -> str:
    """10 月「评审结果」→ 工单状态（老大确认口径）。"""
    r = (result or "").strip()
    if r == "不采纳":
        return "closed"
    if r.startswith("采纳"):
        return "pending"
    return "pending"  # 待定 / 空白


def build_2608() -> list[dict]:
    rows = []
    for r in HUAIAN_2608:
        status = STATUS_MAP_8.get((r["adopt"] or "").strip(), "pending")
        basic = [
            "调研批次：淮安订单中心 8 月调研",
            f"大类：{r['cat']}",
            f"业务类别：{r['biz']}",
            f"系统名称：{r['system']}",
            f"是否需要流程：{r['need_flow'] or '—'}",
            f"预计解决日期：{r['plan_date'] or '—'}",
            f"牵头SA：{r['sa'] or '—'}",
        ]
        rows.append({
            "issue_no": f"RES-HA2608-{r['no']:02d}",
            "title": r["name"] or r["biz"],
            "sub_type": SUB_TYPE,
            "status": status,
            "city": CITY,
            "basic_info": "\n".join(basic),
            "situation_desc": r["desc"] or r["expect"] or r["name"],
            "city_suggestion": r["expect"] or None,
            "feedback_name": r["biz_owner"] or None,
            "vendor_handlers": r["di_owner"] or None,
            "business_admin": None,
            "assessment_result": r["assess"] or None,
            "solution": r["solution"] or None,
            "source": SOURCE_2608,
            "remark": None,
            "impact_level": "P2",
        })
    return rows


def build_2610() -> list[dict]:
    rows = []
    for r in HUAIAN_2610:
        status = status_from_result_10(r["result"])
        basic = [
            "调研批次：淮安订单中心 10 月调研",
            f"批号：{r['batch']}",
            f"业务归属：{r['belong']}",
            f"涉及系统：{r['system']}",
        ]
        reviewer = ""
        if "（" in r["result"]:
            reviewer = r["result"].split("（", 1)[1].rstrip("）")
        remark_parts = []
        if r["case"]:
            remark_parts.append(f"参考案例/订单：{r['case']}")
        if reviewer:
            remark_parts.append(f"评审人：{reviewer}")
        if r["remark"]:
            remark_parts.append(f"备注：{r['remark']}")
        rows.append({
            "issue_no": f"RES-HA2610-{r['no']:02d}",
            "title": r["name"],
            "sub_type": SUB_TYPE,
            "status": status,
            "city": CITY,
            "basic_info": "\n".join(basic),
            "situation_desc": r["desc"],
            "city_suggestion": r["expect"] or None,
            "feedback_name": None,
            "vendor_handlers": None,
            "business_admin": None,
            "assessment_result": r["result"] or None,
            "solution": r["next_step"] or None,
            "source": SOURCE_2610,
            "remark": "\n".join(remark_parts) or None,
            "impact_level": "P2",
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只打印不写库")
    ap.add_argument("--force", action="store_true", help="已存在的 issue_no 覆盖更新")
    args = ap.parse_args()

    payload = build_2608() + build_2610()
    print(f"[plan] 共 {len(payload)} 条：8月 {len(HUAIAN_2608)} + 10月 {len(HUAIAN_2610)}")

    if args.dry_run:
        for p in payload:
            print(f"  {p['issue_no']} | {p['status']:10s} | {p['title'][:40]}")
        return

    db = SessionLocal()
    created = updated = skipped = 0
    try:
        for p in payload:
            exists = db.query(PmwbResearchIssue).filter(
                PmwbResearchIssue.issue_no == p["issue_no"]
            ).first()
            if exists:
                if not args.force:
                    skipped += 1
                    continue
                for k, v in p.items():
                    setattr(exists, k, v)
                updated += 1
            else:
                db.add(PmwbResearchIssue(**p))
                created += 1
        db.commit()
    finally:
        db.close()
    print(f"[done] created={created} updated={updated} skipped={skipped}")


if __name__ == "__main__":
    main()
