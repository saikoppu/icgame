from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List

from .models import Action, AuctionOutcome, CancelAllAction, PlaceOrderAction, Side, Snapshot


class Strategy:
    def __init__(self, name: str) -> None:
        self.name = name

    def on_tick(self, snapshot: Snapshot) -> List[Action]:
        return []

    def on_reveal(self, snapshot: Snapshot, revealed: dict[str, str]) -> List[Action]:
        return []

    def auction_bid(self, snapshot: Snapshot) -> int:
        return 0

    def on_auction_result(self, snapshot: Snapshot, outcome: AuctionOutcome) -> List[Action]:
        return []


@dataclass
class SimpleMarketMakerConfig:
    quote_size: int = 5
    half_spread: float = 8.0
    refresh_interval: int = 5
    inventory_skew: float = 0.35
    auction_bid: int = 0


class SimpleMarketMaker(Strategy):
    def __init__(self, name: str, config: SimpleMarketMakerConfig | None = None) -> None:
        super().__init__(name)
        self.config = config or SimpleMarketMakerConfig()
        self._last_refresh = -10**9

    def on_tick(self, snapshot: Snapshot) -> List[Action]:
        if snapshot.now - self._last_refresh < self.config.refresh_interval:
            return []

        self._last_refresh = snapshot.now
        actions: List[Action] = [CancelAllAction()]

        for symbol in snapshot.contracts:
            fair = snapshot.expected_prices[symbol]
            low, high = snapshot.price_bounds[symbol]
            inventory = snapshot.positions.get(symbol, 0)

            skew = inventory * self.config.inventory_skew
            bid = math.floor(max(low, fair - self.config.half_spread - skew))
            ask = math.ceil(min(high, fair + self.config.half_spread - skew))

            if bid <= 0:
                continue
            if ask <= bid:
                ask = bid + 1
            if ask > high:
                continue

            actions.append(
                PlaceOrderAction(symbol=symbol, side=Side.BUY, price=float(bid), qty=self.config.quote_size)
            )
            actions.append(
                PlaceOrderAction(symbol=symbol, side=Side.SELL, price=float(ask), qty=self.config.quote_size)
            )

        return actions

    def on_reveal(self, snapshot: Snapshot, revealed: dict[str, str]) -> List[Action]:
        return self.on_tick(snapshot)

    def auction_bid(self, snapshot: Snapshot) -> int:
        return self.config.auction_bid
