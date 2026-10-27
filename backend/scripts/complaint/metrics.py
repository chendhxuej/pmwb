"""客诉周度指标（薄封装）—— 12 项指标唯一实现见 services/complaint/metrics.py。"""

from services.complaint.metrics import (  # noqa: F401
    collect,
    latest_week,
    prev_week,
    recent_weeks,
    week_bounds,
)
