# Coding Rules

## TDD

- 새 기능(함수/모듈)을 추가하면 항상 그에 대한 테스트 코드도 같이 작성한다.
- 테스트 프레임워크: pytest
- 테스트 파일 위치: 소스 파일과 같은 이름으로 `simulator/tests/test_<module>.py`
  (예: `simulator/generator.py` → `simulator/tests/test_generator.py`)
- 테스트는 yfinance 등 외부 네트워크 호출 없이, 고정된 샘플 데이터(fixture)로 검증한다.
- 테스트 실행: `pytest` (retirement-planner 루트에서)
