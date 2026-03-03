from __future__ import annotations

import random
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable

from .models import Card

SUIT_TO_VALUE = {"HEART": 1, "SPADE": 2, "CLUB": 3, "DIAMOND": 4}
RANK_ORDER = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
RANK_TO_VALUE = {rank: i + 1 for i, rank in enumerate(RANK_ORDER)}
SUITS = ["HEART", "SPADE", "CLUB", "DIAMOND"]


def standard_deck() -> list[Card]:
    return [Card(rank=rank, suit=suit) for suit in SUITS for rank in RANK_ORDER]


def _draw_with_replacement(deck: list[Card], n: int, rng: random.Random) -> list[Card]:
    return [rng.choice(deck) for _ in range(n)]


@dataclass
class ScenarioConfig:
    scenario_id: int
    name: str
    contracts: tuple[str, ...]
    reveal_symbols: tuple[str, ...]


class ScenarioInstance(ABC):
    duration_seconds = 15 * 60
    reveal_times = tuple(90 * i for i in range(1, 10))
    auction_time = 90 * 5
    auction_peek_indices = (4, 5)

    def __init__(self, config: ScenarioConfig) -> None:
        self.config = config
        self.contracts = config.contracts
        self.reveal_symbols = config.reveal_symbols

    @property
    def scenario_id(self) -> int:
        return self.config.scenario_id

    @property
    def name(self) -> str:
        return self.config.name

    def public_reveal(self, reveal_step: int) -> Dict[str, str]:
        index = reveal_step - 1
        payload: Dict[str, str] = {}
        for symbol in self.reveal_symbols:
            payload[symbol] = self.display_value(symbol, index)
        return payload

    def private_info_for_auction(self) -> tuple[Dict[str, Dict[int, str]], Dict[str, Dict[int, object]]]:
        display: Dict[str, Dict[int, str]] = {}
        raw: Dict[str, Dict[int, object]] = {}
        for symbol in self.reveal_symbols:
            display[symbol] = {}
            raw[symbol] = {}
            for idx in self.auction_peek_indices:
                display[symbol][idx] = self.display_value(symbol, idx)
                raw[symbol][idx] = self.raw_value(symbol, idx)
        return display, raw

    def _known_values(
        self,
        symbol: str,
        revealed_count: int,
        private_draws: Dict[str, Dict[int, object]] | None,
    ) -> Dict[int, object]:
        known: Dict[int, object] = {}
        for idx in range(revealed_count):
            known[idx] = self.raw_value(symbol, idx)

        if private_draws and symbol in private_draws:
            for idx, value in private_draws[symbol].items():
                if idx >= revealed_count:
                    known[idx] = value
        return known

    @abstractmethod
    def raw_value(self, symbol: str, index: int) -> object:
        raise NotImplementedError

    @abstractmethod
    def display_value(self, symbol: str, index: int) -> str:
        raise NotImplementedError

    @abstractmethod
    def settlement_prices(self) -> Dict[str, float]:
        raise NotImplementedError

    @abstractmethod
    def expected_prices(
        self,
        revealed_count: int,
        private_draws: Dict[str, Dict[int, object]] | None = None,
    ) -> Dict[str, float]:
        raise NotImplementedError

    @abstractmethod
    def price_bounds(
        self,
        revealed_count: int,
        private_draws: Dict[str, Dict[int, object]] | None = None,
    ) -> Dict[str, tuple[float, float]]:
        raise NotImplementedError


class Scenario3SpreadSuits(ScenarioInstance):
    def __init__(self, rng: random.Random) -> None:
        super().__init__(
            ScenarioConfig(
                scenario_id=3,
                name="Spread of Suits",
                contracts=("SUMSUITSA", "SUMSUITSB", "SPREADSUITAB"),
                reveal_symbols=("SUMSUITSA", "SUMSUITSB"),
            )
        )
        cards = rng.sample(standard_deck(), 10)
        self.deck_a = cards[:5]
        self.deck_b = cards[5:]
        self.draws_a = _draw_with_replacement(self.deck_a, 10, rng)
        self.draws_b = _draw_with_replacement(self.deck_b, 10, rng)

    def raw_value(self, symbol: str, index: int) -> object:
        if symbol == "SUMSUITSA":
            return SUIT_TO_VALUE[self.draws_a[index].suit]
        if symbol == "SUMSUITSB":
            return SUIT_TO_VALUE[self.draws_b[index].suit]
        raise KeyError(symbol)

    def display_value(self, symbol: str, index: int) -> str:
        if symbol == "SUMSUITSA":
            return self.draws_a[index].suit
        if symbol == "SUMSUITSB":
            return self.draws_b[index].suit
        raise KeyError(symbol)

    def _base_stats(
        self,
        symbol: str,
        revealed_count: int,
        private_draws: Dict[str, Dict[int, object]] | None,
    ) -> tuple[float, float, float]:
        deck = self.deck_a if symbol == "SUMSUITSA" else self.deck_b
        known = self._known_values(symbol, revealed_count, private_draws)
        known_sum = sum(int(v) for v in known.values())
        unknown = 10 - len(known)

        values = [SUIT_TO_VALUE[card.suit] for card in deck]
        mean_val = sum(values) / len(values)
        min_val, max_val = min(values), max(values)

        expected = (known_sum + unknown * mean_val) * 10
        lower = (known_sum + unknown * min_val) * 10
        upper = (known_sum + unknown * max_val) * 10
        return expected, lower, upper

    def settlement_prices(self) -> Dict[str, float]:
        sum_a = sum(SUIT_TO_VALUE[card.suit] for card in self.draws_a) * 10
        sum_b = sum(SUIT_TO_VALUE[card.suit] for card in self.draws_b) * 10
        spread = sum_a - sum_b + 500
        return {"SUMSUITSA": float(sum_a), "SUMSUITSB": float(sum_b), "SPREADSUITAB": float(spread)}

    def expected_prices(
        self,
        revealed_count: int,
        private_draws: Dict[str, Dict[int, object]] | None = None,
    ) -> Dict[str, float]:
        exp_a, _, _ = self._base_stats("SUMSUITSA", revealed_count, private_draws)
        exp_b, _, _ = self._base_stats("SUMSUITSB", revealed_count, private_draws)
        return {
            "SUMSUITSA": exp_a,
            "SUMSUITSB": exp_b,
            "SPREADSUITAB": exp_a - exp_b + 500,
        }

    def price_bounds(
        self,
        revealed_count: int,
        private_draws: Dict[str, Dict[int, object]] | None = None,
    ) -> Dict[str, tuple[float, float]]:
        _, low_a, high_a = self._base_stats("SUMSUITSA", revealed_count, private_draws)
        _, low_b, high_b = self._base_stats("SUMSUITSB", revealed_count, private_draws)
        return {
            "SUMSUITSA": (low_a, high_a),
            "SUMSUITSB": (low_b, high_b),
            "SPREADSUITAB": (low_a - high_b + 500, high_a - low_b + 500),
        }


class Scenario4SumRanks(ScenarioInstance):
    def __init__(self, rng: random.Random) -> None:
        super().__init__(
            ScenarioConfig(
                scenario_id=4,
                name="Sum of Ranks",
                contracts=("SUMRANKA", "SUMRANKB", "SPREADRANKAB"),
                reveal_symbols=("SUMRANKA", "SUMRANKB"),
            )
        )
        cards = rng.sample(standard_deck(), 10)
        self.deck_a = cards[:5]
        self.deck_b = cards[5:]
        self.draws_a = _draw_with_replacement(self.deck_a, 10, rng)
        self.draws_b = _draw_with_replacement(self.deck_b, 10, rng)

    def raw_value(self, symbol: str, index: int) -> object:
        if symbol == "SUMRANKA":
            return RANK_TO_VALUE[self.draws_a[index].rank]
        if symbol == "SUMRANKB":
            return RANK_TO_VALUE[self.draws_b[index].rank]
        raise KeyError(symbol)

    def display_value(self, symbol: str, index: int) -> str:
        if symbol == "SUMRANKA":
            return self.draws_a[index].rank
        if symbol == "SUMRANKB":
            return self.draws_b[index].rank
        raise KeyError(symbol)

    def _base_stats(
        self,
        symbol: str,
        revealed_count: int,
        private_draws: Dict[str, Dict[int, object]] | None,
    ) -> tuple[float, float, float]:
        deck = self.deck_a if symbol == "SUMRANKA" else self.deck_b
        known = self._known_values(symbol, revealed_count, private_draws)
        known_sum = sum(int(v) for v in known.values())
        unknown = 10 - len(known)

        values = [RANK_TO_VALUE[card.rank] for card in deck]
        mean_val = sum(values) / len(values)
        min_val, max_val = min(values), max(values)

        expected = known_sum + unknown * mean_val
        lower = known_sum + unknown * min_val
        upper = known_sum + unknown * max_val
        return expected, lower, upper

    def settlement_prices(self) -> Dict[str, float]:
        sum_a = sum(RANK_TO_VALUE[card.rank] for card in self.draws_a)
        sum_b = sum(RANK_TO_VALUE[card.rank] for card in self.draws_b)
        spread = sum_a - sum_b + 1000
        return {"SUMRANKA": float(sum_a), "SUMRANKB": float(sum_b), "SPREADRANKAB": float(spread)}

    def expected_prices(
        self,
        revealed_count: int,
        private_draws: Dict[str, Dict[int, object]] | None = None,
    ) -> Dict[str, float]:
        exp_a, _, _ = self._base_stats("SUMRANKA", revealed_count, private_draws)
        exp_b, _, _ = self._base_stats("SUMRANKB", revealed_count, private_draws)
        return {
            "SUMRANKA": exp_a,
            "SUMRANKB": exp_b,
            "SPREADRANKAB": exp_a - exp_b + 1000,
        }

    def price_bounds(
        self,
        revealed_count: int,
        private_draws: Dict[str, Dict[int, object]] | None = None,
    ) -> Dict[str, tuple[float, float]]:
        _, low_a, high_a = self._base_stats("SUMRANKA", revealed_count, private_draws)
        _, low_b, high_b = self._base_stats("SUMRANKB", revealed_count, private_draws)
        return {
            "SUMRANKA": (low_a, high_a),
            "SUMRANKB": (low_b, high_b),
            "SPREADRANKAB": (low_a - high_b + 1000, high_a - low_b + 1000),
        }


class Scenario7NumberPairs(ScenarioInstance):
    def __init__(self, rng: random.Random) -> None:
        super().__init__(
            ScenarioConfig(
                scenario_id=7,
                name="Number of Pairs",
                contracts=("NUMPAIRS",),
                reveal_symbols=("NUMPAIRS",),
            )
        )
        self.deck = rng.sample(standard_deck(), 7)
        self.draws = _draw_with_replacement(self.deck, 10, rng)
        self.rank_probs = self._rank_probabilities(self.deck)

    @staticmethod
    def _rank_probabilities(deck: Iterable[Card]) -> Dict[str, float]:
        ranks = [card.rank for card in deck]
        counts = Counter(ranks)
        total = len(ranks)
        return {rank: count / total for rank, count in counts.items()}

    @staticmethod
    def _num_pairs(rank_counts: Counter[str]) -> int:
        return sum(max(count - 1, 0) for count in rank_counts.values())

    def raw_value(self, symbol: str, index: int) -> object:
        if symbol != "NUMPAIRS":
            raise KeyError(symbol)
        return self.draws[index].rank

    def display_value(self, symbol: str, index: int) -> str:
        return str(self.raw_value(symbol, index))

    def _rank_counts(
        self,
        revealed_count: int,
        private_draws: Dict[str, Dict[int, object]] | None,
    ) -> Counter[str]:
        known = self._known_values("NUMPAIRS", revealed_count, private_draws)
        return Counter(str(v) for v in known.values())

    def settlement_prices(self) -> Dict[str, float]:
        counts = Counter(card.rank for card in self.draws)
        return {"NUMPAIRS": float(self._num_pairs(counts) * 100)}

    def expected_prices(
        self,
        revealed_count: int,
        private_draws: Dict[str, Dict[int, object]] | None = None,
    ) -> Dict[str, float]:
        counts = self._rank_counts(revealed_count, private_draws)
        seen_ranks = {rank for rank, count in counts.items() if count > 0}
        m = 10 - sum(counts.values())

        expected_distinct = float(len(seen_ranks))
        for rank, prob in self.rank_probs.items():
            if rank in seen_ranks:
                continue
            expected_distinct += 1 - (1 - prob) ** m

        expected_pairs = 10 - expected_distinct
        return {"NUMPAIRS": expected_pairs * 100.0}

    def price_bounds(
        self,
        revealed_count: int,
        private_draws: Dict[str, Dict[int, object]] | None = None,
    ) -> Dict[str, tuple[float, float]]:
        counts = self._rank_counts(revealed_count, private_draws)
        current_pairs = self._num_pairs(counts)
        seen_count = sum(1 for count in counts.values() if count > 0)
        rank_space = len(self.rank_probs)
        m = 10 - sum(counts.values())

        unseen_count = max(rank_space - seen_count, 0)
        min_pairs = current_pairs + max(0, m - unseen_count)

        if seen_count > 0:
            max_pairs = current_pairs + m
        else:
            max_pairs = current_pairs + max(m - 1, 0)

        return {"NUMPAIRS": (min_pairs * 100.0, max_pairs * 100.0)}


def build_scenario(scenario_id: int, rng: random.Random) -> ScenarioInstance:
    if scenario_id == 3:
        return Scenario3SpreadSuits(rng)
    if scenario_id == 4:
        return Scenario4SumRanks(rng)
    if scenario_id == 7:
        return Scenario7NumberPairs(rng)
    raise ValueError(f"Unsupported scenario: {scenario_id}. Supported scenarios are 3, 4, and 7.")
