"""Rules: list, create, update, delete (docs/API.md "Items, categories, rules")."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.api.deps import StoresDep
from app.api.errors import ApiError
from app.api.lookups import check_category_ids, check_item_ids
from app.api.schemas import RuleIn, RuleOut
from app.db import Stores
from app.models import Rule, RuleScope

router = APIRouter(prefix="/api/rules", tags=["rules"])


def _validate_shape(body: RuleIn) -> None:
    if body.scope == RuleScope.COMBINATION:
        if not body.category_ids:
            raise ApiError(400, "validation_error", "combination rules need category_ids")
        if body.item_id is not None:
            raise ApiError(400, "validation_error", "combination rules must not set item_id")
    else:
        if body.item_id is None:
            raise ApiError(400, "validation_error", "item rules need item_id")
        if body.category_ids:
            raise ApiError(400, "validation_error", "item rules must not set category_ids")


async def _save(stores: Stores, rule_id: int, body: RuleIn) -> RuleOut:
    _validate_shape(body)
    category_ids = set(body.category_ids)
    await check_category_ids(stores, category_ids)
    if body.item_id is not None:
        await check_item_ids(stores, [body.item_id])
    saved = await stores.rules.save_rule(
        Rule(
            id=rule_id,
            kind=body.kind,
            scope=body.scope,
            category_ids=frozenset(category_ids),
            item_id=body.item_id,
            enabled=body.enabled,
        )
    )
    return RuleOut.from_model(saved)


async def _require_rule(stores: Stores, rule_id: int) -> Rule:
    for rule in await stores.rules.list_rules():
        if rule.id == rule_id:
            return rule
    raise ApiError(404, "not_found", f"rule {rule_id} not found")


@router.get("", response_model=list[RuleOut])
async def list_rules(stores: StoresDep) -> list[RuleOut]:
    return [RuleOut.from_model(r) for r in await stores.rules.list_rules()]


@router.post("", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(body: RuleIn, stores: StoresDep) -> RuleOut:
    return await _save(stores, 0, body)


@router.put("/{rule_id}", response_model=RuleOut)
async def update_rule(rule_id: int, body: RuleIn, stores: StoresDep) -> RuleOut:
    await _require_rule(stores, rule_id)
    return await _save(stores, rule_id, body)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_rule(rule_id: int, stores: StoresDep) -> Response:
    await _require_rule(stores, rule_id)
    await stores.rules.delete_rule(rule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
