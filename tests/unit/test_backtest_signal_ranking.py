from datetime import date

import pandas as pd

import quant_os_app_backtest.services.backtest_service as backtest_service
from quant_os_domain_factor.entities.factor import FactorDirection


def test_build_factor_rank_signals_selects_highest_values_for_long_factors():
    factor_values = pd.DataFrame(
        {
            "ts_code": ["A", "B", "C"],
            "trade_date": [date(2024, 1, 2)] * 3,
            "value": [0.1, 0.5, -0.2],
        }
    )

    signals = backtest_service.build_factor_rank_signals(
        factor_values, FactorDirection.LONG, top_n=2
    )

    assert signals["ts_code"].tolist() == ["B", "A"]
    assert signals["weight"].tolist() == [0.5, 0.5]


def test_build_factor_rank_signals_selects_lowest_values_for_short_factors():
    factor_values = pd.DataFrame(
        {
            "ts_code": ["A", "B", "C"],
            "trade_date": [date(2024, 1, 2)] * 3,
            "value": [0.1, 0.5, -0.2],
        }
    )

    signals = backtest_service.build_factor_rank_signals(
        factor_values, FactorDirection.SHORT, top_n=2
    )

    assert signals["ts_code"].tolist() == ["C", "A"]
    assert signals["weight"].tolist() == [0.5, 0.5]
