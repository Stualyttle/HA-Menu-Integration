"""HTTP routers for the add-on API (Phase 2, owner A)."""

from fastapi import APIRouter

from app.api.categories import router as categories_router
from app.api.items import router as items_router
from app.api.rules import router as rules_router
from app.api.settings import router as settings_router
from app.api.stock import router as stock_router
from app.api.warnings import router as warnings_router

DATA_ROUTERS: tuple[APIRouter, ...] = (
    items_router,
    categories_router,
    rules_router,
    stock_router,
    settings_router,
    warnings_router,
)
