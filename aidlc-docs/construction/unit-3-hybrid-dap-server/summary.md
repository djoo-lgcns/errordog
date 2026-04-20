# Unit 3 Summary: Hybrid DAP Server

## 개요

IDE(Neovim, VS Code 등)와 디버거(debugpy) 사이에서 동작하는 DAP(Debug Adapter Protocol) 프록시 서버이다. Proxy 모드와 Mock 모드 두 가지로 동작하며, 에러 스냅샷을 IDE에서 직접 시각화할 수 있게 한다.

---

## 목적

- **Proxy 모드**: IDE ↔ debugpy 사이의 DAP 메시지를 중계하면서, `StoppedEvent` 발생 시 디버깅 상태(스택/변수)를 캐싱
- **Mock 모드**: ESF 스냅샷을 로드하여 죽은 프로세스의 상태를 IDE에서 마치 라이브 디버깅처럼 시각화
- AI 에이전트가 캐싱된 디버깅 상태를 활용할 수 있는 기반 제공

---

## 효과

- 죽은 프로세스도 디버깅할 수 있다 — ESF 스냅샷만 있으면 IDE에서 stackTrace, variables를 탐색할 수 있다. (Mock 모드)
- 라이브 디버깅 중 상태가 캐싱된다 — Proxy 모드에서 StoppedEvent 발생 시 스택/변수가 비동기로 캐싱되어, 이후 AI가 활용할 수 있다.
- 하나의 진입점으로 두 모드가 동작한다 — errordog dap 하나로 attach 요청의 error_id 유무에 따라 Proxy/Mock이 자동 선택된다.

---

## 도메인 엔티티

| 엔티티 | 설명 |
|--------|------|
| **DapMessage** | DAP 프로토콜 메시지. seq, type(request/response/event), command, event, body 등 |
| **DebugSession** | 라이브 프록시 세션 상태. thread_id, frame_id, stack_trace, variables, mode |
| **StackFrame** | DAP stackTrace 응답의 단일 프레임. id, name, source_path, line |
| **Variable** | DAP variables 응답의 단일 변수. name, value, type, variables_reference |
| **MockSession** | ESF 스냅샷에서 사전 구성된 DebugSession. 라이브 debugpy 연결 없음 |

---

## 핵심 비즈니스 룰

### 포트 설정
- DAP 프록시: `:5679` (IDE 연결 수신)
- debugpy: `localhost:5678` (프록시가 연결하는 대상)

### 세션 관리
- 동시에 하나의 디버그 세션만 활성
- 세션 활성 중 새 연결 시도는 에러 로그와 함께 거부
- IDE 연결 해제 시 세션 정리

### Proxy 모드
- IDE ↔ debugpy 간 모든 DAP 메시지를 변경 없이 양방향 전달
- `StoppedEvent` 수신 시: 즉시 IDE에 전달 + 비동기로 stackTrace/variables 캐싱
- 캐싱은 비차단(non-blocking) — IDE 흐름에 영향 없음

### Mock 모드
- `attach` 요청에 `error_id`가 포함되면 Mock 모드 진입
- ESF 스냅샷을 로드하여 합성 DAP 세션 구성 (thread_id=1, frame_id는 순차 할당)
- 지원 요청: `initialize`, `attach`, `threads`, `stackTrace`, `variables`, `disconnect`
- 미지원 요청: `continue`, `next`, `stepIn`, `stepOut`, `setBreakpoints` → 에러 응답
- 변수는 읽기 전용 (`variables_reference=0`, 확장 불가)

### 메시지 프레이밍
- DAP는 `Content-Length: N\r\n\r\n` 헤더 프레이밍 사용 (LSP와 동일)
- 불완전한 메시지는 전체 수신까지 버퍼링

---

## 모듈 구조

```
src/errordog/dap/
├── __init__.py       # 패키지 초기화
├── protocol.py       # DAP Content-Length 프레이밍 (read_message, write_message, encode_message)
├── session.py        # 도메인 엔티티: DebugSession, StackFrame, Variable
├── mock.py           # MockAdapter: ESF 스냅샷 → DAP 응답 변환
└── proxy.py          # DapServer: async TCP 프록시 + StoppedEvent 상태 캐싱
```

---

## 생성/수정된 파일

### 소스 코드
| 파일 | 역할 |
|------|------|
| `src/errordog/dap/__init__.py` | 패키지 초기화 |
| `src/errordog/dap/protocol.py` | DAP 메시지 프레이밍 파싱/인코딩 |
| `src/errordog/dap/session.py` | DebugSession, StackFrame, Variable 엔티티 |
| `src/errordog/dap/mock.py` | ESF → DAP 응답 매핑 (MockAdapter) |
| `src/errordog/dap/proxy.py` | 비동기 TCP 프록시 + 상태 캐싱 |

### 수정 파일
| 파일 | 변경 내용 |
|------|-----------|
| `src/errordog/__main__.py` | `errordog dap` 서브커맨드 추가 |

### 테스트
| 파일 | 테스트 수 | 범위 |
|------|-----------|------|
| `tests/test_dap_protocol.py` | 8 | 프레이밍 인코드/디코드, EOF, 누락 헤더 |
| `tests/test_dap_session.py` | 7 | StackFrame, Variable, DebugSession 기본값 |
| `tests/test_dap_mock.py` | 12 | initialize, attach, threads, stackTrace, scopes, variables, disconnect, 미지원 요청 |
| `tests/test_dap_proxy.py` | 8 | _intercept 상태 캐싱, 세션 가드 |

---

## ESF → DAP 매핑

| ESF 필드 | DAP 응답 필드 |
|----------|---------------|
| `frame.function_name` | `stackFrame.name` |
| `frame.file_path` | `stackFrame.source.path` |
| `frame.line_number` | `stackFrame.line` |
| frame index | `stackFrame.id` (0-based) |
| `frame.locals[key]` | `variable.name` |
| `frame.locals[value]` | `variable.value` |

---

## 테스트 결과

- **Unit 3 테스트**: 35/35 통과
- **누적 전체 테스트 (Unit 1+2+3)**: 94/94 통과

---

## 사용법

```bash
# DAP 프록시 서버 시작
errordog dap    # :5679에서 IDE 연결 대기

# Proxy 모드: IDE에서 일반 attach/launch → debugpy(:5678)로 중계
# Mock 모드: IDE에서 attach 시 arguments에 error_id 포함 → ESF 스냅샷 시각화
```

---

## 후속 Unit과의 관계

- **Unit 1** (Core MCP & ESF): `SnapshotStore`를 통해 ESF 스냅샷 로드
- **Unit 2** (Runtime Tracker): tracker가 저장한 스냅샷을 Mock 모드에서 시각화
- **Unit 4** (AI Hypothesis Testing): 캐싱된 디버깅 상태를 활용하여 표현식 평가 및 IDE 자동화
