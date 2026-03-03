from __future__ import annotations

from datetime import datetime, timezone

import pytest

from bet_sizing_game.engine import GameEngine
from bet_sizing_game.models import BetOption, FermiQuestion, GameEvent


def make_event_yes_never_hits() -> GameEvent:
    return GameEvent(
        event_id=1,
        title="Lose Test",
        description="YES never happens.",
        bet_window_seconds=1,
        options=(
            BetOption(key="yes", label="YES", probability=0.0, payout_multiplier=10.0),
            BetOption(key="no", label="NO", probability=1.0, payout_multiplier=1.0),
        ),
    )


def make_fermi_question(true_value: float = 100.0) -> FermiQuestion:
    return FermiQuestion(
        question_id=1,
        prompt="Estimate X",
        true_value=true_value,
        unit="units",
        answer_window_seconds=1,
    )


def test_default_shape() -> None:
    engine = GameEngine()
    assert len(engine.events) == 12
    assert len(engine.fermi_questions) == 5
    assert engine.starting_bankroll == 1000
    assert engine.bust_rebuy_amount == 500


def test_join_requires_correct_code() -> None:
    engine = GameEngine(access_code="quant")

    with pytest.raises(ValueError):
        engine.join_player("A", "wrong")

    p = engine.join_player("A", "quant")
    assert p.name == "A"


def test_admin_only_start_no_lobby_autostart() -> None:
    engine = GameEngine(access_code="quant")
    engine.join_player("A", "quant")

    future = datetime(2030, 1, 1, tzinfo=timezone.utc)
    changed = engine.advance_clock(future)

    assert not changed
    assert engine.phase == "lobby"


def test_bust_resets_to_500() -> None:
    engine = GameEngine(
        access_code="quant",
        starting_bankroll=1000,
        bust_rebuy_amount=500,
        events=[make_event_yes_never_hits()],
        fermi_questions=[make_fermi_question()],
    )
    player = engine.join_player("Trader", "quant")

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    engine.force_start(now)
    engine.place_bet(player.token, option_key="yes", amount=1000)
    engine.force_advance(now)

    assert engine.phase == "fermi"
    assert player.bankroll == 500
    assert player.contributions == 1500
    assert player.ever_busted
    assert player.bust_count == 1


def test_fermi_percentile_and_below_truth_rule() -> None:
    engine = GameEngine(
        access_code="quant",
        events=[make_event_yes_never_hits()],
        fermi_questions=[make_fermi_question(100.0)],
    )
    p1 = engine.join_player("A", "quant")
    p2 = engine.join_player("B", "quant")
    p3 = engine.join_player("C", "quant")

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    engine.force_start(now)
    engine.force_advance(now)  # resolve event and enter fermi

    engine.submit_fermi_guess(p1.token, 110)  # valid and closest
    engine.submit_fermi_guess(p2.token, 130)  # valid but worse
    engine.submit_fermi_guess(p3.token, 90)   # below truth -> invalid

    engine.force_advance(now)

    assert engine.phase == "finished"
    assert engine.players[p1.token].bankroll == 2000
    assert engine.players[p2.token].bankroll == 1000
    assert engine.players[p3.token].bankroll == 1000


def test_fermi_excludes_busted_players_from_percentile_pool() -> None:
    engine = GameEngine(
        access_code="quant",
        events=[make_event_yes_never_hits()],
        fermi_questions=[make_fermi_question(100.0)],
    )
    p1 = engine.join_player("A", "quant")
    p2 = engine.join_player("B", "quant")
    p3 = engine.join_player("C", "quant")

    # Mark C as busted to ensure they are excluded from percentile computation.
    engine.players[p3.token].ever_busted = True

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    engine.force_start(now)
    engine.force_advance(now)

    engine.submit_fermi_guess(p1.token, 105)
    engine.submit_fermi_guess(p2.token, 130)
    engine.submit_fermi_guess(p3.token, 1000)

    engine.force_advance(now)

    assert engine.players[p1.token].bankroll == 2000
    assert engine.players[p2.token].bankroll == 1000
    assert engine.players[p3.token].bankroll == 1000
