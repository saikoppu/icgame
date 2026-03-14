from __future__ import annotations

from datetime import datetime, timezone

import pytest

from bet_sizing_game.engine import GameEngine
from bet_sizing_game.models import FermiQuestion, GameEvent


def make_event_never_hits(event_id: int = 1) -> GameEvent:
    return GameEvent(
        event_id=event_id,
        title="Lose Test",
        description="This proposition never hits.",
        true_probability=-1.0,
        odds_numerator=3.0,
        odds_denominator=1.0,
        bet_window_seconds=1,
    )


def make_event_always_hits(event_id: int = 1) -> GameEvent:
    return GameEvent(
        event_id=event_id,
        title="Win Test",
        description="This proposition always hits.",
        true_probability=2.0,
        odds_numerator=1.0,
        odds_denominator=1.0,
        bet_window_seconds=1,
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
    assert len(engine.events) == 15
    assert len(engine.fermi_questions) == 0
    assert engine.starting_bankroll == 1000
    assert engine.bust_rebuy_amount == 500
    assert engine.volatility_hold_cost == 100
    assert engine.max_players == 1


def test_join_requires_name() -> None:
    engine = GameEngine(access_code="quant")

    with pytest.raises(ValueError):
        engine.join_player("")

    p = engine.join_player("A")
    assert p.name == "A"


def test_single_player_limit_enforced() -> None:
    engine = GameEngine(access_code="quant", max_players=1)
    engine.join_player("A")

    with pytest.raises(ValueError):
        engine.join_player("B")


def test_admin_only_start_no_lobby_autostart() -> None:
    engine = GameEngine(access_code="quant")
    engine.join_player("A")

    future = datetime(2030, 1, 1, tzinfo=timezone.utc)
    changed = engine.advance_clock(future)

    assert not changed
    assert engine.phase == "lobby"


def test_bust_resets_to_500() -> None:
    engine = GameEngine(
        access_code="quant",
        starting_bankroll=1000,
        bust_rebuy_amount=500,
        volatility_hold_cost=0,
        events=[make_event_never_hits()],
        fermi_questions=[make_fermi_question()],
    )
    player = engine.join_player("Trader")

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    engine.force_start(now)
    engine.place_bet(player.token, amount=1000)
    engine.force_advance(now)

    assert engine.phase == "fermi"
    assert player.bankroll == 500
    assert player.contributions == 1500
    assert player.ever_busted
    assert player.bust_count == 1


def test_fermi_percentile_and_below_truth_rule() -> None:
    engine = GameEngine(
        access_code="quant",
        max_players=3,
        volatility_hold_cost=0,
        events=[make_event_never_hits()],
        fermi_questions=[make_fermi_question(100.0)],
    )
    p1 = engine.join_player("A")
    p2 = engine.join_player("B")
    p3 = engine.join_player("C")

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
        max_players=3,
        volatility_hold_cost=0,
        events=[make_event_never_hits()],
        fermi_questions=[make_fermi_question(100.0)],
    )
    p1 = engine.join_player("A")
    p2 = engine.join_player("B")
    p3 = engine.join_player("C")

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


def test_decimal_bet_and_zero_unbet() -> None:
    engine = GameEngine(access_code="quant", volatility_hold_cost=0, events=[make_event_never_hits()], fermi_questions=[make_fermi_question()])
    player = engine.join_player("Decimal")

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    engine.force_start(now)

    engine.place_bet(player.token, amount=123.45)
    assert player.current_bet is not None
    assert player.current_bet.amount == 123.45
    assert player.bankroll == pytest.approx(876.55, rel=0.0, abs=0.001)

    engine.place_bet(player.token, amount=0)
    assert player.current_bet is None
    assert player.bankroll == pytest.approx(1000.0, rel=0.0, abs=0.001)


def test_leaderboard_uses_bankroll_order() -> None:
    engine = GameEngine(access_code="quant", max_players=2)
    p1 = engine.join_player("A")
    p2 = engine.join_player("B")

    engine.players[p1.token].bankroll = 900
    engine.players[p1.token].contributions = 1000
    engine.players[p2.token].bankroll = 800
    engine.players[p2.token].contributions = 500

    ordered = [player.name for player in engine.leaderboard()]
    assert ordered == ["A", "B"]


def test_double_down_and_insurance_on_losing_round() -> None:
    engine = GameEngine(
        access_code="quant",
        volatility_hold_cost=0,
        events=[make_event_never_hits()],
        fermi_questions=[],
    )
    player = engine.join_player("A")
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    engine.force_start(now)

    engine.place_bet(player.token, amount=100, use_double_down=True, use_insurance=True)
    # cost at placement: 200 stake + 24 premium
    assert player.bankroll == pytest.approx(776.0, rel=0.0, abs=0.01)

    engine.force_advance(now)
    # lose round: insurance refunds 60% of 200 => +120
    # net bankroll = 776 + 120 = 896
    assert player.bankroll == pytest.approx(896.0, rel=0.0, abs=0.01)
    assert player.results[-1].double_down_used
    assert player.results[-1].insurance_used


def test_volatility_carry_cost_charged_until_card_used() -> None:
    engine = GameEngine(
        access_code="quant",
        volatility_hold_cost=100,
        events=[make_event_always_hits(1), make_event_always_hits(2)],
        fermi_questions=[],
    )
    player = engine.join_player("A")
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    engine.force_start(now)
    assert player.bankroll == pytest.approx(900.0, rel=0.0, abs=0.01)

    engine.place_bet(player.token, amount=100, use_volatility=True)
    engine.force_advance(now)

    assert player.results[0].volatility_used
    assert player.results[0].volatility_multiplier == pytest.approx(1.5, rel=0.0, abs=0.0001)
    assert player.results[0].volatility_carry_cost == pytest.approx(100.0, rel=0.0, abs=0.01)
    assert player.volatility_available == 0
    assert player.current_round_volatility_carry_cost == 0.0


def test_volatility_carry_cost_applies_each_round_while_unused() -> None:
    engine = GameEngine(
        access_code="quant",
        volatility_hold_cost=100,
        events=[make_event_never_hits(), make_event_never_hits(event_id=2)],
        fermi_questions=[],
    )
    player = engine.join_player("A")
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    engine.force_start(now)
    assert player.bankroll == pytest.approx(900.0, rel=0.0, abs=0.01)

    engine.force_advance(now)
    assert player.results[0].volatility_carry_cost == pytest.approx(100.0, rel=0.0, abs=0.01)
    # Round 2 carry deducted because card is still unused.
    assert player.bankroll == pytest.approx(800.0, rel=0.0, abs=0.01)
