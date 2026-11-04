"""Tests for the Open Food Facts and USDA clients and the name matcher (Phase 4)."""

import json
from pathlib import Path

import httpx
import pytest

from app.models import NutritionSource
from app.nutrition.clients import (
    NutritionCandidate,
    NutritionClientError,
    OpenFoodFactsClient,
    UsdaClient,
    best_match,
    match_score,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _http(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _json_response(payload: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload)


async def test_off_parses_products_and_skips_unnamed() -> None:
    chicken = _fixture("off_search_chicken.json")
    async with _http(lambda request: _json_response(chicken)) as http:
        candidates = await OpenFoodFactsClient(http).search("chicken breast")

    assert [c.matched_name for c in candidates] == ["Chicken breast fillet", "Chicken soup"]
    fillet = candidates[0]
    assert fillet.source is NutritionSource.OPEN_FOOD_FACTS
    assert fillet.external_id == "4006381333931"
    assert fillet.kcal == 110
    assert fillet.protein_g == 23.1
    assert fillet.carbs_g == 0.4
    assert fillet.fat_g == 1.9
    assert fillet.fiber_g == 0


async def test_off_derives_kcal_from_kj_when_kcal_missing() -> None:
    chicken = _fixture("off_search_chicken.json")
    async with _http(lambda request: _json_response(chicken)) as http:
        candidates = await OpenFoodFactsClient(http).search("chicken")

    soup = candidates[1]
    assert soup.kcal == pytest.approx(44.0, abs=0.1)
    assert soup.fiber_g is None


async def test_off_sends_search_params_and_user_agent() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = request.url
        seen["agent"] = request.headers.get("user-agent")
        return _json_response(_fixture("off_search_empty.json"))

    async with _http(handler) as http:
        await OpenFoodFactsClient(http).search("oat milk")

    assert seen["url"].params["search_terms"] == "oat milk"
    assert seen["url"].params["json"] == "1"
    assert seen["agent"].startswith("MenuPlanner/")


async def test_off_empty_result_is_empty_list() -> None:
    async with _http(lambda request: _json_response(_fixture("off_search_empty.json"))) as http:
        assert await OpenFoodFactsClient(http).search("zzzz") == []


@pytest.mark.parametrize(
    ("status", "reason", "retryable"),
    [
        (429, "rate_limited", True),
        (503, "unavailable", True),
        (401, "auth", False),
        (404, "rejected", False),
    ],
)
async def test_off_http_errors_are_classified(status: int, reason: str, retryable: bool) -> None:
    async with _http(lambda request: httpx.Response(status, text="nope")) as http:
        with pytest.raises(NutritionClientError) as info:
            await OpenFoodFactsClient(http).search("milk")
    assert info.value.reason == reason
    assert info.value.retryable is retryable


async def test_off_network_error_is_retryable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    async with _http(handler) as http:
        with pytest.raises(NutritionClientError) as info:
            await OpenFoodFactsClient(http).search("milk")
    assert info.value.reason == "network"
    assert info.value.retryable is True


async def test_off_malformed_body_is_retryable() -> None:
    async with _http(lambda request: httpx.Response(200, text="<html>down</html>")) as http:
        with pytest.raises(NutritionClientError) as info:
            await OpenFoodFactsClient(http).search("milk")
    assert info.value.reason == "bad_response"
    assert info.value.retryable is True


async def test_usda_disabled_without_key_makes_no_request() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return _json_response(_fixture("usda_search_broccoli.json"))

    async with _http(handler) as http:
        for key in (None, "", "   "):
            client = UsdaClient(http, api_key=lambda k=key: k)
            assert client.enabled() is False
            assert await client.search("broccoli") == []
    assert calls == []


async def test_usda_sends_key_in_header_not_url() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["request"] = request
        return _json_response(_fixture("usda_search_broccoli.json"))

    async with _http(handler) as http:
        client = UsdaClient(http, api_key=lambda: "SECRET-KEY-123")
        assert client.enabled() is True
        await client.search("broccoli")

    request = seen["request"]
    assert request.headers["x-api-key"] == "SECRET-KEY-123"
    assert "SECRET-KEY-123" not in str(request.url)
    assert request.url.params["query"] == "broccoli"


async def test_usda_parses_nutrients_by_id() -> None:
    async with _http(lambda request: _json_response(_fixture("usda_search_broccoli.json"))) as http:
        candidates = await UsdaClient(http, api_key=lambda: "k").search("broccoli")

    assert [c.external_id for c in candidates] == ["747447", "170379"]
    first = candidates[0]
    assert first.source is NutritionSource.USDA
    assert first.matched_name == "Broccoli, raw"
    assert first.kcal == 31.0
    assert first.protein_g == 2.57
    assert first.carbs_g == 6.27
    assert first.fat_g == 0.34
    assert first.fiber_g == 2.4


async def test_usda_auth_error_does_not_leak_key() -> None:
    async with _http(lambda request: httpx.Response(403, text="forbidden")) as http:
        with pytest.raises(NutritionClientError) as info:
            await UsdaClient(http, api_key=lambda: "SECRET-KEY-123").search("broccoli")
    assert info.value.retryable is False
    assert info.value.reason == "auth"
    assert "SECRET-KEY-123" not in str(info.value)
    assert "SECRET-KEY-123" not in repr(info.value)


def _candidate(name: str, external_id: str = "1") -> NutritionCandidate:
    return NutritionCandidate(
        source=NutritionSource.OPEN_FOOD_FACTS,
        external_id=external_id,
        matched_name=name,
        kcal=100.0,
        protein_g=None,
        carbs_g=None,
        fat_g=None,
        fiber_g=None,
    )


def test_match_score_counts_shared_words() -> None:
    assert match_score("chicken breast", "Chicken breast fillet") == 1.0
    assert match_score("chicken breast", "Chicken soup") == 0.5
    assert match_score("Greek-yogurt", "greek yogurt, plain") == 1.0
    assert match_score("", "anything") == 0.0


def test_best_match_prefers_highest_score_and_earlier_on_tie() -> None:
    candidates = [_candidate("Chicken soup", "a"), _candidate("Chicken breast fillet", "b")]
    assert best_match("chicken breast", candidates).external_id == "b"

    tied = [_candidate("Broccoli, raw", "x"), _candidate("Broccoli, cooked", "y")]
    assert best_match("broccoli", tied).external_id == "x"


def test_best_match_threshold_is_inclusive() -> None:
    soup = _candidate("Chicken soup", "s")
    assert best_match("chicken breast", [soup]) is soup
    assert best_match("tuna", [_candidate("Chicken breast fillet")]) is None
    assert best_match("anything", []) is None
