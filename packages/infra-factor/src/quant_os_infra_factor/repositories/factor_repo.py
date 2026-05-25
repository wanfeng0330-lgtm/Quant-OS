"""Factor repository implementation."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from quant_os_infra_factor.models.factor_model import FactorModel, FactorAnalysisResultModel

logger = logging.getLogger(__name__)


class FactorRepository:
    """Repository for factor CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, factor_id: str) -> FactorModel | None:
        result = await self._session.execute(
            select(FactorModel).where(FactorModel.id == factor_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, factor_name: str) -> FactorModel | None:
        result = await self._session.execute(
            select(FactorModel).where(FactorModel.factor_name == factor_name)
        )
        return result.scalar_one_or_none()

    async def list_factors(
        self,
        category: str | None = None,
        is_active: bool | None = None,
    ) -> list[FactorModel]:
        query = select(FactorModel).order_by(FactorModel.factor_name)
        if category:
            query = query.where(FactorModel.category == category)
        if is_active is not None:
            query = query.where(FactorModel.is_active == is_active)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def create_factor(self, data: dict[str, Any]) -> FactorModel:
        factor = FactorModel(**data)
        self._session.add(factor)
        await self._session.flush()
        return factor

    async def upsert_from_registry(self, definition) -> FactorModel:
        """Upsert a factor from a FactorDefinition (domain entity)."""
        existing = await self.get_by_name(definition.factor_name)
        if existing:
            existing.display_name = definition.display_name
            existing.category = definition.category.value
            existing.description = definition.description
            existing.formula = definition.formula
            existing.direction = definition.direction.value
            existing.params = definition.params
            await self._session.flush()
            return existing
        else:
            factor = FactorModel(
                factor_name=definition.factor_name,
                display_name=definition.display_name,
                category=definition.category.value,
                description=definition.description,
                formula=definition.formula,
                direction=definition.direction.value,
                params=definition.params,
            )
            self._session.add(factor)
            await self._session.flush()
            return factor

    async def save_analysis_result(self, data: dict[str, Any]) -> FactorAnalysisResultModel:
        result_model = FactorAnalysisResultModel(**data)
        self._session.add(result_model)
        await self._session.flush()
        return result_model

    async def get_latest_analysis(self, factor_id: str) -> FactorAnalysisResultModel | None:
        result = await self._session.execute(
            select(FactorAnalysisResultModel)
            .where(FactorAnalysisResultModel.factor_id == factor_id)
            .order_by(FactorAnalysisResultModel.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def sync_registry_factors(self, registry_factors: list) -> int:
        """Sync all registered factors to database. Returns count of upserted."""
        count = 0
        for defn in registry_factors:
            await self.upsert_from_registry(defn)
            count += 1
        logger.info("Synced %d factors from registry to database", count)
        return count
