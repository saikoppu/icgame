from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import random
from typing import Any
from uuid import uuid4

from .models import BetOption, EventResult, GameEvent, GamePhase, PlayerBet, PlayerEventResult, PlayerState


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
        bet_window_seconds=bet_window_seconds,
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


def default_events() -> list[GameEvent]:
    return [
        _binary_event(1, "Coin Toss", "A fair coin lands heads.", 0.50, 28, yes_label="HEADS", no_label="TAILS"),
        _binary_event(2, "Spinner", "A 10-slot spinner lands on one of 4 green slots.", 0.40, 28, yes_label="GREEN", no_label="NOT GREEN"),
        _binary_event(3, "Dice Pair", "Two dice sum to at least 9.", 0.28, 30, yes_label="SUM >= 9", no_label="SUM < 9"),
        _binary_event(
            4,
            "Card Draw",
            "A single card drawn from a fresh deck is a face card.",
            12.0 / 52.0,
            30,
            yes_label="FACE CARD",
            no_label="NOT FACE",
        ),
        _binary_event(
            5,
            "Three Coins",
            "Three coins all match (all heads or all tails).",
            0.25,
            32,
            yes_label="ALL MATCH",
            no_label="MIXED",
        ),
        _binary_event(
            6,
            "Four Dice",
            "At least one die shows a 6 when rolling four dice.",
            1.0 - (5.0 / 6.0) ** 4,
            32,
            yes_label="HAS A 6",
            no_label="NO SIXES",
        ),
        _binary_event(7, "Lucky Number", "A random integer from 1 to 20 equals 1.", 0.05, 35, yes_label="HIT #1", no_label="MISS"),
        _binary_event(
            8,
            "Rare Card",
            "Two cards drawn without replacement are both hearts.",
            (13.0 / 52.0) * (12.0 / 51.0),
            35,
            yes_label="BOTH HEARTS",
            no_label="OTHER",
        ),
        _binary_event(
            9,
            "Roulette Shot",
            "A roulette wheel lands on your chosen number (0-36).",
            1.0 / 37.0,
            38,
            yes_label="HIT NUMBER",
            no_label="MISS NUMBER",
        ),
        _binary_event(
            10,
            "Grand Finale",
            "A random integer from 1 to 100 equals 1.",
            0.01,
            40,
            yes_label="HIT #1",
            no_label="NOT #1",
        ),
    ]


class GameEngine:
    def __init__(
        self,
        *,
        seed: int = 2026,
        lobby_seconds: int = 30,
        starting_bankroll: int = 1_000,
        round_stipend: int = 100,
        events: list[GameEvent] | None = None,
    ) -> None:
        self.seed = seed
        self._rng = random.Random(seed)
        self.lobby_seconds = max(5, lobby_seconds)
        self.starting_bankroll = float(starting_bankroll)
        self.round_stipend = float(round_stipend)
        self.events = events or default_events()

        self.phase: GamePhase = "lobby"
        self.players: dict[str, PlayerState] = {}
        self.event_history: list[EventResult] = []
        self.current_event_index = -1
        self.lobby_deadline: datetime | None = None
        self.event_deadline: datetime | None = None

    @property
    def current_event(self) -> GameEvent | None:
        if 0 <= self.current_event_index < len(self.events):
            return self.events[self.current_event_index]
        return None

    def join_player(self, raw_name: str) -> PlayerState:
        if self.phase != "lobby":
            raise ValueError("The game is already running. New players can only join during lobby.")

        name = (raw_name or "").strip()
        if not name:
            raise ValueError("Name is required.")

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

        if self.lobby_deadline is None:
            self.lobby_deadline = datetime.now(timezone.utc) + timedelta(seconds=self.lobby_seconds)

        return player

    def place_bet(self, token: str, option_key: str, amount: int) -> PlayerBet:
        if self.phase != "running":
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

    def advance_clock(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)

        if self.phase == "lobby" and self.players and self.lobby_deadline and now >= self.lobby_deadline:
            self._start_next_event(now)
            return True

        if self.phase == "running" and self.event_deadline and now >= self.event_deadline:
            self._resolve_current_event()
            if self.current_event_index + 1 < len(self.events):
                self._start_next_event(now)
            else:
                self.phase = "finished"
                self.event_deadline = None
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

    def _start_next_event(self, now: datetime) -> None:
        self.current_event_index += 1
        if self.current_event_index >= len(self.events):
            self.phase = "finished"
            self.event_deadline = None
            return

        event = self.current_event
        assert event is not None

        self.phase = "running"
        self.event_deadline = now + timedelta(seconds=event.bet_window_seconds)

        for player in self.players.values():
            player.bankroll += self.round_stipend
            player.contributions += self.round_stipend
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

            player.results.append(
                PlayerEventResult(
                    event_id=event.event_id,
                    title=event.title,
                    bet_option_key=bet_option_key,
                    bet_amount=bet_amount,
                    outcome_key=outcome.key,
                    pnl_delta=round(pnl_delta, 2),
                    bankroll_after=round(player.bankroll, 2),
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

    def public_state_for(self, token: str, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        player = self.players.get(token)

        leaderboard = self.leaderboard()
        leaderboard_rows = [
            {
                "rank": idx,
                "name": p.name,
                "pnl": round(p.pnl, 2),
                "bankroll": round(p.bankroll, 2),
            }
            for idx, p in enumerate(leaderboard[:10], start=1)
        ]

        player_payload: dict[str, Any] | None = None
        if player is not None:
            player_payload = {
                "name": player.name,
                "bankroll": round(player.bankroll, 2),
                "pnl": round(player.pnl, 2),
                "rank": self.rank_for(token),
                "current_bet": asdict(player.current_bet) if player.current_bet else None,
                "results": [asdict(result) for result in player.results[-10:]],
            }

        current_event_payload: dict[str, Any] | None = None
        event = self.current_event
        if event and self.phase == "running":
            current_event_payload = {
                "event_id": event.event_id,
                "title": event.title,
                "description": event.description,
                "options": [asdict(option) for option in event.options],
                "bet_window_seconds": event.bet_window_seconds,
                "seconds_remaining": max(0, int((self.event_deadline - now).total_seconds())) if self.event_deadline else 0,
            }

        lobby_seconds_remaining = 0
        if self.phase == "lobby" and self.lobby_deadline:
            lobby_seconds_remaining = max(0, int((self.lobby_deadline - now).total_seconds()))

        return {
            "phase": self.phase,
            "seed": self.seed,
            "player_count": len(self.players),
            "event_index": self.current_event_index + 1 if self.phase != "lobby" else 0,
            "total_events": len(self.events),
            "lobby_seconds_remaining": lobby_seconds_remaining,
            "current_event": current_event_payload,
            "resolved_events": [asdict(result) for result in self.event_history],
            "leaderboard": leaderboard_rows,
            "podium": leaderboard_rows[:3] if self.phase == "finished" else [],
            "you": player_payload,
            "server_time": now.isoformat(),
        }

    def event_catalog(self) -> list[dict[str, Any]]:
        return [
            {
                "event_id": event.event_id,
                "title": event.title,
                "description": event.description,
                "bet_window_seconds": event.bet_window_seconds,
                "options": [asdict(option) for option in event.options],
            }
            for event in self.events
        ]
