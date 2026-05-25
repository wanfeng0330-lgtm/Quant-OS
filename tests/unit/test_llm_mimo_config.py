from quant_os_infra_agent.llm.factory import LLMProviderFactory
from quant_os_infra_agent.llm.openai import OpenAIProvider
from quant_os_shared.config.settings import Settings


def test_mimo_provider_uses_openai_compatible_endpoint(monkeypatch):
    monkeypatch.setenv("LLM_DEFAULT_PROVIDER", "mimo")
    monkeypatch.setenv("MIMO_API_KEY", "test-key")
    monkeypatch.setenv("MIMO_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
    monkeypatch.setenv("MIMO_MODEL", "mimo-v2.5-pro")

    settings = Settings()
    LLMProviderFactory.clear_cache()

    config = LLMProviderFactory._get_provider_config("mimo", settings)
    provider = LLMProviderFactory.create("mimo", **config)

    assert isinstance(provider, OpenAIProvider)
    assert provider.provider_name == "mimo"
    assert provider.default_model == "mimo-v2.5-pro"
