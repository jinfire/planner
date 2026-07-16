# AI Retirement Portfolio Planner Architecture

## Overview

The system is designed around a simple philosophy.

-   LLM decides **what should be evaluated**.
-   Python evaluates **every possible portfolio objectively**.
-   LLM explains **why the final portfolio was selected**.

``` text
                User
                  │
                  ▼
      Portfolio Planner (LLM)
                  │
                  ▼
        Portfolio Generator
                  │
                  ▼
        Portfolio Simulator
                  │
                  ▼
        Portfolio Ranking
                  │
                  ▼
          Advisor (LLM)
```

## Portfolio Planner (LLM)

### User Inputs

-   Additional contribution
-   Current retirement assets
-   Required monthly retirement income
-   Free-form requests

Examples of free-form requests:

-   Include leveraged ETFs
-   Prefer growth ETFs
-   Include dividend ETFs
-   Include QQQ
-   Search ETFs that Korean investors can easily purchase through a
    brokerage account

### Output

``` json
{
  "candidate_etfs": [
    "QQQ",
    "QLD",
    "SCHD",
    "TLT",
    "SGOV"
  ]
}
```

The Portfolio Planner never determines portfolio weights.

## Portfolio Generator

Generates every valid portfolio allocation from the candidate ETFs.

It performs **no financial calculations**.

## Portfolio Simulator

Simulation pipeline:

1.  Historical Backtest
2.  Dividend Reinvestment
3.  Compare All Rebalancing Strategies
4.  Compare All Withdrawal Strategies
5.  Inflation Adjustment
6.  Monte Carlo Simulation
7.  Performance Metrics
8.  Retirement Score

Internal modules:

-   Historical Backtest
-   Dividend Engine
-   Rebalancing Engine
-   Withdrawal Engine
-   Inflation Engine
-   Monte Carlo Engine
-   Metrics Engine
-   Retirement Score Engine

Performance metrics include:

-   CAGR
-   Annual Return
-   Volatility
-   Maximum Drawdown (MDD)
-   Sharpe Ratio
-   Sortino Ratio
-   Calmar Ratio
-   Ulcer Index
-   Recovery Time
-   Survival Probability
-   Final Wealth
-   Retirement Score

## Data Availability

The system only uses real historical market data. It does not fabricate
pre-inception price history for a ticker.

### Inflation rate source

-   **Historical Backtest**: uses the actual historical CPI index (US
    CPIAUCSL, from FRED) over the backtest period, so withdrawals track real
    inflation rather than an assumption.
-   **Monte Carlo Simulation**: projects into the future, where no real CPI
    data exists yet, so it uses an assumed constant inflation rate instead.

### Candidate ETFs with different inception dates

Candidate ETFs from the Portfolio Planner can have very different listing
dates (e.g. QQQ: 1999, TLT: 2002, SCHD: 2011). The Simulator only backtests
over the date range where **every** candidate ETF has data (the intersection
of their histories) and reports that effective range, rather than silently
truncating or fabricating data.

Reconstructing an ETF's pre-inception performance from its underlying
holdings was considered and rejected for now:

-   Free data sources only expose an ETF's **current** top holdings (e.g. the
    top ~10 by weight), not its full historical constituent list and weights
    at each point in the past.
-   Applying today's holdings retroactively models "what if I'd held today's
    basket back then," not the ETF's actual (different) historical
    composition — a materially different, easily-mislabeled result.
-   This approximation is more defensible for products with a fully
    mechanical replication formula (e.g. a 2x leveraged ETF tracking a
    long-lived index), and may be revisited for that narrower case.

## Portfolio Ranking

Ranks every simulated portfolio by Retirement Score.

## Advisor (LLM)

Explains:

-   Why the portfolio ranked first
-   Strengths
-   Weaknesses
-   Risks
-   Alternative portfolios

## Folder Structure

Each pipeline stage is its own top-level package. No stage's code lives inside
another stage's folder.

``` text
retirement-planner/
├── planner/                # Portfolio Planner (LLM)
├── generator/               # Portfolio Generator
│   ├── generator.py
│   └── tests/
├── simulator/                # Portfolio Simulator
│   ├── data.py                # Historical Backtest
│   ├── portfolio.py           # Dividend Engine + Rebalancing Engine
│   ├── rebalance.py
│   ├── withdrawal.py          # Withdrawal Engine
│   ├── inflation.py           # Inflation Engine (assumed rate, for Monte Carlo)
│   ├── cpi.py                 # Inflation Engine (actual CPI, for Historical Backtest)
│   ├── monte_carlo.py         # Monte Carlo Engine
│   ├── metrics.py             # Metrics Engine
│   ├── retirement_score.py    # Retirement Score Engine
│   └── tests/
├── ranking/                  # Portfolio Ranking
│   ├── ranking.py
│   └── tests/
├── advisor/                  # Advisor (LLM)
└── main.py                   # Wires the pipeline together, owned by no single stage
```

## System Philosophy

### LLM

-   Understand retirement goals
-   Select candidate ETFs
-   Explain recommendations

### Python

-   Portfolio generation
-   Historical backtesting
-   Dividend simulation
-   Rebalancing comparison
-   Withdrawal comparison
-   Inflation adjustment
-   Monte Carlo simulation
-   Metric calculation
-   Retirement score calculation
-   Portfolio ranking

## Vision

Build an AI system that finds retirement portfolios capable of:

-   Growing over decades
-   Surviving retirement withdrawals
-   Minimizing depletion risk
-   Maximizing long-term wealth
-   Supporting lasting financial independence
