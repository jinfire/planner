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

## 아직 안 한 것 (지금 상태의 한계)

- **여전히 고정 포트폴리오 하나(QQQ/SCHD 60:40)만 테스트 중.**
  Generator(후보 ETF로 가능한 모든 비중 조합 생성)는 아직 없음
- Withdrawal Engine (인출 전략 비교)
- Inflation Adjustment
- Monte Carlo Simulation
- Retirement Score Engine
- Portfolio Ranking
- Portfolio Planner (LLM) - 후보 ETF 선정
- Advisor (LLM) - 결과 설명

## 다음 후보

1. Portfolio Generator - 후보 ETF 리스트를 받아 모든 비중 조합 생성 (재무 계산 없음)
2. Withdrawal Engine - 은퇴 후 인출 시뮬레이션
3. Monte Carlo Engine - 확률적 시뮬레이션으로 생존 확률 계산
