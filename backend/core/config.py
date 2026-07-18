from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "产品经理个人工作台"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    SECRET_KEY: str = "your-secret-key-change-in-production"

    # Database
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "123456"
    DB_NAME: str = "yxtyg_db"
    DB_CHARSET: str = "utf8mb4"
    DATABASE_URL: str = ""

    EMAIL_CENTER_URL: str = "http://localhost:3210"
    OBSIDIAN_VAULT_PATH: str = "D:\\项目\\知识图谱"

    # 需求交付：附件 / 分析说明书 归档目录（基于 Obsidian vault 派生）
    REQUIREMENT_ATTACHMENT_DIR: str = "业务建设\\需求附件"
    REQUIREMENT_DOC_DIR: str = "业务建设\\需求分析说明书"
    REQUIREMENT_DOC_TEMPLATE: str = str(
        Path(__file__).resolve().parent.parent / "templates" / "需求分析说明书.docx"
    )

    # 产品圣经：业务大类 -> Obsidian vault 内相对路径（新增业务只需加一项）
    PRODUCT_BIBLE: list = [
        {
            "key": "group-sms",
            "name": "集团短信业务",
            "path": "01-业务知识/政企业务知识库/集团短信业务/集团短信产品业务知识.md",
        },
        {
            "key": "e-contract",
            "name": "电子协议",
            "format": "docx",
            "path": "06-附件/电子协议支撑服务能力白皮书V0.1.docx",
        },
    ]

    # 运营工单关联的知识笔记路径（Obsidian vault 内相对目录，已被重构整理）
    OPERATION_NOTE_FOLDERS: list = [
        "11-业务运营",
        "01-业务知识/政企业务知识库",
    ]

    BACKEND_HOST: str = "127.0.0.1"
    BACKEND_PORT: int = 8000

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
                f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
                f"?charset={self.DB_CHARSET}"
            )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
