from pathlib import Path

from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{DATA_DIR / 'bettingmaster.db'}"
    timezone: str = "Europe/Bratislava"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    auto_upgrade_db_on_startup: bool = True
    enable_scheduler: bool = True
    scrape_interval_tipsport: int = 90
    scrape_interval_tipos: int = 120
    scrape_interval_nike: int = 60
    scrape_interval_fortuna: int = 120
    scrape_interval_doxxbet: int = 180  # Slower — uses headless browser
    scrape_interval_polymarket: int = 120
    on_demand_fortuna_max_age_seconds: int = 120
    on_demand_doxxbet_max_age_seconds: int = 180
    on_demand_nike_max_age_seconds: int = 60
    on_demand_tipos_max_age_seconds: int = 120
    on_demand_tipsport_max_age_seconds: int = 120
    on_demand_polymarket_max_age_seconds: int = 60
    scrape_interval_default: int = 120
    tipsport_proxy_url: str | None = None
    tipsport_browser_channel: str | None = None
    tipsport_headless: bool = True
    tipos_headless: bool = True
    live_feed_poll_seconds: int = 3
    active_league_ids: str = "en-premier-league,es-la-liga"
    active_match_window_hours: int = 48
    active_match_lookback_hours: int = 3
    nike_rate_limit_cooldown_seconds: int = 120
    nike_adaptive_interval_step: int = 5
    nike_gold_spot_streak: int = 5
    debug_dump: bool = False
    football_data_token: str | None = None
    api_football_token: str | None = None
    match_status_sync_interval: int = 300

    model_config = {"env_prefix": "BM_"}


settings = Settings()
