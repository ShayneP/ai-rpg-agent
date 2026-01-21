from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Tabletop RPG API"
    database_url: str = "sqlite:///./tabletop_rpg.db"
    debug: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
