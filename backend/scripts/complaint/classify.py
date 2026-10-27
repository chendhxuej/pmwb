"""客诉分类引擎（薄封装）—— 真实实现见 services/complaint/classify.py。"""

from services.complaint.classify import (  # noqa: F401
    Dictionary,
    Rule,
    UNCLASSIFIED,
    clear_cache,
    load_dictionary,
)
