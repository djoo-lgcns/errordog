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
uv sync

# 2. 시나리오 실행 (에러 자동 캡처)
uv run --directory .. python orders.py      # TypeError 스냅샷 저장
uv run --directory .. python payment.py     # ValueError 스냅샷 저장
uv run --directory .. python inventory.py   # ZeroDivisionError 스냅샷 저장
uv run --directory .. python user_auth.py   # KeyError 스냅샷 저장
uv run --directory .. python report_gen.py  # TypeError 스냅샷 저장

# 3. MCP 서버 시작 (Claude Code용)
uv run --directory .. python -m errordog serve
```

## A/B 테스트 실행

```bash
# 전제: codex CLI 설치 및 인증
uv run --directory .. python ab_test.py

# 디버그 모드 (per-turn 토큰 상세 출력)
uv run --directory .. python ab_test.py --debug

# 특정 시나리오만
uv run --directory .. python ab_test.py --scenarios orders,payment
```

## KPI 측정: Before / After 비교

각 시나리오에서 아래 두 가지 방식으로 디버깅 시간을 측정하세요.

### Before — 수동 방식

1. 스크립트 실행 → 터미널에 traceback 출력
2. 에러 메시지 + traceback 전체를 AI에 복붙
3. "이 에러 원인이 뭔가요?" 질문
4. AI 응답 확인 후 코드 수정 시도

**측정 포인트**: 에러 발생 ~ 원인 특정 완료까지 분(min)

### After — Errordog + AI 방식

1. 스크립트 실행 → 자동 스냅샷 저장
2. AI (Claude Code 또는 Codex CLI)가 MCP 툴로 조회:
   - `dap_get_stack_frames(error_id)` → 콜스택 탐색
   - `dap_get_variables(error_id, frame_index=0)` → 로컬 변수 확인
   - `dap_drill_into(error_id, variables_reference)` → 중첩 객체 drill-down (필요 시만)
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

## DAP 드릴다운 예시 (AI 관점)

`payment.py`의 중첩 discount 객체를 분석하는 AI 툴 콜 체인:

```
1. dap_get_stack_frames("err_20260526T120000_abc123")
   → frame_index=0: apply_discount / payment.py:14

2. dap_get_variables("err_20260526T120000_abc123", frame_index=0)
   → payment  value="{'amount': 500000, 'discount': {'rate': 1.5, 'code': 'INVALID_CODE'}}"
              variablesReference=1001
   → discounted  value="-250000.0"  variablesReference=0

   ✅ value 필드에서 rate=1.5가 직접 보임 → dap_drill_into 불필요
   결론: discount.rate가 1을 초과하여 음수 금액 발생
```

drill이 필요한 경우 (긴 리스트):

```
2. dap_get_variables("err_...", frame_index=0)
   → items  value="[{...qty:2}, {...qty:1}, {'price': 'free', 'qty': 3}]"
            variablesReference=2001
   (어느 index인지 불명확 → drill 필요)

3. dap_drill_into("err_...", 2001)
   → [2]  value="{'price': 'free', 'qty': 3}"  ← items[2].price가 문자열
```

## Codex CLI 연동

`~/.codex/config.toml`:

```toml
[mcpServers.errordog]
command = "uv"
args = ["run", "--directory", "/path/to/debugger-v4", "python", "-m", "errordog", "serve"]
```

또는 A/B 테스트처럼 `-c` 플래그로 인라인 주입 (config 파일 불필요):

```bash
codex exec --ephemeral --ignore-user-config \
  -c 'mcp_servers.errordog.command="uv"' \
  -c 'mcp_servers.errordog.args=["run","--directory","/path/to/errordog","python","-m","errordog","serve"]' \
  - <<< "dap_get_stack_frames로 err_XXX 분석해줘"
```
