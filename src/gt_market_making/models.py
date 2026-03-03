from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, Optional


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

    @property
    def opposite(self) -> "Side":
        return Side.SELL if self is Side.BUY else Side.BUY


@dataclass(frozen=True)
class Card:
    rank: str
    suit: str


@dataclass
class Order:
    order_id: int
    owner: str
    symbol: str
    side: Side
    price: float
    qty: int
    remaining: int
    timestamp: int


@dataclass(frozen=True)
class Trade:
    symbol: str
    price: float
    qty: int
    buyer: str
    seller: str
    timestamp: int


@dataclass(frozen=True)
class PlaceOrderAction:
    symbol: str
    side: Side
    price: float
    qty: int


@dataclass(frozen=True)
class CancelAllAction:
    symbol: Optional[str] = None


Action = PlaceOrderAction | CancelAllAction


@dataclass
class Account:
    cash: float = 0.0
    positions: Dict[str, int] = field(default_factory=dict)
    open_qty: Dict[str, int] = field(default_factory=dict)

    def position(self, symbol: str) -> int:
        return self.positions.get(symbol, 0)

    def outstanding(self, symbol: str) -> int:
        return self.open_qty.get(symbol, 0)


@dataclass(frozen=True)
class TopOfBook:
    best_bid: Optional[float]
    best_ask: Optional[float]


@dataclass
class Snapshot:
    team: str
    now: int
    duration: int
    contracts: tuple[str, ...]
    top_of_book: Dict[str, TopOfBook]
    positions: Dict[str, int]
    cash: float
    public_reveals: Dict[str, list[str]]
    expected_prices: Dict[str, float]
    price_bounds: Dict[str, tuple[float, float]]
    private_draws: Dict[str, Dict[int, str]]


@dataclass(frozen=True)
class AuctionOutcome:
    winner: Optional[str]
    winning_bid: int
    bids: Dict[str, int]
    private_draws: Dict[str, Dict[int, str]]


def empty_position_map(symbols: Iterable[str]) -> Dict[str, int]:
    return {symbol: 0 for symbol in symbols}
