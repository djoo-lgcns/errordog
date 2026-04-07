# Unit 3 Functional Design Plan — Hybrid DAP Server

## Steps
- [x] Step 1: Collect and analyze user answers
- [x] Step 2: Generate domain-entities.md
- [x] Step 3: Generate business-rules.md
- [x] Step 4: Generate business-logic-model.md
- [x] Step 5: Update aidlc-state.md and audit.md

---

## Questions

**Q1. Proxy port architecture**
errordog가 DAP 프록시로 동작할 때 포트 구조는 어떻게 할까요?

A) IDE → errordog(:5679) → debugpy(:5678) 고정 포트
B) IDE → errordog(:5679) → debugpy(:5678) 기본값, 설정으로 변경 가능
C) 실행 시 CLI 인자로 지정 (예: `errordog serve --dap-port 5679 --debugpy-port 5678`)

[Answer]: A

---

**Q2. Mock mode 진입 방식**
Post-mortem 분석을 위해 IDE가 mock 모드로 attach할 때 어떤 방식을 사용할까요?

A) DAP `attach` 요청에 `error_id` 필드를 추가 (커스텀 확장)
B) 별도 CLI 커맨드: `errordog mock <error_id>` — IDE가 이 포트에 attach
C) 특수 포트(예: :5680)로 접속하면 자동으로 mock 모드

[Answer]: A

---

**Q3. Proxy 세션 관리**
동시에 여러 디버그 세션을 지원해야 할까요?

A) No — 단일 세션만 지원 (프로토타입 단계)
B) Yes — 다중 세션 지원

[Answer]: A

---

**Q4. StoppedEvent 캐싱 범위**
브레이크포인트에서 멈췄을 때 캐싱할 상태는 무엇인가요?

A) 최소: threadId, frameId만
B) 표준: threadId, frameId + stackTrace (모든 frame 목록)
C) 풀: threadId, frameId + stackTrace + variables (frame별 로컬 변수까지)

[Answer]: C

---

**Q5. errordog serve 와의 통합**
DAP 서버를 MCP 서버와 어떻게 실행할까요?

A) 통합: `errordog serve` 하나로 MCP + DAP 동시 기동
B) 분리: `errordog serve`(MCP)와 `errordog dap`(DAP)을 각각 실행

[Answer]: 더 표준적인 구현 형태로
