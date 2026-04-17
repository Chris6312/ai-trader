from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.brokers import BrokerError, OrderNotFoundError
from app.models import AssetClass, OrderStatus
from app.schemas.paper_api import (
    AccountSummaryResponse,
    BalanceResponse,
    OrderResponse,
    PositionResponse,
    ResetBalanceRequest,
)
from app.services.paper_accounts import PaperAccountService


router = APIRouter(prefix="/api/paper", tags=["paper-accounts"])


def get_paper_account_service(request: Request) -> PaperAccountService:
    return request.app.state.paper_account_service


@router.get("/{asset_class}/summary", response_model=AccountSummaryResponse)
def get_account_summary(
    asset_class: AssetClass,
    service: PaperAccountService = Depends(get_paper_account_service),
) -> AccountSummaryResponse:
    return AccountSummaryResponse.model_validate(service.get_account_snapshot(asset_class))


@router.get("/{asset_class}/balances", response_model=list[BalanceResponse])
def get_balances(
    asset_class: AssetClass,
    service: PaperAccountService = Depends(get_paper_account_service),
) -> list[BalanceResponse]:
    return [BalanceResponse.model_validate(balance) for balance in service.list_balances(asset_class)]


@router.get("/{asset_class}/positions", response_model=list[PositionResponse])
def get_positions(
    asset_class: AssetClass,
    service: PaperAccountService = Depends(get_paper_account_service),
) -> list[PositionResponse]:
    return [PositionResponse.model_validate(position) for position in service.list_positions(asset_class)]


@router.get("/{asset_class}/orders", response_model=list[OrderResponse])
def get_orders(
    asset_class: AssetClass,
    status_value: str | None = None,
    service: PaperAccountService = Depends(get_paper_account_service),
) -> list[OrderResponse]:
    status_filter = _parse_order_status(status_value)
    return [OrderResponse.model_validate(order) for order in service.list_orders(asset_class, status=status_filter)]


@router.post("/{asset_class}/reset-balance", response_model=AccountSummaryResponse)
def reset_balance(
    asset_class: AssetClass,
    payload: ResetBalanceRequest,
    service: PaperAccountService = Depends(get_paper_account_service),
) -> AccountSummaryResponse:
    try:
        snapshot = service.reset_balance(asset_class, payload.amount)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return AccountSummaryResponse.model_validate(snapshot)


@router.post("/{asset_class}/wipe", response_model=AccountSummaryResponse)
def wipe_account(
    asset_class: AssetClass,
    service: PaperAccountService = Depends(get_paper_account_service),
) -> AccountSummaryResponse:
    return AccountSummaryResponse.model_validate(service.wipe_account(asset_class))


@router.post("/{asset_class}/orders/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    asset_class: AssetClass,
    order_id: str,
    service: PaperAccountService = Depends(get_paper_account_service),
) -> OrderResponse:
    try:
        order = service.cancel_order(asset_class, order_id)
    except OrderNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except BrokerError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return OrderResponse.model_validate(order)


@router.post("/{asset_class}/orders/cancel-all", response_model=list[OrderResponse])
def cancel_all_open_orders(
    asset_class: AssetClass,
    service: PaperAccountService = Depends(get_paper_account_service),
) -> list[OrderResponse]:
    return [OrderResponse.model_validate(order) for order in service.cancel_all_open_orders(asset_class)]


@router.post("/{asset_class}/positions/close", response_model=list[OrderResponse])
def close_positions(
    asset_class: AssetClass,
    service: PaperAccountService = Depends(get_paper_account_service),
) -> list[OrderResponse]:
    try:
        return [OrderResponse.model_validate(order) for order in service.close_positions(asset_class)]
    except BrokerError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _parse_order_status(raw_value: str | None) -> OrderStatus | None:
    if raw_value is None:
        return None
    try:
        return OrderStatus(raw_value)
    except ValueError as exc:
        allowed_values = ", ".join(status.value for status in OrderStatus)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid order status '{raw_value}'. Allowed values: {allowed_values}.",
        ) from exc
