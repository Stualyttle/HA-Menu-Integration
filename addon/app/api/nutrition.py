"""Nutrition: read-only lookup of candidates and confirmed or manual storage per item.

Docs: docs/API.md "Nutrition". Only verified data (manual or user-confirmed) is stored as
confirmed. The USDA API key is write-only and is never returned.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from app.api.deps import StoresDep
from app.api.errors import ApiError
from app.api.lookups import require_item
from app.db import Stores
from app.models import Nutrition, NutritionSource, NutritionStatus
from app.nutrition.clients import OpenFoodFactsClient, UsdaClient
from app.nutrition.lookup import find_candidates
from app.nutrition.service import NutritionError, NutritionService

router = APIRouter(prefix="/api/items", tags=["nutrition"])

USDA_KEY_SETTING = "usda_api_key"
HTTP_TIMEOUT_SECONDS = 10.0


class CandidateOut(BaseModel):
    source: NutritionSource
    external_id: str
    matched_name: str
    score: float
    kcal: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    fiber_g: float | None = None


class LookupOut(BaseModel):
    item_id: int
    candidates: list[CandidateOut]
    failed_sources: list[NutritionSource]


class NutritionIn(BaseModel):
    """Manual entry (source "manual") or confirmation of a candidate from the lookup.

    For candidate sources, external_id and matched_name identify the product the user picked;
    the macros are the values shown for that product.
    """

    model_config = ConfigDict(extra="forbid")

    source: Literal["manual", "open_food_facts", "usda"]
    external_id: str | None = None
    matched_name: str | None = None
    kcal: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    fiber_g: float | None = None


class NutritionOut(BaseModel):
    item_id: int
    source: NutritionSource
    status: NutritionStatus
    verified: bool
    external_id: str | None = None
    matched_name: str | None = None
    kcal: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    fiber_g: float | None = None
    user_confirmed: bool
    fetched_at: datetime | None = None

    @classmethod
    def from_model(cls, record: Nutrition) -> NutritionOut:
        verified = record.status is NutritionStatus.OK and (
            record.source is NutritionSource.MANUAL or record.user_confirmed
        )
        return cls(
            item_id=record.item_id,
            source=record.source,
            status=record.status,
            verified=verified,
            external_id=record.external_id,
            matched_name=record.matched_name,
            kcal=record.kcal,
            protein_g=record.protein_g,
            carbs_g=record.carbs_g,
            fat_g=record.fat_g,
            fiber_g=record.fiber_g,
            user_confirmed=record.user_confirmed,
            fetched_at=record.fetched_at,
        )


@asynccontextmanager
async def _http_client(request: Request) -> AsyncIterator[httpx.AsyncClient]:
    """Uses an injected client when the app provides one (tests), else a short-lived client."""
    injected = getattr(request.app.state, "nutrition_http", None)
    if injected is not None:
        yield injected
        return
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
        yield client


def _sources(http: httpx.AsyncClient, stores: Stores) -> list:
    """Open Food Facts is always on; USDA stays disabled until a key is set in settings."""
    return [
        OpenFoodFactsClient(http),
        UsdaClient(http, api_key=lambda: stores.settings.get_value(USDA_KEY_SETTING)),
    ]


@router.get("/{item_id}/nutrition/lookup", response_model=LookupOut)
async def lookup_nutrition(item_id: int, request: Request, stores: StoresDep) -> LookupOut:
    """Scored candidates for the item's name. Nothing is stored; the user must confirm one."""
    item = await require_item(stores, item_id)
    async with _http_client(request) as http:
        result = await find_candidates(item.name, _sources(http, stores))
    if result.attempted and len(result.failed_sources) == result.attempted:
        raise ApiError(
            503,
            "lookup_unavailable",
            "nutrition sources are unavailable right now; try again later",
            {"failed_sources": [source.value for source in result.failed_sources]},
        )
    return LookupOut(
        item_id=item_id,
        candidates=[
            CandidateOut(
                source=entry.candidate.source,
                external_id=entry.candidate.external_id,
                matched_name=entry.candidate.matched_name,
                score=entry.score,
                kcal=entry.candidate.kcal,
                protein_g=entry.candidate.protein_g,
                carbs_g=entry.candidate.carbs_g,
                fat_g=entry.candidate.fat_g,
                fiber_g=entry.candidate.fiber_g,
            )
            for entry in result.candidates
        ],
        failed_sources=result.failed_sources,
    )


@router.put("/{item_id}/nutrition", response_model=NutritionOut)
async def put_nutrition(
    item_id: int,
    body: NutritionIn,
    request: Request,
    stores: StoresDep,
) -> NutritionOut:
    """Stores manual values, or confirms a candidate picked from the lookup."""
    await require_item(stores, item_id)
    async with _http_client(request) as http:
        service = NutritionService(
            stores.items,
            stores.nutrition,
            stores.warnings,
            _sources(http, stores),
        )
        try:
            if body.source == "manual":
                record = await service.set_manual(
                    item_id,
                    kcal=body.kcal,
                    protein_g=body.protein_g,
                    carbs_g=body.carbs_g,
                    fat_g=body.fat_g,
                    fiber_g=body.fiber_g,
                )
            else:
                if body.external_id is None or body.matched_name is None:
                    raise NutritionError("external_id and matched_name are required")
                record = await service.confirm_candidate(
                    item_id,
                    source=NutritionSource(body.source),
                    external_id=body.external_id,
                    matched_name=body.matched_name,
                    kcal=body.kcal,
                    protein_g=body.protein_g,
                    carbs_g=body.carbs_g,
                    fat_g=body.fat_g,
                    fiber_g=body.fiber_g,
                )
        except NutritionError as exc:
            raise ApiError(400, "validation_error", str(exc)) from exc
    return NutritionOut.from_model(record)
