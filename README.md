# Errordog

Python 런타임 에러를 자동으로 캡처하고, AI 에이전트가 MCP/HTTP 도구로 분석하는 하이브리드 디버깅 서버.

```
에러 발생 → 스냅샷 자동 저장 → AI가 직접 조회 → 원인 특정
```

터미널 로그를 복붙하지 않아도, AI 에이전트가 스택 프레임과 로컬 변수를 구조적으로 탐색합니다.

---

## Features

- **Zero-config capture** — `import errordog.tracker` 한 줄로 uncaught exception 자동 저장
- **MCP server** — Claude Code, Codex CLI 등 MCP 클라이언트에서 바로 연동
- **HTTP REST API** — ChatGPT Custom GPT Actions, 외부 도구 연동
- **DAP post-mortem** — VS Code Variables 패널에서 스냅샷 시각화 (breakpoint 없이)
- **Nested object drill-down** — `dap_get_variables` → `dap_drill_into`로 중첩 dict/list 계층 탐색
- **Expression evaluation** — 크래시 시점 컨텍스트에서 Python 표현식 실행
- **Reproduction test gen** — 에러 재현 pytest 코드 자동 생성

---

## Quick Start

### Install

```bash
pip install errordog
# or
uv add errordog
```

### Capture errors automatically

```python
import errordog.tracker  # 이 한 줄이 전부

def calculate_price(items):
    return sum(item["price"] * item["qty"] for item in items)

orders = [
    {"price": 1500, "qty": 2},
    {"price": "free", "qty": 1},  # bug: string instead of int
]
calculate_price(orders)
```

```
$ python app.py
[errordog] Snapshot captured: err_20260526T120000_a3f2b1
Traceback (most recent call last):
  ...
TypeError: unsupported operand type(s) for +: 'int' and 'str'
```

스냅샷은 `~/.errordog/snapshots/` 에 저장됩니다.

---

## MCP Integration

### Claude Code

```bash
# MCP 서버 시작 (stdio transport)
errordog serve

# Claude Code 프로젝트에 등록
claude mcp add errordog -- errordog serve
```

또는 `.claude/mcp.json`:

```json
{
  "mcpServers": {
    "errordog": {
      "command": "errordog",
      "args": ["serve"]
    }
  }
}
```

### OpenAI Codex CLI

`~/.codex/config.yaml` 또는 프로젝트의 `.codex/config.yaml`:

```yaml
mcpServers:
  errordog:
    command: errordog
    args: [serve]
```

### Recommended Prompt

MCP 연동 후 아래 프롬프트를 사용하세요:

```
최근 Python 에러를 분석해줘.

1. list_errors()로 최신 에러 확인
2. dap_get_stack_frames(error_id)로 콜스택 탐색
3. dap_get_variables(error_id, frame_index=0)로 크래시 시점 변수 확인
4. variablesReference > 0인 변수는 dap_drill_into()로 전개
5. 구체적인 변수값을 근거로 원인 설명
```

---

## HTTP API (ChatGPT / REST)

```bash
# HTTP 서버 시작
errordog serve --http --port=8080
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | 서버 상태 확인 |
| `GET` | `/openapi.json` | OpenAPI 3.0 스펙 (자동 생성) |
| `POST` | `/tools/list_errors` | 에러 목록 조회 |
| `POST` | `/tools/get_error_details` | 특정 에러 전체 데이터 |
| `POST` | `/tools/dap_get_stack_frames` | 콜스택 프레임 |
| `POST` | `/tools/dap_get_variables` | 프레임 로컬 변수 |
| `POST` | `/tools/dap_drill_into` | 중첩 객체 전개 |
| `POST` | `/tools/evaluate_expression` | 표현식 평가 |
| `POST` | `/tools/generate_reproduction_test` | 재현 테스트 생성 |

```bash
# 예시
curl http://localhost:8080/openapi.json           # ChatGPT Actions 등록용 스펙
curl -X POST http://localhost:8080/tools/list_errors -H "Content-Type: application/json" -d '{}'
```

### ChatGPT Custom GPT Actions 연동

1. `errordog serve --http --port=8080` 실행
2. ngrok 등으로 공개 URL 생성: `ngrok http 8080`
3. ChatGPT Custom GPT → Actions → `https://<your-url>/openapi.json` 등록

---

## MCP Tools Reference

| Tool | 파라미터 | 설명 |
|------|---------|------|
| `list_errors()` | — | 스냅샷 목록 (최신순) |
| `get_error_details(error_id)` | `error_id` | 전체 ESF JSON |
| `dap_get_stack_frames(error_id)` | `error_id` | 콜스택 (frame_index 포함) |
| `dap_get_variables(error_id, frame_index=0)` | `error_id`, `frame_index` | 로컬 변수 + variablesReference |
| `dap_drill_into(error_id, variables_reference)` | `error_id`, `variables_reference` | 중첩 객체 전개 |
| `evaluate_expression(expression, error_id, frame_index=0)` | `expression`, `error_id`, `frame_index` | 표현식 평가 |
| `generate_reproduction_test(error_id)` | `error_id` | pytest 재현 코드 생성 |

### Drill-down Example

중첩 객체 `payment = {"amount": 500000, "discount": {"rate": 1.5}}` 분석:

```
dap_get_variables(error_id, 0)
→ payment: {"amount": ..., "discount": ...}  variablesReference=1001

dap_drill_into(error_id, 1001)
→ amount: 500000
→ discount: {...}  variablesReference=1002

dap_drill_into(error_id, 1002)
→ rate: 1.5    ← 원인 특정
→ code: "INVALID_CODE"
```

---

## VS Code DAP Debugging

스냅샷을 VS Code Variables 패널에서 시각화하는 post-mortem 디버깅.

```bash
# DAP 서버 시작
errordog dap
```

`.vscode/launch.json`:

```json
{
  "configurations": [
    {
      "name": "Errordog Post-Mortem",
      "type": "debugpy",
      "request": "attach",
      "connect": { "host": "localhost", "port": 5679 },
      "preLaunchTask": "Errordog: Select Snapshot"
    }
  ]
}
```

`.vscode/tasks.json`:

```json
{
  "tasks": [{
    "label": "Errordog: Select Snapshot",
    "type": "shell",
    "command": "errordog select"
  }]
}
```

---

## CLI Commands

```bash
errordog serve                        # MCP 서버 (stdio)
errordog serve --http --port=8080     # HTTP REST API 서버
errordog dap                          # DAP 서버 (post-mortem + live proxy)
errordog select                       # 스냅샷 선택 (DAP에서 사용할 error_id 저장)
errordog clean                        # 스냅샷 전체 삭제
errordog run <script.py> [args...]    # 스크립트 실행 + 에러 캡처
```

---

## A/B Testing

Errordog 없이 스택트레이스만으로 진단할 때와 비교하는 자동화 테스트:

```bash
# 1. HTTP 서버 시작 (다른 터미널)
errordog serve --http --port=8080

# 2. A/B 테스트 실행
cd sample
OPENAI_API_KEY=sk-... python ab_test.py

# 특정 시나리오만
python ab_test.py --scenarios orders,payment

# 모델 지정
python ab_test.py --model gpt-4o
```

결과 예시:

```
┌─────────────────────────────────────────────────────────────────┐
│ Scenario: payment (ValueError: discount rate > 1)               │
├─────────────────────────┬───────────────┬───────────────────────┤
│ Metric                  │ A: Stacktrace │ B: Errordog           │
├─────────────────────────┼───────────────┼───────────────────────┤
│ Input Tokens            │ 312           │ 180                   │
│ Output Tokens           │ 248           │ 380                   │
│ Total Tokens            │ 560           │ 560 (4 tool calls)    │
│ Response Time           │ 1.4s          │ 4.2s                  │
│ Root Cause Identified   │ ✗ Partial     │ ✓ Specific            │
│ Specificity Score       │ 1/4           │ 4/4                   │
└─────────────────────────┴───────────────┴───────────────────────┘
```

자세한 내용은 [`sample/README.md`](sample/README.md) 참조.

---

## How It Works

### Snapshot Format (ESF)

```json
{
  "error_id": "err_20260526T120000_a3f2b1",
  "timestamp": "2026-05-26T12:00:00Z",
  "exception_type": "TypeError",
  "exception_message": "unsupported operand type(s) for +: 'int' and 'str'",
  "tracelog": "...",
  "cwd": "/Users/dev/project",
  "frames": [
    {
      "file_path": "orders.py",
      "line_number": 8,
      "function_name": "calculate_total",
      "locals": {
        "item": "{'price': 'free', 'qty': 1}",
        "items": "[...]"
      }
    }
  ]
}
```

### Architecture

```
Python App
    │  import errordog.tracker
    │  (sys.excepthook override)
    ▼
~/.errordog/snapshots/{error_id}.json   ← ESF 저장
    │
    ├── MCP (stdio) ────────────────── Claude Code, Codex CLI
    ├── HTTP (REST) ────────────────── ChatGPT, curl, 외부 도구
    └── DAP (TCP:5679) ─────────────── VS Code, Neovim
```

---

## Development

```bash
git clone https://github.com/your-org/errordog
cd errordog
uv sync

# 테스트
uv run pytest

# 빌드
uv build
```

---

## License

MIT
