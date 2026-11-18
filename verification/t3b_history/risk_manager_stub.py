"""The signature of athena risk_management.risk_manager.compute_position_size at commit 705db5b (athena, 2026-11-16), for the T3b sets from real history (scripts/t3b_fixtures.py).
Only the signature is kept: the sets show the reader the numbers the real function returned on that commit (run once with athena's own venv: entry 50, ATR 3 -> blocked True, stop 50.0 at c82cd47 and blocked False, stop 45.0 at 705db5b; entry 1000, ATR 20, buffer 0.15 -> stop_distance_for_sizing 34.5, 0.07 -> 32.1), and the card needs the parameter names."""
def compute_position_size(
    ticker: str,
    capital_idr: float,
    entry_price: float,
    atr: float,
    confidence_level: str,
    volatility_state: str = "normal",
    avg_daily_value_idr: float | None = None,
    risk_pct: float = DEFAULT_RISK_PCT,
    slippage_buffer_pct: float = DEFAULT_SLIPPAGE_BUFFER_PCT,
    stop_atr_multiple: float = DEFAULT_STOP_ATR_MULTIPLE,
    take_profit_r_multiple: float = DEFAULT_TAKE_PROFIT_R_MULTIPLE,
    max_position_pct_of_daily_value: float = DEFAULT_MAX_POSITION_PCT_OF_DAILY_VALUE,
    max_position_pct_of_capital: float = DEFAULT_MAX_SINGLE_POSITION_PCT,
    lot_size: int = LOT_SIZE,
) -> PositionSizeResult:
    ...
