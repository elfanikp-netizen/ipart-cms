from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PORTAL_ROOT = Path(__file__).resolve().parents[2]
APPS_ROOT = PORTAL_ROOT.parent
SCRAPER_BACKEND_ROOT = APPS_ROOT / "scrapper-site" / "backend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(SCRAPER_BACKEND_ROOT / ".env"),
        extra="ignore",
    )

    database_url: str = ""
    database_schema: str = "scrapping"
    secret_key: str = "change-me-in-.env"
    cookie_secure: bool = False
    data_dir: Path = APPS_ROOT / "scrapper-site" / "data"

    def model_post_init(self, __context) -> None:
        if not self.database_url:
            db_path = (self.data_dir / "app.db").as_posix()
            self.database_url = f"sqlite:///{db_path}"


settings = Settings()