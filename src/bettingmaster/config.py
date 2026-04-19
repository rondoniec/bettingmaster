from pathlib import Path

from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{DATA_DIR / 'bettingmaster.db'}"
    timezone: str = "Europe/Bratislava"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    enable_scheduler: bool = True
    scrape_interval_tipsport: int = 90
    scrape_interval_tipos: int = 120
    scrape_interval_nike: int = 120
    scrape_interval_fortuna: int = 120
    scrape_interval_doxxbet: int = 180  # Slower — uses headless browser
    scrape_interval_polymarket: int = 300  # Slow — prediction market, updates slowly
    scrape_interval_default: int = 120
    live_feed_poll_seconds: int = 3
    debug_dump: bool = False

    model_config = {"env_prefix": "BM_"}


settings = Settings()
