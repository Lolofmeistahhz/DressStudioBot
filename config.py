from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str
    API_BASE_URL: str = "http://127.0.0.1:8000/api/v1"
    WEBAPP_URL: str

    class Config:
        env_file = ".env"


settings = Settings()