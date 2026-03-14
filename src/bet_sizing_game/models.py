from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


GamePhase = Literal["lobby", "events", "fermi", "finished"]


@dataclass(frozen=True)
class GameEvent:
    event_id: int
    title: str
    description: str
    true_probability: float
    odds_numerator: float
    odds_denominator: float
    bet_window_seconds: int
    signal_enabled: bool = True
    signal_quality: float = 0.65
    signal_reserve_multiplier: float = 1.0


@dataclass(frozen=True)
class FermiQuestion:
    question_id: int
    prompt: str
    true_value: float
    unit: str
    answer_window_seconds: int


@dataclass
class PlayerBet:
    event_id: int
    base_amount: float
    amount: float
    double_down: bool = False
    insurance: bool = False
    volatility: bool = False
    insurance_premium: float = 0.0


@dataclass
class EventResult:
    event_id: int
    title: str
    outcome_hit: bool
    outcome_label: str
    odds_label: str


@dataclass
class FermiResult:
    question_id: int
    prompt: str
    true_value: float
    unit: str
    valid_guess_count: int
    eligible_count: int


@dataclass
class PlayerEventResult:
    event_id: int
    title: str
    base_bet_amount: float
    bet_amount: float
    double_down_used: bool
    insurance_used: bool
    volatility_used: bool
    volatility_multiplier: float | None
    volatility_carry_cost: float
    insurance_premium: float
    insurance_refund: float
    signal_bid: float
    signal_hint: str | None
    outcome_hit: bool
    pnl_delta: float
    bankroll_after: float
    rebuy_applied: bool


@dataclass
class PlayerFermiResult:
    question_id: int
    prompt: str
    guess: float | None
    true_value: float
    unit: str
    eligible_for_percentile: bool
    counted_in_percentile: bool
    percentile: float
    boost_pct: float
    bankroll_after: float


@dataclass
class PlayerState:
    token: str
    name: str
    bankroll: float
    contributions: float
    current_bet: PlayerBet | None = None
    current_fermi_guess: float | None = None
    current_signal_hint: str | None = None
    current_signal_bid: float = 0.0
    current_signal_event_id: int | None = None
    signal_spend_total: float = 0.0
    double_down_available: int = 1
    insurance_available: int = 1
    volatility_available: int = 1
    volatility_hold_cost_paid: float = 0.0
    current_round_volatility_carry_cost: float = 0.0
    current_round_pre_bet_rebuy: bool = False
    ever_busted: bool = False
    bust_count: int = 0
    results: list[PlayerEventResult] = field(default_factory=list)
    fermi_results: list[PlayerFermiResult] = field(default_factory=list)

    @property
    def pnl(self) -> float:
        return self.bankroll - self.contributions
