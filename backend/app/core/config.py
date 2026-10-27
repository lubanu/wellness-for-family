import os
from pathlib import Path

class Settings:
    PROJECT_NAME: str = "WelFamily API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    
    # Path to master catalog
    BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
    CATALOG_PATH = os.getenv("CATALOG_PATH", str(BASE_DIR / "data" / "welfare_catalog.json"))
    SYNC_PATH = os.getenv("SYNC_PATH", str(BASE_DIR / "data" / "latest_sync.json"))
    REGIONS_PATH = os.getenv("REGIONS_PATH", str(BASE_DIR / "data" / "regions.json"))
    
    # CORS
    BACKEND_CORS_ORIGINS: list = ["*"]
    
    # Care+ Subscription Pricing (KRW)
    CARE_PLUS_MONTHLY_PRICE: int = 3900
    CARE_PLUS_ANNUAL_PRICE: int = 39000

settings = Settings()
