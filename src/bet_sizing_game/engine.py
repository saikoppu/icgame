from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
import random
from typing import Any
from uuid import uuid4

from .models import (
    BetOption,
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


def _binary_event(
    event_id: int,
    title: str,
    description: str,
    yes_probability: float,
    bet_window_seconds: int,
    *,
    yes_label: str = "YES",
    no_label: str = "NO",
) -> GameEvent:
    yes_probability = max(0.01, min(0.99, yes_probability))
    no_probability = 1.0 - yes_probability
    return GameEvent(
        event_id=event_id,
        title=title,
        description=description,
        bet_window_seconds=max(5, int(bet_window_seconds)),
        options=(
            BetOption(
                key="yes",
                label=yes_label,
                probability=yes_probability,
                payout_multiplier=round(1.0 / yes_probability, 2),
            ),
            BetOption(
                key="no",
                label=no_label,
                probability=no_probability,
                payout_multiplier=round(1.0 / no_probability, 2),
            ),
        ),
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
    return [
        _binary_event(
            1,
            "Coin Toss Warmup",
            "Fair coin lands heads.",
            0.50,
            22,
            yes_label="HEADS",
            no_label="TAILS",
        ),
        _binary_event(
            2,
            "Two Dice High Sum",
            "Roll two fair dice. Sum is at least 10.",
            6.0 / 36.0,
            24,
            yes_label="SUM >= 10",
            no_label="SUM <= 9",
        ),
        _binary_event(
            3,
            "Three Dice Distinct",
            "Roll 3 fair dice. All three outcomes are distinct.",
            (6.0 * 5.0 * 4.0) / (6.0**3),
            24,
            yes_label="ALL DISTINCT",
            no_label="HAS MATCH",
        ),
        _binary_event(
            4,
            "Four Dice Exact",
            "Roll 4 fair dice. Exactly one die shows 6.",
            4.0 * (1.0 / 6.0) * ((5.0 / 6.0) ** 3),
            25,
            yes_label="EXACTLY ONE 6",
            no_label="OTHER",
        ),
        _binary_event(
            5,
            "Ace In Two",
            "Draw 2 cards without replacement. At least one ace appears.",
            1.0 - ((48.0 / 52.0) * (47.0 / 51.0)),
            25,
            yes_label=">=1 ACE",
            no_label="NO ACE",
        ),
        _binary_event(
            6,
            "Four Coins Exact",
            "Flip 4 fair coins. Exactly 2 are heads.",
            6.0 / 16.0,
            26,
            yes_label="EXACT 2H",
            no_label="OTHER",
        ),
        _binary_event(
            7,
            "Card Color Match",
            "Draw 2 cards without replacement. Both cards are the same color.",
            50.0 / 102.0,
            26,
            yes_label="SAME COLOR",
            no_label="DIFF COLOR",
        ),
        _binary_event(
            8,
            "Prime Sum",
            "Roll two fair dice. Sum is prime.",
            15.0 / 36.0,
            27,
            yes_label="PRIME SUM",
            no_label="NON-PRIME",
        ),
        _binary_event(
            9,
            "Five Coins Tail Risk",
            "Flip 5 fair coins. At least 4 heads appear.",
            6.0 / 32.0,
            27,
            yes_label=">=4 HEADS",
            no_label="<=3 HEADS",
        ),
        _binary_event(
            10,
            "Card Color Composition",
            "Draw 3 cards without replacement. Exactly one is red.",
            (26.0 * 26.0 * 25.0 * 3.0) / (52.0 * 51.0 * 50.0),
            28,
            yes_label="EXACT 1 RED",
            no_label="OTHER",
        ),
        _binary_event(
            11,
            "Face Card Pair",
            "Draw 2 cards without replacement. Both are face cards.",
            (12.0 / 52.0) * (11.0 / 51.0),
            30,
            yes_label="BOTH FACE",
            no_label="OTHER",
        ),
        _binary_event(
            12,
            "Final EV Check",
            "Roll 3 fair dice. Sum is at least 13.",
            56.0 / 216.0,
            32,
            yes_label="SUM >= 13",
            no_label="SUM <= 12",
        ),
    ]


def default_fermi_questions() -> list[FermiQuestion]:
    return [
        _fermi_question(
            1,
            "Estimate annual undergraduate applications submitted to Georgia Tech (Atlanta campus).",
            58_000,
            "applications",
            35,
        ),
        _fermi_question(
            2,
            "Estimate total seats in Bobby Dodd Stadium.",
            55_000,
            "seats",
            35,
        ),
        _fermi_question(
            3,
            "Estimate total square footage of the Georgia Tech Library complex.",
            375_000,
            "sq ft",
            35,
        ),
        _fermi_question(
            4,
            "Estimate how many meals are served per week across major GT dining halls.",
            180_000,
            "meals/week",
            35,
        ),
        _fermi_question(
            5,
            "Estimate total number of alumni worldwide associated with Georgia Tech.",
            210_000,
            "alumni",
            35,
        ),
    ]


def default_rules() -> list[str]:
    return [
        "All players start with $1000 and place bets across 12 probabilistic events.",
        "Event outcomes are randomized server-side and every player receives the same outcome each round.",
        "Bets can be replaced during the timer; only the latest bet is active for that round.",
        "If a player's bankroll hits $0 at any point, they are automatically reset to $500 so they can keep playing.",
        "Admin is the only role that can start the game.",
        "Players must join with the correct lobby code set by admin.",
        "After the 12 betting rounds, the game moves to 5 GT Fermi questions.",
        "For each Fermi question, only guesses >= true value are valid; guesses below true value get 0% boost.",
        "Fermi percentile boosts are computed only among non-busted players with valid guesses.",
        "Bankroll boost is applied as: bankroll *= (1 + percentile). Example: 90th percentile -> +90%.",
        "Leaderboard is visible to everyone and shows all players from rank 1 through rank N.",
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

    def join_player(self, raw_name: str, raw_code: str) -> PlayerState:
        if self.phase != "lobby":
            raise ValueError("The game is already running. New players can only join during lobby.")

        name = (raw_name or "").strip()
        if not name:
            raise ValueError("Name is required.")

        code = (raw_code or "").strip()
        if not code:
            raise ValueError("Join code is required.")
        if code != self.access_code:
            raise ValueError("Invalid join code.")

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
        )
        self.players[token] = player
        return player

    def place_bet(self, token: str, option_key: str, amount: int) -> PlayerBet:
        if self.phase != "events":
            raise ValueError("Betting is closed right now.")

        event = self.current_event
        if event is None:
            raise ValueError("No active event.")

        player = self.players.get(token)
        if player is None:
            raise ValueError("Unknown player session.")

        if amount <= 0:
            raise ValueError("Bet amount must be positive.")

        option_lookup = {option.key: option for option in event.options}
        if option_key not in option_lookup:
            raise ValueError("Invalid bet option.")

        if player.current_bet is not None and player.current_bet.event_id == event.event_id:
            player.bankroll += player.current_bet.amount

        if amount > player.bankroll:
            raise ValueError("Insufficient bankroll.")

        player.bankroll -= amount
        player.current_bet = PlayerBet(event_id=event.event_id, option_key=option_key, amount=amount)
        return player.current_bet

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
            key=lambda player: (player.pnl, player.bankroll, player.name.lower()),
            reverse=True,
        )

    def rank_for(self, token: str) -> int | None:
        for idx, player in enumerate(self.leaderboard(), start=1):
            if player.token == token:
                return idx
        return None

    def _apply_rebuy_if_busted(self, player: PlayerState) -> bool:
        if player.bankroll > 0:
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

    def _resolve_current_event(self) -> None:
        event = self.current_event
        if event is None:
            return

        threshold = self._rng.random()
        cumulative = 0.0
        outcome = event.options[-1]
        for option in event.options:
            cumulative += option.probability
            if threshold <= cumulative:
                outcome = option
                break

        option_lookup = {option.key: option for option in event.options}

        for player in self.players.values():
            bet = player.current_bet
            pnl_delta = 0.0
            bet_option_key: str | None = None
            bet_amount = 0

            if bet and bet.event_id == event.event_id:
                bet_option_key = bet.option_key
                bet_amount = bet.amount
                selected = option_lookup[bet.option_key]
                if bet.option_key == outcome.key:
                    gross_return = bet.amount * selected.payout_multiplier
                    player.bankroll += gross_return
                    pnl_delta = gross_return - bet.amount
                else:
                    pnl_delta = -float(bet.amount)

            rebuy_applied = self._apply_rebuy_if_busted(player)

            player.results.append(
                PlayerEventResult(
                    event_id=event.event_id,
                    title=event.title,
                    bet_option_key=bet_option_key,
                    bet_amount=bet_amount,
                    outcome_key=outcome.key,
                    pnl_delta=round(pnl_delta, 2),
                    bankroll_after=round(player.bankroll, 2),
                    rebuy_applied=rebuy_applied,
                )
            )
            player.current_bet = None

        self.event_history.append(
            EventResult(
                event_id=event.event_id,
                title=event.title,
                outcome_key=outcome.key,
                outcome_label=outcome.label,
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

    def _public_option(self, option: BetOption) -> dict[str, Any]:
        return {
            "key": option.key,
            "label": option.label,
        }

    def _public_event(self, event: GameEvent) -> dict[str, Any]:
        return {
            "event_id": event.event_id,
            "title": event.title,
            "description": event.description,
            "bet_window_seconds": event.bet_window_seconds,
            "options": [self._public_option(option) for option in event.options],
        }

    def _admin_event(self, event: GameEvent) -> dict[str, Any]:
        return {
            "event_id": event.event_id,
            "title": event.title,
            "description": event.description,
            "bet_window_seconds": event.bet_window_seconds,
            "options": [asdict(option) for option in event.options],
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
                "current_bet": asdict(player.current_bet) if player.current_bet else None,
                "current_fermi_guess": player.current_fermi_guess,
                "results": [asdict(result) for result in player.results[-12:]],
                "fermi_results": [asdict(result) for result in player.fermi_results[-5:]],
            }

        current_event_payload: dict[str, Any] | None = None
        if self.phase == "events" and self.current_event:
            event = self.current_event
            current_event_payload = {
                "event_id": event.event_id,
                "title": event.title,
                "description": event.description,
                "options": [self._public_option(option) for option in event.options],
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
            "admin_start_required": True,
            "player_count": len(self.players),
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
                "current_bet": asdict(player.current_bet) if player.current_bet else None,
                "current_fermi_guess": player.current_fermi_guess,
            }
            for idx, player in enumerate(self.leaderboard(), start=1)
        ]

        event_results: list[dict[str, Any]] = []
        history_by_event = {result.event_id: result for result in self.event_history}
        for event in self.events:
            resolved = history_by_event.get(event.event_id)
            total_wagered = 0
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
                    "total_wagered": total_wagered,
                    "bet_window_seconds": event.bet_window_seconds,
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
            "event_index": self.current_event_index + 1 if self.current_event_index >= 0 else 0,
            "total_events": len(self.events),
            "fermi_index": self.current_fermi_index + 1 if self.current_fermi_index >= 0 else 0,
            "total_fermi": len(self.fermi_questions),
            "lobby_seconds": self.lobby_seconds,
            "starting_bankroll": self.starting_bankroll,
            "round_stipend": self.round_stipend,
            "bust_rebuy_amount": self.bust_rebuy_amount,
            "access_code": self.access_code,
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
        yes_label: str | None = None,
        no_label: str | None = None,
        yes_probability: float | None = None,
        bet_window_seconds: int | None = None,
    ) -> GameEvent:
        self._require_lobby()

        idx = self._event_index_by_id(event_id)
        current = self.events[idx]

        option_yes = current.options[0]
        option_no = current.options[1]

        new_prob = option_yes.probability if yes_probability is None else float(yes_probability)
        new_yes_label = option_yes.label if yes_label is None else yes_label.strip() or option_yes.label
        new_no_label = option_no.label if no_label is None else no_label.strip() or option_no.label
        new_title = current.title if title is None else title.strip() or current.title
        new_description = current.description if description is None else description.strip() or current.description
        new_window = current.bet_window_seconds if bet_window_seconds is None else int(bet_window_seconds)

        updated = _binary_event(
            event_id=current.event_id,
            title=new_title,
            description=new_description,
            yes_probability=new_prob,
            bet_window_seconds=new_window,
            yes_label=new_yes_label,
            no_label=new_no_label,
        )
        self.events[idx] = updated
        return updated

    def replace_events(self, event_specs: list[dict[str, Any]]) -> None:
        self._require_lobby()
        if not event_specs:
            raise ValueError("At least one event is required.")

        new_events: list[GameEvent] = []
        for idx, spec in enumerate(event_specs, start=1):
            title = str(spec.get("title") or f"Event {idx}").strip()
            description = str(spec.get("description") or "Random event").strip()
            yes_label = str(spec.get("yes_label") or "YES").strip()
            no_label = str(spec.get("no_label") or "NO").strip()
            probability = float(spec.get("yes_probability", 0.5))
            window = int(spec.get("bet_window_seconds", 30))
            new_events.append(
                _binary_event(
                    event_id=idx,
                    title=title,
                    description=description,
                    yes_probability=probability,
                    bet_window_seconds=window,
                    yes_label=yes_label,
                    no_label=no_label,
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

        new_prompt = current.prompt if prompt is None else prompt.strip() or current.prompt
        new_true_value = current.true_value if true_value is None else float(true_value)
        new_unit = current.unit if unit is None else unit.strip() or current.unit
        new_seconds = current.answer_window_seconds if answer_window_seconds is None else int(answer_window_seconds)

        updated = _fermi_question(
            question_id=current.question_id,
            prompt=new_prompt,
            true_value=new_true_value,
            unit=new_unit,
            answer_window_seconds=new_seconds,
        )
        self.fermi_questions[idx] = updated
        return updated

    def replace_fermi_questions(self, question_specs: list[dict[str, Any]]) -> None:
        self._require_lobby()
        if not question_specs:
            raise ValueError("At least one Fermi question is required.")

        new_questions: list[FermiQuestion] = []
        for idx, spec in enumerate(question_specs, start=1):
            prompt = str(spec.get("prompt") or f"Fermi Question {idx}").strip()
            true_value = float(spec.get("true_value", 1.0))
            unit = str(spec.get("unit") or "value").strip()
            seconds = int(spec.get("answer_window_seconds", 35))
            new_questions.append(
                _fermi_question(
                    question_id=idx,
                    prompt=prompt,
                    true_value=true_value,
                    unit=unit,
                    answer_window_seconds=seconds,
                )
            )

        self.fermi_questions = new_questions
