from __future__ import annotations

from dataclasses import asdict, replace
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
    yes_probability = max(0.001, min(0.999, yes_probability))
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


def default_events() -> list[GameEvent]:
    # Probabilities get progressively harder as event_id increases.
    return [
        _binary_event(1, "Coin Toss", "A fair coin lands heads.", 0.50, 25, yes_label="HEADS", no_label="TAILS"),
        _binary_event(2, "Spinner", "A 10-slot spinner lands on one of 4 green slots.", 0.40, 25, yes_label="GREEN", no_label="NOT GREEN"),
        _binary_event(3, "Dice Pair", "Two dice sum to at least 9.", 0.28, 27, yes_label="SUM >= 9", no_label="SUM < 9"),
        _binary_event(4, "Card Draw", "A single card is a face card.", 12.0 / 52.0, 27, yes_label="FACE CARD", no_label="NOT FACE"),
        _binary_event(5, "Three Coins", "Three coins all match.", 0.25, 28, yes_label="ALL MATCH", no_label="MIXED"),
        _binary_event(6, "Four Dice", "At least one die shows a 6.", 1.0 - (5.0 / 6.0) ** 4, 28, yes_label="HAS A 6", no_label="NO SIXES"),
        _binary_event(7, "Lucky 1-20", "A random integer from 1..20 equals 1.", 0.05, 30, yes_label="HIT #1", no_label="MISS"),
        _binary_event(8, "Two Hearts", "Two cards drawn without replacement are both hearts.", (13.0 / 52.0) * (12.0 / 51.0), 30, yes_label="BOTH HEARTS", no_label="OTHER"),
        _binary_event(9, "Roulette Shot", "Roulette lands on your chosen number (0-36).", 1.0 / 37.0, 32, yes_label="HIT", no_label="MISS"),
        _binary_event(10, "Pick 1-100", "A random integer from 1..100 equals 1.", 0.01, 32, yes_label="HIT #1", no_label="MISS"),
        _binary_event(11, "Double Six", "Two dice both show 6.", 1.0 / 36.0, 34, yes_label="DOUBLE 6", no_label="OTHER"),
        _binary_event(12, "One-in-250", "A random integer from 1..250 equals 1.", 1.0 / 250.0, 34, yes_label="HIT", no_label="MISS"),
        _binary_event(13, "Three Aces", "3 cards without replacement are all aces.", (4.0 / 52.0) * (3.0 / 51.0) * (2.0 / 50.0), 36, yes_label="3 ACES", no_label="OTHER"),
        _binary_event(14, "One-in-500", "A random integer from 1..500 equals 1.", 1.0 / 500.0, 36, yes_label="HIT", no_label="MISS"),
        _binary_event(15, "Grand Finale", "A random integer from 1..1000 equals 1.", 1.0 / 1000.0, 40, yes_label="HIT", no_label="MISS"),
    ]


def default_rules() -> list[str]:
    return [
        "All players share the exact same outcome for each event.",
        "Each event resolves randomly based on its displayed probability.",
        "You can place or replace one bet per event before the timer ends.",
        "PnL is bankroll minus starting bankroll.",
        "No automatic bankroll top-ups are added between events.",
        "Leaderboard ranks by highest PnL; ties break by bankroll then name.",
        "Top 10 players appear on the final leaderboard and top 3 on the podium.",
    ]


class GameEngine:
    def __init__(
        self,
        *,
        seed: int = 2026,
        lobby_seconds: int = 30,
        starting_bankroll: int = 1_000,
        round_stipend: int = 0,
        events: list[GameEvent] | None = None,
    ) -> None:
        self.seed = seed
        self._rng = random.Random(seed)
        self.lobby_seconds = max(5, int(lobby_seconds))
        self.starting_bankroll = float(starting_bankroll)
        self.round_stipend = float(round_stipend)
        self.events = list(events) if events else default_events()
        self.rules = default_rules()

        self.phase: GamePhase = "lobby"
        self.paused = False
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

    def _require_lobby(self) -> None:
        if self.phase != "lobby":
            raise ValueError("This action is only allowed during lobby.")

    def _event_index_by_id(self, event_id: int) -> int:
        for idx, event in enumerate(self.events):
            if event.event_id == event_id:
                return idx
        raise ValueError(f"Unknown event_id: {event_id}")

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

        if self.paused:
            return False

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
                "results": [asdict(result) for result in player.results[-15:]],
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
            "paused": self.paused,
            "seed": self.seed,
            "random_outcomes": True,
            "player_count": len(self.players),
            "event_index": self.current_event_index + 1 if self.phase != "lobby" else 0,
            "total_events": len(self.events),
            "lobby_seconds_remaining": lobby_seconds_remaining,
            "current_event": current_event_payload,
            "resolved_events": [asdict(result) for result in self.event_history],
            "leaderboard": leaderboard_rows,
            "podium": leaderboard_rows[:3] if self.phase == "finished" else [],
            "you": player_payload,
            "rules": self.rules,
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

    def admin_state(self, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        full_leaderboard = [
            {
                "rank": idx,
                "name": player.name,
                "pnl": round(player.pnl, 2),
                "bankroll": round(player.bankroll, 2),
                "current_bet": asdict(player.current_bet) if player.current_bet else None,
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

        return {
            "phase": self.phase,
            "paused": self.paused,
            "seed": self.seed,
            "player_count": len(self.players),
            "event_index": self.current_event_index + 1 if self.phase != "lobby" else 0,
            "total_events": len(self.events),
            "lobby_seconds": self.lobby_seconds,
            "starting_bankroll": self.starting_bankroll,
            "round_stipend": self.round_stipend,
            "rules": self.rules,
            "events": self.event_catalog(),
            "event_results": event_results,
            "leaderboard": full_leaderboard,
            "lobby_deadline": self.lobby_deadline.isoformat() if self.lobby_deadline else None,
            "event_deadline": self.event_deadline.isoformat() if self.event_deadline else None,
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

        if self.phase == "running":
            self._resolve_current_event()
            if self.current_event_index + 1 < len(self.events):
                self._start_next_event(now)
            else:
                self.phase = "finished"
                self.event_deadline = None
            return

        raise ValueError("Game is already finished.")

    def restart(self, *, new_seed: int | None = None, clear_players: bool = True) -> None:
        if new_seed is not None:
            self.seed = int(new_seed)
        self._rng = random.Random(self.seed)
        self.phase = "lobby"
        self.paused = False
        self.event_history = []
        self.current_event_index = -1
        self.lobby_deadline = None
        self.event_deadline = None

        if clear_players:
            self.players = {}
        else:
            for player in self.players.values():
                player.bankroll = self.starting_bankroll
                player.contributions = self.starting_bankroll
                player.current_bet = None
                player.results = []

    def update_settings(
        self,
        *,
        lobby_seconds: int | None = None,
        starting_bankroll: int | None = None,
        round_stipend: int | None = None,
        uniform_event_seconds: int | None = None,
    ) -> None:
        self._require_lobby()

        if lobby_seconds is not None:
            self.lobby_seconds = max(5, int(lobby_seconds))
            if self.players:
                self.lobby_deadline = datetime.now(timezone.utc) + timedelta(seconds=self.lobby_seconds)

        if starting_bankroll is not None:
            new_value = float(starting_bankroll)
            if new_value <= 0:
                raise ValueError("starting_bankroll must be positive.")
            self.starting_bankroll = new_value
            for player in self.players.values():
                player.bankroll = new_value
                player.contributions = new_value
                player.current_bet = None
                player.results = []

        if round_stipend is not None:
            self.round_stipend = max(0.0, float(round_stipend))

        if uniform_event_seconds is not None:
            sec = max(5, int(uniform_event_seconds))
            self.events = [replace(event, bet_window_seconds=sec) for event in self.events]

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
