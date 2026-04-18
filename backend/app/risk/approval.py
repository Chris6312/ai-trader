from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from app.risk.types import (
    RiskApprovalInput,
    RiskApprovalReasoning,
    RiskApprovalRejection,
    RiskApprovalResult,
)

_ONE_HUNDRED = Decimal("100")
_ZERO = Decimal("0")


class RiskApprovalService(ABC):
    @abstractmethod
    def approve(self, approval_input: RiskApprovalInput) -> RiskApprovalResult:
        ...


class DeterministicRiskApprovalService(RiskApprovalService):
    def approve(self, approval_input: RiskApprovalInput) -> RiskApprovalResult:
        open_position_count = len(approval_input.open_positions)
        current_total_exposure = sum((position.notional_value for position in approval_input.open_positions), start=_ZERO)
        current_symbol_exposure = sum(
            (
                position.notional_value
                for position in approval_input.open_positions
                if position.symbol.strip().upper() == approval_input.symbol.strip().upper()
            ),
            start=_ZERO,
        )

        daily_loss_limit_amount = approval_input.account_equity * (approval_input.max_daily_loss_percent / _ONE_HUNDRED)
        total_exposure_cap_amount = approval_input.account_equity * (approval_input.max_total_exposure_percent / _ONE_HUNDRED)
        symbol_exposure_cap_amount = approval_input.account_equity * (approval_input.max_symbol_exposure_percent / _ONE_HUNDRED)
        midpoint = (approval_input.quote_bid + approval_input.quote_ask) / Decimal("2")
        spread_amount = approval_input.quote_ask - approval_input.quote_bid
        spread_percent = (spread_amount / midpoint) * _ONE_HUNDRED if midpoint > _ZERO else Decimal("0")

        checks = {
            "quote_positive": approval_input.quote_bid > _ZERO and approval_input.quote_ask > _ZERO,
            "quote_ordered": approval_input.quote_ask >= approval_input.quote_bid,
            "quote_fresh": approval_input.quote_age_seconds <= approval_input.max_quote_age_seconds,
            "spread_within_limit": spread_percent <= approval_input.max_spread_percent,
            "max_open_positions_ok": open_position_count < approval_input.max_open_positions,
            "daily_loss_ok": approval_input.realized_pnl_today > -daily_loss_limit_amount,
            "total_exposure_ok": (current_total_exposure + approval_input.proposed_notional_value) <= total_exposure_cap_amount,
            "symbol_exposure_ok": (current_symbol_exposure + approval_input.proposed_notional_value) <= symbol_exposure_cap_amount,
        }

        computed = {
            "open_position_count": str(open_position_count),
            "current_total_exposure": str(current_total_exposure),
            "current_symbol_exposure": str(current_symbol_exposure),
            "proposed_notional_value": str(approval_input.proposed_notional_value),
            "proposed_risk_amount": str(approval_input.proposed_risk_amount),
            "daily_loss_limit_amount": str(daily_loss_limit_amount),
            "total_exposure_cap_amount": str(total_exposure_cap_amount),
            "symbol_exposure_cap_amount": str(symbol_exposure_cap_amount),
            "quote_midpoint": str(midpoint),
            "spread_amount": str(spread_amount),
            "spread_percent": str(spread_percent),
        }

        if not checks["quote_positive"] or not checks["quote_ordered"]:
            return self._reject(
                approval_input,
                checks,
                computed,
                RiskApprovalRejection.INVALID_QUOTE,
                "quote failed positivity or ordering checks",
            )

        if not checks["quote_fresh"]:
            return self._reject(
                approval_input,
                checks,
                computed,
                RiskApprovalRejection.STALE_QUOTE,
                "quote age exceeded configured freshness limit",
            )

        if not checks["spread_within_limit"]:
            return self._reject(
                approval_input,
                checks,
                computed,
                RiskApprovalRejection.SPREAD_TOO_WIDE,
                "spread exceeded configured sanity limit",
            )

        if not checks["daily_loss_ok"]:
            return self._reject(
                approval_input,
                checks,
                computed,
                RiskApprovalRejection.DAILY_LOSS_LIMIT_REACHED,
                "daily loss guard blocked new risk",
            )

        if not checks["max_open_positions_ok"]:
            return self._reject(
                approval_input,
                checks,
                computed,
                RiskApprovalRejection.MAX_OPEN_POSITIONS_EXCEEDED,
                "max open positions cap reached",
            )

        if not checks["total_exposure_ok"]:
            return self._reject(
                approval_input,
                checks,
                computed,
                RiskApprovalRejection.TOTAL_EXPOSURE_CAP_EXCEEDED,
                "total exposure cap would be exceeded",
            )

        if not checks["symbol_exposure_ok"]:
            return self._reject(
                approval_input,
                checks,
                computed,
                RiskApprovalRejection.SYMBOL_EXPOSURE_CAP_EXCEEDED,
                "symbol exposure cap would be exceeded",
            )

        reasoning = RiskApprovalReasoning(
            summary="signal approved by deterministic risk controls",
            checks=checks,
            inputs=self._inputs_dict(approval_input),
            computed=computed,
            rejection_path=[],
        )
        return RiskApprovalResult(
            symbol=approval_input.symbol,
            asset_class=approval_input.asset_class,
            approved=True,
            rejection_reason=None,
            reasoning=reasoning,
        )

    def _reject(
        self,
        approval_input: RiskApprovalInput,
        checks: dict[str, bool],
        computed: dict[str, str],
        rejection_reason: RiskApprovalRejection,
        summary: str,
    ) -> RiskApprovalResult:
        reasoning = RiskApprovalReasoning(
            summary=summary,
            checks=checks,
            inputs=self._inputs_dict(approval_input),
            computed=computed,
            rejection_path=[rejection_reason.value],
        )
        return RiskApprovalResult(
            symbol=approval_input.symbol,
            asset_class=approval_input.asset_class,
            approved=False,
            rejection_reason=rejection_reason,
            reasoning=reasoning,
        )

    def _inputs_dict(self, approval_input: RiskApprovalInput) -> dict[str, str]:
        return {
            "account_equity": str(approval_input.account_equity),
            "proposed_notional_value": str(approval_input.proposed_notional_value),
            "proposed_risk_amount": str(approval_input.proposed_risk_amount),
            "quote_bid": str(approval_input.quote_bid),
            "quote_ask": str(approval_input.quote_ask),
            "quote_age_seconds": str(approval_input.quote_age_seconds),
            "max_open_positions": str(approval_input.max_open_positions),
            "max_total_exposure_percent": str(approval_input.max_total_exposure_percent),
            "max_symbol_exposure_percent": str(approval_input.max_symbol_exposure_percent),
            "max_daily_loss_percent": str(approval_input.max_daily_loss_percent),
            "realized_pnl_today": str(approval_input.realized_pnl_today),
            "max_quote_age_seconds": str(approval_input.max_quote_age_seconds),
            "max_spread_percent": str(approval_input.max_spread_percent),
        }
