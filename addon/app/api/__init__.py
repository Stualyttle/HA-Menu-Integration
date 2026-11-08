"""HTTP routers for the add-on API (Phase 2, owner A)."""

from fastapi import APIRouter

from app.api.categories import router as categories_router
from app.api.io import router as io_router
from app.api.items import router as items_router
from app.api.menu import router as menu_router
from app.api.nutrition import router as nutrition_router
from app.api.rules import router as rules_router
from app.api.rules_check import router as rules_check_router
from app.api.settings import router as settings_router
from app.api.stock import router as stock_router
from app.api.sync import router as sync_router
from app.api.warnings import router as warnings_router

DATA_ROUTERS: tuple[APIRouter, ...] = (
    items_router,
    categories_router,
    rules_router,
    rules_check_router,
    stock_router,
    settings_router,
    warnings_router,
    menu_router,
    sync_router,
    nutrition_router,
    io_router,
)
