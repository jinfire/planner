# Dependencies

| Package  | Version | Purpose                                             |
| -------- | ------- | ---------------------------------------------------- |
| yfinance | 0.2.66  | Yahoo Finance에서 과거 가격/배당 데이터 fetch           |
| pandas   | 2.3.3   | 시계열/표 형태 데이터 처리                              |
| numpy    | 2.2.6   | Monte Carlo 시뮬레이션 난수 샘플링                       |
| requests | 2.32.4  | Portfolio Planner의 Claude API 호출 (SDK 없이 REST 직접 호출) |
| pytest   | 9.1.1   | 테스트 프레임워크 ([CLAUDE.md](CLAUDE.md) TDD 규칙)      |

설치: `pip install -r requirements.txt`

Planner는 `anthropic` SDK 대신 `requests`로 Anthropic Messages API를 직접
호출함. 실제로 호출하려면 `ANTHROPIC_API_KEY` 환경변수를 직접 설정해야 함
(API 키는 코드/레포에 절대 넣지 않음).
