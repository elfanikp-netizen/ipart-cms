from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent.parent  # scrapper-site/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT_DIR / "backend" / ".env"), extra="ignore")

    data_dir: Path = ROOT_DIR / "data"
    database_url: str = ""
    cors_origins: str = "http://localhost:5173"
    secret_key: str = "change-me-in-.env"

    # Locations of the existing crawler projects
    keystone_dir: Path = Path(r"C:\ELFANI\scrapper-keystone")
    carid_dir: Path = Path(r"C:\ELFANI\scrapper")
    brand_dir: Path = Path(r"C:\ELFANI\scrapper-brand")
    ccc_dir: Path = Path(r"C:\ELFANI\scrapper-ccc")

    def model_post_init(self, __context) -> None:
        if not self.database_url:
            db_path = (self.data_dir / "app.db").as_posix()
            self.database_url = f"sqlite:///{db_path}"


settings = Settings()
