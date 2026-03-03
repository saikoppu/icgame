from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass, field
from typing import Dict, Iterable, List, Optional

from .exchange import Exchange
from .models import Action, AuctionOutcome, CancelAllAction, PlaceOrderAction, Snapshot
from .scenarios import ScenarioInstance, build_scenario
from .strategies import Strategy
from .taker_bot import TakerBot, TakerBotConfig


@dataclass
class TeamResult:
    team: str
    pnl: float
    score: float
    cash: float
    positions: Dict[str, int]
    auction_paid: int
    won_auction: bool


@dataclass
class SimulationReport:
    scenario_id: int
    scenario_name: str
    seed: int
    settlements: Dict[str, float]
    public_reveals: Dict[str, List[str]]
    auction: Optional[AuctionOutcome]
    teams: List[TeamResult]
    bot_pnl: float
    trade_count: int
    assumptions: Dict[str, str] = field(default_factory=dict)

    def to_json(self) -> str:
        payload = asdict(self)
        if self.auction is not None:
            payload["auction"] = asdict(self.auction)
        return json.dumps(payload, indent=2, sort_keys=True)


class MarketMakingSimulation:
    def __init__(
        self,
        scenario_id: int,
        strategies: Iterable[Strategy],
        seed: int = 1,
        position_limit: int = 100,
        decision_interval_seconds: int = 5,
        taker_bot_config: TakerBotConfig | None = None,
    ) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.scenario: ScenarioInstance = build_scenario(scenario_id, self.rng)
        self.strategies = list(strategies)
        self.strategy_by_name = {s.name: s for s in self.strategies}
        if len(self.strategy_by_name) != len(self.strategies):
            raise ValueError("Strategy names must be unique.")

        self.decision_interval_seconds = max(1, decision_interval_seconds)
        self.exchange = Exchange(self.scenario.contracts, position_limit=position_limit)
        self.taker_bot = TakerBot(config=taker_bot_config)

        self.public_reveals: Dict[str, List[str]] = {symbol: [] for symbol in self.scenario.reveal_symbols}
        self.private_draws_display: Dict[str, Dict[str, Dict[int, str]]] = {s.name: {} for s in self.strategies}
        self.private_draws_raw: Dict[str, Dict[str, Dict[int, object]]] = {s.name: {} for s in self.strategies}
        self.auction_paid: Dict[str, int] = {s.name: 0 for s in self.strategies}

        for strategy in self.strategies:
            self.exchange.ensure_account(strategy.name)
        self.exchange.ensure_account(self.taker_bot.team_name)

    def run(self) -> SimulationReport:
        reveal_steps_by_time = {t: i + 1 for i, t in enumerate(self.scenario.reveal_times)}
        reveal_count = 0
        auction_outcome: Optional[AuctionOutcome] = None

        for now in range(self.scenario.duration_seconds + 1):
            if now in reveal_steps_by_time:
                reveal_count = reveal_steps_by_time[now]
                reveal_payload = self.scenario.public_reveal(reveal_count)
                for symbol, value in reveal_payload.items():
                    self.public_reveals[symbol].append(value)
                self._handle_reveal(now, reveal_payload, reveal_count)

            if now == self.scenario.auction_time:
                auction_outcome = self._run_auction(now, reveal_count)

            if now % self.decision_interval_seconds == 0:
                for strategy in self.strategies:
                    snapshot = self._snapshot_for(strategy.name, now, reveal_count)
                    actions = strategy.on_tick(snapshot)
                    self._apply_actions(strategy.name, actions, now)

            fair_prices = self.scenario.expected_prices(reveal_count, private_draws=None)
            bounds = self.scenario.price_bounds(reveal_count, private_draws=None)
            for symbol in self.scenario.contracts:
                self.taker_bot.run_for_symbol(
                    exchange=self.exchange,
                    symbol=symbol,
                    fair_price=fair_prices[symbol],
                    bounds=bounds[symbol],
                    now=now,
                )

        settlements = self.scenario.settlement_prices()
        bot_pnl = self.exchange.mark_to_market(self.taker_bot.team_name, settlements)
        free_money = max(-bot_pnl, 1.0)

        team_results: List[TeamResult] = []
        for strategy in self.strategies:
            team = strategy.name
            account = self.exchange.ensure_account(team)
            pnl = self.exchange.mark_to_market(team, settlements)
            team_results.append(
                TeamResult(
                    team=team,
                    pnl=pnl,
                    score=self._utility_score(pnl, free_money),
                    cash=account.cash,
                    positions=dict(account.positions),
                    auction_paid=self.auction_paid[team],
                    won_auction=(auction_outcome.winner == team if auction_outcome else False),
                )
            )

        team_results.sort(key=lambda x: x.score, reverse=True)

        return SimulationReport(
            scenario_id=self.scenario.scenario_id,
            scenario_name=self.scenario.name,
            seed=self.seed,
            settlements=settlements,
            public_reveals=self.public_reveals,
            auction=auction_outcome,
            teams=team_results,
            bot_pnl=bot_pnl,
            trade_count=len(self.exchange.trades),
            assumptions={
                "scoring_formula": "Assumed U(x)=ln(1+35*x/C) for x>=0, else U(x)=35*x/C because PDF formula text extraction dropped the division symbol.",
                "auction_scope": "Winner gets draw #5 and #6 for each reveal symbol in the scenario.",
            },
        )

    @staticmethod
    def _utility_score(pnl: float, c: float) -> float:
        ratio = pnl / c
        if ratio >= 0:
            return math.log(1 + 35 * ratio)
        return 35 * ratio

    def _handle_reveal(self, now: int, reveal_payload: Dict[str, str], reveal_count: int) -> None:
        for strategy in self.strategies:
            snapshot = self._snapshot_for(strategy.name, now, reveal_count)
            actions = strategy.on_reveal(snapshot, reveal_payload)
            self._apply_actions(strategy.name, actions, now)

    def _run_auction(self, now: int, reveal_count: int) -> AuctionOutcome:
        bids: Dict[str, int] = {}
        for strategy in self.strategies:
            snapshot = self._snapshot_for(strategy.name, now, reveal_count)
            bid = strategy.auction_bid(snapshot)
            bids[strategy.name] = max(0, int(bid))

        max_bid = max(bids.values()) if bids else 0
        winner: Optional[str] = None
        winning_bid = 0
        display_payload: Dict[str, Dict[int, str]] = {}
        raw_payload: Dict[str, Dict[int, object]] = {}

        if max_bid > 0:
            winners = [team for team, bid in bids.items() if bid == max_bid]
            winner = self.rng.choice(winners)
            winning_bid = max_bid
            self.exchange.adjust_cash(winner, -winning_bid)
            self.auction_paid[winner] += winning_bid
            display_payload, raw_payload = self.scenario.private_info_for_auction()
            self.private_draws_display[winner] = display_payload
            self.private_draws_raw[winner] = raw_payload

        outcome = AuctionOutcome(
            winner=winner,
            winning_bid=winning_bid,
            bids=bids,
            private_draws=display_payload if winner else {},
        )

        for strategy in self.strategies:
            snapshot = self._snapshot_for(strategy.name, now, reveal_count)
            actions = strategy.on_auction_result(snapshot, outcome)
            self._apply_actions(strategy.name, actions, now)

        return outcome

    def _snapshot_for(self, team: str, now: int, reveal_count: int) -> Snapshot:
        account = self.exchange.ensure_account(team)
        private_raw = self.private_draws_raw.get(team, {})
        expected = self.scenario.expected_prices(reveal_count, private_draws=private_raw)
        bounds = self.scenario.price_bounds(reveal_count, private_draws=private_raw)

        return Snapshot(
            team=team,
            now=now,
            duration=self.scenario.duration_seconds,
            contracts=self.scenario.contracts,
            top_of_book=self.exchange.all_top_of_book(),
            positions=dict(account.positions),
            cash=account.cash,
            public_reveals={symbol: list(values) for symbol, values in self.public_reveals.items()},
            expected_prices=expected,
            price_bounds=bounds,
            private_draws=self.private_draws_display.get(team, {}),
        )

    def _apply_actions(self, team: str, actions: Iterable[Action], now: int) -> None:
        for action in actions:
            if isinstance(action, CancelAllAction):
                self.exchange.cancel_all(team, symbol=action.symbol)
            elif isinstance(action, PlaceOrderAction):
                self.exchange.place_limit_order(
                    owner=team,
                    symbol=action.symbol,
                    side=action.side,
                    price=action.price,
                    qty=action.qty,
                    timestamp=now,
                    enforce_limits=True,
                )
