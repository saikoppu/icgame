from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


GamePhase = Literal["lobby", "running", "finished"]


@dataclass(frozen=True)
class BetOption:
    key: str
    label: str
    probability: float
    payout_multiplier: float


@dataclass(frozen=True)
class GameEvent:
    event_id: int
    title: str
    description: str
    options: tuple[BetOption, ...]
    bet_window_seconds: int


@dataclass
class PlayerBet:
    event_id: int
    option_key: str
    amount: int


@dataclass
class EventResult:
    event_id: int
    title: str
    outcome_key: str
    outcome_label: str


@dataclass
class PlayerEventResult:
    event_id: int
    title: str
    bet_option_key: str | None
    bet_amount: int
    outcome_key: str
    pnl_delta: float
    bankroll_after: float


@dataclass
class PlayerState:
    token: str
    name: str
    bankroll: float
    contributions: float
    current_bet: PlayerBet | None = None
    results: list[PlayerEventResult] = field(default_factory=list)

    @property
    def pnl(self) -> float:
        return self.bankroll - self.contributions
