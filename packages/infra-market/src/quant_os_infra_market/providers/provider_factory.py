"""Data provider factory."""

from __future__ import annotations

import logging
from typing import Any

from quant_os_infra_market.providers.base import DataProvider

logger = logging.getLogger(__name__)


class ProviderFactory:
    """Factory for creating and managing data providers.

    Maintains a registry of named ``DataProvider`` instances and tracks
    which provider should be treated as the *primary* data source and
    which as the *fallback*.  Callers typically interact with the
    factory via ``ProviderFactory.get()`` which returns the primary
    provider unless a specific name is requested.
    """

    _providers: dict[str, DataProvider] = {}
    _primary: str = "akshare"
    _fallback: str = "tushare"

    @classmethod
    def register(cls, name: str, provider: DataProvider) -> None:
        """Register a provider instance under *name*."""
        cls._providers[name] = provider
        logger.info("Registered data provider: %s", name)

    @classmethod
    def get(cls, name: str | None = None) -> DataProvider:
        """Return a provider by *name*, or the primary/fallback default.

        Raises ``ValueError`` if an explicit *name* is given but not
        registered.
        """
        if name:
            if name not in cls._providers:
                raise ValueError(f"Unknown provider: {name}")
            return cls._providers[name]
        provider = (
            cls._providers.get(cls._primary)
            or cls._providers.get(cls._fallback)
            or next(iter(cls._providers.values()), None)
        )
        if provider is None:
            raise RuntimeError("No data providers initialized")
        return provider

    @classmethod
    def get_with_fallback(cls) -> list[DataProvider]:
        """Return an ordered list: [primary, fallback] (when available)."""
        providers: list[DataProvider] = []
        if cls._primary in cls._providers:
            providers.append(cls._providers[cls._primary])
        if cls._fallback in cls._providers and cls._fallback != cls._primary:
            providers.append(cls._providers[cls._fallback])
        return providers

    @classmethod
    def set_primary(cls, name: str) -> None:
        """Designate *name* as the primary data source."""
        cls._primary = name

    @classmethod
    def set_fallback(cls, name: str) -> None:
        """Designate *name* as the fallback data source."""
        cls._fallback = name

    @classmethod
    def list_providers(cls) -> list[str]:
        """Return the names of all registered providers."""
        return list(cls._providers.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear provider registry. Intended for tests and process reinitialization."""
        cls._providers.clear()
        cls._primary = "akshare"
        cls._fallback = "tushare"


def init_providers(
    akshare_enabled: bool = True,
    tushare_token: str = "",
    primary_provider: str = "akshare",
    fallback_provider: str = "tushare",
) -> None:
    """Initialize all available data providers.

    Parameters
    ----------
    akshare_enabled:
        Whether to register the AKShare provider (free, no token
        required).  Defaults to ``True``.
    tushare_token:
        Tushare API token.  When non-empty the Tushare provider is also
        registered.
    """
    ProviderFactory.set_primary(primary_provider)
    ProviderFactory.set_fallback(fallback_provider)

    if akshare_enabled and "akshare" not in ProviderFactory._providers:
        from quant_os_infra_market.providers.akshare_provider import AKShareProvider

        ProviderFactory.register("akshare", AKShareProvider())

    if tushare_token and "tushare" not in ProviderFactory._providers:
        from quant_os_infra_market.providers.tushare_provider import TushareProvider

        ProviderFactory.register("tushare", TushareProvider(token=tushare_token))

    logger.info("Initialized data providers: %s", ProviderFactory.list_providers())


def init_providers_from_settings(settings: object | None = None) -> None:
    """Initialize providers using aggregated application settings."""
    if settings is None:
        from quant_os_shared.config.settings import get_settings

        settings = get_settings()

    data_source = settings.data_source
    init_providers(
        akshare_enabled=data_source.akshare_enabled,
        tushare_token=data_source.tushare_token,
        primary_provider=data_source.primary_provider,
        fallback_provider=data_source.fallback_provider,
    )


def ensure_providers_initialized(settings: object | None = None) -> None:
    """Initialize providers only when the current process registry is empty."""
    if not ProviderFactory.list_providers():
        init_providers_from_settings(settings)
