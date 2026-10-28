from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from datetime import datetime
import os
import json

from app.core.config import settings
from app.api.v1.api import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="대한민국 맞춤형 복지 큐레이션 및 복지 케어 플러스(Care+) 수익화 백엔드 엔진",
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS for GitHub Pages, local development, and external partner widgets
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

# Mount prototype and data static directories for local all-in-one preview
prototype_dir = settings.BASE_DIR / "prototype"
data_dir = settings.BASE_DIR / "data"

if prototype_dir.exists():
    app.mount("/prototype", StaticFiles(directory=str(prototype_dir), html=True), name="prototype")

if data_dir.exists():
    app.mount("/data", StaticFiles(directory=str(data_dir)), name="data")

@app.get("/")
def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "ONLINE",
        "web_app_url": "/prototype/index.html",
        "admin_url": "/prototype/admin.html",
        "widget_url": "/prototype/widget.html",
        "docs_url": "/docs",
        "description": "정부·지자체 맞춤 복지 진단 & 고수익 제휴·Care+ 구독 플랫폼 API"
    }

@app.get("/health")
def health_check():
    catalog_count = 0
    if os.path.exists(settings.CATALOG_PATH):
        try:
            with open(settings.CATALOG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                catalog_count = len(data.get("policies", []))
        except Exception:
            catalog_count = -1

    return {
        "status": "HEALTHY",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "catalog_policies_count": catalog_count,
        "environment": "production" if not settings.DEBUG else "development"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
