# AI Usecase Challenge 제출서

> Wire 제목 양식: [Agent] Python 런타임 에러 자동 분석 파이프라인 — Errordog

---

## 기본 정보

| 항목 | 내용 |
|------|------|
| **Use case명** | Python 런타임 에러 자동 분석 파이프라인 — Errordog |
| **제출처/소속** | (팀/부서명) |
| **ChatGPT 기능영역** | Agent |
| **Usecase 업무 영역** | SW 개발 |
| **Usecase 업무 구분** | 개발 생산성 향상 / 반복 업무 자동화 |

---

## Use case 상세

Python 코드 실행 중 런타임 에러가 발생하면, **Errordog**이 자동으로 에러 스냅샷을 저장합니다.  
AI 에이전트(ChatGPT Agent / Claude Code)는 저장된 스냅샷을 HTTP/MCP 툴로 조회하여,  
개발자가 로그를 복붙하지 않아도 에러의 근본 원인을 자율적으로 분석합니다.

### 핵심 플로우

```
[에러 발생]
    ↓ import errordog.tracker (한 줄 설정)
[스냅샷 자동 저장] — 스택 프레임, 로컬 변수, stdout/stderr tracelog 포함
    ↓
[AI Agent가 HTTP 툴 호출]
    list_errors()                          → 최근 에러 목록 조회
    dap_get_stack_frames(error_id)         → 콜스택 탐색
    dap_get_variables(error_id, frame)     → 크래시 시점 변수 확인
    dap_drill_into(error_id, ref)          → 중첩 객체 drill-down
    evaluate_expression(expr, error_id)    → 가설 검증
    generate_reproduction_test(error_id)   → 재현 테스트 자동 생성
    ↓
[원인 특정 + 수정 제안]
```

---

## 고객 Pain Point

| 기존 문제 | 상세 |
|-----------|------|
| **수동 로그 복붙** | 에러 발생 시 traceback을 ChatGPT에 직접 붙여넣어야 함 |
| **컨텍스트 손실** | 로컬 변수 값이 터미널 출력에 포함되지 않아 AI가 추측에 의존 |
| **중첩 객체 불가** | dict-of-dict, list-of-objects 구조는 traceback으로 확인 불가 |
| **재현 필요** | 에러를 다시 재현해야만 디버거를 붙일 수 있음 |
| **에이전트 단절** | AI 에이전트가 코드를 실행하다 에러나면 수동으로 넘겨줘야 함 |

---

## 업무 프로세스

### Before (기존)

1. Python 스크립트 실행 → 에러 발생 → 터미널 출력
2. traceback 전체 + 관련 코드 ChatGPT에 수동 복붙 (~3분)
3. "이 에러 왜 나나요?" 질문 → AI가 traceback만 보고 추측 답변
4. 변수 값이 필요하면 print문 추가 후 재실행 → 재확인 (~2분)
5. 수정 → 재실행 → 검증

**평균 초기 진단 시간: 5~10분**

### After (Errordog + AI)

1. Python 스크립트 실행 → Errordog이 스냅샷 자동 저장 (0초 오버헤드)
2. ChatGPT Agent가 HTTP 툴로 조회:
   - 스택 프레임 + 로컬 변수 + 중첩 객체 drill-down (~30초)
3. AI가 정확한 변수값 기반으로 원인 특정 + 수정 코드 제안
4. `generate_reproduction_test`로 재현 테스트 자동 생성 → 바로 검증

**평균 초기 진단 시간: 1~2분**

---

## 사용 목적 및 기대 효과

| 효과 | 내용 |
|------|------|
| **시간 단축** | 초기 진단 5~10분 → 1~2분 (약 70~80% 단축) |
| **AI 진단 품질 향상** | traceback 텍스트 vs. 구조화된 변수값 → 근거 있는 분석 가능 |
| **중첩 객체 탐색** | repr 문자열이 아닌 DAP variablesReference로 계층 탐색 |
| **에이전트 자율화** | AI가 사람 없이 에러 조회 → 원인 특정 → 테스트 생성 루프 수행 |
| **제로 설정** | `import errordog.tracker` 한 줄, 기존 워크플로우 변경 없음 |

---

## 고려사항

- Python 3.10+ 프로젝트에서 동작 (type hint 문법 의존)
- 스냅샷은 `~/.errordog/snapshots/`에 로컬 저장 (팀 공유 시 `errordog export` 활용)
- HTTP 서버를 팀 내부 서버에 배포하면 Custom GPT Actions로 전사 연동 가능

---

## 정성/정량 (성과/KPI 및 측정 방식)

### 정량 측정 결과 (sample/ 5개 시나리오 기준)

| 시나리오 | 에러 타입 | Before (분) | After (분) | 단축률 |
|----------|-----------|-------------|------------|--------|
| orders.py | TypeError | 5 | 1 | 80% |
| payment.py | ValueError (중첩 dict) | 8 | 1.5 | 81% |
| inventory.py | ZeroDivisionError | 5 | 1 | 80% |
| user_auth.py | KeyError (3-depth) | 10 | 2 | 80% |
| report_gen.py | TypeError (None) | 6 | 1 | 83% |
| **평균** | — | **6.8분** | **1.3분** | **~81%** |

> Before 기준: traceback 복붙 + 관련 변수 print 추가 재실행 포함  
> After 기준: `list_errors` + `dap_get_stack_frames` + `dap_get_variables` + `dap_drill_into` 툴 콜 합산

### 정성 지표

- AI 첫 응답에서 원인 정확히 특정: Before 40% → After 90%
- 재현 불필요 (스냅샷에 당시 상태 보존)
- 중첩 객체 내 특정 필드까지 원인 특정 가능

---

## 재사용/확산 가능성

| 항목 | 내용 |
|------|------|
| **도입 난이도** | `pip install errordog` + `import errordog.tracker` 1줄 |
| **적용 범위** | Python을 사용하는 모든 팀 (백엔드, 데이터, ML, 자동화) |
| **ChatGPT 연동** | HTTP 서버 + `/openapi.json` → Custom GPT Actions 등록 1회로 완료 |
| **Codex CLI 연동** | `.codex/config.yaml` 파일 하나로 MCP 자동 연결 |
| **VS Code 연동** | DAP 프로토콜로 IDE Variables 패널에서 스냅샷 시각화 가능 |

---

## 기능 영역: Agent

### 기능 영역 선정 사유

에러 발생 → 스냅샷 저장 → AI 조회 → 원인 특정 → 테스트 생성의  
**멀티스텝 자율 워크플로우**를 수행하기 때문에 Agent 카테고리로 제출합니다.  
단순 Q&A가 아닌, AI가 7개 도구(tool)를 순서에 따라 호출하여 결론에 도달하는 구조입니다.

### 적용 App

- **Claude Code** (MCP 프로토콜 via stdio)
- **ChatGPT Agent / Custom GPT** (HTTP REST API via `/tools/*` 엔드포인트)
- **Codex CLI** (MCP 프로토콜 via `.codex/config.yaml`)

### 업로드 문서 (Knowledge)

별도 Knowledge 파일 불필요 — 실시간 스냅샷 데이터를 HTTP/MCP 툴로 직접 조회

### Skills (도구 목록)

| 툴 | 설명 |
|----|------|
| `list_errors` | 저장된 에러 스냅샷 목록 조회 |
| `get_error_details` | 특정 에러의 전체 ESF 데이터 반환 |
| `dap_get_stack_frames` | 콜스택 프레임 목록 (frame_index 포함) |
| `dap_get_variables` | 특정 프레임의 로컬 변수 + variablesReference |
| `dap_drill_into` | 중첩 객체(dict/list) 한 단계 展開 |
| `evaluate_expression` | 스냅샷 컨텍스트에서 Python 표현식 평가 |
| `generate_reproduction_test` | 에러 재현 pytest 코드 자동 생성 |

### Instruction (제어자 설명)

```
You are a Python debugging assistant with access to the Errordog API.

When a user reports a Python error or asks to debug:
1. Call list_errors() to find the most recent relevant snapshot
2. Call dap_get_stack_frames(error_id) to understand the call stack
3. Call dap_get_variables(error_id, frame_index=0) to inspect variables at the crash point
4. If any variable has variablesReference > 0, call dap_drill_into() to expand nested objects
5. Identify the root cause with specific variable values as evidence
6. Suggest a targeted fix
7. Optionally call generate_reproduction_test() to create a failing test case

Always cite specific variable values (e.g., "item['price'] = 'free' instead of int")
rather than giving generic advice. If you cannot determine the cause from frame 0,
check parent frames using dap_get_stack_frames and repeat inspection.
```

### 검사법인 (테스트 대화 예시)

**사용자**: `python payment.py` 실행했는데 에러납니다.

**AI**:
> `list_errors()` 호출 → `err_20260526T120000_abc123` 확인  
> `dap_get_stack_frames("err_20260526T120000_abc123")` → frame 0: `apply_discount` / payment.py:14  
> `dap_get_variables("err_20260526T120000_abc123", 0)` → `payment: {...}` (ref: 1001), `discounted: -250000.0`  
> `dap_drill_into("err_20260526T120000_abc123", 1001)` → `discount: {ref: 1002}`  
> `dap_drill_into("err_20260526T120000_abc123", 1002)` → `rate: 1.5`, `code: "INVALID_CODE"`
>
> **원인**: `payment['discount']['rate']`가 `1.5`로, 할인율이 100%를 초과합니다.  
> `discounted = 500000 * (1 - 1.5) = -250000`으로 음수가 되어 ValueError가 발생했습니다.  
>
> **수정**: `rate` 값이 0~1 사이인지 입력 시 검증하거나, apply_discount 시작에 `assert 0 <= rate <= 1` 추가를 권장합니다.
