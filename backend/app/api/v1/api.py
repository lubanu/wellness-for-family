from fastapi import APIRouter
from app.api.v1 import policies, matching, affiliate, care_plus, widgets, admin, admin_local

api_router = APIRouter()

api_router.include_router(policies.router, prefix="/policies", tags=["policies"])
api_router.include_router(matching.router, prefix="/matching", tags=["matching"])
api_router.include_router(affiliate.router, prefix="/affiliate", tags=["affiliate"])
api_router.include_router(care_plus.router, prefix="/care-plus", tags=["care-plus"])
api_router.include_router(widgets.router, prefix="/widgets", tags=["widgets"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_local.router, prefix="/admin/local-policies", tags=["admin-local"])
