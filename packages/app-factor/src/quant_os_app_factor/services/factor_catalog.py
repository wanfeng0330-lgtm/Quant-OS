"""Factor catalog helpers for loading and syncing built-in factors."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from quant_os_domain_factor.services.registry import factor_registry
from quant_os_infra_factor.repositories.factor_repo import FactorRepository


_loaded = False


def load_builtin_factors() -> None:
    """Import built-in factor modules so decorators register their definitions."""
    global _loaded
    if _loaded:
        return

    import quant_os_infra_factor.built_in  # noqa: F401

    _loaded = True


async def sync_builtin_factors(session: AsyncSession) -> int:
    """Ensure built-in factor definitions are present in the database."""
    load_builtin_factors()
    repo = FactorRepository(session)
    return await repo.sync_registry_factors(factor_registry.list_all())
