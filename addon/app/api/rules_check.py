"""POST /api/rules/check: feasibility of a proposed rule before it is saved (docs/API.md)."""

from __future__ import annotations

from dataclasses import replace

from fastapi import APIRouter

from app.api.deps import StoresDep
from app.api.errors import ApiError
from app.api.lookups import check_category_ids, check_item_ids
from app.api.planning import build_context, build_planner
from app.api.rules import _validate_shape
from app.api.schemas import RuleCheckIn, RuleCheckOut, RuleIn
from app.db import Stores
from app.models import Rule

router = APIRouter(prefix="/api/rules", tags=["rules"])


async def _validate_rule(stores: Stores, body: RuleIn) -> Rule:
    _validate_shape(body)
    category_ids = set(body.category_ids)
    await check_category_ids(stores, category_ids)
    if body.item_id is not None:
        await check_item_ids(stores, [body.item_id])
    return Rule(
        id=0,
        kind=body.kind,
        scope=body.scope,
        category_ids=frozenset(category_ids),
        item_id=body.item_id,
        enabled=body.enabled,
    )


@router.post("/check", response_model=RuleCheckOut)
async def check_rule(body: RuleCheckIn, stores: StoresDep) -> RuleCheckOut:
    candidate = await _validate_rule(stores, body.rule)
    stored = await stores.rules.list_rules()
    if body.rule_id is None:
        proposed = [*stored, candidate]
    else:
        if not any(rule.id == body.rule_id for rule in stored):
            raise ApiError(404, "not_found", f"rule {body.rule_id} not found")
        proposed = [
            replace(candidate, id=body.rule_id) if rule.id == body.rule_id else rule
            for rule in stored
        ]
    planner = build_planner(stores)
    ctx = build_context(stores)
    result = await planner.check_rules(ctx, proposed)
    return RuleCheckOut(
        feasible=result.feasible,
        exhausted=result.exhausted,
        affected_days=[day.isoformat() for day in result.affected_days],
        locked_conflicts=[day.isoformat() for day in result.locked_conflicts],
    )
