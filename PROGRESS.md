# Progress

architecture-1.md 기준 진행 상황 기록.

## 아키텍처 흐름

```
User → Portfolio Planner (LLM) → Portfolio Generator → Portfolio Simulator
     → Portfolio Ranking → Advisor (LLM)
```

LLM 파트(Planner, Advisor)는 아직 손대지 않았고, Python 쪽 `Portfolio Simulator`부터
바닥부터 쌓는 중.

## 설계 결정

- **인플레이션율 소스**: 백테스트(Historical Backtest)는 실제 과거 CPI 데이터를 써서
  일관성 유지. Monte Carlo Simulation은 미래를 다루므로 실제 데이터가 없어 가정치
  (고정 `inflation_rate`) 사용.
- **후보 티커 중 상장일이 늦은 종목이 있을 때**: `simulator/backfill.py`로 상장 전
  기간을 최대한 채움 (아래 14번 참고). 그래도 못 채운 티커는 정직하게 실제 상장일로
  잘라서 쓰고 경고를 띄움 - 근거 없는 티커는 데이터를 지어내지 않는다는 원칙.

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

### 5. 폴더 구조를 아키텍처 파이프라인에 맞게 재정리
- `generator.py`를 `simulator/` 밖으로 빼서 `generator/` 패키지로 분리 (Generator는
  Simulator의 하위가 아니라 파이프라인상 형제 컴포넌트)
- `main.py`를 루트로 이동 (Generator+Simulator를 엮어 돌리는 실행 스크립트이므로
  특정 컴포넌트 소속이 아님)
- `simulator/`, `generator/`를 `__init__.py`가 있는 정식 패키지로 전환, import 경로
  전부 갱신 (`from simulator.data import ...` 등)
- 아직 만들지 않은 파이프라인 단계를 위해 `planner/`, `ranking/`, `advisor/` 빈 폴더
  생성 (architecture-1.md 참고)

### 6. Withdrawal Engine (최소 슬라이스)
- `simulator/withdrawal.py` - `simulate_withdrawal()`: 배당 재투자 + 리밸런싱은 기존
  `simulate_portfolio`와 동일하게 가져가되, 매년 첫 거래일에 고정 금액
  (초기 자본 × 인출률)을 인출. 잔고가 0 이하가 되면 그 시점부터 0으로 고정(고갈)
- `simulator/tests/test_withdrawal.py` - 매년 인출 반영, 고갈 후 0 유지,
  인출률 0일 때 `simulate_portfolio`(annual 리밸런싱)와 결과 일치 검증

### 7. Inflation Adjustment
- `simulator/inflation.py` - `inflation_adjusted_withdrawal()`: 기준 인출액을
  경과 연수만큼 인플레이션율로 복리 성장시켜 명목 인출액 계산
- `simulator/withdrawal.py` - `simulate_withdrawal()`에 `inflation_rate` 파라미터 추가.
  매년 인출액이 물가만큼 커지도록 반영 (기본값 0.0이면 기존과 동일하게 고정 인출)
- `simulator/tests/test_inflation.py`, `simulator/tests/test_withdrawal.py` - 인플레이션
  0/첫해/복리 성장 검증, 인출액이 매년 커지는지 검증

### 8. Monte Carlo Simulation
- `simulator/monte_carlo.py`
  - `annual_returns()`: 일별 포트폴리오 가치 시계열에서 연간 수익률 배열 추출
  - `simulate_paths()`: 과거 연간 수익률을 부트스트랩(복원추출)해서 `years`년치
    무작위 경로를 `num_simulations`번 생성, 인플레이션 조정 인출을 적용해서
    각 경로의 최종 잔고 계산 (`inflation_rate`는 가정치 파라미터, 설계 결정 참고)
  - `survival_probability()`: 최종 잔고가 0보다 큰 경로의 비율
- `simulator/tests/test_monte_carlo.py` - 연간 수익률 계산, 단일 수익률 복리 검증,
  인출로 고갈되는 케이스, seed로 재현 가능한지, 생존확률 계산 검증
- QQQ/SCHD 60:40 실데이터로 확인: 30년 4% 인출 + 3% 인플레이션 가정 시 생존확률 99.9%
  (2012~2024 강세장 데이터라 낙관적인 수치 - 나중에 더 긴/다양한 기간 데이터 필요)

### 9. CPI 연동 (실제 인플레이션 데이터)
- `simulator/cpi.py`
  - `fetch_cpi()`: FRED(세인트루이스 연준)의 CPIAUCSL(월간 CPI) 지수를 API 키 없이
    CSV로 fetch, 기간으로 slice
  - `cpi_adjusted_withdrawal()`: 기준 인출액에 실제 CPI 비율(해당 시점 CPI / 첫
    인출 시점 CPI)을 곱해 명목 인출액 계산 - 가정치가 아닌 실제 물가로 조정
- `simulator/withdrawal.py` - `simulate_withdrawal()`에 `cpi` 파라미터 추가.
  `cpi`를 넘기면 실제 CPI로, 안 넘기면 기존처럼 `inflation_rate` 가정치로 계산
- `simulator/tests/test_cpi.py`, `simulator/tests/test_withdrawal.py` - CPI 데이터
  fetch/slice 검증(네트워크 mock), CPI 비율 계산 검증, 실제 인출 시뮬레이션에
  CPI가 반영되는지 검증
- QQQ/SCHD 60:40 + 실제 CPI로 확인: 4% 인출 시 2012~2024 기간 고갈 없이 잔고 성장

### 10. Retirement Score Engine
- `simulator/retirement_score.py` - `retirement_score()`: 생존확률·CAGR·MDD를
  가중합해서 하나의 점수로 산출 (생존확률 100배 + CAGR 100배 - |MDD| 50배).
  0~100 절대 등급이 아니라 포트폴리오 간 상대 비교/정렬용
- `simulator/tests/test_retirement_score.py` - 생존확률/CAGR 높을수록,
  MDD 클수록 점수 방향이 맞는지, 알려진 값 검증

### 11. Portfolio Ranking
- `ranking/ranking.py` - `rank_portfolios()`: retirement_score 기준 내림차순 정렬,
  입력 리스트는 변경하지 않음
- `ranking/tests/test_ranking.py` - 정렬 순서, 빈 리스트, 원본 미변경 검증
- `main.py` - Generator → Simulator(백테스트+Monte Carlo) → retirement_score →
  Ranking까지 전체 파이프라인 연결. QQQ/SCHD/TLT 66개 조합을 4%룰+3%인플레이션
  가정, 30년/200회 Monte Carlo로 계산해서 Retirement Score 상위 5개 출력
- 실행 결과: CAGR만으로 줄 세우면 QQQ 100%가 1위였는데, Retirement Score로는
  QQQ 70%/SCHD 30%가 1위(Score=103.2, 생존확률 100%, MDD -29.29%)로 바뀜 -
  위험(MDD)과 생존확률을 반영한 점수가 실제로 순위에 영향을 준다는 것 확인

### 12. 결과를 CSV로 저장
- `main.py` - 상위 5개만 콘솔 출력하던 걸, 66개 전체를 `results.csv`로 저장하도록
  변경 (콘솔 출력은 그대로 상위 5개만 유지)
- `results.csv`는 실행할 때마다 새로 생기는 산출물이라 `.gitignore`에 추가
  (git에는 안 올림)

### 13. Portfolio Planner (LLM) - 최소 슬라이스
- `planner/planner.py`
  - `select_candidate_etfs()`: 사용자 입력(추가 납입액/현재 자산/필요 월 소득/
    자유 요청)을 프롬프트로 만들어 Anthropic Messages API를 **SDK 없이
    `requests`로 직접 HTTP 호출**, 응답에서 후보 티커 리스트를 뽑아옴.
    포트폴리오 비중은 절대 정하지 않음 (architecture-1.md와 동일한 제약)
  - `_parse_candidate_etfs()`: LLM 응답 텍스트를 JSON으로 파싱해서 검증하는
    순수 함수로 분리 (네트워크 없이 독립적으로 테스트 가능)
  - `select_candidate_etfs()`는 `http_client` 파라미터로 `.post()`를 가진
    객체를 주입받음 (기본값은 `requests` 모듈 자체) - 테스트에서 가짜
    클라이언트로 교체해서 실제 API 호출 없이 검증. API 키는 `api_key`
    파라미터 또는 `ANTHROPIC_API_KEY` 환경변수에서 읽음
- `planner/tests/test_planner.py` - JSON 파싱/빈 리스트/깨진 JSON 검증,
  가짜 HTTP 클라이언트로 호출 흐름·헤더·프롬프트 내용 검증, HTTP 에러 전파,
  환경변수에서 API 키를 읽는지 검증
- `requirements.txt`, `DEPENDENCIES.md` - SDK 대신 `requests` 사용.
  실제 호출에는 `ANTHROPIC_API_KEY` 환경변수가 필요 (이 환경엔 키가 없어서
  아직 실제 LLM 호출로 검증은 못 함 - mock 테스트만 통과한 상태)
- 아직 `main.py`에 연결 안 함 (API 키 없이도 기존 파이프라인이 계속 돌아가야
  해서 별도로 둠)

### 14. 상장일이 늦은 티커의 과거 데이터 확장 (Backfill)
- `simulator/backfill.py` - `extend_close_series()`: 티커의 실제 데이터가 원하는
  시작일까지 못 미치면, 아래 3가지 방법을 **우선순위대로** 시도해서 최대한 채움.
  1번이 안 되면 2번, 2번도 안 되면 3번, 그마저 일부만 되면(예: 목표 2000년인데
  2006년까지만 늘어남) **되는 데까지는 적용**하고 부족한 만큼만 경고를 남김
  1. **합성 복제(leverage replication)** - 레버리지/인버스 ETF는 복제 공식이
     명확함 (`LEVERAGE_REPLICATION` 매핑, 예: QLD = QQQ 일일수익률×2 - 연 0.95%
     비용). base 티커의 진짜 데이터로 역산 - 근사가 아니라 사실상 정확한 재구성
  2. **추종 지수 프록시(index proxy)** - ETF가 추종하는 지수 티커로 대체
     (`INDEX_PROXY` 매핑, 예: QQQ → ^NDX). 지수 자체가 ETF보다 오래된 경우에 씀.
     지수는 보통 price-only라 상장 전 구간의 배당은 0으로 처리 (근사)
  3. **유사 펀드 스플라이싱(splice)** - 비슷한 더 오래된 펀드로 대체
     (`SPLICE_PROXY` 매핑, 예: SCHD → VYM). 가장 부정확한 방법이라 우선순위 최하
  - `splice_series()`: 프록시의 일별 등락률을 그대로 가져와서, 실제 데이터가
    시작하는 시점 값과 정확히 이어지도록 배율만 맞춰 이어붙임(체인링크)
  - **매핑이 없거나 프록시도 데이터가 부족한 티커는 확장하지 않고 정직하게 실제
    상장일로 자름 + 경고 로그** (예: TLT는 채권 ETF라 위 3가지 어디에도 안 맞아서
    2002-07-30 이전은 못 채움 - 무료 소스로 채권 지수/ETF를 2000년대 초반보다
    더 예전까지 구하기 어려움. 유료 데이터(Bloomberg/CRSP/GFD 등)면 가능하지만
    이 프로젝트 규모에 안 맞아서 보류. 참고로 Yale Robert Shiller의 무료
    장기(1871~) 채권 수익률 데이터가 대안이 될 수 있는데 월별이라 일별 파이프라인에
    바로 안 맞아서 아직 안 씀)
  - `simulator/data.py` - `fetch_price_data()`가 각 티커별로 실제 데이터를 받아온
    뒤, 시작일에 못 미치는 티커만 `extend_close_series()`로 보완. 나머지 흐름
    (여러 티커 교집합으로 정렬)은 그대로
  - `simulator/tests/test_backfill.py` - 복제 공식 계산(비용 차감 포함),
    스플라이싱 체인링크, 우선순위 순서대로 시도하는지, 부분 확장도 유지하는지,
    매핑이 아예 없으면 원본 그대로 반환하는지 검증
  - **투명성 원칙**: 어떤 구간이 실제 데이터고 어떤 구간이 합성/추정인지 항상
    구분 가능해야 함 (나중에 Advisor가 "이 백테스트는 어디까지가 실데이터인지"
    설명할 때 이 로직을 그대로 근거로 씀) - 실측: QLD는 2000년까지 완전히 복제
    성공(방법 1), SCHD는 VYM으로 2006년까지만 확장(방법 3, 목표 2000년엔 못 미침),
    TLT는 매핑이 없어 2002-07-30 그대로

### 15. 실제 인출 시뮬레이션을 Monte Carlo의 선행 게이트로 연결
- `main.py` - 포트폴리오마다 먼저 `withdrawal.py`(실제 CPI로 과거를 그대로
  인출하며 재생)를 돌려서 실제 역사에서 고갈됐는지 확인 (`historical_survived`).
  고갈됐으면 그 자리에서 `survival_probability=0.0`으로 확정하고 Monte Carlo는
  건너뜀 - 실제 역사도 못 버틴 포트폴리오에 확률적 시뮬레이션을 돌릴 필요가 없다는
  판단. 통과한 포트폴리오만 기존처럼 Monte Carlo로 미래 확률까지 계산
- 결과에 `historical_survived` 필드 추가 (CSV에도 포함) - 실제 역사 기준 통과
  여부와 확률적 생존확률을 구분해서 볼 수 있음
- 실측: QQQ+TLT(2002~2024), 4% 인출 시 11개 조합 전부 역사적으로 생존. 10%
  인출로 올리면 QQQ 100% 조합이 실제로 고갈되는 것 확인 (분기 로직 정상 동작)

## 아직 안 한 것 (지금 상태의 한계)

- Portfolio Planner를 실제 API 키로 검증 (지금은 mock 테스트만 통과)
- Portfolio Planner를 main.py에 연결
- Advisor (LLM) - 결과 설명
- 채권류(TLT 등) 과거 데이터 확장 - Shiller 월별 데이터 연동은 보류 (지금 우선순위
  아님)

## 다음 후보

1. Advisor (LLM) - 1위 포트폴리오가 선정된 이유, 강점/약점/리스크/대안 설명
2. Planner를 실제 API 키로 검증 후 main.py에 연결
