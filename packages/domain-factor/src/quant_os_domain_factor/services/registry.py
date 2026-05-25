"""Factor registry with decorator-based registration."""

from __future__ import annotations

import importlib
import logging
from typing import Any, Callable

import pandas as pd

from quant_os_domain_factor.entities.factor import (
    FactorCategory, FactorDefinition, FactorDirection,
)
from quant_os_shared.errors import FactorNotFoundError, FactorRegistrationError

logger = logging.getLogger(__name__)


class FactorRegistry:
    """Registry for factor definitions and their computation functions."""

    _instance: FactorRegistry | None = None

    def __init__(self) -> None:
        self._factors: dict[str, FactorDefinition] = {}
        self._computers: dict[str, Callable] = {}

    @classmethod
    def get_instance(cls) -> FactorRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def register(
        self,
        name: str,
        category: FactorCategory = FactorCategory.CUSTOM,
        display_name: str = "",
        description: str = "",
        formula: str = "",
        direction: FactorDirection = FactorDirection.LONG,
        params: dict[str, Any] | None = None,
    ) -> Callable:
        """Decorator to register a factor computation function."""
        def decorator(func: Callable) -> Callable:
            if name in self._factors:
                raise FactorRegistrationError(
                    f"Factor '{name}' is already registered",
                    code="FACTOR_DUPLICATE",
                )

            definition = FactorDefinition(
                factor_name=name,
                display_name=display_name or name,
                category=category,
                description=description,
                formula=formula,
                direction=direction,
                params=params or {},
            )

            self._factors[name] = definition
            self._computers[name] = func
            logger.info("Registered factor: %s (%s)", name, category.value)
            return func

        return decorator

    def unregister(self, name: str) -> None:
        self._factors.pop(name, None)
        self._computers.pop(name, None)

    def get(self, name: str) -> FactorDefinition:
        if name not in self._factors:
            raise FactorNotFoundError(f"Factor '{name}' not found", code="FACTOR_NOT_FOUND")
        return self._factors[name]

    def get_computer(self, name: str) -> Callable:
        if name not in self._computers:
            raise FactorNotFoundError(f"Factor computer '{name}' not found", code="FACTOR_NOT_FOUND")
        return self._computers[name]

    def compute(self, name: str, data: pd.DataFrame, params: dict[str, Any] | None = None) -> pd.Series:
        """Compute a factor value given OHLCV data."""
        computer = self.get_computer(name)
        definition = self.get(name)
        merged_params = {**definition.params, **(params or {})}
        return computer(data, merged_params)

    def list_all(self) -> list[FactorDefinition]:
        return list(self._factors.values())

    def list_by_category(self, category: FactorCategory) -> list[FactorDefinition]:
        return [f for f in self._factors.values() if f.category == category]

    def list_names(self) -> list[str]:
        return list(self._factors.keys())

    def has(self, name: str) -> bool:
        return name in self._factors

    @property
    def count(self) -> int:
        return len(self._factors)


# Global singleton instance
factor_registry = FactorRegistry.get_instance()


def register_factor(
    name: str,
    category: FactorCategory = FactorCategory.CUSTOM,
    display_name: str = "",
    description: str = "",
    formula: str = "",
    direction: FactorDirection = FactorDirection.LONG,
    params: dict[str, Any] | None = None,
) -> Callable:
    """Convenience decorator using the global factor registry."""
    return factor_registry.register(
        name=name,
        category=category,
        display_name=display_name,
        description=description,
        formula=formula,
        direction=direction,
        params=params,
    )
