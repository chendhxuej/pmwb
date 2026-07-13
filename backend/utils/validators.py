import re


def validate_phone(phone: str) -> bool:
    return bool(re.match(r"^1[3-9]\d{9}$", phone))


def validate_email(email: str) -> bool:
    return bool(re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email))


def validate_required(value) -> bool:
    return value is not None and str(value).strip() != ""
