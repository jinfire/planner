# Coding Rules

## TDD

- 새 기능(함수/모듈)을 추가하면 항상 그에 대한 테스트 코드도 같이 작성한다.
- 테스트 프레임워크: pytest
- 테스트 파일 위치: 소스 파일과 같은 이름으로 `simulator/tests/test_<module>.py`
  (예: `simulator/generator.py` → `simulator/tests/test_generator.py`)
- 테스트는 yfinance 등 외부 네트워크 호출 없이, 고정된 샘플 데이터(fixture)로 검증한다.
- 테스트 실행: `pytest` (retirement-planner 루트에서)

## Commit Message

[Conventional Commits](https://www.conventionalcommits.org/) 형식을 따른다.

- 제목: `<type>: <변경 내용 요약>` (영어, 명령형, 50자 내외)
  - `feat`: 새 기능 추가
  - `fix`: 버그 수정
  - `test`: 테스트 추가/수정
  - `docs`: 문서(md 등)만 변경
  - `refactor`: 동작 변화 없는 코드 구조 개선
  - `chore`: 빌드 설정, 의존성 등 기타 잡무
- 본문(필요시): 무엇을 바꿨는지가 아니라 **왜** 바꿨는지 위주로 작성
- 예: `feat: add portfolio generator for weight combinations`
