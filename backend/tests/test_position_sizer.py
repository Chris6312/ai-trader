from decimal import Decimal

from app.risk.position_sizer import AtrPositionSizer
from app.risk.types import PositionSizingInput, PositionSizingRejection


def test_atr_position_sizer_sizes_stock_with_whole_shares() -> None:
    sizer = AtrPositionSizer()

    result = sizer.size_position(
        PositionSizingInput(
            symbol="AAPL",
            asset_class="stock",
            entry_price=Decimal("100"),
            atr=Decimal("2"),
            stop_atr_multiple=Decimal("1.5"),
            account_equity=Decimal("10000"),
            available_cash=Decimal("10000"),
            risk_percent=Decimal("1"),
        )
    )

    assert result.rejected is False
    assert result.quantity == Decimal("33")
    assert result.stop_price == Decimal("97.0")
    assert result.risk_amount == Decimal("99.0")
    assert result.reasoning.computed["risk_budget"] == "100.00"


def test_atr_position_sizer_caps_crypto_by_available_cash_and_exposure() -> None:
    sizer = AtrPositionSizer()

    result = sizer.size_position(
        PositionSizingInput(
            symbol="BTC/USD",
            asset_class="crypto",
            entry_price=Decimal("50000"),
            atr=Decimal("1000"),
            stop_atr_multiple=Decimal("2"),
            account_equity=Decimal("10000"),
            available_cash=Decimal("2500"),
            risk_percent=Decimal("2"),
            max_position_notional_percent=Decimal("20"),
        )
    )

    assert result.rejected is False
    assert result.quantity == Decimal("0.04000000")
    assert result.notional_value == Decimal("2000.00000000")
    assert result.risk_amount == Decimal("80.000000000")
    assert "available_cash" in result.reasoning.caps_applied
    assert "max_position_notional" in result.reasoning.caps_applied


def test_atr_position_sizer_rejects_invalid_atr() -> None:
    sizer = AtrPositionSizer()

    result = sizer.size_position(
        PositionSizingInput(
            symbol="TSLA",
            asset_class="stock",
            entry_price=Decimal("250"),
            atr=Decimal("0"),
            stop_atr_multiple=Decimal("2"),
            account_equity=Decimal("10000"),
            available_cash=Decimal("10000"),
            risk_percent=Decimal("1"),
        )
    )

    assert result.rejected is True
    assert result.rejection_reason == PositionSizingRejection.INVALID_ATR


def test_atr_position_sizer_rejects_zero_quantity_after_caps() -> None:
    sizer = AtrPositionSizer()

    result = sizer.size_position(
        PositionSizingInput(
            symbol="NVDA",
            asset_class="stock",
            entry_price=Decimal("1000"),
            atr=Decimal("10"),
            stop_atr_multiple=Decimal("2"),
            account_equity=Decimal("10000"),
            available_cash=Decimal("500"),
            risk_percent=Decimal("1"),
        )
    )

    assert result.rejected is True
    assert result.rejection_reason == PositionSizingRejection.ZERO_QUANTITY
