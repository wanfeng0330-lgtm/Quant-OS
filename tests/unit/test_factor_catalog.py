import pandas as pd

from quant_os_domain_factor.services.registry import factor_registry


def test_load_builtin_factors_registers_broad_catalog_idempotently():
    from quant_os_app_factor.services.factor_catalog import load_builtin_factors

    load_builtin_factors()
    first_count = factor_registry.count
    load_builtin_factors()

    names = set(factor_registry.list_names())
    assert factor_registry.count == first_count
    assert {"momentum", "alpha001", "amihud_illiquidity", "price_volume_corr"} <= names
    assert first_count >= 50


def test_liquidity_factor_computes_from_ohlcv_amount():
    from quant_os_app_factor.services.factor_catalog import load_builtin_factors

    load_builtin_factors()
    data = pd.DataFrame(
        {
            "ts_code": ["000001.SZ"] * 4,
            "trade_date": pd.date_range("2024-01-01", periods=4),
            "open": [10.0, 10.2, 10.3, 10.1],
            "high": [10.3, 10.5, 10.5, 10.4],
            "low": [9.9, 10.1, 10.0, 9.9],
            "close": [10.2, 10.3, 10.1, 10.4],
            "volume": [1000.0, 1100.0, 1050.0, 1300.0],
            "amount": [10200.0, 11330.0, 10605.0, 13520.0],
        }
    )

    result = factor_registry.compute("amihud_illiquidity", data, {"period": 2})

    assert len(result) == len(data)
    assert result.dropna().ge(0).all()
