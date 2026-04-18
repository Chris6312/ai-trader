from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal, ROUND_DOWN

from app.risk.types import (
    PositionSizingInput,
    PositionSizingReasoning,
    PositionSizingRejection,
    PositionSizingResult,
)

_STOCK_QUANTITY_STEP = Decimal("1")
_CRYPTO_QUANTITY_STEP = Decimal("0.00000001")
_ONE_HUNDRED = Decimal("100")
_ZERO = Decimal("0")


class PositionSizer(ABC):
    @abstractmethod
    def size_position(self, sizing_input: PositionSizingInput) -> PositionSizingResult:
        ...


class AtrPositionSizer(PositionSizer):
    def size_position(self, sizing_input: PositionSizingInput) -> PositionSizingResult:
        checks = {
            "entry_price_positive": sizing_input.entry_price > _ZERO,
            "atr_positive": sizing_input.atr > _ZERO,
            "stop_multiple_positive": sizing_input.stop_atr_multiple > _ZERO,
            "risk_percent_positive": sizing_input.risk_percent > _ZERO,
        }

        if not checks["entry_price_positive"]:
            return self._reject(sizing_input, checks, PositionSizingRejection.INVALID_ENTRY_PRICE, "entry price must be positive")

        if not checks["atr_positive"]:
            return self._reject(sizing_input, checks, PositionSizingRejection.INVALID_ATR, "atr must be positive")

        if not checks["stop_multiple_positive"]:
            return self._reject(sizing_input, checks, PositionSizingRejection.INVALID_STOP_MULTIPLE, "stop multiple must be positive")

        if not checks["risk_percent_positive"]:
            return self._reject(sizing_input, checks, PositionSizingRejection.INVALID_RISK_PERCENT, "risk percent must be positive")

        risk_budget = sizing_input.account_equity * (sizing_input.risk_percent / _ONE_HUNDRED)
        if risk_budget <= _ZERO:
            return self._reject(sizing_input, checks, PositionSizingRejection.ZERO_RISK_BUDGET, "risk budget resolved to zero")

        stop_distance = sizing_input.atr * sizing_input.stop_atr_multiple
        fee_buffer = sizing_input.entry_price * (sizing_input.fee_buffer_percent / _ONE_HUNDRED)
        risk_per_unit = stop_distance + fee_buffer
        stop_price = sizing_input.entry_price - stop_distance

        raw_quantity = risk_budget / risk_per_unit
        capped_quantity = raw_quantity
        caps_applied: list[str] = []

        cash_capped_quantity = sizing_input.available_cash / sizing_input.entry_price
        if cash_capped_quantity < capped_quantity:
            capped_quantity = cash_capped_quantity
            caps_applied.append("available_cash")

        if sizing_input.max_position_notional_percent is not None:
            max_notional = sizing_input.account_equity * (sizing_input.max_position_notional_percent / _ONE_HUNDRED)
            if max_notional > _ZERO:
                exposure_capped_quantity = max_notional / sizing_input.entry_price
                if exposure_capped_quantity < capped_quantity:
                    capped_quantity = exposure_capped_quantity
                    caps_applied.append("max_position_notional")

        quantity = self._quantize_quantity(capped_quantity, sizing_input.asset_class)
        if quantity <= _ZERO:
            return self._reject(sizing_input, checks, PositionSizingRejection.ZERO_QUANTITY, "sizing resulted in zero quantity")

        notional_value = quantity * sizing_input.entry_price
        realized_risk = quantity * risk_per_unit

        reasoning = PositionSizingReasoning(
            summary="position sized from ATR-normalized stop distance",
            checks=checks,
            inputs={
                "entry_price": str(sizing_input.entry_price),
                "atr": str(sizing_input.atr),
                "stop_atr_multiple": str(sizing_input.stop_atr_multiple),
                "account_equity": str(sizing_input.account_equity),
                "available_cash": str(sizing_input.available_cash),
                "risk_percent": str(sizing_input.risk_percent),
                "fee_buffer_percent": str(sizing_input.fee_buffer_percent),
                "max_position_notional_percent": str(sizing_input.max_position_notional_percent),
            },
            computed={
                "risk_budget": str(risk_budget),
                "stop_distance": str(stop_distance),
                "fee_buffer_per_unit": str(fee_buffer),
                "risk_per_unit": str(risk_per_unit),
                "raw_quantity": str(raw_quantity),
                "final_quantity": str(quantity),
                "stop_price": str(stop_price),
                "notional_value": str(notional_value),
                "realized_risk": str(realized_risk),
            },
            caps_applied=caps_applied,
        )

        return PositionSizingResult(
            symbol=sizing_input.symbol,
            asset_class=sizing_input.asset_class,
            quantity=quantity,
            stop_price=stop_price,
            risk_amount=realized_risk,
            risk_per_unit=risk_per_unit,
            notional_value=notional_value,
            rejected=False,
            rejection_reason=None,
            reasoning=reasoning,
        )

    def _reject(
        self,
        sizing_input: PositionSizingInput,
        checks: dict[str, bool],
        rejection_reason: PositionSizingRejection,
        summary: str,
    ) -> PositionSizingResult:
        reasoning = PositionSizingReasoning(
            summary=summary,
            checks=checks,
            inputs={
                "entry_price": str(sizing_input.entry_price),
                "atr": str(sizing_input.atr),
                "stop_atr_multiple": str(sizing_input.stop_atr_multiple),
                "account_equity": str(sizing_input.account_equity),
                "available_cash": str(sizing_input.available_cash),
                "risk_percent": str(sizing_input.risk_percent),
                "fee_buffer_percent": str(sizing_input.fee_buffer_percent),
                "max_position_notional_percent": str(sizing_input.max_position_notional_percent),
            },
            computed={},
            caps_applied=[],
        )
        return PositionSizingResult(
            symbol=sizing_input.symbol,
            asset_class=sizing_input.asset_class,
            quantity=_ZERO,
            stop_price=_ZERO,
            risk_amount=_ZERO,
            risk_per_unit=_ZERO,
            notional_value=_ZERO,
            rejected=True,
            rejection_reason=rejection_reason,
            reasoning=reasoning,
        )

    def _quantize_quantity(self, quantity: Decimal, asset_class: str) -> Decimal:
        normalized_asset_class = asset_class.strip().lower()
        step = _CRYPTO_QUANTITY_STEP if normalized_asset_class == "crypto" else _STOCK_QUANTITY_STEP
        return quantity.quantize(step, rounding=ROUND_DOWN)
