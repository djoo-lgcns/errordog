# Errordog Sample Scenarios

Python 런타임 에러 자동 분석 파이프라인 데모 및 KPI 측정용 시나리오입니다.

## 시나리오 목록

| 파일 | 에러 타입 | 핵심 버그 | 중첩 객체 |
|------|-----------|-----------|-----------|
| `orders.py` | TypeError | 문자열 가격 × 수량 | list of dicts |
| `payment.py` | ValueError | 할인율 > 1 (음수 금액 발생) | dict-of-dict (discount) |
| `inventory.py` | ZeroDivisionError | 재고 0인 카테고리 소진율 계산 | dict-of-dict (categories) |
| `user_auth.py` | KeyError | 권한 객체에서 role 키 누락 | 3-depth nested dict |
| `report_gen.py` | TypeError | None 반환값에 dict 접근 | — |

## 빠른 시작

```bash
# 1. errordog 설치 확인 (debugger-v4 루트에서)
uv run python -m errordog --help

# 2. 시나리오 실행 (에러 자동 캡처)
cd sample
python orders.py       # TypeError 스냅샷 저장
python payment.py      # ValueError 스냅샷 저장
python inventory.py    # ZeroDivisionError 스냅샷 저장
python user_auth.py    # KeyError 스냅샷 저장
python report_gen.py   # TypeError 스냅샷 저장

# 3. MCP 서버 시작 (Claude Code용)
uv run --directory .. python -m errordog serve

# 4. HTTP 서버 시작 (ChatGPT Custom GPT / Codex용)
uv run --directory .. python -m errordog serve --http --port=8080
```

## KPI 측정: Before / After 비교

각 시나리오에서 아래 두 가지 방식으로 디버깅 시간을 측정하세요.

### Before — 수동 방식

1. 스크립트 실행 → 터미널에 traceback 출력
2. 에러 메시지 + traceback 전체를 ChatGPT에 복붙
3. "이 에러 원인이 뭔가요?" 질문
4. AI 응답 확인 후 코드 수정 시도

**측정 포인트**: 에러 발생 ~ 원인 특정 완료까지 분(min)

### After — Errordog + AI 방식

1. 스크립트 실행 → 자동 스냅샷 저장
2. AI (Claude Code 또는 ChatGPT)가 MCP/HTTP 툴로 조회:
   - `list_errors()` → 최신 에러 확인
   - `dap_get_stack_frames(error_id)` → 콜스택 탐색
   - `dap_get_variables(error_id, frame_index)` → 로컬 변수 확인
   - `dap_drill_into(error_id, variables_reference)` → 중첩 객체 drill-down
3. AI 진단 결과 확인

**측정 포인트**: 에러 발생 ~ 원인 특정 완료까지 분(min)

### 측정 기록표

| 시나리오 | Before (수동, 분) | After (Errordog, 분) | 단축률 |
|----------|-------------------|----------------------|--------|
| orders.py (TypeError) | | | |
| payment.py (ValueError) | | | |
| inventory.py (ZeroDivisionError) | | | |
| user_auth.py (KeyError) | | | |
| report_gen.py (TypeError) | | | |
| **평균** | | | |

> 참고 기준: 수동 방식 평균 5~10분 / Errordog 방식 평균 1~2분 (툴 콜 3~5회)

## DAP 드릴다운 예시 (AI 관점)

`payment.py`의 중첩 discount 객체를 분석하는 AI 툴 콜 체인:

```
1. list_errors()
   → error_id: "err_20260526T120000_abc123"

2. dap_get_stack_frames("err_20260526T120000_abc123")
   → frame_index=0: apply_discount / payment.py:14

3. dap_get_variables("err_20260526T120000_abc123", frame_index=0)
   → payment: {value: "{'amount': 500000, 'discount': {...}}", variablesReference: 1001}
   → discounted: -250000.0

4. dap_drill_into("err_20260526T120000_abc123", 1001)
   → amount: 500000
   → discount: {variablesReference: 1002}

5. dap_drill_into("err_20260526T120000_abc123", 1002)
   → code: "INVALID_CODE"
   → rate: 1.5   ← 원인 특정: rate가 1을 초과
```

## Codex CLI 연동

`.codex/config.yaml` 파일이 이 디렉토리에 포함되어 있습니다.  
Codex CLI 설치 후 이 디렉토리에서 실행하면 errordog MCP가 자동 연결됩니다.

## ChatGPT Custom GPT Actions 연동

```bash
# HTTP 서버 시작
uv run --directory .. python -m errordog serve --http --port=8080

# OpenAPI 스펙 확인 (ChatGPT Actions 등록용)
curl http://localhost:8080/openapi.json
```

ngrok 등으로 공개 URL을 만들면 ChatGPT Custom GPT의 Actions에 등록 가능합니다.
