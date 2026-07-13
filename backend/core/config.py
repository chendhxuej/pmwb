from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "产品经理个人工作台"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    SECRET_KEY: str = "your-secret-key-change-in-production"

    DATABASE_URL: str = "mysql+pymysql://username:password@localhost:3306/aicoding"
    EMAIL_CENTER_URL: str = "http://localhost:3210"
    OBSIDIAN_VAULT_PATH: str = "D:\\项目\\知识图谱"

    BACKEND_HOST: str = "127.0.0.1"
    BACKEND_PORT: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
