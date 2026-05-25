from datetime import date

from fastapi.testclient import TestClient


def test_factor_list_returns_success_wrapper_with_registered_factors(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    from main import create_app

    client = TestClient(create_app())
    response = client.get("/api/v1/factors")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]
    assert {"id", "name", "category", "description"} <= set(payload["data"][0])


def test_backtest_run_endpoint_returns_sync_result_with_demo_strategy(monkeypatch):
    from datetime import date
    import pandas as pd
    from quant_os_infra_market.providers import ProviderFactory

    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

    # Mock a provider that returns sample market data
    class MockProvider:
        provider_name = "mock"

        async def fetch_stock_list(self):
            return pd.DataFrame([{
                "ts_code": "000001.SZ", "symbol": "000001", "name": "Mock Stock",
                "exchange": "SZSE", "board": "main", "list_date": None,
                "delist_date": None, "industry": None, "is_hs": False,
                "total_share": None, "float_share": None, "is_st": False, "status": "active",
            }])

        async def fetch_ohlcv_daily(self, ts_code=None, trade_date=None, start_date=None, end_date=None):
            dates = pd.bdate_range("2024-01-02", "2024-01-12")
            rows = []
            for i, d in enumerate(dates):
                close = 10.1 + i * 0.1
                pre_close = 10.0 + (i - 1) * 0.1 if i > 0 else close
                rows.append({
                    "ts_code": ts_code or "000001.SZ",
                    "trade_date": d.date(),
                    "open": 10.0 + i * 0.1,
                    "high": 10.2 + i * 0.1,
                    "low": 9.8 + i * 0.1,
                    "close": close,
                    "pre_close": pre_close,
                    "change": close - pre_close,
                    "pct_chg": (close / pre_close - 1) * 100 if pre_close else 0.0,
                    "volume": 100000.0,
                    "amount": 1010000.0,
                    "turnover_rate": 1.0,
                    "is_limit_up": False,
                    "is_limit_down": False,
                    "is_suspended": False,
                })
            return pd.DataFrame(rows)

    ProviderFactory.clear()
    ProviderFactory.register("mock", MockProvider())
    ProviderFactory.set_primary("mock")

    from main import create_app

    client = TestClient(create_app())
    response = client.post(
        "/api/v1/backtest/run",
        json={
            "strategy_id": "demo_momentum",
            "start_date": "2024-01-02",
            "end_date": "2024-01-12",
            "benchmark": "000300.SH",
            "initial_capital": 1000000,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["backtest_id"]
    assert "total_return" in payload["data"]["results"]


def test_market_endpoints_return_success_wrapper_with_empty_db(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    from main import create_app

    client = TestClient(create_app())

    stocks_response = client.get("/api/v1/market/stocks", params={"page": 1, "size": 5})
    assert stocks_response.status_code == 200
    stocks_payload = stocks_response.json()
    assert stocks_payload["success"] is True
    assert "items" in stocks_payload["data"]
    assert "total" in stocks_payload["data"]


def test_agent_run_calls_configured_llm_and_returns_messages(monkeypatch):
    from quant_os_infra_agent.llm.base import LLMResponse
    from quant_os_infra_agent.llm.factory import LLMProviderFactory

    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("LLM_DEFAULT_PROVIDER", "mimo")
    monkeypatch.setenv("MIMO_API_KEY", "test-key")

    class FakeProvider:
        provider_name = "mimo"
        default_model = "mimo-v2.5-pro"

        async def chat(self, messages, tools=None, config=None):
            return LLMResponse(content=f"answer: {messages[-1].content}", model="mimo-v2.5-pro")

    monkeypatch.setattr(LLMProviderFactory, "create", classmethod(lambda cls, provider_name=None, **kwargs: FakeProvider()))

    from main import create_app

    client = TestClient(create_app())
    agents = client.get("/api/v1/agents").json()["data"]
    response = client.post(
        f"/api/v1/agents/{agents[0]['id']}/runs",
        json={"message": "分析一下动量因子"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["status"] == "completed"
    assert payload["data"]["messages"][-1]["role"] == "assistant"
    assert "动量因子" in payload["data"]["messages"][-1]["content"]
