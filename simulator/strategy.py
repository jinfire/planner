from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd

from .bucket_strategy import simulate_bucket_withdrawal
from .constant_withdrawal import simulate_constant_withdrawal
from .guyton_klinger import simulate_guyton_klinger_withdrawal
from .portfolio import simulate_portfolio


@dataclass
class WithdrawalResult:
    """Standardized output every withdrawal strategy produces, so callers can score
    and rank strategies together even though each is shaped completely differently
    internally (fixed weights vs growth/reserve/cash roles, etc.).

    `value` is the one thing every retirement strategy actually has: the balance a
    retiree would really see after withdrawing, mark-to-market over time. CAGR/MDD/
    survival are all judged from it, so strategies are compared on the same footing -
    what actually happened to the money, not a hypothetical no-withdrawal version.

    `monte_carlo_returns` is optional: a pure-growth (no withdrawal) return series to
    bootstrap Monte Carlo from, for strategies that can supply one. Strategies whose
    withdrawal logic is baked into share dynamics from day 1 (no separate growth-only
    path exists) leave it as None, and are scored on historical survival alone."""

    label: dict
    value: pd.Series
    monte_carlo_returns: pd.Series | None = None
    extra: dict = field(default_factory=dict)


class WithdrawalStrategy(Protocol):
    def simulate(self, close: pd.DataFrame, dividends: pd.DataFrame, cpi: pd.Series | None) -> WithdrawalResult: ...


class ConstantWithdrawalStrategy:
    """Fixed-rate proportional withdrawal across a fixed set of ticker weights."""

    def __init__(self, weights: dict[str, float], withdrawal_rate: float, rebalance_freq: str = "annual"):
        self.weights = weights
        self.withdrawal_rate = withdrawal_rate
        self.rebalance_freq = rebalance_freq

    def simulate(self, close: pd.DataFrame, dividends: pd.DataFrame, cpi: pd.Series | None) -> WithdrawalResult:
        growth_value = simulate_portfolio(close, dividends, self.weights, rebalance_freq=self.rebalance_freq)
        withdrawal_value = simulate_constant_withdrawal(
            close,
            dividends,
            self.weights,
            withdrawal_rate=self.withdrawal_rate,
            rebalance_freq=self.rebalance_freq,
            cpi=cpi,
        )
        return WithdrawalResult(
            label=dict(self.weights), value=withdrawal_value, monte_carlo_returns=growth_value
        )


class GuytonKlingerWithdrawalStrategy:
    """Fixed weights, but the withdrawal amount itself is adjusted each year by the
    Guyton-Klinger guardrail rules instead of staying a fixed real amount."""

    def __init__(
        self,
        weights: dict[str, float],
        initial_withdrawal_rate: float,
        rebalance_freq: str = "annual",
        upper_guardrail: float = 1.20,
        lower_guardrail: float = 0.80,
        adjustment_pct: float = 0.10,
    ):
        self.weights = weights
        self.initial_withdrawal_rate = initial_withdrawal_rate
        self.rebalance_freq = rebalance_freq
        self.upper_guardrail = upper_guardrail
        self.lower_guardrail = lower_guardrail
        self.adjustment_pct = adjustment_pct

    def simulate(self, close: pd.DataFrame, dividends: pd.DataFrame, cpi: pd.Series | None) -> WithdrawalResult:
        growth_value = simulate_portfolio(close, dividends, self.weights, rebalance_freq=self.rebalance_freq)
        withdrawal_value = simulate_guyton_klinger_withdrawal(
            close,
            dividends,
            self.weights,
            initial_withdrawal_rate=self.initial_withdrawal_rate,
            rebalance_freq=self.rebalance_freq,
            cpi=cpi,
            upper_guardrail=self.upper_guardrail,
            lower_guardrail=self.lower_guardrail,
            adjustment_pct=self.adjustment_pct,
        )
        return WithdrawalResult(
            label=dict(self.weights), value=withdrawal_value, monte_carlo_returns=growth_value
        )


class BucketWithdrawalStrategy:
    """QQQ/QLD/cash-style bucket strategy: a never-sold reserve sleeve, a cash buffer,
    and a growth ticker that funds withdrawals except in down years."""

    def __init__(
        self,
        growth_ticker: str,
        reserve_ticker: str,
        reserve_weight: float,
        withdrawal_rate: float,
        cash_years: float,
        down_threshold: float = 0.0,
    ):
        self.growth_ticker = growth_ticker
        self.reserve_ticker = reserve_ticker
        self.reserve_weight = reserve_weight
        self.withdrawal_rate = withdrawal_rate
        self.cash_years = cash_years
        self.down_threshold = down_threshold

    def simulate(self, close: pd.DataFrame, dividends: pd.DataFrame, cpi: pd.Series | None) -> WithdrawalResult:
        outcome = simulate_bucket_withdrawal(
            close,
            dividends,
            self.growth_ticker,
            self.reserve_ticker,
            reserve_weight=self.reserve_weight,
            withdrawal_rate=self.withdrawal_rate,
            cash_years=self.cash_years,
            down_threshold=self.down_threshold,
            cpi=cpi,
        )
        # Withdrawal decisions are baked into share dynamics from day 1 here, so there's
        # no separate pure-growth path to bootstrap Monte Carlo return samples from -
        # monte_carlo_returns stays None and this strategy is scored on historical
        # survival alone.
        return WithdrawalResult(
            label={"cash_years": self.cash_years},
            value=outcome["value"],
            extra={"guardrail_failures": len(outcome["guardrail_failures"])},
        )
