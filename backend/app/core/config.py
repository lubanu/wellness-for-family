import os
from pathlib import Path

class Settings:
    PROJECT_NAME: str = "WelFamily API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    
    # Path to master catalog
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent
    CATALOG_PATH: str = os.getenv("CATALOG_PATH", str(BASE_DIR / "data" / "welfare_catalog.json"))
    SYNC_PATH: str = os.getenv("SYNC_PATH", str(BASE_DIR / "data" / "latest_sync.json"))
    REGIONS_PATH: str = os.getenv("REGIONS_PATH", str(BASE_DIR / "data" / "regions.json"))
    CHANGELOGS_DIR: str = os.getenv("CHANGELOGS_DIR", str(BASE_DIR / "data" / "changelogs"))
    STAGING_PATH: str = os.getenv("STAGING_PATH", str(BASE_DIR / "data" / "local_staging_queue.json"))
    QUARANTINE_PATH: str = os.getenv("QUARANTINE_PATH", str(BASE_DIR / "data" / "quarantine_records.json"))
    
    # CORS: this API is local-only. Other websites must not be able to call it.
    BACKEND_CORS_ORIGINS: list = ["http://127.0.0.1:8000", "http://localhost:8000"]
    
    # Care+ Subscription Pricing (KRW)
    CARE_PLUS_MONTHLY_PRICE: int = 3900
    CARE_PLUS_ANNUAL_PRICE: int = 39000

settings = Settings()
