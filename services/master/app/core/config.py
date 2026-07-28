"""Master service 配置。"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MASTER_PORT: int = 8001

    # Database — 默认指向宿主机 MySQL 的 pmwb_master schema
    MASTER_DB_HOST: str = "host.docker.internal"
    MASTER_DB_PORT: int = 3306
    MASTER_DB_USER: str = "root"
    MASTER_DB_PASSWORD: str
    MASTER_DB_NAME: str = "pmwb_master"
    MASTER_DB_CHARSET: str = "utf8mb4"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.MASTER_DB_USER}:{self.MASTER_DB_PASSWORD}"
            f"@{self.MASTER_DB_HOST}:{self.MASTER_DB_PORT}/{self.MASTER_DB_NAME}"
            f"?charset={self.MASTER_DB_CHARSET}"
        )

    class Config:
        env_file = r"D:\项目\个人工作台系统\services\master\.env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
