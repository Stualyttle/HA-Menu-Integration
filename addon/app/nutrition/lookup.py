"""Read-only nutrition search: returns scored candidates without storing anything."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.models import NutritionSource
from app.nutrition.clients import (
    NutritionCandidate,
    NutritionClientError,
    NutritionSearchClient,
    match_score,
)


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    candidate: NutritionCandidate
    score: float


@dataclass(frozen=True, slots=True)
class LookupResult:
    candidates: list[ScoredCandidate] = field(default_factory=list)
    failed_sources: list[NutritionSource] = field(default_factory=list)
    attempted: int = 0


async def find_candidates(
    item_name: str,
    sources: Sequence[NutritionSearchClient],
) -> LookupResult:
    """Searches every enabled source and scores each candidate against the item name.

    Candidates with a zero score are dropped and the rest are sorted best first. Sources that
    raise a client error are reported in ``failed_sources`` and do not stop the search.
    """
    scored: list[ScoredCandidate] = []
    failed: list[NutritionSource] = []
    attempted = 0
    for source in sources:
        if not source.enabled():
            continue
        attempted += 1
        try:
            candidates = await source.search(item_name)
        except NutritionClientError:
            failed.append(source.source)
            continue
        for candidate in candidates:
            score = match_score(item_name, candidate.matched_name)
            if score > 0:
                scored.append(ScoredCandidate(candidate=candidate, score=score))
    scored.sort(key=lambda entry: entry.score, reverse=True)
    return LookupResult(candidates=scored, failed_sources=failed, attempted=attempted)
