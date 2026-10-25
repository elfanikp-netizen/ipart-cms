from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

UNIVERSE_ROOT = Path(__file__).resolve().parents[2]
APPS_ROOT = UNIVERSE_ROOT.parent
SCRAPER_BACKEND_ROOT = APPS_ROOT / "scrapper-site" / "backend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(SCRAPER_BACKEND_ROOT / ".env"), extra="ignore")

    database_url: str = ""
    secret_key: str = "change-me-in-.env"
    cookie_secure: bool = False
    data_dir: Path = APPS_ROOT / "scrapper-site" / "data"

    def model_post_init(self, __context) -> None:
        if not self.database_url:
            raise ValueError("Set database_url in scrapper-site/backend/.env to the PostgreSQL ipart database")
        if not self.database_url.startswith(("postgresql://", "postgresql+")):
            raise ValueError("Universe requires PostgreSQL; database_url must use a postgresql driver")


settings = Settings()