from pydantic import BaseSettings


class Settings(BaseSettings):
    token: str
    api_url: str
    websocket_url: str


settings = Settings()
