"""Factor value repository implementation."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from quant_os_infra_factor.models.factor_model import FactorValueModel

logger = logging.getLogger(__name__)


class FactorValueRepository:
    """Repository for factor value operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_factor_values(
        self,
        factor_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
        ts_codes: list[str] | None = None,
    ) -> list[FactorValueModel]:
        """Get factor values for a factor within date range."""
        query = select(FactorValueModel).where(
            FactorValueModel.factor_id == factor_id
        )
        
        if start_date:
            query = query.where(FactorValueModel.trade_date >= start_date)
        if end_date:
            query = query.where(FactorValueModel.trade_date <= end_date)
        if ts_codes:
            query = query.where(FactorValueModel.ts_code.in_(ts_codes))
        
        query = query.order_by(
            FactorValueModel.trade_date,
            FactorValueModel.ts_code,
        )
        
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_factor_values_as_dataframe(
        self,
        factor_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
        ts_codes: list[str] | None = None,
    ) -> pd.DataFrame:
        """Get factor values as DataFrame."""
        values = await self.get_factor_values(
            factor_id, start_date, end_date, ts_codes
        )
        
        if not values:
            return pd.DataFrame(
                columns=["ts_code", "trade_date", "value", "factor_id"]
            )
        
        data = []
        for v in values:
            data.append({
                "ts_code": v.ts_code,
                "trade_date": v.trade_date,
                "value": v.value,
                "factor_id": v.factor_id,
            })
        
        return pd.DataFrame(data)

    async def bulk_insert(self, records: list[dict[str, Any]]) -> int:
        """Bulk insert factor values."""
        if not records:
            return 0
        
        # Validate required fields
        required_fields = ["ts_code", "trade_date", "factor_id", "value"]
        for record in records:
            for field in required_fields:
                if field not in record:
                    raise ValueError(f"Missing required field: {field}")
        
        # Convert to model instances
        models = []
        for record in records:
            model = FactorValueModel(
                ts_code=record["ts_code"],
                trade_date=record["trade_date"],
                factor_id=record["factor_id"],
                value=record["value"],
                rank=record.get("rank"),
                zscore=record.get("zscore"),
            )
            models.append(model)
        
        # Add all and flush
        self._session.add_all(models)
        await self._session.flush()
        
        logger.info("Inserted %d factor values", len(models))
        return len(models)

    async def upsert_from_dataframe(
        self,
        df: pd.DataFrame,
        factor_id: str,
    ) -> int:
        """Upsert factor values from DataFrame.
        
        Args:
            df: DataFrame with columns [ts_code, trade_date, value]
            factor_id: Factor ID
            
        Returns:
            Number of upserted records
        """
        if df.empty:
            return 0
        
        # Ensure required columns exist
        required_cols = ["ts_code", "trade_date", "value"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"DataFrame missing required column: {col}")
        
        # Prepare records
        records = []
        for _, row in df.iterrows():
            record = {
                "ts_code": row["ts_code"],
                "trade_date": row["trade_date"],
                "factor_id": factor_id,
                "value": float(row["value"]) if pd.notna(row["value"]) else None,
                "rank": float(row["rank"]) if "rank" in df.columns and pd.notna(row.get("rank")) else None,
                "zscore": float(row["zscore"]) if "zscore" in df.columns and pd.notna(row.get("zscore")) else None,
            }
            records.append(record)
        
        # For now, do a simple insert
        # In production, you'd want to do an upsert (INSERT ... ON CONFLICT UPDATE)
        return await self.bulk_insert(records)

    async def delete_by_factor_and_date_range(
        self,
        factor_id: str,
        start_date: date,
        end_date: date,
    ) -> int:
        """Delete factor values for a factor within date range."""
        stmt = delete(FactorValueModel).where(
            FactorValueModel.factor_id == factor_id,
            FactorValueModel.trade_date >= start_date,
            FactorValueModel.trade_date <= end_date,
        )
        
        result = await self._session.execute(stmt)
        await self._session.flush()
        
        deleted = result.rowcount
        logger.info(
            "Deleted %d factor values for %s from %s to %s",
            deleted, factor_id, start_date, end_date,
        )
        return deleted

    async def get_latest_date(self, factor_id: str) -> date | None:
        """Get the latest date with factor values for a factor."""
        result = await self._session.execute(
            select(func.max(FactorValueModel.trade_date))
            .where(FactorValueModel.factor_id == factor_id)
        )
        return result.scalar_one_or_none()

    async def count_by_factor(self, factor_id: str) -> int:
        """Count factor values for a factor."""
        result = await self._session.execute(
            select(func.count())
            .select_from(FactorValueModel)
            .where(FactorValueModel.factor_id == factor_id)
        )
        return result.scalar_one()