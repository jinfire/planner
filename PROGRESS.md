# Progress

architecture-1.md 기준 진행 상황 기록.

## 아키텍처 흐름

```
User → Portfolio Planner (LLM) → Portfolio Generator → Portfolio Simulator
     → Portfolio Ranking → Advisor (LLM)
```

LLM 파트(Planner, Advisor)는 아직 손대지 않았고, Python 쪽 `Portfolio Simulator`부터
바닥부터 쌓는 중.

## 한 것

### 1. Simulator 최소 슬라이스
- `simulator/data.py` - yfinance로 가격/배당 데이터 fetch
- `simulator/portfolio.py` - 고정 비중 buy-and-hold 포트폴리오 가치 계산
- `simulator/metrics.py` - CAGR, 연변동성, MDD
- `simulator/main.py` - QQQ 60% / SCHD 40% 샘플 포트폴리오로 실행 확인

### 2. 배당 재투자 + 리밸런싱 비교
- `simulator/data.py` - 원본(미조정) 가격과 배당을 분리해서 가져오도록 변경
- `simulator/rebalance.py` - 리밸런싱 주기(none/monthly/quarterly/annual)별 실행일 계산
- `simulator/portfolio.py` - 주식 수(shares) 기반 시뮬레이션으로 재작성.
  배당을 같은 종목에 재투자하고, 리밸런싱 시점마다 목표 비중으로 재조정
- `simulator/main.py` - 같은 포트폴리오를 4가지 리밸런싱 전략으로 비교 출력

### 3. Git / GitHub
- `retirement-planner` 폴더를 상위 `coding` repo와 별개의 독립 git 저장소로 생성
- https://github.com/jinfire/planner.git 에 `main` 브랜치로 push 완료

### 4. Portfolio Generator
- `simulator/generator.py` - `generate_portfolios()`: 후보 티커 리스트 + step(%)을 받아
  합이 100%가 되는 모든 비중 조합 생성 (stars-and-bars 조합론, 재무 계산 없음)
- `simulator/tests/test_generator.py` - 조합 개수, 합=1.0, stars-and-bars 공식 대조 검증
- `simulator/main.py` - QQQ/SCHD/TLT 3종목, 10% 단위로 조합 생성 → 각 조합 시뮬레이션 →
  CAGR 기준 상위 5개 출력까지 연결

### 5. Withdrawal Engine (최소 슬라이스)
- `simulator/withdrawal.py` - `simulate_withdrawal()`: 배당 재투자 + 리밸런싱은 기존
  `simulate_portfolio`와 동일하게 가져가되, 매년 첫 거래일에 고정 금액
  (초기 자본 × 인출률)을 인출. 잔고가 0 이하가 되면 그 시점부터 0으로 고정(고갈)
- `simulator/tests/test_withdrawal.py` - 매년 인출 반영, 고갈 후 0 유지,
  인출률 0일 때 `simulate_portfolio`(annual 리밸런싱)와 결과 일치 검증
- 아직 인플레이션 조정 없음 (매년 인출액이 실질 가치로 감소하지 않고 고정 명목 금액)

## 아직 안 한 것 (지금 상태의 한계)

- Inflation Adjustment (인출액 물가 연동)
- Monte Carlo Simulation
- Retirement Score Engine
- Portfolio Ranking
- Portfolio Planner (LLM) - 후보 ETF 선정
- Advisor (LLM) - 결과 설명

## 다음 후보

1. Inflation Adjustment - 매년 인출액을 물가상승률만큼 조정
2. Monte Carlo Engine - 확률적 시뮬레이션으로 생존 확률 계산
