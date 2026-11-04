"""Nutrition search clients (Open Food Facts first, USDA FoodData Central second).

Clients take an injected ``httpx.AsyncClient`` so tests can use ``MockTransport``.
Errors never include the USDA key or raw response bodies.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.models import NutritionSource

OFF_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"
USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
USDA_NUTRIENT_IDS = {
    "kcal": 1008,
    "protein_g": 1003,
    "carbs_g": 1005,
    "fat_g": 1004,
    "fiber_g": 1079,
}
MATCH_THRESHOLD = 0.5
USER_AGENT = "MenuPlanner/1.0 (Home Assistant add-on; nutrition lookup)"

_WORD = re.compile(r"[a-z0-9]+")


class NutritionClientError(Exception):
    """A failed search. ``retryable`` tells the service whether a later retry may succeed."""

    def __init__(self, reason: str, *, retryable: bool) -> None:
        super().__init__(reason)
        self.reason = reason
        self.retryable = retryable


@dataclass(slots=True)
class NutritionCandidate:
    source: NutritionSource
    external_id: str
    matched_name: str
    kcal: float
    protein_g: float | None
    carbs_g: float | None
    fat_g: float | None
    fiber_g: float | None


class NutritionSearchClient(Protocol):
    source: NutritionSource

    def enabled(self) -> bool: ...

    async def search(self, query: str) -> list[NutritionCandidate]: ...


def match_score(query: str, name: str) -> float:
    """Share of query words that appear in the product name (0.0 to 1.0)."""
    query_words = set(_WORD.findall(query.lower()))
    if not query_words:
        return 0.0
    name_words = set(_WORD.findall(name.lower()))
    return len(query_words & name_words) / len(query_words)


def best_match(query: str, candidates: list[NutritionCandidate]) -> NutritionCandidate | None:
    """Highest-scoring candidate at or above the threshold; the earlier one wins ties."""
    best: NutritionCandidate | None = None
    best_score = 0.0
    for candidate in candidates:
        score = match_score(query, candidate.matched_name)
        if score > best_score:
            best, best_score = candidate, score
    if best is None or best_score < MATCH_THRESHOLD:
        return None
    return best


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _raise_for_status(response: httpx.Response) -> None:
    status = response.status_code
    if status < 300:
        return
    if status == 429:
        raise NutritionClientError("rate_limited", retryable=True)
    if status in (401, 403):
        raise NutritionClientError("auth", retryable=False)
    if status >= 500:
        raise NutritionClientError("unavailable", retryable=True)
    raise NutritionClientError("rejected", retryable=False)


async def _get_json(http: httpx.AsyncClient, url: str, **kwargs: Any) -> Any:
    try:
        response = await http.get(url, **kwargs)
    except httpx.TransportError as exc:
        raise NutritionClientError("network", retryable=True) from exc
    _raise_for_status(response)
    try:
        return response.json()
    except ValueError as exc:
        raise NutritionClientError("bad_response", retryable=True) from exc


class OpenFoodFactsClient:
    """Name search against the public Open Food Facts v1 search endpoint."""

    source = NutritionSource.OPEN_FOOD_FACTS

    def __init__(self, http: httpx.AsyncClient, page_size: int = 10) -> None:
        self._http = http
        self._page_size = page_size

    def enabled(self) -> bool:
        return True

    async def search(self, query: str) -> list[NutritionCandidate]:
        params = {
            "search_terms": query,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": self._page_size,
            "fields": "code,product_name,nutriments",
        }
        data = await _get_json(
            self._http, OFF_SEARCH_URL, params=params, headers={"User-Agent": USER_AGENT}
        )
        products = data.get("products") if isinstance(data, dict) else None
        if not isinstance(products, list):
            raise NutritionClientError("bad_response", retryable=True)
        return [c for c in (self._to_candidate(p) for p in products) if c is not None]

    @staticmethod
    def _to_candidate(product: Any) -> NutritionCandidate | None:
        if not isinstance(product, dict):
            return None
        name = product.get("product_name")
        nutriments = product.get("nutriments")
        if not isinstance(name, str) or not name.strip() or not isinstance(nutriments, dict):
            return None
        kcal = _number(nutriments.get("energy-kcal_100g"))
        if kcal is None:
            kj = _number(nutriments.get("energy-kj_100g"))
            kcal = kj / 4.184 if kj is not None else None
        if kcal is None:
            return None
        return NutritionCandidate(
            source=NutritionSource.OPEN_FOOD_FACTS,
            external_id=str(product.get("code", "")),
            matched_name=name.strip(),
            kcal=round(kcal, 1),
            protein_g=_number(nutriments.get("proteins_100g")),
            carbs_g=_number(nutriments.get("carbohydrates_100g")),
            fat_g=_number(nutriments.get("fat_100g")),
            fiber_g=_number(nutriments.get("fiber_100g")),
        )


class UsdaClient:
    """USDA FoodData Central search. Skipped entirely when no API key is configured."""

    source = NutritionSource.USDA

    def __init__(
        self,
        http: httpx.AsyncClient,
        api_key: Callable[[], str | None],
        page_size: int = 10,
    ) -> None:
        self._http = http
        self._api_key = api_key
        self._page_size = page_size

    def enabled(self) -> bool:
        key = self._api_key()
        return bool(key and key.strip())

    async def search(self, query: str) -> list[NutritionCandidate]:
        key = self._api_key()
        if not key or not key.strip():
            return []
        params = {
            "query": query,
            "pageSize": self._page_size,
            "dataType": "Foundation,SR Legacy",
        }
        data = await _get_json(
            self._http,
            USDA_SEARCH_URL,
            params=params,
            headers={"X-Api-Key": key.strip(), "User-Agent": USER_AGENT},
        )
        foods = data.get("foods") if isinstance(data, dict) else None
        if not isinstance(foods, list):
            raise NutritionClientError("bad_response", retryable=True)
        return [c for c in (self._to_candidate(f) for f in foods) if c is not None]

    @staticmethod
    def _to_candidate(food: Any) -> NutritionCandidate | None:
        if not isinstance(food, dict):
            return None
        description = food.get("description")
        nutrients = food.get("foodNutrients")
        if not isinstance(description, str) or not isinstance(nutrients, list):
            return None
        values: dict[str, float | None] = dict.fromkeys(USDA_NUTRIENT_IDS)
        for nutrient in nutrients:
            if not isinstance(nutrient, dict):
                continue
            for field_name, nutrient_id in USDA_NUTRIENT_IDS.items():
                if nutrient.get("nutrientId") == nutrient_id and values[field_name] is None:
                    values[field_name] = _number(nutrient.get("value"))
        if values["kcal"] is None:
            return None
        return NutritionCandidate(
            source=NutritionSource.USDA,
            external_id=str(food.get("fdcId", "")),
            matched_name=description.strip(),
            kcal=values["kcal"],
            protein_g=values["protein_g"],
            carbs_g=values["carbs_g"],
            fat_g=values["fat_g"],
            fiber_g=values["fiber_g"],
        )
