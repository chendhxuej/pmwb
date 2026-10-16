"""工作量分析路由。

独立 router（prefix=/workload-analysis）而非挂在 routers/requirement.py 下，
是为了彻底规避该文件的路由顺序坑：`GET /requirements/{req_id}` 会吃掉同级路径。
"""
import io
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.response import success
from db.base import get_db
from services.workload_analysis import workload_analysis_service

router = APIRouter(prefix="/workload-analysis", tags=["工作量分析"])


@router.get("/stats")
def get_workload_stats(
    month_from: Optional[str] = Query(None, description="起始月 YYYY-MM"),
    month_to: Optional[str] = Query(None, description="结束月 YYYY-MM"),
    sa: Optional[str] = Query(None, description="SA 负责人（模糊）"),
    system_name: Optional[str] = Query(None, description="负责系统（模糊）"),
    req_keyword: Optional[str] = Query(None, description="需求文号/名称关键字"),
    include_zero: bool = Query(True, description="是否统计 0 人天（False=仅统计 >0）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """工作量统计（按月 / 按 SA / 按系统）。

    统计的**单一数据源**：汇总卡、趋势图、分桶表全部取本接口，前端禁止自己算。

    未传 month_from/month_to 时，区间锚定 `data_range`（全库有 dev 记录的起止月），
    避免默认"近 12 个月"而数据稀疏导致趋势图大面积空月。
    """
    data = workload_analysis_service.get_workload_stats(
        db=db,
        month_from=month_from,
        month_to=month_to,
        sa=sa,
        system_name=system_name,
        req_keyword=req_keyword,
        include_zero=include_zero,
        page=page,
        page_size=page_size,
    )
    return success(data=data)


@router.get("/export")
def export_workload_stats(
    month_from: Optional[str] = Query(None),
    month_to: Optional[str] = Query(None),
    sa: Optional[str] = Query(None),
    system_name: Optional[str] = Query(None),
    req_keyword: Optional[str] = Query(None),
    include_zero: bool = Query(True),
    db: Session = Depends(get_db),
):
    """导出工作量明细为 Excel（全量，不分页）。"""
    data = workload_analysis_service.get_workload_stats(
        db=db,
        month_from=month_from,
        month_to=month_to,
        sa=sa,
        system_name=system_name,
        req_keyword=req_keyword,
        include_zero=include_zero,
        page=1,
        page_size=100000,
    )
    buf = _build_xlsx(data)
    fname = f"工作量分析_{data['range']['month_from']}_{data['range']['month_to']}.xlsx"
    disp = f"attachment; filename=\"workload.xlsx\"; filename*=UTF-8''{quote(fname)}"
    return StreamingResponse(
        io.BytesIO(buf),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": disp},
    )


def _build_xlsx(data: dict) -> bytes:
    """组装 Excel：需求明细 + 按 SA 汇总 + 月度分布 三个 sheet。"""
    import openpyxl
    from openpyxl.styles import Font

    wb = openpyxl.Workbook()

    def fill(ws, headers, rows):
        ws.append(headers)
        for c in ws[1]:
            c.font = Font(bold=True)
        for r in rows:
            ws.append(r)
        for col in ws.columns:
            width = max((len(str(c.value)) for c in col if c.value is not None), default=8)
            ws.column_dimensions[col[0].column_letter].width = min(max(width + 2, 10), 46)

    ws1 = wb.active
    ws1.title = "需求明细"
    fill(
        ws1,
        ["需求文号", "需求名称", "归月", "启动开发时间", "时间来源", "SA 负责人", "系统", "工作量(人天)", "状态"],
        [
            [
                r["req_id"], r["req_name"], r["month"], r["entered_at"] or "",
                r["stage_source"], "、".join(r["sa_names"]), "、".join(r["systems"]),
                r["workload"], r["workload_state"],
            ]
            for r in data["requirements"]["items"]
        ],
    )

    ws2 = wb.create_sheet("按SA汇总")
    fill(
        ws2,
        ["SA 负责人", "需求数", "工作量(人天)"],
        [[x["name"], x["req_count"], x["workload"]] for x in data["by_sa"]],
    )

    ws3 = wb.create_sheet("月度分布")
    fill(
        ws3,
        ["月份", "需求数", "工作量(人天)"],
        [[m["month"], m["req_count"], m["workload"]] for m in data["months"]],
    )

    if data["unmonth"]:
        ws4 = wb.create_sheet("未归月需求")
        fill(
            ws4,
            ["需求文号", "需求名称", "工作量(人天)", "SA 负责人", "原因"],
            [
                [
                    u["req_id"], u["req_name"], u["workload"], "、".join(u["sa_names"]),
                    "无启动开发环节记录" if u["reason"] == "no_dev_stage" else "启动开发时间为空",
                ]
                for u in data["unmonth"]
            ],
        )

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
