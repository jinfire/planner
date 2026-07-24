# Progress

architecture-1.md 기준 진행 상황 기록.

## 아키텍처 흐름

```
User → Portfolio Generator → Portfolio Simulator → Portfolio Ranking → Advisor
```

Planner(LLM)는 만들지 않기로 결정하고 폴더째 삭제함 (28번 항목 앞 "다음 후보"
참고) - "생각지도 못한 조합 발견"이라는 원래 목적이 Generator의 전수조사로 이미
커버됨. Advisor도 LLM 대신 코드 기반으로 구현함(28번).

## 설계 결정

- **인플레이션율 소스**: 백테스트(Historical Backtest)는 실제 과거 CPI 데이터를 써서
  일관성 유지. Monte Carlo Simulation은 미래를 다루므로 실제 데이터가 없어 가정치
  (고정 `inflation_rate`) 사용.
- **후보 티커 중 상장일이 늦은 종목이 있을 때**: `simulator/backfill.py`로 상장 전
  기간을 최대한 채움 (아래 14번 참고). 그래도 못 채운 티커는 정직하게 실제 상장일로
  잘라서 쓰고 경고를 띄움 - 근거 없는 티커는 데이터를 지어내지 않는다는 원칙.
- **정확한 값 vs 근사값 구분은 최종적으로 사용자에게 보여줘야 함**: backfill로
  채운 구간이 실제 데이터(real)인지, 공식으로 정확히 역산한 값(exact - 레버리지
  복제/국채·T-Bill 수익률 역산)인지, 비슷한 다른 자산으로 근사한 값(approx - 지수
  프록시/유사 펀드 스플라이싱)인지는 지금 경고 로그로만 남고 결과에는 안 드러남.
  나중에 결과를 보여줄 때(Advisor 설명, CSV 등) 이 구분이 사용자에게 보이도록
  해야 함 - 지금 당장 구현하진 않고 다음 후보로만 남겨둠 (20번 참고).

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

### 16. 가드레일(버킷) 인출 전략 추가 + 전략 선택 가능하게 분리
- `simulator/guardrail.py` - `simulate_guardrail_withdrawal()`: 기존 고정비율
  인출(`withdrawal.py`)과 별개로, "성장/보존/현금" 3개 역할로 자산을 나누는
  버킷 전략을 구현
  - **reserve 티커(예: QLD)는 절대 안 팜** - 배당 재투자만 하며 계속 복리로 굴림
  - **현금 버퍼** - `cash_years`(인출액 기준 몇 년치를 현금으로 들고 있을지)로
    크기를 정함, 시장에 투자하지 않고 그대로 보유 (이자 없음 - 최소 슬라이스)
  - **growth 티커(예: QQQ)의 그 해 수익률이 `down_threshold`(기본 0%) 미만이면
    "하락한 해"로 판단** - 하락한 해엔 growth를 안 팔고 현금에서 인출.
    안 하락한 해엔 growth를 팔아서 인출하고, 남는 만큼 현금 버퍼를 목표치까지
    다시 채움
  - 현금이 부족한 하락한 해엔 어쩔 수 없이 growth를 팔고 `guardrail_failures`에
    그 날짜를 기록 (가드레일이 막지 못한 경우를 추적)
  - "하락한 해" 기준을 0%(그 해 수익률이 마이너스면 무조건)로 잡은 이유: 버킷
    전략의 핵심이 "손실 상태에서 파는 것 자체를 피하는 것"이라, -5%나 -10%처럼
    문턱을 높이면 그 사이 구간에서도 여전히 손절 매도가 발생해서 전략의 취지가
    흐려짐
  - `simulator/tests/test_guardrail.py` - 상승한 해 growth로 인출+현금 리필,
    하락한 해 현금으로 인출(growth 안 건드림), 현금 부족 시 growth 매도+실패
    로그, reserve 티커가 어떤 상황에서도 안 팔리는지, `cash_years`에 비례해서
    초기 현금 크기가 커지는지 검증
  - 실측(QQQ growth/QLD reserve 10%, 2000~2024, 4% 인출, `cash_years` 1~10년
    스윕): **현금 버퍼 크기와 무관하게 최종 잔고가 전부 동일(0.339)** - 2000년
    닷컴버블이 워낙 커서 growth+현금(전체의 90%)이 `cash_years`에 상관없이
    2010~2013년 사이 완전히 고갈되고, 그 이후는 한 번도 안 판 QLD 10%가
    2003년 저점 대비 2024년까지 약 94배 불어난 것만 남아서 결과가 수렴함.
    다만 `cash_years`가 클수록 "손실 상태에서 강제 매도(guardrail_failures)"
    횟수는 확실히 줄어듦 (1년치 6회 → 5년치 이상 2회로 안정화) - 현금 버퍼가
    최종 잔고를 못 지켜도 매도 시점의 질은 개선시킴
- `main.py` - `WITHDRAWAL_STRATEGY` 상수("flat" 또는 "guardrail")로 두 인출
  전략 중 하나를 선택해서 돌릴 수 있게 분리
  - `"flat"`: 기존처럼 Generator가 만든 비중 조합들을 스윕, Monte Carlo까지 포함
  - `"guardrail"`: 비중 조합 대신 `GUARDRAIL_CASH_YEARS_OPTIONS`(현금 버퍼
    연수 목록)를 스윕. **Monte Carlo는 아직 연결 안 함** - 미래 경로마다
    버킷 상태머신(어느 해가 상승/하락인지에 따라 분기)을 통째로 재현해야 해서
    단순 인출 공식(`simulate_paths`)으로는 안 됨. 지금은 실제 역사 기준
    생존 여부만(0.0/1.0) 보고함

### 17. 인출 전략 파일/함수명 정리 (용어 혼동 방지)
- 은퇴설계 업계에서 "가드레일(Guardrails)"은 원래 Guyton-Klinger 방식(인출률이
  상/하한선을 넘으면 인출**액** 자체를 올리고 내리는 전략)을 가리키는 용어인데,
  16번에서 만든 건 정확히는 "**버킷 전략**"(자산을 성장/보존/현금으로 나눠서
  어디서 팔지 정하는 것)이라 이름이 겹쳐서 혼동될 수 있었음
- `simulator/guardrail.py` → `simulator/bucket_strategy.py`,
  `simulate_guardrail_withdrawal()` → `simulate_bucket_withdrawal()`로 변경
- `simulator/withdrawal.py` → `simulator/constant_withdrawal.py`,
  `simulate_withdrawal()` → `simulate_constant_withdrawal()`로 변경 (이것도
  "Constant Dollar" 인출 전략이라는 걸 이름에서 바로 알 수 있게)
- 테스트 파일도 `test_bucket_strategy.py`, `test_constant_withdrawal.py`로 함께
  변경, `main.py`의 `GUARDRAIL_*` 상수도 `BUCKET_*`로, `WITHDRAWAL_STRATEGY`
  값도 `"guardrail"` → `"bucket"`으로 변경
- (참고) 결과 딕셔너리의 `guardrail_failures` 키 자체는 그대로 둠 - "버킷
  전략 안의 가드레일 규칙이 막지 못한 경우"라는 의미라 이름 충돌이 아님

### 18. 인출 전략에 Strategy 패턴 적용 - 하나만 고르거나 전부 다 비교
- 문제의식: "전략을 하나 고를지, 전부 다 해볼지"는 결국 둘 다 "같은 인터페이스를
  가진 전략 객체들을 순회"하는 문제라, `main.py`의 if/elif 분기 대신 공통
  인터페이스로 통일하면 둘 다 자연히 해결됨 (Strategy 패턴)
- `simulator/strategy.py` (신규)
  - `WithdrawalResult` (dataclass) - 모든 전략이 공통으로 반환하는 표준 결과.
    처음엔 `growth_value`(무인출 성장)/`withdrawal_value`(인출 반영)로 나눴는데,
    버킷 전략엔 "무인출 성장"이라는 개념 자체가 없어서(첫날부터 인출 로직이
    주식 수 계산에 얽혀있음) 결국 같은 시리즈를 두 필드에 억지로 채워넣는
    상황이 됐음. **은퇴설계에서 진짜 중요한 건 "실제로 인출하며 산 잔고"
    하나뿐**이라는 결론을 내리고, `value`(실제 인출 반영 잔고 - CAGR/MDD/생존
    여부의 유일한 기준) 하나로 단순화. Monte Carlo용 순수 성장 수익률은
    `monte_carlo_returns`(선택값, 없으면 `None`)로 분리해서 "이 전략은 확률
    계산을 못 한다"는 게 코드에서 정직하게 드러나게 함
  - `ConstantWithdrawalStrategy` - `value`는 `simulate_constant_withdrawal`
    결과, `monte_carlo_returns`는 `simulate_portfolio`(무인출) 결과
  - `BucketWithdrawalStrategy` - `value`만 있고 `monte_carlo_returns=None`
    (버킷 상태머신을 경로마다 재현 못 해서 아직 Monte Carlo 지원 안 됨)
  - `simulator/tests/test_strategy.py` - 각 전략의 label/value/
    monte_carlo_returns가 올바른지, guardrail_failures가 extra에 담기는지 검증
- `main.py` - `WITHDRAWAL_STRATEGY`를 `"flat"` / `"bucket"` / **`"all"`**(둘 다
  돌려서 한 리스트로 같이 랭킹) 중 하나로 설정. 전략별 특수 처리(if/elif)는
  전부 사라지고, `evaluate(strategy.simulate(...))`를 순회하는 한 가지 경로로
  통일됨. `required_tickers()`로 활성화된 전략들이 필요로 하는 티커를 합쳐서
  fetch - 어느 조합이든 데이터 누락 없이 동작
- CAGR/MDD를 `growth_value`(순수 성장) 대신 `value`(실제 인출 경로) 기준으로
  바꾸면서 부작용 발견: 잔고가 정확히 0으로 고갈되는 순간 CAGR/MDD 공식이
  항상 -100%/-100%가 나와서, **고갈된 포트폴리오끼리는 원래 자산 품질과
  무관하게 전부 점수가 똑같아짐** (예: QQQ 100%도 QLD 100%도 똑같이 최하위) →
  19번에서 해결

### 19. 고갈된 포트폴리오끼리도 "얼마나 오래 버텼는지"로 순위 매기기
- `simulator/metrics.py` - `years_survived()`: 잔고가 0을 찍기 전까지 버틴
  기간이 전체 백테스트 기간의 몇 %인지 반환 (한 번도 고갈 안 하면 1.0)
- `simulator/retirement_score.py` - `retirement_score()`에 `survival_fraction`
  파라미터(기본 1.0) 추가, 가중치는 10(`longevity_weight`)으로 일부러 작게 잡음
  - 실제로 생존한 포트폴리오의 순위는 절대 못 뒤집음 (survival_probability
    가중치 100에 비해 10은 미미함) - 오직 "이미 똑같이 실패한 것들" 사이에서만
    타이브레이커로 작동
- `main.py` - `evaluate()`가 `years_survived(result.value)`를 계산해서
  `retirement_score()`에 넘김, 결과 딕셔너리에 `years_survived` 필드도 추가
- 실측: QQQ/QLD 2000~2024, flat 전략 11개 전부 고갈이지만 이제 점수가
  -146.4 ~ -147.6로 세분화됨 - QQQ 100%(제일 오래 버팀)가 실패 그룹 중 1위,
  QLD 비중이 높을수록 더 일찍 고갈돼서 순위가 낮아짐

### 20. Backfill 확장 - "고전적 자산배분(60/40, 3-Fund 등)"용 12개 자산 지원
- 사용자가 공유한 설계 문서(Classic Portfolio Backtest Data Strategy) 기준으로
  MVP 자산 12개(대형주/성장주/전체주식/배당성장/배당귀족/선진국/신흥국/장기국채/
  중기국채/종합채권/단기채/금)를 2000년부터 끊김 없이 백테스트 가능하게 확장
- 자산군마다 "그 ETF가 실제로 추종하는 지수"를 프록시로 쓰는 게 이상적인데,
  MSCI/Dow Jones/S&P/Bloomberg 지수 원자료는 대부분 유료라 무료로는 못 구함.
  **진짜 무료로 정확하게 되는 것과, 근사치로만 되는 것을 구분**해서 처리:
  - **진짜로 정확한 것 (신규 방법)**:
    - `simulator/fred_data.py` (신규) - `fetch_fred_series()`: FRED 아무 시리즈나
      API 키 없이 CSV로 fetch (기존 `cpi.py`와 같은 패턴을 재사용 가능하게 일반화)
    - `simulator/backfill.py`
      - `replicate_from_treasury_yield()`: FRED 국채 수익률(예: DGS20)로 채권
        ETF 가격을 역산. 공식: `일일수익률 ≈ -듀레이션 × 수익률변화분 + 수익률/365(캐리)`.
        TLT(듀레이션 17년 가정, DGS20)/IEF(듀레이션 7.5년 가정, DGS10) 둘 다
        **2000년까지 완전히 채워짐** (FRED가 1962년부터 있어서)
      - `replicate_from_tbill_yield()`: FRED 3개월 T-Bill 수익률(DTB3)로 단순
        일일 복리만 반영(듀레이션 거의 0이라 수익률 변동 항은 무시). SGOV/BIL도
        **2000년까지 완전히 채워짐** (DTB3가 1954년부터 있어서)
      - `INDEX_PROXY`에 `"GLD": "GC=F"`(금 선물) 추가 - FRED엔 더 이상 금 시세
        시리즈가 없어서, 야후파이낸스의 금 선물 티커로 대체 (2000-08부터, 완전한
        2000년 커버는 아니지만 개선됨)
  - **근사치로만 되는 것 (기존 스플라이싱 방법 확장)**: `SPLICE_PROXY`에 추가
    - VTI → SPY (1993~, 소형주 차이는 있지만 둘 다 미국 전체 시장)
    - NOBL → DVY (2003-11~, 둘 다 배당 중심 ETF)
    - VEA → EFA (2001-08~, **둘 다 MSCI EAFE 추종이라 근사 정확도 높음**)
    - VWO → EEM (2003-04~, **둘 다 MSCI EM 추종이라 근사 정확도 높음**)
    - BND → AGG (2003-09~, 둘 다 Bloomberg US Aggregate Bond 추종)
  - **여전히 안 되는 것**: DBC(원자재) - 2006년 이전 무료로 구할 수 있는 광범위
    원자재 지수 프록시가 없어서 정직하게 2006-02부터로 남김
  - `extend_close_series()`가 이제 5단계 우선순위로 확장됨: 레버리지 복제 →
    국채 수익률 역산 → T-Bill 수익률 역산 → 지수/선물 프록시 → 유사 펀드
    스플라이싱. `fetch_fred` 콜백을 새로 받아서(없으면 FRED 관련 두 단계는
    자동 스킵) `simulator/data.py`의 `fetch_price_data()`가 실제로 연결
  - `simulator/tests/test_fred_data.py`, `simulator/tests/test_backfill.py` -
    두 역산 공식(평평한 수익률=순수 캐리, 수익률 상승=손실 방향인지), 우선순위
    순서, `fetch_fred` 없을 때 자동 스킵되는지 검증
  - 실측(TLT+SGOV, 2000~2024): 경고 없이 **2000-01-03부터 완전히 채워짐**
    (6253거래일). 핸드오프 지점(TLT 2002-07-29, SGOV 2020-05-29)도 값이
    자연스럽게 이어짐 확인. VEA/NOBL/VWO/BND는 각각 EFA/DVY/EEM/AGG 상장일까지만
    개선(2000년 완전 커버는 아님), DBC는 그대로 2006-02

### 21. 시뮬레이션 엔진 벡터화 (하루 단위 파이썬 루프 → 구간 단위 numpy 연산)
- 문제: 6개 티커 조합 252개를 스윕하는 데 36분이 걸렸음. 실측해보니 데이터 fetch는
  12초(1회성)인데 **포트폴리오 1개 시뮬레이션에 8.5초**가 걸림 - 원인은
  `simulate_portfolio`/`simulate_constant_withdrawal`/`simulate_bucket_withdrawal`
  전부 ~6300 거래일을 순수 파이썬 `for` 루프로 돌면서 매번 `pandas.loc`로 값을
  꺼내던 방식이었음
- **핵심 아이디어**: 리밸런싱/인출 시점 사이에는 주식 수가 배당재투자로만
  바뀌는데, 이건 "매일 (1 + 배당/가격)을 곱하는" 누적곱(cumulative product)이라
  **구간 전체를 numpy로 한 번에 계산 가능**함. 그래서 파이썬 루프를 "하루마다"가
  아니라 "**리밸런싱/인출 시점마다**"(연 1회~분기 1회, 25년이면 25~100번)만
  돌도록 재작성. 각 구간 안에서는 `cumprod()`로 벡터 연산
  - `simulator/portfolio.py` - `simulate_portfolio()`: 리밸런싱 시점 기준으로 구간을
    나눠서 각 구간을 numpy 배열로 한 번에 계산, 구간 경계에서만 비중 재조정
  - `simulator/constant_withdrawal.py` - `simulate_constant_withdrawal()`: 리밸런싱
    시점과 인출 시점의 합집합으로 구간을 나눔, 인출 시점에서만 인출액 계산+고갈
    체크(파이썬 스칼라 연산, 구간 자체는 여전히 벡터화)
  - `simulator/bucket_strategy.py` - `simulate_bucket_withdrawal()`: reserve
    티커는 절대 안 팔리니까 **전체 기간을 통째로 한 번에** `cumprod()`, growth
    티커만 인출 시점마다 구간을 나눠서 계산
  - 기존 테스트(고정 샘플 데이터, `pytest.approx` 정확값 비교)를 전부 그대로
    두고 통과시켜서 동작이 100% 동일한지 검증 - 새 테스트 추가 없이 리팩터링만
  - 실측: 포트폴리오 1개 시뮬레이션 **8.5초 → 0.014초 (약 600배)**. 252개 조합
    스윕이 36분 → 3.5초. 버킷 전략도 실제 QQQ/QLD 데이터로 이전 결과
    (`final_value=0.339028`, `guardrail_failures` 6/2/2)와 **정확히 일치** 확인
- 이 속도 개선 덕분에 롤링 윈도우(여러 시작연도)나 인출 전략 여러 개를 곱해서
  돌리는 게 이제 현실적으로 가능해짐 (예전엔 몇 시간~며칠 걸릴 게 몇 분으로)

## 아직 안 한 것 (지금 상태의 한계)

- Portfolio Planner를 실제 API 키로 검증 (지금은 mock 테스트만 통과)
- Portfolio Planner를 main.py에 연결
- Advisor (LLM) - 결과 설명
- DBC(원자재) 2006년 이전 데이터 - 무료로 구할 수 있는 프록시가 없어서 보류
- 버킷 전략에 Monte Carlo 연결 (버킷 상태머신을 경로마다 재현해야 함) - 지금은
  Monte Carlo 없이 역사적 생존 여부(binary)만으로 점수 매김
- 다른 인출 전략들 (Constant Percentage, Guyton-Klinger Guardrails, Floor-and-Upside,
  VPW, Endowment 스무딩 등) - 아직 설계만 논의, 구현은 안 함
- 전략을 사용자가 고르는 게 아니라, architecture-1.md 의도대로 모든 전략을 자동
  비교해서 Retirement Score로 랭킹하는 구조로 바꾸는 것 (지금은 `main.py`에
  개발자가 상수로 하드코딩)
- 새로 지원한 12개 자산으로 실제 60/40, 3-Fund, All Weather 같은 고전적
  자산배분 전략을 `main.py`에서 돌려보는 것 (지금은 backfill 기능만 검증됨,
  포트폴리오 조합으로는 아직 안 써봄)
- **정확값(real/exact)과 근사값(approx) 구분을 사용자에게 보여주기** - 지금
  `extend_close_series()`/`splice_series()`는 구간이 바뀌는 지점을 계산 중엔 알고
  있지만 그 정보를 버리고 최종 가격 시리즈만 반환함. 나중에 이 정보를 결과에
  같이 실어서(예: 티커별 "언제부터 언제까지는 실데이터, 언제부터는 어떤 방법의
  근사치" 같은 형태) Advisor가 설명할 때나 최종 결과 화면에서 사용자가 볼 수
  있게 해야 함

### 22. Guyton-Klinger 인출 전략
- `simulator/guyton_klinger.py` - `simulate_guyton_klinger_withdrawal()`: 인출**액**
  자체를 매년 성과에 맞춰 동적으로 조정. 다른 엔진들과 동일하게 리밸런싱/인출
  구간별로 벡터화해서 처음부터 빠르게 작성
  - 매년 "지난 1년간 포트폴리오 순수 투자수익률"(인출 시점 직전 잔고 ÷ 작년
    인출 후 잔고 - 1)을 계산 - 이게 마이너스면 **인플레이션 동결 규칙**: 이번
    인출액은 작년 인출액에서 물가 반영 없이 그대로
  - "계획된 인출액 ÷ 지금 잔고" = 현재 인출률을 초기 인출률과 비교해서:
    **초기의 120% 초과 → 인출액 10% 삭감**(자본보존 규칙),
    **초기의 80% 미만 → 인출액 10% 인상**(번영 규칙)
  - 초기 구현 때 "몇 년 전 수익률을 어느 해 인출 결정에 반영해야 하는지" 순서를
    한 번 잘못 짤 뻔함(이전 반복문에서 계산해서 다음 반복문에 넘기는 방식) -
    "그 해 인출을 결정하는 바로 그 시점에, 그 시점 기준 직전 1년 수익률을 즉시
    계산해서 그 해 결정에 바로 쓰는" 방식으로 바로잡음 (하나의 인출 시점 안에서
    year_return 계산 → 동결 여부 판단 → 가드레일 적용까지 한 번에)
  - `simulator/tests/test_guyton_klinger.py` - 기본 케이스(초기 인출률 그대로),
    자본보존 규칙(폭락 후 삭감), 번영 규칙(급등 후 인상), 인플레이션 동결
    규칙(하락한 해 다음 동결 vs 상승한 해 다음 정상 인상 - 짝으로 비교), 고갈
    검증
  - `simulator/strategy.py` - `GuytonKlingerWithdrawalStrategy` 추가 (Constant와
    구조 동일: `simulate_portfolio`로 Monte Carlo용 순수 성장 경로 같이 제공)
  - `main.py` - `WITHDRAWAL_STRATEGY`에 `"guyton_klinger"` 옵션 추가
- 실측(SPY/QQQ/QLD/TLT/IEF/SGOV, 2000~2024, 252개 조합, `"all"` 모드로 flat과
  나란히 비교): **G-K 1위(Score 90.9)가 flat 1위(89.6)보다 높음** - 같은
  자산배분이어도 인출액을 동적으로 조정하는 것 자체가 실제로 더 나은 결과를
  만든다는 걸 확인. 252개 조합 13.5초, flat+G-K+bucket 514개 다 합쳐도 14.3초
  (벡터화 이전이었으면 수십 분~1시간 이상 걸렸을 규모)

### 23. 롤링 윈도우 테스트 + Score 가중치를 사용자가 정하게 분리
- `simulator/rolling_window.py` (신규)
  - `rolling_start_years()`: 전체 데이터 기간 안에서 `window_years`짜리 구간이
    완전히 들어가는 시작연도를 전부 계산 (예: 2000~2024, 15년 윈도우면
    2000~2010년 시작, 총 11개 윈도우)
  - `evaluate_rolling_window()`: 같은 전략 객체를 각 시작연도로 슬라이싱한
    데이터에 대고 반복 실행해서 성공률(생존 비율)/중간값·최악 최종잔고를 집계.
    전략 객체가 `.simulate(close, dividends, cpi)`만 지원하면 되니까 flat/G-K/
    bucket 아무 전략이나 그대로 재사용 가능 (Strategy 패턴 덕)
  - `simulator/tests/test_rolling_window.py` - 진짜 인출 로직 대신 가짜 전략
    객체(정해진 연도만 실패하도록 조작 가능)로 윈도우 분할/집계 로직만 독립적으로
    검증 (실제 인출 수식 검증은 각 엔진 테스트에서 이미 하니까 중복 안 함)
- `main.py` - `USE_ROLLING_WINDOW`/`ROLLING_WINDOW_YEARS` 추가. 켜면
  `survival_probability`가 (기존의) Monte Carlo 확률이나 단일 이력 생존 여부
  대신 **여러 시작연도에 걸친 실제 성공률**로 대체됨 - 하나의 역사적 경로(2000년)
  만 보고 판단하는 것보다 더 탄탄한 근거
- **Score 가중치를 상수로 분리**: `retirement_score()`는 원래도
  `survival_weight`/`growth_weight`/`risk_weight`/`longevity_weight` 파라미터를
  받았는데 `main.py`에서 기본값만 썼음 → `SCORE_*_WEIGHT` 상수로 빼서 사람마다
  다른 선호를 반영 가능하게 함
  - 기본값을 "은퇴 후엔 생존이 최우선, 성장은 간접적 보너스(성장→실효 인출률이
    낮아짐→더 안전해짐)"라는 사용자 철학에 맞춰 조정: `growth_weight`
    100 → **20**, 나머지(`survival_weight`=100, `risk_weight`=50,
    `longevity_weight`=10)는 유지
- 실측(SPY/QQQ/QLD/TLT/IEF/SGOV, 15년 윈도우 11개, flat+G-K+bucket 514개
  조합, `USE_ROLLING_WINDOW=True`): 전체 514초 스윕이 108초 (벡터화 덕분에
  현실적인 시간). 근데 **1위가 CAGR -0.13%인 극도로 보수적인 조합**으로 나옴 -
  다들 생존률 100%(11/11 윈도우 전부 생존)로 동률이라, 그 안에서는 MDD 가중치
  (50)가 성장 가중치(20)보다 커서 "덜 흔들린" 조합이 이김. 이건 버그가 아니라
  "4% 고정 인출률 기준으로 안전하게 살아남으려면 이 자산군 안에서는 성장을
  거의 포기해야 한다"는 걸 보여주는 실제 결과로 받아들이기로 함 (사용자 확인)
- 한계: 데이터가 2000~2024 딱 25년뿐이라 윈도우가 6~16개밖에 안 나옴 (Trinity
  Study류는 90~100년 데이터로 수십 개 윈도우를 만듦) - "성공률 100%"가 통계적
  으로 아주 튼튼한 결론은 아님

### 24. Backfill 재귀 확장 - 베이스/프록시 티커 자체도 늘어난 만큼 물려받기
- 문제 발견: QLD는 "QQQ×2배" 공식으로 확장하는데, QQQ 자체가 ^NDX 지수 프록시로
  1985년까지 늘어날 수 있어도 QLD는 그 혜택을 못 받고 **QQQ의 실제 상장일(1999)
  에만 묶여있었음**. `simulator/data.py`의 `fetch_close()`가 베이스/프록시
  티커를 요청받으면 그 티커의 **진짜 데이터만** 돌려주고, 그 티커 자신의 backfill
  매핑은 안 써봤던 게 원인 (레버리지 복제·스플라이싱 둘 다 걸리는 문제 -
  SCHD→VYM, VTI→SPY 등도 마찬가지였음)
- 해결: `fetch_close()`가 재귀적으로 자기 자신을 호출해서, 요청받은 티커도
  스스로 확장을 시도한 뒤 돌려주도록 변경. 순환 참조 방지용으로 `_seen` 집합을
  같이 넘김
- `simulator/tests/test_data.py` - QLD(짧은 실데이터)가 QQQ(중간 길이 실데이터)를
  거쳐 ^NDX(제일 긴 데이터)까지 재귀적으로 이어지는지 가짜 `yf.download`로 검증
- 실측: **QLD 1999년 → 1985년으로 확장**(14년 추가), VTI는 SPY→^GSPC 체인으로
  1927년까지, SPY/QQQ/QLD/TLT/IEF/SGOV 6개를 다 같이 쓰면 **1999년 → 1985년**
  (26년 → 40년)으로 늘어남

### 25. 포트폴리오마다 자기 티커만큼만 데이터 기간 쓰기 (사전계산의 첫 조각)
- 문제의식: 지금까지는 "18개(또는 6개) 다 같이 fetch → 교집합"이라 제일 짧은
  자산 하나가 전체를 다 끌어내렸음. 근데 실제로 QLD를 0% 쓰는 조합이라면 QLD의
  짧은 역사에 얽매일 이유가 없음 - **조합마다 실제로 쓰는 자산만으로 교집합해야
  더 긴 기간을 쓸 수 있음**
- `simulator/data.py`
  - `fetch_extended_series(tickers, start, end)` (신규) - 기존 `fetch_price_data`의
    내부 로직(재귀 확장 포함)은 그대로 두되, 마지막에 전체 티커를 교집합하지
    않고 **티커별로 각자 확장된 시리즈를 그대로** 딕셔너리로 반환
  - `intersect_tickers(series_by_ticker, tickers)` (신규) - 딕셔너리에서 원하는
    티커 부분집합만 골라 교집합 - 어떤 부분집합을 고르느냐에 따라 결과 기간이
    달라짐
  - `fetch_price_data()`는 이제 이 둘을 합친 얇은 래퍼로 재작성 (기존 동작/
    테스트는 그대로 유지)
- `simulator/strategy.py` - 모든 전략 클래스에 `.tickers` 속성 추가 (실제로
  쓰는 티커 목록). `ConstantWithdrawalStrategy`/`GuytonKlingerWithdrawalStrategy`는
  **비중이 0인 티커를 자동으로 제외**(`self.tickers`도, `simulate()`에 넘기는
  가중치도), `BucketWithdrawalStrategy`는 growth+reserve 티커 고정 2개.
  `label`(CSV 표시용)은 0% 티커도 그대로 남겨서 결과표는 모든 티커 컬럼을
  일관되게 유지
- `main.py` - 전체 유니버스를 `fetch_extended_series()`로 한 번만 fetch해두고,
  `evaluate()`가 전략마다 `intersect_tickers(universe, strategy.tickers)`로
  필요한 것만 골라 씀. 결과에 `data_start`/`data_years` 필드 추가 - 이 조합이
  실제로 몇 년치 데이터로 평가됐는지 그대로 노출 (나중에 Advisor가 "이 추천은
  55년치 기준, 이건 39년치 기준"이라고 신뢰도를 같이 말해줄 수 있는 근거)
- `simulator/tests/test_data.py` - LONG/SHORT 두 가짜 티커로, 부분집합에 따라
  교집합 기간이 실제로 달라지는지 검증. `simulator/tests/test_strategy.py` -
  0% 비중 티커가 `.tickers`/시뮬레이션 입력에서 빠지는지, 그렇게 활성 티커만
  담긴 좁은 `close`/`dividends`로도 정상 동작하는지 검증
- 실측(SPY/QQQ/QLD/TLT/IEF/SGOV 유니버스, 1970년부터 요청):
  - SPY+TLT+IEF+SGOV(QQQ/QLD 없음): 1970~2024 (**55.0년**)
  - +QQQ(QLD는 없음): 1985~2024 (39.2년)
  - +QLD까지 다 포함: 1985~2024 (39.2년, QQQ 한계와 동일)
  - 같은 유니버스 안에서도 조합에 따라 최대 16년 차이가 실제로 남

### 26. "무한 은퇴기간" 생존 평가 + 17개 자산 사전계산 배치
- 문제의식: 기존 롤링 윈도우(23번)는 윈도우 길이를 고정(예: 15년)해야 해서
  "이 조합이 평생 버티는가"를 직접 묻지 못함. 은퇴기간을 "무한대"로 보고 싶다는
  요청에 맞춰, **매 시작연도마다 그 조합이 가진 데이터의 끝까지** 시뮬레이션해서
  "그때 인출을 시작했다면 지금까지 살아남았는가"를 묻는 방식으로 근사
- `simulator/rolling_window.py`
  - `perpetual_start_years()`: 데이터 끝까지 최소 `min_years`(기본 5년) 이상
    남는 시작연도만 골라냄 (끝자락 시작연도는 판단할 근거가 너무 짧아서 제외)
  - `evaluate_perpetual_success()`: `rolling_start_years`/`evaluate_rolling_window`와
    달리 **윈도우 길이가 시작연도마다 다 다르고, 끝은 항상 데이터의 마지막 날로
    고정** - "몇 년을 버티는가"가 아니라 "지금까지 버티는가"를 물음
  - `simulator/tests/test_rolling_window.py` - 시작연도별로 길이가 다르지만
    끝은 항상 같은 날짜인지, 성공률 계산이 맞는지 검증
- `main.py` - `USE_PERPETUAL`(신규, 기본 `True`)이 `USE_ROLLING_WINDOW`보다
  우선순위 높게 적용되도록 분기 순서 정리. `PERPETUAL_MIN_YEARS=5.0`
- **17개 자산 × 20% 단위 × 인출률 9종(2.0~6.0%, 0.5%p 단위) 사전계산 배치**
  (다음 후보 1번의 실제 실행): 18개 후보 중 BIL 제외(SGOV와 기능 중복)한 17개로
  20,349개 비중 조합 × 9개 인출률 = **183,141개 전략**을 `results.csv`로 저장
  - 최초 실행 시간 추정이 크게 틀렸던 것을 발견: "183,141회 × 0.014초 = 43분"으로
    계산했는데, `USE_PERPETUAL=True`일 때는 조합 하나당 `simulate()`가 시작연도
    수만큼(약 15~20회) 반복 호출된다는 걸 빠뜨림 - 실제로는 그 15~20배인
    **10~14시간** 규모. `Get-Process python`으로 실제 CPU 시간을 확인하고서야
    발견함. 사용자에게 정정 보고 후 "몇 시간 걸려도 백그라운드로 계속 돌리자"로
    합의하고 진행
  - **배치 완료 후 심각한 버그 발견**: 1위(Retirement Score 기준 정렬 상위)가
    전부 `Score=nan`으로 나옴 → 확인해보니 **결과 183,141행 전체가 NaN**이었음
    (DBC 단일 종목만의 문제가 아니었음). Python `sorted()`는 NaN 비교가 항상
    `False`라 정렬 순서가 사실상 무작위인데, 우연히 NaN 그룹이 맨 위로 온 것
  - **근본 원인**: `main.py`의 `evaluate()`가 `cpi = full_cpi.loc[close.index.min() :
    close.index.max()]`로 CPI 시리즈를 포트폴리오의 데이터 시작일에 딱 맞춰
    잘랐음. CPI(FRED CPIAUCSL)는 매달 **1일** 기준 데이터인데, 주식 데이터의
    첫 거래일은 절대 1일이 아니므로, 이렇게 자르면 **첫 인출 시점보다 앞선 CPI
    데이터가 하나도 안 남음**. `cpi_adjusted_withdrawal()`이 `cpi.asof(첫_인출일)`을
    호출하면 값을 못 찾아 `NaN`을 반환하고, 이 NaN이 `remaining_value <= 0`
    체크를 무사통과(NaN 비교는 항상 False)한 채 그대로 잔고에 기록돼서 그 뒤
    전체 시리즈가 NaN으로 오염됨. `simulator/rolling_window.py`의
    `evaluate_perpetual_success`/`evaluate_rolling_window`도 창(window)마다
    `cpi.loc[start:]`로 똑같이 잘랐어서 같은 문제가 있었음 (Guyton-Klinger는
    첫 인출엔 CPI를 안 써서 우연히 영향 없었음)
  - **수정**: `cpi`는 하한을 자르지 않고 **원본 그대로** 넘기도록 변경
    (`main.py`, `simulator/rolling_window.py` 둘 다). `.asof()`는 조회 시점
    이전의 가장 최근 값만 찾으면 되므로 미래/과거로 더 넓은 범위를 갖고 있어도
    무관 - 자를 이유가 애초에 없었음
  - `simulator/tests/test_rolling_window.py`,
    `simulator/tests/test_constant_withdrawal.py` - 회귀 테스트 3개 추가:
    각 윈도우가 원본 CPI 객체를 그대로 받는지(슬라이싱 안 됐는지), CPI 시작일이
    첫 인출일보다 늦어도 NaN 없이 정상 계산되는지. 전체 106개 테스트 통과
    (기존 103 + 신규 3)
  - 수정 확인: DBC 100%/4% 인출로 직접 재현 → 수정 전 `value` 전체 NaN, 수정 후
    `final_value=0.0, cagr=-100%`(정상적으로 고갈)로 나옴
- **183,141개 배치 완료, 결과 정상** (`results.csv`, 39.5MB): NaN 0건. 상위 5개는
  전부 **인출률 2.0~2.5%, SGOV(현금성) 40% 안팎 + 국채(IEF)/금(GLD) 조합**으로
  MDD -13% 안팎, 생존확률 100% - 지금 Score 가중치(생존 100·MDD 50·성장 20)가
  "덜 흔들리는" 보수적 조합을 우대하도록 짜여 있어서 나온 당연한 결과. 1위:
  VTI 20%/IEF 20%/SGOV 40%/GLD 20%, 인출률 2.0% (Score 104.2, CAGR 3.24%,
  MDD -12.94%, 생존 100%, 24.3년 데이터)

### 27. 사전계산 배치 병렬화 (18시간+ → 2시간 21분)
- CPI 버그(26번) 수정 후 재실행한 배치가 **18시간이 지나도 안 끝남** - 확인해보니
  단일 프로세스라 12코어 중 1개만 쓰고 있었고, `Get-Process`로 재보니 경과시간
  대비 실제 CPU 시간이 5배 넘게 적어서(로그오프 상태의 전원 관리/백그라운드
  프로세스 스로틀링으로 추정) 이 페이스면 총 40~60시간까지도 갈 수 있는 상황이었음
- `main.py` - `evaluate()` 호출을 리스트 컴프리헨션(1코어) 대신
  `multiprocessing.Pool`로 병렬화. 183,141개 전략이 서로 완전히 독립적이라
  자연스럽게 병렬화 가능
  - `NUM_WORKERS = os.cpu_count() - 2`(이 머신 기준 10) - OS/다른 프로그램용으로
    2코어는 남겨둠
  - `universe`/`full_cpi`(모든 전략이 공유하는 읽기전용 데이터)는 매 작업마다
    다시 pickle해서 넘기면 낭비라, `Pool`의 `initializer`(`_init_worker`)로
    **워커 프로세스 시작할 때 한 번만** 넘기고 워커 쪽 전역변수에 저장, 실제
    작업 함수(`_evaluate_worker`)는 `strategy` 하나만 받음
  - **진행률 로그 추가**: 예전엔 다 끝나야 한 번에 저장돼서 중간 상태를 전혀
    볼 수 없었음 - `PROGRESS_EVERY=2000`개마다 경과시간/ETA/처리 속도를 출력.
    처음엔 `tee`로 파이프에 물렸더니 Python 기본 버퍼링 때문에 로그가 실시간으로
    안 찍히는 걸 발견해서 `python -u`(unbuffered)로 다시 실행해 해결
- **추정 실수를 반복하지 않기 위해, 전체 재실행 전에 2,000개 샘플로 먼저 실측**:
  10워커로 2,000개를 104초에 처리(초당 19.2개) → 전체 183,141개 예상 **2.65시간**.
  이 실측치를 근거로 기존 18시간+짜리 프로세스를 종료하고 병렬 버전으로 재시작
  - 실제 결과: **140.8분(2시간 21분)**, 초당 21.7개로 예측과 거의 일치, NaN 0건
- **교훈**: "조합 수 × 시간"처럼 계산으로만 추정하면(26번의 43분 vs 실제
  10~14시간 사례) 숨은 배수를 놓치기 쉬움 - 코드를 실제로 바꾼 뒤에는 전체를
  돌리기 전에 **작은 샘플로 실측해서 추정치를 검증**하는 게 훨씬 안전함

### 28. Advisor 로직 (코드 기반, LLM 없음)
- `advisor/advisor.py` (신규)
  - `recommend_portfolios(results, tickers, withdrawal_rate, total_assets, ...)`:
    사전계산된 `results.csv`(183,141행)에서 사용자의 인출률에 맞는 행만 골라,
    저장돼 있던 원재료(`survival_probability`/`cagr`/`mdd`/`years_survived`)로
    `retirement_score()`를 **사용자가 고른 가중치로 그 자리에서 재계산** - 배치
    돌릴 때 박아넣은 고정 가중치에 안 묶이고, 재시뮬레이션 없이 즉시 응답 가능
  - **다양성**: 활성 티커 조합(비중>0인 티커 집합)이 같은 행은 점수 제일 높은
    것 하나만 남김 - 그래야 상위 3개가 "SPY 60/TLT 40"과 "SPY 62/TLT 38"처럼
    사실상 같은 조합의 미세 변주로 채워지지 않음. 같은 티커 집합이라도
    **가중치에 따라 그 안에서 어느 비중이 대표로 뽑히는지는 달라짐** (테스트로
    growth 위주 vs 기본 가중치를 비교해서 확인)
  - `total_assets`(사용자의 실제 자산 총액)는 결과 계산엔 안 쓰이고 오직
    `월 인출액 = total_assets × 인출률 ÷ 12` 환산에만 씀 - `results.csv` 자체는
    초기자본 1.0 기준 비율로 저장돼 있어서
  - **고갈 시점 추정**: `results.csv`엔 무한 은퇴기간(perpetual, 27번) 평가의
    시작연도별 결과가 개별로 안 남아있고(성공률 하나로 집계됨), 대신 단일
    고정시작 백테스트의 `years_survived`(전체 백테스트 기간 중 고갈 전까지
    버틴 비율)는 있음 - 이걸로 `data_start + years_survived × data_years`를
    **근사 고갈 시점**으로 씀 (정확한 날짜가 아니라 근사치라는 걸 명시)
  - `explain_recommendation(rec, rank)`: 위 결과를 자연어 문장으로 포맷 (비중,
    인출률, 생존확률, 월 인출액, CAGR/MDD, 고갈 여부/시점)
  - `advisor/tests/test_advisor.py` - 인출률 필터링, 활성 티커 집합 기준
    중복제거(+ 가중치 바뀌면 대표 행도 바뀌는지), 고갈 행의 추정 날짜, 월
    인출액 환산, 설명 문구 검증. 총 112개 테스트 통과(기존 106 + 신규 6)
- 실측(실제 `results.csv`, 인출률 4%, 자산 5억원, main.py 기본 Score 가중치):
  상위 3개가 VTI/IEF/GLD, QQQ/BND/GLD, QQQ/BND/SGOV/GLD로 서로 다른 자산 구성
  - 전부 생존확률 100%, MDD -20%대, 월 인출액 1,666,667원으로 정상 계산됨

### 29. 프론트엔드 (Streamlit) - Advisor 조회 화면
- 범위를 사용자와 먼저 좁힘: 배치 트리거나 다른 백엔드 항목(버킷 Monte Carlo,
  데이터 출처 표시)은 나중으로 미루고, **Advisor 조회 화면 하나만** 우선 구현
- `app.py` (루트, `main.py`와 동급 - 특정 파이프라인 컴포넌트 소속 아님)
  - 사이드바 입력: 총 자산(원), 인출률(`main.WITHDRAWAL_RATE_OPTIONS` 중 선택),
    Score 가중치 4개(슬라이더, 기본값은 `main.SCORE_*_WEIGHT`) - "추천 받기"
    누르면 `advisor.recommend_portfolios()`로 상위 3개 계산
  - 결과 카드마다: 비중 막대그래프, 생존확률/월 인출액/CAGR·MDD 지표,
    `explain_recommendation()` 텍스트, **자산 추이 꺾은선 그래프**
  - 자산 추이는 `results.csv`에 저장 안 돼 있어서(요약 지표만 있음), 추천된
    조합에 한해 그 자리에서 `ConstantWithdrawalStrategy.simulate()`를 한 번
    다시 돌려서 얻음 - 조합 하나 재계산은 순식간이라 문제없음
  - `st.cache_data`(results.csv)/`st.cache_resource`(yfinance 유니버스+CPI)로
    캐싱 - 유니버스 fetch(네트워크, 느림)가 서버 프로세스당 한 번만 실행되게 함
  - `app.py`는 이미 테스트된 모듈(advisor/simulator/main)을 엮기만 하는
    오케스트레이션 코드라 `main.py`와 같은 이유로 별도 테스트 없음
- `.claude/launch.json` (신규) - `python -m streamlit run app.py`로 미리보기
  서버 실행 설정 (streamlit 실행파일이 PATH에 없어서 `python -m` 형태로 고정)
- 실제 브라우저로 동작 확인: 사이드바 기본값 그대로 "추천 받기" 클릭 →
  advisor 실측과 동일한 상위 3개(VTI/IEF/GLD 등)가 막대그래프+꺾은선그래프와
  함께 정상 렌더링됨. 에러 없음
- `requirements.txt`에 `streamlit==1.60.0` 추가 (설치 시 시스템 Python
  경로 권한 문제로 `pip install --user` 필요했음 - 이 머신 한정 메모)

## 다음 후보 (사용자와 큰 그림 논의: 사전계산 + 가치관 기반 Advisor + 프론트엔드)

- 순서는 **백엔드 먼저, UI는 마지막**으로 합의함
- 최종 목표: 18개 자산 전체 조합을 사전계산해서 캐싱 → 사용자가
  (1) Score 가중치(생존/성장/MDD), (2) 은퇴 기간, (3) 인출률(기본값 4%)을
  고르면 → Advisor가 그 가치관에 맞는 포트폴리오 3개를 추천하면서
  생존확률/고갈 시점(고갈된다면 언제)/월 인출 가능액을 설명 → 자산 추이 그래프
- 중요한 제약: **자산을 여러 개 섞으면 데이터 기간은 제일 짧은 자산한테 끌려
  내려감** (교집합). 18개 다 쓰면 ~19년(2006~), 6개(QLD 포함, 24번 항목 수정
  이후 기준)면 ~40년(1985~), QQQ/QLD 다 빼면 SPY(1927)+TLT/IEF(1962)+SGOV(1954)
  조합으로 최대 ~63~98년까지도 가능. **"어떤 자산 조합을 쓰느냐"와 "롤링
  윈도우 표본이 얼마나 튼튼하냐"가 직접 트레이드오프** - 나중에 포트폴리오마다
  실제 사용 가능한 기간이 다르다는 걸 Advisor가 같이 알려주는 방향으로 갈 예정
- 계산량 추정: 18개 자산, 20% 단위 조합만 해도 26,334개. 인출률(9개)×전략(3개)
  ×은퇴기간(3개)까지 곱하면 약 200만 번 시뮬레이션 - 벡터화 덕분에 몇 시간 안에
  1회성 사전계산으로 처리 가능할 것으로 추정 (아직 실측 안 함)
- **Planner(LLM)는 안 만들기로 결정** - "생각지도 못한 조합 발견"이라는
  원래 목적이 Generator의 전수조사로 이미 커버돼서 의미가 약하다고 판단.
  `planner/` 폴더는 아직 정리(삭제) 안 한 상태로 남아있음

## 다음 후보

1. ~~18개 자산 전체로 TICKERS 확장 + 20% 단위 조합 사전계산 배치 스크립트~~ →
   17개(BIL 제외) 조합 × 인출률 9종 배치, 26/27번에서 완료 (`results.csv`,
   183,141행)
2. ~~인출률을 main.py 상수가 아니라 스윕 가능한 옵션으로~~ → 26번에서 완료
   (은퇴기간은 `USE_PERPETUAL`로 대체 - 고정 N년 대신 "데이터 끝까지" 방식)
3. ~~Advisor 로직 (가중치 기반 추천 3개 + 생존확률/고갈시점/월인출액 서술)~~ →
   28번에서 완료 (LLM 없이 코드 기반)
4. ~~`planner/` 폴더 정리(삭제)~~ → 완료. `requirements.txt`/`DEPENDENCIES.md`에서
   Planner 전용 의존성(`requests`)도 같이 제거
5. ~~프론트엔드 (Streamlit 유력)~~ → 29번에서 Advisor 조회 화면 완료
   (`app.py`). 배치 트리거 화면, 다른 화면 추가는 아직
6. 버킷 전략용 Monte Carlo 엔진
7. 데이터 출처(real/exact/approx) 표시를 결과에 반영
