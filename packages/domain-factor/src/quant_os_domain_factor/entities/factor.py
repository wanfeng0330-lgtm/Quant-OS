"""Factor domain entity."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

import pandas as pd


class FactorCategory(str, Enum):
    ALPHA101 = "alpha101"
    ALPHA191 = "alpha191"
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    CUSTOM = "custom"


class FactorDirection(int, Enum):
    LONG = 1
    SHORT = -1


@dataclass
class FactorDefinition:
    """Core factor definition."""
    factor_name: str
    display_name: str
    category: FactorCategory
    description: str = ""
    formula: str = ""
    direction: FactorDirection = FactorDirection.LONG
    params: dict[str, Any] = field(default_factory=dict)
    version: int = 1
    is_active: bool = True

    def __hash__(self) -> int:
        return hash(self.factor_name)
