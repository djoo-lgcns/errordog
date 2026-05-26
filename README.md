# Errordog

```mermaid
flowchart TD
      app["Python Application"]
      exc(["Uncaught Exception"])

      subgraph intercept ["① Runtime Interception"]
          hook["sys.excepthook\nimport errordog.tracker"]
          snap[("ESF Snapshot\nstack frames · locals · object refs")]
          hook --> snap
      end

      subgraph expose ["② Protocol Bridge"]
          mcp["MCP Server  (stdio)"]
          t1["dap_get_stack_frames"]
          t2["dap_get_variables"]
          t3["dap_drill_into"]
      end

      agent["AI Agent  (Codex CLI)"]
      dx["Root Cause\n(concrete variable values)"]

      app -->|raises| exc
      exc -->|"before object graph is lost"| hook
      snap -->|structured · queryable| mcp
      t1 & t2 & t3 <-->|tool calling loop| agent
      agent --> dx

      style intercept fill:#fff3cd,stroke:#e6a817
      style expose fill:#d6eaf8,stroke:#2e86c1
```

Python 런타임 에러를 자동으로 캡처하고, AI 에이전트가 MCP 도구로 분석하는 포스트모텀 디버깅 서버.

```
에러 발생 → 스냅샷 자동 저장 → AI가 스택/변수 직접 조회 → 원인 특정
```

터미널 로그를 복붙하지 않아도, AI 에이전트가 스택 프레임과 로컬 변수를 구조적으로 탐색합니다.

---

## Features

- **Zero-config capture** — `import errordog.tracker` 한 줄로 uncaught exception 자동 저장
- **MCP server** — Claude Code, Codex CLI 등 MCP 클라이언트에서 바로 연동
- **DAP post-mortem** — VS Code Variables 패널에서 스냅샷 시각화 (breakpoint 없이)
- **Nested object drill-down** — `dap_get_variables` → `dap_drill_into`로 중첩 dict/list 계층 탐색
- **Conditional tool workflow** — 단순한 에러는 변수 repr만으로, 복잡한 중첩 객체만 drill-down

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

`~/.codex/config.toml` 또는 프로젝트의 `.codex/config.toml`:

```toml
[mcpServers.errordog]
command = "uv"
args = ["run", "--directory", "/path/to/errordog", "python", "-m", "errordog", "serve"]
```

### Recommended Prompt

에러 ID를 모를 때 (일반적인 경우):

```
최근에 발생한 Python 에러를 분석해줘.
```

에러 ID를 알고 있을 때:

```
err_20260526T120000_a3f2b1 에러를 분석해줘.
```

AI 에이전트는 AGENTS.md (또는 툴 docstring)의 워크플로우에 따라 자동으로
`list_errors` → `dap_get_stack_frames` → `dap_get_variables` → (필요시) `dap_drill_into` 순서로 호출합니다.

---

## MCP Tools Reference

MCP 서버는 에러 발견부터 변수 탐색까지 4개 툴을 노출합니다.  
툴 스키마 수를 최소화하여 **단순한 에러는 stacktrace-only 방식보다 적은 토큰으로 진단**합니다.

| Tool | 파라미터 | 설명 |
|------|---------|------|
| `list_errors()` | — | 스냅샷 목록 (최신순) — error_id 조회용 |
| `dap_get_stack_frames(error_id)` | `error_id: str` | 콜스택 (frame_index 포함, 0=크래시 지점) |
| `dap_get_variables(error_id, frame_index=0)` | `error_id: str`, `frame_index: int` | 로컬 변수 + value repr + variablesReference |
| `dap_drill_into(error_id, variables_reference)` | `error_id: str`, `variables_reference: int` | 중첩 객체 1레벨 전개 (조건부 사용) |

### 핵심 설계 원칙: value 필드 우선 읽기

Errordog의 `dap_get_variables`는 실제 DAP 디버거(VS Code)와 다르게 동작합니다.

| | 실제 DAP (VS Code) | Errordog MCP |
|---|---|---|
| `value` 필드 | 축약된 미리보기 | **완전한 Python repr** |
| `variablesReference > 0` | 값이 아직 로드 안 됨 → 반드시 조회 필요 | 구조 탐색 가능 → 조회는 선택 |

따라서 `variablesReference > 0` 이더라도 `value` 필드를 먼저 읽고 원인을 특정할 수 있으면 `dap_drill_into`를 호출하지 않습니다.

### Drill-down 예시

`payment.py`의 중첩 discount 객체 분석:

```
1. dap_get_stack_frames("err_...")
   → frame_index=0: apply_discount / payment.py:14

2. dap_get_variables("err_...", frame_index=0)
   → payment  value="{'amount': 500000, 'discount': {'rate': 1.5, 'code': 'INVALID_CODE'}}"
                variablesReference=1001
   → discounted  value="-250000.0"  variablesReference=0

   ✅ value에 rate: 1.5가 직접 보임 → dap_drill_into 불필요, 원인 특정 완료
```

drill이 필요한 경우 (긴 리스트에서 특정 인덱스 찾기):

```
2. dap_get_variables("err_...", frame_index=0)
   → items  value="[{...}, {...}, {'price': 'free', ...}]"  variablesReference=2001
     (3개 element의 전체 repr이지만, 어느 index인지 불명확)

3. dap_drill_into("err_...", 2001)
   → [0]  value="{'price': 1500, 'qty': 2}"
   → [1]  value="{'price': 1200, 'qty': 1}"
   → [2]  value="{'price': 'free', 'qty': 3}"  ← 원인: items[2].price가 문자열
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
errordog serve                        # MCP 서버 시작 (stdio)
errordog dap                          # DAP 서버 시작 (post-mortem + live proxy)
errordog select                       # 스냅샷 선택 (DAP에서 사용할 error_id 저장)
errordog clean                        # 스냅샷 전체 삭제
errordog run <script.py> [args...]    # 스크립트 실행 + 에러 자동 캡처
```

---

## A/B Testing

`sample/ab_test.py`는 Errordog MCP tools 방식(B)과 stacktrace-only 방식(A)의 진단 정확도와 토큰 사용량을 자동으로 비교합니다.

**전제 조건**: [codex CLI](https://github.com/openai/codex) 설치 및 인증

```bash
# 전체 5개 시나리오 실행
uv run sample/ab_test.py

# 디버그 모드 (per-turn 토큰 상세 출력)
uv run sample/ab_test.py --debug

# 특정 시나리오만
uv run sample/ab_test.py --scenarios orders,payment

# 결과 파일 저장
uv run sample/ab_test.py --output results.json
```

### 설계 의도

| 케이스 | 기대 동작 |
|--------|----------|
| 단순한 에러 (변수 repr으로 원인 명확) | **B < A** 토큰 — 3-tool 스키마(~8k) < stacktrace 방식(~22k) |
| 복잡한 에러 (중첩 객체 drill 필요) | **B > A** 토큰, 하지만 더 높은 정확도 달성 |

MCP 서버 툴 수를 3개로 최소화하여 시스템 프롬프트 오버헤드를 ~8k tokens으로 낮췄습니다.  
이전 8-tool 구성 대비 ~13k tokens 절감, 단순 에러에서 B가 A보다 저렴해집니다.

### 출력 예시

```
Errordog A/B Test  |  codex=codex  |  scenarios=5
Condition A: stacktrace only (MCP isolated)
Condition B: Errordog MCP tools (dap_get_stack_frames → dap_get_variables → dap_drill_into)

── Scenario: payment ──
───────────────────────────────────────────────────────────────────
Scenario : payment — ValueError — discount rate > 1 causes negative amount
───────────────────────────────────────────────────────────────────
Metric                          A: Stacktrace        B: Errordog
───────────────────────────────────────────────────────────────────
Input tokens                           22,404             ~17,000
Output tokens                             175                324
Total tokens                           22,579             ~17,300
MCP tool calls                              0                  2
  tools used                                  dap_get_stack_frames, dap_get_variables
Response time (s)                        12.6               18.0
Keyword match                      4/4 (100%)         4/4 (100%)
───────────────────────────────────────────────────────────────────

═══════════════════════════════════════════════════════════════════
SUMMARY
═══════════════════════════════════════════════════════════════════
Metric                          A: Stacktrace        B: Errordog
───────────────────────────────────────────────────────────────────
Avg input tokens                       22,400             ~25,000
Avg MCP tool calls                          0                ~2.0
Avg response time (s)                    15.0               25.0
Avg specificity                          62%               95%
Keyword coverage                  13/21 (62%)        20/21 (95%)
═══════════════════════════════════════════════════════════════════
```

자세한 시나리오 내용은 [`sample/README.md`](sample/README.md) 참조.

---

## How It Works

### Snapshot Format (ESF)

```json
{
  "error_id": "err_20260526T120000_a3f2b1",
  "timestamp": "2026-05-26T12:00:00Z",
  "exception_type": "TypeError",
  "exception_message": "unsupported operand type(s) for +: 'int' and 'str'",
  "cwd": "/Users/dev/project",
  "frames": [
    {
      "file_path": "orders.py",
      "line_number": 8,
      "function_name": "calculate_total",
      "locals": {
        "item": "{'price': 'free', 'qty': 1}",
        "items": "[{'price': 1500, 'qty': 2}, {'price': 'free', 'qty': 1}]"
      }
    }
  ]
}
```

`locals` 값은 크래시 시점의 Python `repr()` 문자열입니다.  
`dap_get_variables`의 `value` 필드가 이 repr을 그대로 반환하므로, 중첩 객체도 한 번의 호출로 완전한 내용을 볼 수 있습니다.

### Architecture

```
Python App
    │  import errordog.tracker
    │  (sys.excepthook override)
    ▼
~/.errordog/snapshots/{error_id}.json   ← ESF 저장
    │
    ├── MCP (stdio) ────────────────── Claude Code, Codex CLI
    └── DAP (TCP:5679) ─────────────── VS Code, Neovim
```

---

## Development

```bash
git clone https://github.com/djoo-lgcns/errordog
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
