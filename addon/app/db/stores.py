"""Bundle of the database and every repository, built from one database path."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .connection import Database
from .repositories import (
    SettingsStore,
    SqliteCategoryRepository,
    SqliteItemRepository,
    SqliteMenuRepository,
    SqliteNutritionRepository,
    SqliteRuleRepository,
    SqliteWarningRepository,
    StockStore,
    TemplateStore,
)


@dataclass(slots=True)
class Stores:
    database: Database
    items: SqliteItemRepository
    categories: SqliteCategoryRepository
    rules: SqliteRuleRepository
    menu: SqliteMenuRepository
    nutrition: SqliteNutritionRepository
    warnings: SqliteWarningRepository
    stock: StockStore
    settings: SettingsStore
    template: TemplateStore

    @classmethod
    def open(cls, path: Path | str) -> Stores:
        return cls.from_database(Database(path))

    @classmethod
    def from_database(cls, database: Database) -> Stores:
        return cls(
            database=database,
            items=SqliteItemRepository(database),
            categories=SqliteCategoryRepository(database),
            rules=SqliteRuleRepository(database),
            menu=SqliteMenuRepository(database),
            nutrition=SqliteNutritionRepository(database),
            warnings=SqliteWarningRepository(database),
            stock=StockStore(database),
            settings=SettingsStore(database),
            template=TemplateStore(database),
        )

    def close(self) -> None:
        self.database.close()
