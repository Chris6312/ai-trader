from decimal import Decimal

from app.risk.approval import DeterministicRiskApprovalService
from app.risk.types import OpenPositionSnapshot, RiskApprovalInput, RiskApprovalRejection


def test_risk_approval_service_approves_when_all_controls_pass() -> None:
    service = DeterministicRiskApprovalService()

    result = service.approve(
        RiskApprovalInput(
            symbol="AAPL",
            asset_class="stock",
            account_equity=Decimal("10000"),
            proposed_notional_value=Decimal("1500"),
            proposed_risk_amount=Decimal("100"),
            quote_bid=Decimal("99.95"),
            quote_ask=Decimal("100.05"),
            quote_age_seconds=10,
            open_positions=[OpenPositionSnapshot(symbol="MSFT", asset_class="stock", notional_value=Decimal("1000"))],
            max_open_positions=5,
            max_total_exposure_percent=Decimal("50"),
            max_symbol_exposure_percent=Decimal("25"),
            max_daily_loss_percent=Decimal("3"),
            realized_pnl_today=Decimal("-50"),
            max_quote_age_seconds=30,
            max_spread_percent=Decimal("0.50"),
        )
    )

    assert result.approved is True
    assert result.rejection_reason is None
    assert result.reasoning.summary == "signal approved by deterministic risk controls"
    assert result.reasoning.checks["spread_within_limit"] is True



def test_risk_approval_service_rejects_stale_quote() -> None:
    service = DeterministicRiskApprovalService()

    result = service.approve(
        RiskApprovalInput(
            symbol="BTC/USD",
            asset_class="crypto",
            account_equity=Decimal("10000"),
            proposed_notional_value=Decimal("1000"),
            proposed_risk_amount=Decimal("75"),
            quote_bid=Decimal("50000"),
            quote_ask=Decimal("50010"),
            quote_age_seconds=75,
            open_positions=[],
            max_open_positions=10,
            max_total_exposure_percent=Decimal("80"),
            max_symbol_exposure_percent=Decimal("40"),
            max_daily_loss_percent=Decimal("5"),
            max_quote_age_seconds=60,
            max_spread_percent=Decimal("1.0"),
        )
    )

    assert result.approved is False
    assert result.rejection_reason == RiskApprovalRejection.STALE_QUOTE
    assert result.reasoning.rejection_path == ["stale_quote"]



def test_risk_approval_service_rejects_total_exposure_cap_breach() -> None:
    service = DeterministicRiskApprovalService()

    result = service.approve(
        RiskApprovalInput(
            symbol="NVDA",
            asset_class="stock",
            account_equity=Decimal("10000"),
            proposed_notional_value=Decimal("2200"),
            proposed_risk_amount=Decimal("100"),
            quote_bid=Decimal("899.50"),
            quote_ask=Decimal("900.50"),
            quote_age_seconds=5,
            open_positions=[
                OpenPositionSnapshot(symbol="AAPL", asset_class="stock", notional_value=Decimal("1800")),
                OpenPositionSnapshot(symbol="MSFT", asset_class="stock", notional_value=Decimal("1500")),
            ],
            max_open_positions=5,
            max_total_exposure_percent=Decimal("50"),
            max_symbol_exposure_percent=Decimal("30"),
            max_daily_loss_percent=Decimal("3"),
            max_quote_age_seconds=30,
            max_spread_percent=Decimal("0.50"),
        )
    )

    assert result.approved is False
    assert result.rejection_reason == RiskApprovalRejection.TOTAL_EXPOSURE_CAP_EXCEEDED
    assert result.reasoning.checks["total_exposure_ok"] is False



def test_risk_approval_service_rejects_symbol_exposure_cap_breach() -> None:
    service = DeterministicRiskApprovalService()

    result = service.approve(
        RiskApprovalInput(
            symbol="ETH/USD",
            asset_class="crypto",
            account_equity=Decimal("10000"),
            proposed_notional_value=Decimal("1500"),
            proposed_risk_amount=Decimal("80"),
            quote_bid=Decimal("3000"),
            quote_ask=Decimal("3003"),
            quote_age_seconds=5,
            open_positions=[OpenPositionSnapshot(symbol="ETH/USD", asset_class="crypto", notional_value=Decimal("1200"))],
            max_open_positions=8,
            max_total_exposure_percent=Decimal("80"),
            max_symbol_exposure_percent=Decimal("25"),
            max_daily_loss_percent=Decimal("5"),
            max_quote_age_seconds=60,
            max_spread_percent=Decimal("0.50"),
        )
    )

    assert result.approved is False
    assert result.rejection_reason == RiskApprovalRejection.SYMBOL_EXPOSURE_CAP_EXCEEDED
    assert result.reasoning.checks["symbol_exposure_ok"] is False



def test_risk_approval_service_rejects_daily_loss_guard() -> None:
    service = DeterministicRiskApprovalService()

    result = service.approve(
        RiskApprovalInput(
            symbol="TSLA",
            asset_class="stock",
            account_equity=Decimal("10000"),
            proposed_notional_value=Decimal("1000"),
            proposed_risk_amount=Decimal("100"),
            quote_bid=Decimal("199.90"),
            quote_ask=Decimal("200.10"),
            quote_age_seconds=5,
            open_positions=[],
            max_open_positions=5,
            max_total_exposure_percent=Decimal("60"),
            max_symbol_exposure_percent=Decimal("25"),
            max_daily_loss_percent=Decimal("2"),
            realized_pnl_today=Decimal("-250"),
            max_quote_age_seconds=30,
            max_spread_percent=Decimal("0.50"),
        )
    )

    assert result.approved is False
    assert result.rejection_reason == RiskApprovalRejection.DAILY_LOSS_LIMIT_REACHED



def test_risk_approval_service_rejects_wide_spread() -> None:
    service = DeterministicRiskApprovalService()

    result = service.approve(
        RiskApprovalInput(
            symbol="SOL/USD",
            asset_class="crypto",
            account_equity=Decimal("10000"),
            proposed_notional_value=Decimal("1000"),
            proposed_risk_amount=Decimal("60"),
            quote_bid=Decimal("100"),
            quote_ask=Decimal("103"),
            quote_age_seconds=3,
            open_positions=[],
            max_open_positions=5,
            max_total_exposure_percent=Decimal("70"),
            max_symbol_exposure_percent=Decimal("30"),
            max_daily_loss_percent=Decimal("4"),
            max_quote_age_seconds=30,
            max_spread_percent=Decimal("1.5"),
        )
    )

    assert result.approved is False
    assert result.rejection_reason == RiskApprovalRejection.SPREAD_TOO_WIDE
