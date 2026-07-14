import re


def validate_phone(phone: str) -> bool:
    return bool(re.match(r"^1[3-9]\d{9}$", phone))


def validate_email(email: str) -> bool:
    return bool(re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email))


# 严格邮箱校验：本地名仅允许 ASCII 字符，拒绝中文等非 ASCII 本地名
# （如「吴雨霜@chinamobile.com」会被判为非法，避免被邮件中心以 500 拒收）。
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def validate_email_strict(email: str) -> bool:
    """校验邮箱是否合法且本地名为 ASCII（可用于真实发信）。"""
    if not email or not isinstance(email, str):
        return False
    return bool(_EMAIL_RE.match(email.strip()))


def split_and_validate_emails(raw: str):
    """将逗号/分号/空格分隔的邮箱串拆分，返回 (valid_list, invalid_list)。

    invalid_list 为无法解析为合法邮箱的原始片段（已 strip）。
    """
    if not raw:
        return [], []
    parts = [p.strip() for p in re.split(r"[,;，；\s]+", raw) if p.strip()]
    valid = [p for p in parts if validate_email_strict(p)]
    invalid = [p for p in parts if not validate_email_strict(p)]
    return valid, invalid


def validate_required(value) -> bool:
    return value is not None and str(value).strip() != ""
