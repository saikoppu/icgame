from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
import random
from typing import Any
from uuid import uuid4

from .models import (
    EventResult,
    FermiQuestion,
    FermiResult,
    GameEvent,
    GamePhase,
    PlayerBet,
    PlayerEventResult,
    PlayerFermiResult,
    PlayerState,
)


def _event(
    event_id: int,
    title: str,
    description: str,
    true_probability: float,
    odds_numerator: float,
    odds_denominator: float,
    bet_window_seconds: int,
    signal_enabled: bool = True,
    signal_quality: float = 0.65,
    signal_reserve_multiplier: float = 1.0,
) -> GameEvent:
    return GameEvent(
        event_id=event_id,
        title=title,
        description=description,
        true_probability=max(0.01, min(0.99, float(true_probability))),
        odds_numerator=max(0.01, float(odds_numerator)),
        odds_denominator=max(0.01, float(odds_denominator)),
        bet_window_seconds=max(5, int(bet_window_seconds)),
        signal_enabled=bool(signal_enabled),
        signal_quality=max(0.1, min(1.0, float(signal_quality))),
        signal_reserve_multiplier=max(0.2, float(signal_reserve_multiplier)),
    )


def _fermi_question(question_id: int, prompt: str, true_value: float, unit: str, answer_window_seconds: int) -> FermiQuestion:
    return FermiQuestion(
        question_id=question_id,
        prompt=prompt,
        true_value=float(true_value),
        unit=unit,
        answer_window_seconds=max(8, int(answer_window_seconds)),
    )


def default_events() -> list[GameEvent]:
    # Scattered difficulty and odds (not monotonic by round).
    return [
        _event(1, "Coin Flip", "A fair coin lands heads.", 0.50, 6, 5, 22, signal_quality=0.35, signal_reserve_multiplier=0.9),
        _event(2, "Dice High Sum", "Two fair dice sum to at least 10.", 6.0 / 36.0, 5, 1, 24, signal_quality=0.55, signal_reserve_multiplier=1.0),
        _event(3, "Distinct Triple", "Three fair dice are all distinct.", (6.0 * 5.0 * 4.0) / (6.0**3), 39, 50, 24, signal_quality=0.45, signal_reserve_multiplier=0.9),
        _event(4, "One Six Exactly", "Four fair dice have exactly one 6.", 4.0 * (1.0 / 6.0) * ((5.0 / 6.0) ** 3), 2, 1, 25, signal_quality=0.6),
        _event(5, "Ace In Two", "Two cards include at least one ace.", 1.0 - ((48.0 / 52.0) * (47.0 / 51.0)), 8, 1, 25, signal_quality=0.8, signal_reserve_multiplier=1.1),
        _event(6, "Two Heads In Four", "Exactly two heads in four fair coin flips.", 6.0 / 16.0, 2, 1, 26, signal_quality=0.5),
        _event(7, "Color Match", "Two cards are the same color.", 50.0 / 102.0, 1, 1, 26, signal_quality=0.35, signal_reserve_multiplier=0.8),
        _event(8, "Prime Sum", "Two fair dice have a prime sum.", 15.0 / 36.0, 2, 1, 27, signal_quality=0.6),
        _event(9, "Tail Risk", "At least 4 heads in 5 fair coin flips.", 6.0 / 32.0, 6, 1, 27, signal_quality=0.85, signal_reserve_multiplier=1.2),
        _event(10, "One Red", "Exactly one red card in 3 draws.", (26.0 * 26.0 * 25.0 * 3.0) / (52.0 * 51.0 * 50.0), 2, 1, 28, signal_quality=0.55),
        _event(11, "Face Pair", "Two cards are both face cards.", (12.0 / 52.0) * (11.0 / 51.0), 25, 1, 30, signal_quality=0.9, signal_reserve_multiplier=1.25),
        _event(12, "Final EV Check", "Three fair dice sum to at least 13.", 56.0 / 216.0, 9, 2, 32, signal_quality=0.7),
        _event(13, "Ace In Four", "Four cards include at least one ace.", 1.0 - ((48.0 / 52.0) * (47.0 / 51.0) * (46.0 / 50.0) * (45.0 / 49.0)), 4, 1, 30, signal_quality=0.75),
        _event(14, "Two Heads In Three", "Exactly two heads in three fair coin flips.", 3.0 / 8.0, 8, 5, 29, signal_quality=0.5, signal_reserve_multiplier=0.95),
        _event(15, "Same Suit Triple", "Three drawn cards are all the same suit.", (12.0 / 51.0) * (11.0 / 50.0), 26, 1, 33, signal_quality=0.9, signal_reserve_multiplier=1.3),
    ]


def default_fermi_questions() -> list[FermiQuestion]:
    return []


def default_rules() -> list[str]:
    return [
        "This build is single-player: only one player can join each game instance at a time.",
        "All players start with $1000 and place bets across 15 probabilistic events.",
        "Each betting round has one proposition with fixed posted odds (for example 3:1).",
        "You only choose how much to stake on that proposition; no side-selection market is used.",
        "Posted odds vary by round: some are fair or slightly negative EV, most are positive EV, and a few are high-volatility.",
        "Decimal bet sizing is allowed and minimum bet is $0.",
        "You have one Double Down card per game: it doubles stake/risk on a chosen round.",
        "You have one Insurance card per game: it charges a premium and refunds 50% of the losing stake.",
        "You have one Volatility Regime card per game: if used on a round, your win payout uses a fixed 1.50x multiplier.",
        "To hold an unused Volatility card, you pay a fixed $100 carry cost each event round until the card is used.",
        "Event outcomes are randomized server-side and every player receives the same outcome each round.",
        "If your bankroll hits $0 at any point, it is auto-reset to $500 so everyone can keep playing.",
        "You can start the game directly from lobby after joining.",
        "Final score is your ending bankroll; use trade history for round-by-round review.",
    ]


class GameEngine:
    def __init__(
        self,
        *,
        seed: int = 2026,
        lobby_seconds: int = 30,
        starting_bankroll: int = 1_000,
        round_stipend: int = 0,
        bust_rebuy_amount: int = 500,
        access_code: str = "quant",
        max_players: int = 1,
        double_down_uses: int = 1,
        insurance_uses: int = 1,
        volatility_uses: int = 1,
        volatility_hold_cost: float = 100.0,
        volatility_profit_multiplier: float = 1.5,
        insurance_premium_pct: float = 0.12,
        insurance_refund_pct: float = 0.5,
        signal_stake_cap_fraction: float = 0.35,
        events: list[GameEvent] | None = None,
        fermi_questions: list[FermiQuestion] | None = None,
    ) -> None:
        self.seed = seed
        self._rng = random.Random(seed)
        self.lobby_seconds = max(5, int(lobby_seconds))
        self.starting_bankroll = float(starting_bankroll)
        self.round_stipend = float(round_stipend)
        self.bust_rebuy_amount = float(max(1, int(bust_rebuy_amount)))
        self.access_code = access_code.strip() or "quant"
        self.max_players = max(1, int(max_players))
        self.double_down_uses = max(0, int(double_down_uses))
        self.insurance_uses = max(0, int(insurance_uses))
        self.volatility_uses = max(0, int(volatility_uses))
        self.volatility_hold_cost = max(0.0, round(float(volatility_hold_cost), 2))
        self.volatility_profit_multiplier = max(0.01, float(volatility_profit_multiplier))
        self.insurance_premium_pct = max(0.0, float(insurance_premium_pct))
        self.insurance_refund_pct = max(0.0, min(1.0, float(insurance_refund_pct)))
        self.signal_stake_cap_fraction = max(0.05, min(0.95, float(signal_stake_cap_fraction)))

        self.events = list(events) if events else default_events()
        self.fermi_questions = list(fermi_questions) if fermi_questions else default_fermi_questions()
        self.rules = default_rules()

        self.phase: GamePhase = "lobby"
        self.paused = False

        self.players: dict[str, PlayerState] = {}
        self.event_history: list[EventResult] = []
        self.fermi_history: list[FermiResult] = []

        self.current_event_index = -1
        self.current_fermi_index = -1
        self.event_deadline: datetime | None = None
        self.fermi_deadline: datetime | None = None

    @property
    def current_event(self) -> GameEvent | None:
        if 0 <= self.current_event_index < len(self.events):
            return self.events[self.current_event_index]
        return None

    @property
    def current_fermi_question(self) -> FermiQuestion | None:
        if 0 <= self.current_fermi_index < len(self.fermi_questions):
            return self.fermi_questions[self.current_fermi_index]
        return None

    def _require_lobby(self) -> None:
        if self.phase != "lobby":
            raise ValueError("This action is only allowed during lobby.")

    def _event_index_by_id(self, event_id: int) -> int:
        for idx, event in enumerate(self.events):
            if event.event_id == event_id:
                return idx
        raise ValueError(f"Unknown event_id: {event_id}")

    def _fermi_index_by_id(self, question_id: int) -> int:
        for idx, question in enumerate(self.fermi_questions):
            if question.question_id == question_id:
                return idx
        raise ValueError(f"Unknown question_id: {question_id}")

    def _odds_label(self, event: GameEvent) -> str:
        return f"{event.odds_numerator:g}:{event.odds_denominator:g}"

    def join_player(self, raw_name: str) -> PlayerState:
        if self.phase != "lobby":
            raise ValueError("The game is already running. New players can only join during lobby.")

        name = (raw_name or "").strip()
        if not name:
            raise ValueError("Name is required.")

        if len(self.players) >= self.max_players:
            raise ValueError(f"Player limit reached ({self.max_players}).")

        existing_names = {player.name.lower() for player in self.players.values()}
        base_name = name
        suffix = 2
        while name.lower() in existing_names:
            name = f"{base_name} #{suffix}"
            suffix += 1

        token = uuid4().hex
        player = PlayerState(
            token=token,
            name=name,
            bankroll=self.starting_bankroll,
            contributions=self.starting_bankroll,
            double_down_available=self.double_down_uses,
            insurance_available=self.insurance_uses,
            volatility_available=self.volatility_uses,
        )
        self.players[token] = player
        return player

    def place_bet(
        self,
        token: str,
        amount: float,
        *,
        use_double_down: bool = False,
        use_insurance: bool = False,
        use_volatility: bool = False,
    ) -> PlayerBet | None:
        if self.phase != "events":
            raise ValueError("Betting is closed right now.")

        event = self.current_event
        if event is None:
            raise ValueError("No active event.")

        player = self.players.get(token)
        if player is None:
            raise ValueError("Unknown player session.")

        amount_f = round(float(amount), 2)
        if amount_f < 0:
            raise ValueError("Bet amount must be >= 0.")

        if player.current_bet is not None and player.current_bet.event_id == event.event_id:
            prior = player.current_bet
            player.bankroll += prior.amount + prior.insurance_premium
            if prior.double_down:
                player.double_down_available += 1
            if prior.insurance:
                player.insurance_available += 1
            if prior.volatility:
                player.volatility_available += 1

        if amount_f == 0:
            player.current_bet = None
            return None

        if use_double_down and player.double_down_available <= 0:
            raise ValueError("Double Down card already used.")
        if use_insurance and player.insurance_available <= 0:
            raise ValueError("Insurance card already used.")
        if use_volatility and player.volatility_available <= 0:
            raise ValueError("Volatility card already used.")

        effective_amount = round(amount_f * (2.0 if use_double_down else 1.0), 2)
        insurance_premium = round(effective_amount * self.insurance_premium_pct, 2) if use_insurance else 0.0
        total_cost = effective_amount + insurance_premium

        if total_cost > player.bankroll + 1e-9:
            raise ValueError("Insufficient bankroll.")

        player.bankroll -= total_cost
        if use_double_down:
            player.double_down_available -= 1
        if use_insurance:
            player.insurance_available -= 1
        if use_volatility:
            player.volatility_available -= 1

        player.current_bet = PlayerBet(
            event_id=event.event_id,
            base_amount=amount_f,
            amount=effective_amount,
            double_down=use_double_down,
            insurance=use_insurance,
            volatility=use_volatility,
            insurance_premium=insurance_premium,
        )
        return player.current_bet

    def _signal_reserve(self, player: PlayerState, event: GameEvent) -> float:
        odds_ratio = event.odds_numerator / event.odds_denominator
        breakeven_prob = 1.0 / (1.0 + odds_ratio)
        edge = abs(event.true_probability - breakeven_prob)
        voi = player.bankroll * self.signal_stake_cap_fraction * edge * event.signal_quality
        reserve = round(voi * event.signal_reserve_multiplier, 2)
        floor = 5.0
        cap = max(10.0, player.bankroll * 0.25)
        return max(floor, min(cap, reserve))

    def _signal_hint(self, event: GameEvent) -> str:
        p = event.true_probability
        odds_ratio = event.odds_numerator / event.odds_denominator
        breakeven_prob = 1.0 / (1.0 + odds_ratio)

        if event.signal_quality < 0.45:
            direction = "above" if p >= breakeven_prob else "below"
            return f"Signal: true probability is likely {direction} breakeven."

        if event.signal_quality < 0.75:
            spread = 0.12
            lo = max(0.01, p - spread)
            hi = min(0.99, p + spread)
            return f"Signal: estimated probability band is [{lo:.2f}, {hi:.2f}]."

        spread = 0.06
        lo = max(0.01, p - spread)
        hi = min(0.99, p + spread)
        return f"Signal: tight estimate is [{lo:.2f}, {hi:.2f}] (high confidence)."

    def purchase_signal(self, token: str, bid: float) -> dict[str, Any]:
        if self.phase != "events":
            raise ValueError("Signals are only available during betting rounds.")

        event = self.current_event
        if event is None:
            raise ValueError("No active event.")
        if not event.signal_enabled:
            raise ValueError("Signal purchase disabled for this round.")

        player = self.players.get(token)
        if player is None:
            raise ValueError("Unknown player session.")
        if player.current_signal_event_id == event.event_id and player.current_signal_hint is not None:
            raise ValueError("Signal already purchased for this round.")

        bid_f = round(float(bid), 2)
        if bid_f <= 0:
            raise ValueError("Bid must be positive.")
        if bid_f > player.bankroll + 1e-9:
            raise ValueError("Insufficient bankroll.")

        reserve = self._signal_reserve(player, event)
        if bid_f < reserve:
            raise ValueError("Bid did not meet the hidden reserve.")

        player.bankroll -= bid_f
        player.signal_spend_total += bid_f
        player.current_signal_event_id = event.event_id
        player.current_signal_bid = bid_f
        player.current_signal_hint = self._signal_hint(event)
        return {
            "event_id": event.event_id,
            "hint": player.current_signal_hint,
            "paid": bid_f,
        }

    def submit_fermi_guess(self, token: str, guess_value: float) -> float:
        if self.phase != "fermi":
            raise ValueError("Fermi guesses are not open right now.")

        question = self.current_fermi_question
        if question is None:
            raise ValueError("No active Fermi question.")

        player = self.players.get(token)
        if player is None:
            raise ValueError("Unknown player session.")

        guess = float(guess_value)
        if guess < 0:
            raise ValueError("Guess must be non-negative.")

        player.current_fermi_guess = guess
        return guess

    def advance_clock(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)

        if self.paused:
            return False

        if self.phase == "events" and self.event_deadline and now >= self.event_deadline:
            self._resolve_current_event()
            if self.current_event_index + 1 < len(self.events):
                self._start_next_event(now)
            else:
                self._start_fermi_mode(now)
            return True

        if self.phase == "fermi" and self.fermi_deadline and now >= self.fermi_deadline:
            self._resolve_current_fermi_question()
            if self.current_fermi_index + 1 < len(self.fermi_questions):
                self._start_next_fermi_question(now)
            else:
                self.phase = "finished"
                self.fermi_deadline = None
            return True

        return False

    def leaderboard(self) -> list[PlayerState]:
        return sorted(
            self.players.values(),
            key=lambda player: (player.bankroll, player.pnl, player.name.lower()),
            reverse=True,
        )

    def rank_for(self, token: str) -> int | None:
        for idx, player in enumerate(self.leaderboard(), start=1):
            if player.token == token:
                return idx
        return None

    def _apply_rebuy_if_busted(self, player: PlayerState) -> bool:
        if player.bankroll > 1e-9:
            return False
        player.bankroll = self.bust_rebuy_amount
        player.contributions += self.bust_rebuy_amount
        player.ever_busted = True
        player.bust_count += 1
        return True

    def _start_next_event(self, now: datetime) -> None:
        self.current_event_index += 1
        if self.current_event_index >= len(self.events):
            self._start_fermi_mode(now)
            return

        event = self.current_event
        assert event is not None

        self.phase = "events"
        self.event_deadline = now + timedelta(seconds=event.bet_window_seconds)

        if self.round_stipend > 0:
            for player in self.players.values():
                player.bankroll += self.round_stipend
                player.contributions += self.round_stipend

        for player in self.players.values():
            player.current_bet = None
            player.current_signal_hint = None
            player.current_signal_bid = 0.0
            player.current_signal_event_id = None
            player.current_round_volatility_carry_cost = 0.0
            player.current_round_pre_bet_rebuy = False

            if player.volatility_available > 0 and self.volatility_hold_cost > 0:
                if player.bankroll >= self.volatility_hold_cost - 1e-9:
                    carry = round(self.volatility_hold_cost, 2)
                    player.bankroll -= carry
                    player.volatility_hold_cost_paid += carry
                    player.current_round_volatility_carry_cost = carry
                else:
                    # Cannot pay holding cost, card expires.
                    player.volatility_available = 0

            if self._apply_rebuy_if_busted(player):
                player.current_round_pre_bet_rebuy = True

    def _resolve_current_event(self) -> None:
        event = self.current_event
        if event is None:
            return

        hit = self._rng.random() <= event.true_probability

        for player in self.players.values():
            bet = player.current_bet
            pnl_delta = 0.0
            bet_amount = 0.0
            base_bet_amount = 0.0
            insurance_refund = 0.0
            insurance_premium = 0.0
            double_down_used = False
            insurance_used = False
            volatility_used = False
            volatility_multiplier: float | None = None
            volatility_carry_cost = round(player.current_round_volatility_carry_cost, 2)
            signal_bid = 0.0
            signal_hint: str | None = None

            if player.current_signal_event_id == event.event_id and player.current_signal_hint:
                signal_bid = round(player.current_signal_bid, 2)
                signal_hint = player.current_signal_hint

            if bet and bet.event_id == event.event_id:
                base_bet_amount = bet.base_amount
                bet_amount = bet.amount
                insurance_premium = bet.insurance_premium
                double_down_used = bet.double_down
                insurance_used = bet.insurance
                volatility_used = bet.volatility
                if volatility_used:
                    volatility_multiplier = self.volatility_profit_multiplier
                if hit:
                    profit = bet.amount * (event.odds_numerator / event.odds_denominator)
                    if volatility_multiplier is not None:
                        profit *= volatility_multiplier
                    player.bankroll += bet.amount + profit
                    pnl_delta = profit - bet.insurance_premium
                else:
                    if bet.insurance:
                        insurance_refund = round(bet.amount * self.insurance_refund_pct, 2)
                        player.bankroll += insurance_refund
                    pnl_delta = -bet.amount + insurance_refund - bet.insurance_premium

            pnl_delta -= signal_bid
            pnl_delta -= volatility_carry_cost

            rebuy_applied = player.current_round_pre_bet_rebuy or self._apply_rebuy_if_busted(player)

            player.results.append(
                PlayerEventResult(
                    event_id=event.event_id,
                    title=event.title,
                    base_bet_amount=round(base_bet_amount, 2),
                    bet_amount=round(bet_amount, 2),
                    double_down_used=double_down_used,
                    insurance_used=insurance_used,
                    volatility_used=volatility_used,
                    volatility_multiplier=round(volatility_multiplier, 4) if volatility_multiplier is not None else None,
                    volatility_carry_cost=volatility_carry_cost,
                    insurance_premium=round(insurance_premium, 2),
                    insurance_refund=round(insurance_refund, 2),
                    signal_bid=round(signal_bid, 2),
                    signal_hint=signal_hint,
                    outcome_hit=hit,
                    pnl_delta=round(pnl_delta, 2),
                    bankroll_after=round(player.bankroll, 2),
                    rebuy_applied=rebuy_applied,
                )
            )
            player.current_bet = None
            player.current_signal_hint = None
            player.current_signal_bid = 0.0
            player.current_signal_event_id = None
            player.current_round_volatility_carry_cost = 0.0
            player.current_round_pre_bet_rebuy = False

        self.event_history.append(
            EventResult(
                event_id=event.event_id,
                title=event.title,
                outcome_hit=hit,
                outcome_label="HIT" if hit else "MISS",
                odds_label=self._odds_label(event),
            )
        )

    def _start_fermi_mode(self, now: datetime) -> None:
        self.event_deadline = None
        self.current_fermi_index = -1
        self._start_next_fermi_question(now)

    def _start_next_fermi_question(self, now: datetime) -> None:
        self.current_fermi_index += 1
        if self.current_fermi_index >= len(self.fermi_questions):
            self.phase = "finished"
            self.fermi_deadline = None
            return

        question = self.current_fermi_question
        assert question is not None

        self.phase = "fermi"
        self.fermi_deadline = now + timedelta(seconds=question.answer_window_seconds)

        for player in self.players.values():
            player.current_fermi_guess = None

    def _resolve_current_fermi_question(self) -> None:
        question = self.current_fermi_question
        if question is None:
            return

        eligible = [p for p in self.players.values() if not p.ever_busted]
        valid = [
            p
            for p in eligible
            if p.current_fermi_guess is not None and p.current_fermi_guess >= question.true_value
        ]
        valid_sorted = sorted(valid, key=lambda p: (p.current_fermi_guess - question.true_value, p.name.lower()))

        rank_map: dict[str, int] = {player.token: idx for idx, player in enumerate(valid_sorted, start=1)}
        n = len(valid_sorted)

        for player in self.players.values():
            guess = player.current_fermi_guess
            eligible_for_percentile = not player.ever_busted
            counted = eligible_for_percentile and guess is not None and guess >= question.true_value and player.token in rank_map

            percentile = 0.0
            boost_pct = 0.0
            if counted:
                rank = rank_map[player.token]
                if n == 1:
                    percentile = 1.0
                else:
                    percentile = max(0.0, (n - rank) / (n - 1))
                boost_pct = percentile
                player.bankroll += player.bankroll * boost_pct

            player.fermi_results.append(
                PlayerFermiResult(
                    question_id=question.question_id,
                    prompt=question.prompt,
                    guess=guess,
                    true_value=question.true_value,
                    unit=question.unit,
                    eligible_for_percentile=eligible_for_percentile,
                    counted_in_percentile=counted,
                    percentile=round(percentile, 4),
                    boost_pct=round(boost_pct, 4),
                    bankroll_after=round(player.bankroll, 2),
                )
            )
            player.current_fermi_guess = None

        self.fermi_history.append(
            FermiResult(
                question_id=question.question_id,
                prompt=question.prompt,
                true_value=question.true_value,
                unit=question.unit,
                valid_guess_count=n,
                eligible_count=len(eligible),
            )
        )

    def _public_event(self, event: GameEvent) -> dict[str, Any]:
        return {
            "event_id": event.event_id,
            "title": event.title,
            "description": event.description,
            "odds_label": self._odds_label(event),
            "bet_window_seconds": event.bet_window_seconds,
        }

    def _admin_event(self, event: GameEvent) -> dict[str, Any]:
        return {
            "event_id": event.event_id,
            "title": event.title,
            "description": event.description,
            "true_probability": event.true_probability,
            "odds_numerator": event.odds_numerator,
            "odds_denominator": event.odds_denominator,
            "odds_label": self._odds_label(event),
            "bet_window_seconds": event.bet_window_seconds,
        }

    def _public_fermi(self, question: FermiQuestion) -> dict[str, Any]:
        return {
            "question_id": question.question_id,
            "prompt": question.prompt,
            "unit": question.unit,
            "answer_window_seconds": question.answer_window_seconds,
        }

    def _admin_fermi(self, question: FermiQuestion) -> dict[str, Any]:
        return {
            "question_id": question.question_id,
            "prompt": question.prompt,
            "true_value": question.true_value,
            "unit": question.unit,
            "answer_window_seconds": question.answer_window_seconds,
        }

    def public_state_for(self, token: str, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        player = self.players.get(token)

        leaderboard_rows = [
            {
                "rank": idx,
                "name": p.name,
                "pnl": round(p.pnl, 2),
                "bankroll": round(p.bankroll, 2),
                "bust_count": p.bust_count,
            }
            for idx, p in enumerate(self.leaderboard(), start=1)
        ]

        player_payload: dict[str, Any] | None = None
        if player is not None:
            player_payload = {
                "name": player.name,
                "bankroll": round(player.bankroll, 2),
                "pnl": round(player.pnl, 2),
                "rank": self.rank_for(token),
                "bust_count": player.bust_count,
                "ever_busted": player.ever_busted,
                "double_down_available": player.double_down_available,
                "insurance_available": player.insurance_available,
                "volatility_available": player.volatility_available,
                "current_bet": asdict(player.current_bet) if player.current_bet else None,
                "current_fermi_guess": player.current_fermi_guess,
                "results": [asdict(result) for result in player.results],
                "fermi_results": [asdict(result) for result in player.fermi_results],
            }

        current_event_payload: dict[str, Any] | None = None
        if self.phase == "events" and self.current_event:
            event = self.current_event
            current_event_payload = {
                "event_id": event.event_id,
                "title": event.title,
                "description": event.description,
                "odds_label": self._odds_label(event),
                "bet_window_seconds": event.bet_window_seconds,
                "seconds_remaining": max(0, int((self.event_deadline - now).total_seconds())) if self.event_deadline else 0,
            }

        current_fermi_payload: dict[str, Any] | None = None
        if self.phase == "fermi" and self.current_fermi_question:
            question = self.current_fermi_question
            current_fermi_payload = {
                "question_id": question.question_id,
                "prompt": question.prompt,
                "unit": question.unit,
                "answer_window_seconds": question.answer_window_seconds,
                "seconds_remaining": max(0, int((self.fermi_deadline - now).total_seconds())) if self.fermi_deadline else 0,
            }

        return {
            "phase": self.phase,
            "paused": self.paused,
            "seed": self.seed,
            "random_outcomes": True,
            "admin_start_required": False,
            "player_count": len(self.players),
            "max_players": self.max_players,
            "double_down_uses": self.double_down_uses,
            "insurance_uses": self.insurance_uses,
            "volatility_uses": self.volatility_uses,
            "volatility_hold_cost": self.volatility_hold_cost,
            "insurance_premium_pct": self.insurance_premium_pct,
            "insurance_refund_pct": self.insurance_refund_pct,
            "event_index": self.current_event_index + 1 if self.current_event_index >= 0 else 0,
            "total_events": len(self.events),
            "fermi_index": self.current_fermi_index + 1 if self.current_fermi_index >= 0 else 0,
            "total_fermi": len(self.fermi_questions),
            "current_event": current_event_payload,
            "current_fermi": current_fermi_payload,
            "resolved_events": [asdict(result) for result in self.event_history],
            "resolved_fermi": [asdict(result) for result in self.fermi_history],
            "leaderboard": leaderboard_rows,
            "podium": leaderboard_rows[:3] if self.phase == "finished" else [],
            "you": player_payload,
            "rules": self.rules,
            "server_time": now.isoformat(),
        }

    def event_catalog(self, *, include_sensitive: bool = False) -> list[dict[str, Any]]:
        if include_sensitive:
            return [self._admin_event(event) for event in self.events]
        return [self._public_event(event) for event in self.events]

    def fermi_catalog(self, *, include_answers: bool = False) -> list[dict[str, Any]]:
        if include_answers:
            return [self._admin_fermi(question) for question in self.fermi_questions]
        return [self._public_fermi(question) for question in self.fermi_questions]

    def admin_state(self, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)

        full_leaderboard = [
            {
                "rank": idx,
                "name": player.name,
                "pnl": round(player.pnl, 2),
                "bankroll": round(player.bankroll, 2),
                "ever_busted": player.ever_busted,
                "bust_count": player.bust_count,
                "double_down_available": player.double_down_available,
                "insurance_available": player.insurance_available,
                "volatility_available": player.volatility_available,
                "current_bet": asdict(player.current_bet) if player.current_bet else None,
                "current_fermi_guess": player.current_fermi_guess,
            }
            for idx, player in enumerate(self.leaderboard(), start=1)
        ]

        event_results: list[dict[str, Any]] = []
        history_by_event = {result.event_id: result for result in self.event_history}
        for event in self.events:
            resolved = history_by_event.get(event.event_id)
            total_wagered = 0.0
            bets_placed = 0
            for player in self.players.values():
                if resolved is not None:
                    for row in player.results:
                        if row.event_id == event.event_id and row.bet_amount > 0:
                            total_wagered += row.bet_amount
                            bets_placed += 1
                            break
                elif player.current_bet and player.current_bet.event_id == event.event_id:
                    total_wagered += player.current_bet.amount
                    bets_placed += 1

            event_results.append(
                {
                    "event_id": event.event_id,
                    "title": event.title,
                    "resolved": resolved is not None,
                    "outcome": asdict(resolved) if resolved is not None else None,
                    "bets_placed": bets_placed,
                    "total_wagered": round(total_wagered, 2),
                    "bet_window_seconds": event.bet_window_seconds,
                    "odds_label": self._odds_label(event),
                }
            )

        fermi_results: list[dict[str, Any]] = []
        history_by_question = {result.question_id: result for result in self.fermi_history}
        for question in self.fermi_questions:
            resolved = history_by_question.get(question.question_id)
            live_guesses = sum(
                1
                for player in self.players.values()
                if player.current_fermi_guess is not None and self.current_fermi_question and question.question_id == self.current_fermi_question.question_id
            )

            fermi_results.append(
                {
                    "question_id": question.question_id,
                    "prompt": question.prompt,
                    "resolved": resolved is not None,
                    "true_value": question.true_value,
                    "unit": question.unit,
                    "answer_window_seconds": question.answer_window_seconds,
                    "valid_guess_count": resolved.valid_guess_count if resolved else None,
                    "eligible_count": resolved.eligible_count if resolved else None,
                    "live_guesses": live_guesses,
                }
            )

        return {
            "phase": self.phase,
            "paused": self.paused,
            "seed": self.seed,
            "player_count": len(self.players),
            "max_players": self.max_players,
            "event_index": self.current_event_index + 1 if self.current_event_index >= 0 else 0,
            "total_events": len(self.events),
            "fermi_index": self.current_fermi_index + 1 if self.current_fermi_index >= 0 else 0,
            "total_fermi": len(self.fermi_questions),
            "lobby_seconds": self.lobby_seconds,
            "starting_bankroll": self.starting_bankroll,
            "round_stipend": self.round_stipend,
            "bust_rebuy_amount": self.bust_rebuy_amount,
            "access_code": self.access_code,
            "double_down_uses": self.double_down_uses,
            "insurance_uses": self.insurance_uses,
            "volatility_uses": self.volatility_uses,
            "volatility_hold_cost": self.volatility_hold_cost,
            "insurance_premium_pct": self.insurance_premium_pct,
            "insurance_refund_pct": self.insurance_refund_pct,
            "rules": self.rules,
            "events": self.event_catalog(include_sensitive=True),
            "fermi_questions": self.fermi_catalog(include_answers=True),
            "event_results": event_results,
            "fermi_results": fermi_results,
            "leaderboard": full_leaderboard,
            "event_deadline": self.event_deadline.isoformat() if self.event_deadline else None,
            "fermi_deadline": self.fermi_deadline.isoformat() if self.fermi_deadline else None,
            "server_time": now.isoformat(),
        }

    def set_paused(self, paused: bool) -> None:
        self.paused = paused

    def force_start(self, now: datetime | None = None) -> None:
        self._require_lobby()
        if not self.players:
            raise ValueError("Cannot start: no players have joined yet.")
        self._start_next_event(now or datetime.now(timezone.utc))

    def force_advance(self, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        if self.phase == "lobby":
            self.force_start(now)
            return

        if self.phase == "events":
            self._resolve_current_event()
            if self.current_event_index + 1 < len(self.events):
                self._start_next_event(now)
            else:
                self._start_fermi_mode(now)
            return

        if self.phase == "fermi":
            self._resolve_current_fermi_question()
            if self.current_fermi_index + 1 < len(self.fermi_questions):
                self._start_next_fermi_question(now)
            else:
                self.phase = "finished"
                self.fermi_deadline = None
            return

        raise ValueError("Game is already finished.")

    def restart(self, *, new_seed: int | None = None, clear_players: bool = True) -> None:
        if new_seed is not None:
            self.seed = int(new_seed)

        self._rng = random.Random(self.seed)
        self.phase = "lobby"
        self.paused = False
        self.event_history = []
        self.fermi_history = []
        self.current_event_index = -1
        self.current_fermi_index = -1
        self.event_deadline = None
        self.fermi_deadline = None

        if clear_players:
            self.players = {}
            return

        for player in self.players.values():
            player.bankroll = self.starting_bankroll
            player.contributions = self.starting_bankroll
            player.current_bet = None
            player.current_fermi_guess = None
            player.current_signal_hint = None
            player.current_signal_bid = 0.0
            player.current_signal_event_id = None
            player.signal_spend_total = 0.0
            player.double_down_available = self.double_down_uses
            player.insurance_available = self.insurance_uses
            player.volatility_available = self.volatility_uses
            player.volatility_hold_cost_paid = 0.0
            player.current_round_volatility_carry_cost = 0.0
            player.current_round_pre_bet_rebuy = False
            player.ever_busted = False
            player.bust_count = 0
            player.results = []
            player.fermi_results = []

    def update_settings(
        self,
        *,
        lobby_seconds: int | None = None,
        starting_bankroll: int | None = None,
        round_stipend: int | None = None,
        bust_rebuy_amount: int | None = None,
        access_code: str | None = None,
        uniform_event_seconds: int | None = None,
        uniform_fermi_seconds: int | None = None,
    ) -> None:
        self._require_lobby()

        if lobby_seconds is not None:
            self.lobby_seconds = max(5, int(lobby_seconds))

        if starting_bankroll is not None:
            new_value = float(starting_bankroll)
            if new_value <= 0:
                raise ValueError("starting_bankroll must be positive.")
            self.starting_bankroll = new_value
            for player in self.players.values():
                player.bankroll = new_value
                player.contributions = new_value
                player.current_bet = None
                player.current_fermi_guess = None
                player.current_signal_hint = None
                player.current_signal_bid = 0.0
                player.current_signal_event_id = None
                player.signal_spend_total = 0.0
                player.double_down_available = self.double_down_uses
                player.insurance_available = self.insurance_uses
                player.volatility_available = self.volatility_uses
                player.volatility_hold_cost_paid = 0.0
                player.current_round_volatility_carry_cost = 0.0
                player.current_round_pre_bet_rebuy = False
                player.ever_busted = False
                player.bust_count = 0
                player.results = []
                player.fermi_results = []

        if round_stipend is not None:
            self.round_stipend = max(0.0, float(round_stipend))

        if bust_rebuy_amount is not None:
            self.bust_rebuy_amount = max(1.0, float(bust_rebuy_amount))

        if access_code is not None:
            value = access_code.strip()
            if not value:
                raise ValueError("access_code must be non-empty.")
            self.access_code = value

        if uniform_event_seconds is not None:
            sec = max(5, int(uniform_event_seconds))
            self.events = [replace(event, bet_window_seconds=sec) for event in self.events]

        if uniform_fermi_seconds is not None:
            sec = max(8, int(uniform_fermi_seconds))
            self.fermi_questions = [replace(question, answer_window_seconds=sec) for question in self.fermi_questions]

    def update_event(
        self,
        event_id: int,
        *,
        title: str | None = None,
        description: str | None = None,
        true_probability: float | None = None,
        odds_numerator: float | None = None,
        odds_denominator: float | None = None,
        bet_window_seconds: int | None = None,
    ) -> GameEvent:
        self._require_lobby()

        idx = self._event_index_by_id(event_id)
        current = self.events[idx]

        updated = _event(
            event_id=current.event_id,
            title=current.title if title is None else (title.strip() or current.title),
            description=current.description if description is None else (description.strip() or current.description),
            true_probability=current.true_probability if true_probability is None else float(true_probability),
            odds_numerator=current.odds_numerator if odds_numerator is None else float(odds_numerator),
            odds_denominator=current.odds_denominator if odds_denominator is None else float(odds_denominator),
            bet_window_seconds=current.bet_window_seconds if bet_window_seconds is None else int(bet_window_seconds),
        )
        self.events[idx] = updated
        return updated

    def replace_events(self, event_specs: list[dict[str, Any]]) -> None:
        self._require_lobby()
        if not event_specs:
            raise ValueError("At least one event is required.")

        new_events: list[GameEvent] = []
        for idx, spec in enumerate(event_specs, start=1):
            new_events.append(
                _event(
                    event_id=idx,
                    title=str(spec.get("title") or f"Event {idx}").strip(),
                    description=str(spec.get("description") or "Event proposition").strip(),
                    true_probability=float(spec.get("true_probability", 0.5)),
                    odds_numerator=float(spec.get("odds_numerator", 1.0)),
                    odds_denominator=float(spec.get("odds_denominator", 1.0)),
                    bet_window_seconds=int(spec.get("bet_window_seconds", 30)),
                )
            )

        self.events = new_events

    def update_fermi_question(
        self,
        question_id: int,
        *,
        prompt: str | None = None,
        true_value: float | None = None,
        unit: str | None = None,
        answer_window_seconds: int | None = None,
    ) -> FermiQuestion:
        self._require_lobby()

        idx = self._fermi_index_by_id(question_id)
        current = self.fermi_questions[idx]

        updated = _fermi_question(
            question_id=current.question_id,
            prompt=current.prompt if prompt is None else (prompt.strip() or current.prompt),
            true_value=current.true_value if true_value is None else float(true_value),
            unit=current.unit if unit is None else (unit.strip() or current.unit),
            answer_window_seconds=current.answer_window_seconds if answer_window_seconds is None else int(answer_window_seconds),
        )
        self.fermi_questions[idx] = updated
        return updated

    def replace_fermi_questions(self, question_specs: list[dict[str, Any]]) -> None:
        self._require_lobby()
        if not question_specs:
            raise ValueError("At least one Fermi question is required.")

        new_questions: list[FermiQuestion] = []
        for idx, spec in enumerate(question_specs, start=1):
            new_questions.append(
                _fermi_question(
                    question_id=idx,
                    prompt=str(spec.get("prompt") or f"Fermi Question {idx}").strip(),
                    true_value=float(spec.get("true_value", 1.0)),
                    unit=str(spec.get("unit") or "value").strip(),
                    answer_window_seconds=int(spec.get("answer_window_seconds", 35)),
                )
            )

        self.fermi_questions = new_questions
