from fastapi import APIRouter, Request

from app import __version__

router = APIRouter(prefix="/v1", tags=["system"])


@router.get("/meta")
async def meta(request: Request) -> dict:
    """Frontend uchun: brend, modullar, versiya (autentifikatsiyasiz)."""
    cfg = request.app.state.client_config
    return {
        "version": __version__,
        "client": cfg.name,
        "brand": cfg.brand,
        "modules": cfg.enabled_modules,
        "plan": cfg.plan,
        "extension": request.app.state.extension_loaded,
        # Xarita tile manbasi (settings.map.tiles / attribution); bo'lmasa frontend OSM ishlatadi
        "map": cfg.settings.get("map"),
    }
