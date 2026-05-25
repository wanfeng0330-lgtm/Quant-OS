from types import SimpleNamespace

import pytest

from quant_os_infra_market.providers import ProviderFactory


def test_provider_factory_initializes_from_settings_and_is_idempotent(monkeypatch):
    from quant_os_infra_market.providers import provider_factory

    class FakeAKShareProvider:
        provider_name = "akshare"

    class FakeTushareProvider:
        provider_name = "tushare"

        def __init__(self, token: str) -> None:
            self.token = token

    monkeypatch.setattr(
        "quant_os_infra_market.providers.akshare_provider.AKShareProvider",
        FakeAKShareProvider,
    )
    monkeypatch.setattr(
        "quant_os_infra_market.providers.tushare_provider.TushareProvider",
        FakeTushareProvider,
    )

    ProviderFactory.clear()
    settings = SimpleNamespace(
        data_source=SimpleNamespace(
            akshare_enabled=True,
            tushare_token="token",
            primary_provider="akshare",
            fallback_provider="tushare",
        )
    )

    provider_factory.init_providers_from_settings(settings)
    provider_factory.init_providers_from_settings(settings)

    assert ProviderFactory.list_providers() == ["akshare", "tushare"]
    assert ProviderFactory.get().provider_name == "akshare"
    assert ProviderFactory.get_with_fallback()[1].provider_name == "tushare"


def test_provider_factory_get_raises_clear_error_when_empty():
    ProviderFactory.clear()

    with pytest.raises(RuntimeError, match="No data providers initialized"):
        ProviderFactory.get()
