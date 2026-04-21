# Unit 4 Summary: AI Hypothesis Testing & Auto-Test Generation

## 개요

에러 스냅샷에 대해 표현식을 평가하고, 재현 테스트를 자동 생성하는 기능을 추가한 네 번째 유닛이다. DAP 디버그 콘솔과 MCP 도구 두 채널로 동일한 기능을 노출한다.

---

## 목적

- Post-mortem 디버깅 경험 완성 — 스냅샷을 열어 변수를 보는 것에서, 디버그 콘솔에서 가설을 검증하는 것까지
- AI 에이전트가 스냅샷을 분석하고 재현 테스트를 생성할 수 있는 MCP 인터페이스 제공
- 개발자와 AI가 동일한 스냅샷 데이터를 각자의 채널(DAP/MCP)로 활용하는 구조 확립

---

## ���과

> Unit 4 완료 후

- Post-mortem이 진짜 디버깅이 되었다 — `<leader>de`로 스냅샷을 열면 디버그 콘솔에서 `type(items[0]['qty'])` 같은 표현식을 직접 평가할 수 있다.
- AI가 가설을 검증할 수 있다 — MCP `evaluate_expression`으로 스냅샷 frame의 locals를 대상으로 임의 Python 표현식을 실행하고 결과를 받는다.
- 재현 테스트가 자동 생성된다 — MCP `generate_reproduction_test`로 스냅샷에서 pytest 스크립트를 추출하여 `~/.errordog/generated_tests/`에 저장���다.

---

## 도메인 엔티티

| 엔티티 | 설명 |
|--------|------|
| **EvalRequest** | 표현식 평가 입력. `expression`, `error_id`, `frame_index` 포함 |
| **EvalResult** | 평가 결과. `success`, `result`, `error`, `unavailable_vars`, `mode` 포�� |
| **TestGenerationResult** | 테스트 생성 결과. `error_id`, `test_code`, `file_path`, `function_name`, `exception_type` 포함 |

### 기존 엔티티 의존

- **ErrorSnapshot**, **Frame** (Unit 1) — 스냅샷 로드 및 frame locals 접근
- **DebugSession**, **Variable** (Unit 3) — MockAdapter의 세션 상태에서 변수 조회

---

## ��심 비즈��스 룰

- **Namespace 복원**: `ast.literal_eval`로 repr 문자열을 Python 값으로 파싱. 실패 시 해당 변수 건너뜀 (skip)
- **No sandboxing**: 개발자 도구로서 REPL과 동일한 수준의 신뢰. `eval()` 사용, `exec()` 미사용
- **테스트 템플릿**: top frame의 함수명·인자·예외 타입을 추출하여 `pytest.raises` 패턴으로 생성
- **`<module>` 스킵**: top frame이 `<module>`이면 frames[1]의 named function 우선 선택
- **모듈 경로 도출**: `snapshot.cwd` 기준 상대경로를 dotted module path로 변환. 불가능 시 TODO 주석
- **출력 위치**: 생성된 테스트는 `~/.errordog/generated_tests/`에 저장 (프로젝트 test 디렉토리 오염 방지)

---

## 생성된 파일

### 소스 코드
| 파일 | 역할 |
|------|------|
| `src/errordog/evaluator.py` | 공유 평가 로직: `reconstruct_namespace()`, `eval_expression()` |
| `src/errordog/testgen.py` | 재현 테스트 생성: `generate_reproduction_test()` |

### 수정된 파일
| 파일 | 변경 내용 |
|------|-----------|
| `src/errordog/dap/mock.py` | DAP `evaluate` 커맨드 핸들러 추가 (post-mortem 디버그 콘솔) |
| `src/errordog/server.py` | MCP 도구 2개 등록 (`evaluate_expression`, `generate_reproduction_test`) |

### 테스트
| 파일 | ��위 |
|------|------|
| `tests/test_evaluator.py` | namespace 복원 (8), 표현식 평가 (8) — 16 테스트 |
| `tests/test_testgen.py` | 테스트 생성, 모듈 경로, 에러 처리 — 5 테스트 |
| `tests/test_dap_mock.py` | MockAdapter evaluate 핸들러 — 5 테스트 추가 |
| `tests/test_server.py` | MCP 도구 통합 테스트 — 6 테스트 추가 |

---

## MCP 도구

| 도구 | 설명 |
|------|------|
| `evaluate_expression(expression, error_id, frame_index)` | 스냅샷 frame의 locals 대상 Python 표현식 평가 (mock mode) |
| `generate_reproduction_test(error_id)` | 스냅샷에서 pytest 재현 테스트 자동 생성 |

---

## DAP 확장

| 커맨드 | 모드 | 설명 |
|--------|------|------|
| `evaluate` | Mock | 디버그 콘솔에서 표현식 평가. 결과가 dict/list이면 drill-down 가능 |

---

## 테스트 결과

- **Unit 4 신규 테스트**: 32개
- **전체 테스트**: 126/126 통과
- **회귀 없음**

---

## 실행 방법

```bash
uv run pytest                # 전체 테스트 실행 (126개)
uv run python -m errordog    # MCP 서버 시작 (evaluate_expression, generate_reproduction_test 포함)
```

### 디버그 콘솔 사용 (nvim-dap)

```
1. <leader>de → 스냅샷 선택
2. 디버그 콘솔 열기 (nvim-dap REPL)
3. 표현식 입력 → 결과 확인
```

### MCP 도구 사용 (AI 에이전트)

```
evaluate_expression("type(items[0]['qty'])", "err_20260414T045713_5ee4d9", 0)
→ {"success": true, "result": "<class 'str'>", "mode": "mock"}

generate_reproduction_test("err_20260414T045713_5ee4d9")
→ {"test_code": "...", "file_path": "~/.errordog/generated_tests/test_reproduce_...py"}
```

---

## 후속 과제

- **Live mode evaluate**: proxy 세션이 활성일 때 DAP evaluate 요청을 debugpy로 포워딩 (현재 mock mode만 구현)
- **Neovim RPC**: `reproduce_error_in_ide` — MCP에서 Neovim에 직접 DAP attach 트리거 (Phase 4에서 보류)
- **LLM 기반 테스트 개선**: 템플릿 기반 생성 후 AI가 테스트를 정교화하는 옵션 (현재 템플릿만)
