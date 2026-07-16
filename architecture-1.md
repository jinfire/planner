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

## Portfolio Ranking

Ranks every simulated portfolio by Retirement Score.

## Advisor (LLM)

Explains:

-   Why the portfolio ranked first
-   Strengths
-   Weaknesses
-   Risks
-   Alternative portfolios

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
