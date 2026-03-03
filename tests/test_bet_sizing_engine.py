from __future__ import annotations

from datetime import datetime, timezone

import pytest

from bet_sizing_game.engine import GameEngine
from bet_sizing_game.models import BetOption, GameEvent


def single_event_game() -> GameEngine:
    event = GameEvent(
        event_id=1,
        title="Deterministic",
        description="Always resolves YES for testing.",
        bet_window_seconds=1,
        options=(
            BetOption(key="yes", label="YES", probability=1.0, payout_multiplier=2.0),
            BetOption(key="no", label="NO", probability=0.0, payout_multiplier=1.0),
        ),
    )
    return GameEngine(seed=11, lobby_seconds=1, starting_bankroll=100, round_stipend=10, events=[event])


def test_join_name_deduplication() -> None:
    engine = single_event_game()

    first = engine.join_player("Alpha")
    second = engine.join_player("alpha")

    assert first.name == "Alpha"
    assert second.name == "alpha #2"


def test_round_progression_and_pnl() -> None:
    engine = single_event_game()
    player = engine.join_player("Trader")

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    engine.lobby_deadline = now
    engine.advance_clock(now)

    assert engine.phase == "running"
    assert engine.current_event is not None
    assert player.bankroll == 110
    assert player.contributions == 110

    engine.place_bet(player.token, option_key="yes", amount=10)
    assert player.bankroll == 100

    engine.event_deadline = now
    engine.advance_clock(now)

    assert engine.phase == "finished"
    assert player.bankroll == 120
    assert round(player.pnl, 2) == 10.0
    assert player.results[0].pnl_delta == 10.0


def test_join_rejected_after_start() -> None:
    engine = single_event_game()
    engine.join_player("A")

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    engine.lobby_deadline = now
    engine.advance_clock(now)

    with pytest.raises(ValueError):
        engine.join_player("Late")
