class PMWBException(Exception):
    """业务异常基类。"""

    def __init__(self, message: str, code: int = 400, status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundException(PMWBException):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(message, code=404, status_code=404)


class ValidationException(PMWBException):
    def __init__(self, message: str = "参数校验失败"):
        super().__init__(message, code=400, status_code=400)


class DuplicateException(PMWBException):
    def __init__(self, message: str = "数据已存在"):
        super().__init__(message, code=409, status_code=409)
