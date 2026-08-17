from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "产品经理个人工作台"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    SECRET_KEY: str  # 强制从环境变量/.env 读取，禁止硬编码默认值

    # Database
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str  # 强制从环境变量/.env 读取，禁止硬编码弱密码默认值
    DB_NAME: str = "yxtyg_db"
    DB_CHARSET: str = "utf8mb4"
    DATABASE_URL: str = ""

    EMAIL_CENTER_URL: str = "http://localhost:3210"
    EMAIL_CENTER_API_KEY: str = ""  # 可选，若邮件中心配置了 API_KEY 则填写

    # 邮件统一治理：本人标识（用于会议遗留任务归属分流）+ 默认邮件签名
    SELF_NAME: str = "陈大海"
    EMAIL_SIGNATURE: str = "陈大海\n中国移动通信集团江苏有限公司 · 数智化部\n13901581364"
    # 邮件签名档（v1 仅 default；后续可按 scene 的 signature_key 引用多档，P3 再做管理页）
    EMAIL_SIGNATURE_MAP: dict = {"default": "陈大海\n中国移动通信集团江苏有限公司 · 数智化部\n13901581364"}
    MASTER_SERVICE_URL: str = "http://localhost:8001"
    OBSIDIAN_VAULT_PATH: str = "D:\\项目\\知识图谱"

    # 需求交付：附件 / 分析说明书 归档目录（基于 Obsidian vault 派生）
    REQUIREMENT_ATTACHMENT_DIR: str = "业务建设\\需求附件"
    REQUIREMENT_DOC_DIR: str = "业务建设\\需求分析说明书"

    # 重点工作交付物归档目录（Obsidian vault 内相对目录，落在 08-工作任务 与 10-业务建设 之间）
    KEY_WORK_VAULT_DIR: str = "09-重点工作"
    REQUIREMENT_DOC_TEMPLATE: str = str(
        Path(__file__).resolve().parent.parent / "templates" / "需求分析说明书.docx"
    )

    # 产品圣经：业务大类 -> Obsidian vault 内相对路径（新增业务只需加一项）
    PRODUCT_BIBLE: list = [
        {
            "key": "group-sms",
            "name": "集团短信业务",
            "path": "01-业务知识/政企业务知识库/集团短信/集团短信产品业务知识.md",
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

    # ===== LLM 用户故事智能生成（继承 WorkBuddy models.json 的 Kimi Coding Plan） =====
    # 支持提供商：kimi / ollama / openai / deepseek / 任意 OpenAI 兼容接口
    US_STORY_LLM_ENABLED: bool = False                # 是否启用 LLM 生成
    US_STORY_LLM_PROVIDER: str = "kimi"               # kimi | ollama | openai | deepseek
    US_STORY_LLM_MODEL: str = "kimi-k2.6"             # Kimi Coding Plan 模型
    US_STORY_LLM_BASE_URL: str = "https://api.kimi.com/coding/v1"  # Kimi Coding Plan API
    US_STORY_LLM_API_KEY: str = ""                    # API Key（从 .env 读取）
    US_STORY_LLM_TEMPERATURE: float = 0.3             # 低温度保证合规输出一致性
    US_STORY_LLM_MAX_TOKENS: int = 4096               # 单次生成最大 token
    US_STORY_LLM_TIMEOUT: int = 120                   # 请求超时（秒），kimi-k2.6 带 reasoning 建议≥120

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
