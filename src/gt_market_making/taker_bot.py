from __future__ import annotations

import math
from dataclasses import dataclass

from .exchange import Exchange
from .models import Side


@dataclass
class TakerBotConfig:
    max_volume: int
    max_spread: float
    decay_factor: float = 0.5

    def decay(self, level_qty: int, level_index: int) -> int:
        scaled = int(math.ceil(level_qty * (self.decay_factor ** (level_index - 1))))
        return max(1, scaled)


class TakerBot:
    def __init__(self, team_name: str = "__TAKER_BOT__", config: TakerBotConfig | None = None) -> None:
        self.team_name = team_name
        self.config = config or TakerBotConfig(max_volume=12, max_spread=30.0)

    def run_for_symbol(
        self,
        exchange: Exchange,
        symbol: str,
        fair_price: float,
        bounds: tuple[float, float],
        now: int,
    ) -> int:
        total_filled = 0
        remaining_volume = self.config.max_volume
        low_bound, high_bound = bounds
        exchange.ensure_account(self.team_name)

        book = exchange.books[symbol]

        ask_levels = list(book.asks)
        for level_index, level in enumerate(ask_levels, start=1):
            if remaining_volume <= 0:
                break
            if level.price > fair_price + self.config.max_spread:
                break
            if level.price > high_bound:
                break
            qty = min(level.remaining, remaining_volume, self.config.decay(level.remaining, level_index))
            filled = exchange.execute_market_order(
                owner=self.team_name,
                symbol=symbol,
                side=Side.BUY,
                qty=qty,
                timestamp=now,
                limit_price=level.price,
            )
            remaining_volume -= filled
            total_filled += filled

        bid_levels = list(book.bids)
        for level_index, level in enumerate(bid_levels, start=1):
            if remaining_volume <= 0:
                break
            if level.price < fair_price - self.config.max_spread:
                break
            if level.price < low_bound:
                break
            qty = min(level.remaining, remaining_volume, self.config.decay(level.remaining, level_index))
            filled = exchange.execute_market_order(
                owner=self.team_name,
                symbol=symbol,
                side=Side.SELL,
                qty=qty,
                timestamp=now,
                limit_price=level.price,
            )
            remaining_volume -= filled
            total_filled += filled

        return total_filled
