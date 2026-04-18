from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.brokers import BrokerInterface, CryptoPaperBroker, OrderRequest, StockPaperBroker
from app.brokers.paper_models import BalanceSnapshot
from app.models import Account, AccountType, AssetClass, Balance, OrderSide, OrderStatus, OrderType


logger = logging.getLogger(__name__)

DEFAULT_INITIAL_CASH = Decimal("100000")
ZERO = Decimal("0")


@dataclass(slots=True)
class PaperAccountRuntime:
    asset_class: AssetClass
    broker_factory: Callable[[Decimal], BrokerInterface]
    default_initial_cash: Decimal
    broker: BrokerInterface


class PaperAccountService:
    def __init__(
        self,
        *,
        stock_initial_cash: Decimal = DEFAULT_INITIAL_CASH,
        crypto_initial_cash: Decimal = DEFAULT_INITIAL_CASH,
        db_session_factory: Callable[[], Session] | None = None,
    ) -> None:
        self._db_session_factory = db_session_factory
        self._runtimes: dict[AssetClass, PaperAccountRuntime] = {
            AssetClass.STOCK: self._build_runtime(
                asset_class=AssetClass.STOCK,
                initial_cash=stock_initial_cash,
            ),
            AssetClass.CRYPTO: self._build_runtime(
                asset_class=AssetClass.CRYPTO,
                initial_cash=crypto_initial_cash,
            ),
        }
        self._hydrate_from_db()

    def get_account_snapshot(self, asset_class: AssetClass):
        return self._get_broker(asset_class).get_account_snapshot()

    def list_balances(self, asset_class: AssetClass):
        return [self._get_broker(asset_class).get_balance()]

    def list_positions(self, asset_class: AssetClass):
        return self._get_broker(asset_class).list_positions()

    def list_orders(self, asset_class: AssetClass, *, status: OrderStatus | None = None):
        return self._get_broker(asset_class).list_orders(status=status)

    def reset_balance(self, asset_class: AssetClass, amount: Decimal):
        if amount <= ZERO:
            raise ValueError("Reset amount must be greater than zero.")

        runtime = self._runtimes[asset_class]
        runtime.broker = runtime.broker_factory(amount)
        self._persist_balance(asset_class)
        self._audit("reset_balance", asset_class, amount=str(amount))
        return runtime.broker.get_account_snapshot()

    def wipe_account(self, asset_class: AssetClass):
        runtime = self._runtimes[asset_class]
        runtime.broker = runtime.broker_factory(runtime.default_initial_cash)
        self._persist_balance(asset_class)
        self._audit("wipe_account", asset_class, reset_to=str(runtime.default_initial_cash))
        return runtime.broker.get_account_snapshot()

    def cancel_order(self, asset_class: AssetClass, order_id: str):
        order = self._get_broker(asset_class).cancel_order(order_id)
        self._persist_balance(asset_class)
        self._audit("cancel_order", asset_class, order_id=order_id)
        return order

    def cancel_all_open_orders(self, asset_class: AssetClass):
        broker = self._get_broker(asset_class)
        canceled = []
        for order in broker.list_orders(status=OrderStatus.OPEN):
            canceled.append(broker.cancel_order(order.id))

        self._persist_balance(asset_class)
        self._audit("cancel_all_open_orders", asset_class, canceled_count=str(len(canceled)))
        return canceled

    def close_positions(self, asset_class: AssetClass):
        broker = self._get_broker(asset_class)
        canceled_orders = self.cancel_all_open_orders(asset_class)
        closing_orders = []

        for position in broker.list_positions():
            close_quantity = position.quantity - position.reserved_quantity
            if close_quantity <= ZERO:
                continue

            order = broker.place_order(
                OrderRequest(
                    symbol=position.symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=close_quantity,
                ),
                fill_price=position.market_price,
            )
            closing_orders.append(order)

        self._persist_balance(asset_class)
        self._audit(
            "close_positions",
            asset_class,
            canceled_count=str(len(canceled_orders)),
            closed_count=str(len(closing_orders)),
        )
        return closing_orders

    def get_broker(self, asset_class: AssetClass) -> BrokerInterface:
        return self._get_broker(asset_class)

    def _get_broker(self, asset_class: AssetClass) -> BrokerInterface:
        return self._runtimes[asset_class].broker

    def _build_runtime(self, *, asset_class: AssetClass, initial_cash: Decimal) -> PaperAccountRuntime:
        factory: Callable[[Decimal], BrokerInterface]
        if asset_class is AssetClass.STOCK:
            factory = lambda cash: StockPaperBroker(initial_cash=cash)
        else:
            factory = lambda cash: CryptoPaperBroker(initial_cash=cash)

        return PaperAccountRuntime(
            asset_class=asset_class,
            broker_factory=factory,
            default_initial_cash=initial_cash,
            broker=factory(initial_cash),
        )

    def _hydrate_from_db(self) -> None:
        if self._db_session_factory is None:
            return

        try:
            with self._db_session_factory() as db:
                for asset_class, runtime in self._runtimes.items():
                    account = self._get_or_create_account(db, asset_class, runtime.default_initial_cash)
                    balance = self._get_or_create_balance(db, account, runtime.default_initial_cash)
                    runtime.broker = runtime.broker_factory(balance.total)
                    self._apply_balance_snapshot(runtime.broker, balance)
                db.commit()
        except Exception as exc:  # pragma: no cover - defensive startup fallback
            logger.warning("Unable to hydrate paper account runtime from DB: %s", exc)

    def _persist_balance(self, asset_class: AssetClass) -> None:
        if self._db_session_factory is None:
            return

        runtime = self._runtimes[asset_class]
        snapshot = runtime.broker.get_balance()

        try:
            with self._db_session_factory() as db:
                account = self._get_or_create_account(db, asset_class, runtime.default_initial_cash)
                balance = self._get_or_create_balance(db, account, runtime.default_initial_cash)
                balance.total = snapshot.total
                balance.available = snapshot.available
                balance.reserved = snapshot.reserved
                balance.updated_at = snapshot.updated_at
                db.commit()
        except Exception as exc:  # pragma: no cover - defensive persistence fallback
            logger.warning("Unable to persist paper account balance for %s: %s", asset_class.value, exc)

    def _get_or_create_account(self, db: Session, asset_class: AssetClass, default_initial_cash: Decimal) -> Account:
        account = db.execute(
            select(Account).where(
                Account.account_type == AccountType.PAPER,
                Account.asset_class == asset_class,
            )
        ).scalar_one_or_none()
        if account is None:
            account = Account(
                name=f"{asset_class.value}-paper",
                account_type=AccountType.PAPER,
                asset_class=asset_class,
                base_currency="USD",
                is_active=True,
            )
            db.add(account)
            db.flush()
            self._get_or_create_balance(db, account, default_initial_cash)
        return account

    def _get_or_create_balance(self, db: Session, account: Account, default_initial_cash: Decimal) -> Balance:
        balance = db.execute(
            select(Balance).where(
                Balance.account_id == account.id,
                Balance.currency == account.base_currency,
            )
        ).scalar_one_or_none()
        if balance is None:
            balance = Balance(
                account_id=account.id,
                currency=account.base_currency,
                total=default_initial_cash,
                available=default_initial_cash,
                reserved=ZERO,
            )
            db.add(balance)
            db.flush()
        return balance

    def _apply_balance_snapshot(self, broker: BrokerInterface, balance: Balance) -> None:
        if not hasattr(broker, "_balance"):
            return
        setattr(
            broker,
            "_balance",
            BalanceSnapshot(
                currency=balance.currency,
                total=balance.total,
                available=balance.available,
                reserved=balance.reserved,
                updated_at=balance.updated_at,
            ),
        )

    def _audit(self, action: str, asset_class: AssetClass, **details: str) -> None:
        logger.info(
            "PAPER_ACCOUNT_CONTROL action=%s asset_class=%s details=%s",
            action,
            asset_class.value,
            details,
        )
