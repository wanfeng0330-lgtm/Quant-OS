"""Application configuration."""

from __future__ import annotations

from quant_os_shared.config.settings import Settings, get_settings


_settings: Settings | None = None


def get_app_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = get_settings()
    return _settings
