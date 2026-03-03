from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from .models import Account, Order, Side, TopOfBook, Trade


@dataclass
class _OrderBook:
    bids: List[Order]
    asks: List[Order]

    def __init__(self) -> None:
        self.bids = []
        self.asks = []

    def sort_books(self) -> None:
        self.bids.sort(key=lambda o: (-o.price, o.timestamp, o.order_id))
        self.asks.sort(key=lambda o: (o.price, o.timestamp, o.order_id))


class Exchange:
    def __init__(self, contracts: Iterable[str], position_limit: int = 100) -> None:
        self.contracts = tuple(contracts)
        self.position_limit = position_limit
        self.books: Dict[str, _OrderBook] = {symbol: _OrderBook() for symbol in self.contracts}
        self.accounts: Dict[str, Account] = {}
        self.order_owner_symbol: Dict[int, tuple[str, str]] = {}
        self._next_order_id = 1
        self.trades: List[Trade] = []

    def ensure_account(self, team: str) -> Account:
        if team not in self.accounts:
            self.accounts[team] = Account(
                cash=0.0,
                positions={symbol: 0 for symbol in self.contracts},
                open_qty={symbol: 0 for symbol in self.contracts},
            )
        return self.accounts[team]

    def top_of_book(self, symbol: str) -> TopOfBook:
        book = self.books[symbol]
        best_bid = book.bids[0].price if book.bids else None
        best_ask = book.asks[0].price if book.asks else None
        return TopOfBook(best_bid=best_bid, best_ask=best_ask)

    def all_top_of_book(self) -> Dict[str, TopOfBook]:
        return {symbol: self.top_of_book(symbol) for symbol in self.contracts}

    def adjust_cash(self, team: str, delta: float) -> None:
        account = self.ensure_account(team)
        account.cash += delta

    def place_limit_order(
        self,
        owner: str,
        symbol: str,
        side: Side,
        price: float,
        qty: int,
        timestamp: int,
        enforce_limits: bool = True,
    ) -> Optional[int]:
        if symbol not in self.books or qty <= 0 or price <= 0:
            return None

        account = self.ensure_account(owner)
        if enforce_limits and not self._within_position_limit(account, symbol, qty):
            return None

        incoming = Order(
            order_id=self._next_order_id,
            owner=owner,
            symbol=symbol,
            side=side,
            price=float(price),
            qty=qty,
            remaining=qty,
            timestamp=timestamp,
        )
        self._next_order_id += 1

        self._match_limit(incoming, timestamp=timestamp)
        if incoming.remaining > 0:
            self._rest_order(incoming)
            account.open_qty[symbol] += incoming.remaining
            self.order_owner_symbol[incoming.order_id] = (incoming.owner, incoming.symbol)
            return incoming.order_id
        return incoming.order_id

    def execute_market_order(
        self,
        owner: str,
        symbol: str,
        side: Side,
        qty: int,
        timestamp: int,
        limit_price: Optional[float] = None,
    ) -> int:
        if symbol not in self.books or qty <= 0:
            return 0

        self.ensure_account(owner)
        book = self.books[symbol]
        remaining = qty
        filled = 0

        if side is Side.BUY:
            book_side = book.asks
            while remaining > 0 and book_side:
                maker = book_side[0]
                if limit_price is not None and maker.price > limit_price:
                    break
                qty_fill = min(remaining, maker.remaining)
                self._execute_trade(symbol, maker.price, qty_fill, buyer=owner, seller=maker.owner, timestamp=timestamp)
                maker.remaining -= qty_fill
                remaining -= qty_fill
                filled += qty_fill
                self._on_resting_order_filled(maker, qty_fill)
                if maker.remaining == 0:
                    self._drop_order(maker)
                    book_side.pop(0)
        else:
            book_side = book.bids
            while remaining > 0 and book_side:
                maker = book_side[0]
                if limit_price is not None and maker.price < limit_price:
                    break
                qty_fill = min(remaining, maker.remaining)
                self._execute_trade(symbol, maker.price, qty_fill, buyer=maker.owner, seller=owner, timestamp=timestamp)
                maker.remaining -= qty_fill
                remaining -= qty_fill
                filled += qty_fill
                self._on_resting_order_filled(maker, qty_fill)
                if maker.remaining == 0:
                    self._drop_order(maker)
                    book_side.pop(0)

        return filled

    def cancel_all(self, owner: str, symbol: Optional[str] = None) -> int:
        cancelled = 0
        symbols = [symbol] if symbol else list(self.books.keys())
        account = self.ensure_account(owner)

        for sym in symbols:
            book = self.books[sym]
            before_bid = len(book.bids)
            before_ask = len(book.asks)

            retained_bids: List[Order] = []
            for order in book.bids:
                if order.owner == owner:
                    cancelled += 1
                    account.open_qty[sym] -= order.remaining
                    self._drop_order(order)
                else:
                    retained_bids.append(order)
            book.bids = retained_bids

            retained_asks: List[Order] = []
            for order in book.asks:
                if order.owner == owner:
                    cancelled += 1
                    account.open_qty[sym] -= order.remaining
                    self._drop_order(order)
                else:
                    retained_asks.append(order)
            book.asks = retained_asks

            if before_bid != len(book.bids) or before_ask != len(book.asks):
                book.sort_books()

        return cancelled

    def mark_to_market(self, team: str, marks: Dict[str, float]) -> float:
        account = self.ensure_account(team)
        pnl = account.cash
        for symbol, mark in marks.items():
            pnl += account.positions.get(symbol, 0) * mark
        return pnl

    def _within_position_limit(self, account: Account, symbol: str, new_qty: int) -> bool:
        exposure = abs(account.position(symbol)) + account.outstanding(symbol) + new_qty
        return exposure <= self.position_limit

    def _match_limit(self, incoming: Order, timestamp: int) -> None:
        book = self.books[incoming.symbol]

        if incoming.side is Side.BUY:
            opposite = book.asks
            while incoming.remaining > 0 and opposite and opposite[0].price <= incoming.price:
                maker = opposite[0]
                qty_fill = min(incoming.remaining, maker.remaining)
                self._execute_trade(
                    incoming.symbol,
                    maker.price,
                    qty_fill,
                    buyer=incoming.owner,
                    seller=maker.owner,
                    timestamp=timestamp,
                )
                incoming.remaining -= qty_fill
                maker.remaining -= qty_fill
                self._on_resting_order_filled(maker, qty_fill)
                if maker.remaining == 0:
                    self._drop_order(maker)
                    opposite.pop(0)
        else:
            opposite = book.bids
            while incoming.remaining > 0 and opposite and opposite[0].price >= incoming.price:
                maker = opposite[0]
                qty_fill = min(incoming.remaining, maker.remaining)
                self._execute_trade(
                    incoming.symbol,
                    maker.price,
                    qty_fill,
                    buyer=maker.owner,
                    seller=incoming.owner,
                    timestamp=timestamp,
                )
                incoming.remaining -= qty_fill
                maker.remaining -= qty_fill
                self._on_resting_order_filled(maker, qty_fill)
                if maker.remaining == 0:
                    self._drop_order(maker)
                    opposite.pop(0)

    def _rest_order(self, order: Order) -> None:
        book = self.books[order.symbol]
        side = book.bids if order.side is Side.BUY else book.asks
        side.append(order)
        book.sort_books()

    def _execute_trade(self, symbol: str, price: float, qty: int, buyer: str, seller: str, timestamp: int) -> None:
        buyer_account = self.ensure_account(buyer)
        seller_account = self.ensure_account(seller)

        cash_flow = price * qty
        buyer_account.cash -= cash_flow
        seller_account.cash += cash_flow

        buyer_account.positions[symbol] = buyer_account.positions.get(symbol, 0) + qty
        seller_account.positions[symbol] = seller_account.positions.get(symbol, 0) - qty

        self.trades.append(
            Trade(
                symbol=symbol,
                price=price,
                qty=qty,
                buyer=buyer,
                seller=seller,
                timestamp=timestamp,
            )
        )

    def _drop_order(self, order: Order) -> None:
        self.order_owner_symbol.pop(order.order_id, None)

    def _on_resting_order_filled(self, maker: Order, qty_fill: int) -> None:
        maker_account = self.ensure_account(maker.owner)
        maker_account.open_qty[maker.symbol] -= qty_fill
        if maker_account.open_qty[maker.symbol] < 0:
            maker_account.open_qty[maker.symbol] = 0
