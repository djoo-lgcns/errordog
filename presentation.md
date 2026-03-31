⏺ Errordog Demo Scenario for Teammates

  Setup (before the demo)

  # Clean previous snapshots for a fresh demo
  rm -rf ~/.errordog/snapshots/

  ---
  Act 1: "The Problem" — Errors disappear in terminal noise

  "Python 에러가 터지면 터미널 로그에 묻혀서 사라지잖아. 특히 AI 에이전트가 돌리는 코드면 에러를 놓치기 쉬워. Errordog은 이걸 자동으로 잡아줘."

  ---
  Act 2: "One-line activation" — import 한 줄이면 끝

  Write a tiny demo script (or do it live):

  # demo.py
  import errordog.tracker  # 이 한 줄이 전부

  def calculate_price(items):
      total = sum(item["price"] * item["qty"] for item in items)
      return total

  orders = [
      {"price": 1500, "qty": 2},
      {"price": "free", "qty": 1},  # bug: string instead of int
  ]

  calculate_price(orders)

  Run it:
  uv run python demo.py

  "보이지? 평소처럼 traceback이 그대로 뜨지만, 뒤에서 Errordog이 에러 스냅샷을 자동 저장했어."

  ---
  Act 3: "AI agent가 에러를 조회한다" — MCP Tools

  Start the inspector:
  uv run fastmcp dev inspector src/errordog/server.py:mcp --with-editable .

  Open http://localhost:6274, then:

  1. list_errors 클릭 → 방금 발생한 TypeError 스냅샷이 보임
  2. get_error_details 클릭 → error_id 붙여넣기 →
    - 어떤 파일, 몇 번째 줄에서 터졌는지
    - 각 frame의 로컬 변수값까지 전부 보임
    - item["price"]가 "free"였다는 걸 바로 확인 가능

  "AI 에이전트가 이 MCP 도구를 호출해서, 에러 정보를 읽고 스스로 디버깅할 수 있어. 사람이 로그 뒤질 필요가 없어."

  ---
  Act 4: "Stack trace + locals = 즉시 원인 파악"

  get_error_details 결과를 보여주면서 강조할 포인트:
  ┌─────────────────────────┬───────────────────────────────────┬─────────────────┐
  │          정보           │                값                 │      의미       │
  ├─────────────────────────┼───────────────────────────────────┼─────────────────┤
  │ exception_type          │ TypeError                         │ 에러 종류       │
  ├─────────────────────────┼───────────────────────────────────┼─────────────────┤
  │ frames[0].function_name │ calculate_price                   │ 어디서 터졌는지 │
  ├─────────────────────────┼───────────────────────────────────┼─────────────────┤
  │ frames[0].line_number   │ 3                                 │ 정확한 라인     │
  ├─────────────────────────┼───────────────────────────────────┼─────────────────┤
  │ frames[0].locals        │ item: {'price': 'free', 'qty': 1} │ 원인 데이터     │
  └─────────────────────────┴───────────────────────────────────┴─────────────────┘
  "로컬 변수까지 캡처하니까, 재현 안 해도 원인을 바로 알 수 있어."

  ---
  Act 5: "What's next" — Phase 3, 4 미리보기

  "지금은 에러를 잡아서 저장하고 조회하는 단계야. 다음 Phase에서는:"
  - Phase 3: DAP 프로토콜로 VS Code/Neovim에서 브레이크포인트 걸고 라이브 디버깅
  - Phase 4: AI가 에러 보고 가설 세우고, 자동으로 테스트 코드까지 생성

  ---
  Key talking points

  - Zero config: import errordog.tracker 한 줄, 설정 파일 없음
  - Non-invasive: 기존 traceback 그대로 유지, 앱 동작에 영향 없음
  - MCP native: Claude 같은 AI 에이전트가 바로 연동 가능
  - Locals captured: 에러 시점의 변수값까지 보존 → 재현 불필요
