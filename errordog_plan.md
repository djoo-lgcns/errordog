# 📄 Errordog Development Plan (For Claude Code)

## 🎯 Project Overview

**Errordog**은 AI 에이전트와 개발자를 위한 하이브리드 디버깅 및 테스트 자동화 서버입니다.
1. **Zero-Touch Post-Mortem:** 런타임 에러 발생 시 메모리와 스택을 캡처(ESF 포맷)하여, AI나 개발자의 요청 시 가상 DAP 서버로 동작해 죽은 프로세스의 상태를 IDE에 시각적으로 재현합니다.
2. **AI-Driven Hypothesis & Test Generation:** AI 에이전트(Claude Code)가 MCP를 통해 캡처된 상태를 분석하고, 가설을 검증(Evaluate)하며, 에러를 즉시 재현할 수 있는 **단위 테스트(Unit Test) 코드를 자동 생성**합니다.
3. **Live Debugging Proxy:** IDE와 실제 디버거 사이의 DAP 메시지를 중계하여 멈춰있는 상태의 컨텍스트를 AI에게 실시간으로 제공합니다.

---

## 🛠️ Phase 1: Core MCP Server & Snapshot Format (ESF)

**목표:** 에러 스냅샷의 데이터 구조를 정의하고, 이를 관리할 수 있는 기본 MCP 서버를 구축합니다.

### Task 1.1: ESF (Errordog Snapshot Format) 정의

* 에러 정보를 담을 JSON 스키마를 설계합니다.
* 필수 필드: `error_id`, `timestamp`, `exception_type`, `exception_message`, `frames` (콜스택 리스트).
* `frames` 내부 구조: `file_path`, `line_number`, `function_name`, `locals` (직렬화된 지역 변수 딕셔너리), `globals`.

### Task 1.2: 기본 MCP 서버 스캐폴딩

* Python을 사용하여 기본 MCP 서버를 구축합니다.
* 에러 스냅샷 파일들이 저장될 디렉토리(예: `~/.errordog/snapshots/`)를 관리하는 로직을 작성합니다.

### Task 1.3: MCP Tools 구현

* `list_errors()`: 저장된 스냅샷 파일 목록 반환.
* `get_error_details(error_id)`: 특정 스냅샷의 JSON 데이터 반환.

### ✅ Phase 1 Runnable Success Criteria & Guarantee

* **테스트:** 더미 JSON 스냅샷 파일을 만들고 MCP 도구를 통해 정상 반환되는지 확인.
* **보장 (Guarantee):** **"AI의 에러 인지 파이프라인"** - 더 이상 터미널 로그를 복사/붙여넣기 할 필요 없이, AI가 로컬의 에러 히스토리와 컨텍스트를 스스로 조회할 수 있게 됩니다.

---

## 🐍 Phase 2: Python Runtime Tracker (Agent)

**목표:** 실제 Python 스크립트에서 에러가 났을 때 Phase 1에서 정의한 ESF 포맷으로 스냅샷을 자동 생성하는 라이브러리를 만듭니다.

### Task 2.1: `sys.excepthook` 오버라이드

* `errordog_tracker` 모듈을 생성하여 Uncaught exception 발생 시 가로채는 훅을 작성합니다.

### Task 2.2: Stack & Memory 추출 로직

* `traceback` 및 `inspect` 모듈을 사용하여 크래시 시점의 프레임들을 순회합니다.
* 각 프레임의 `f_locals`와 `f_globals`를 안전하게 직렬화합니다 (직렬화 불가능한 객체는 `repr()` 처리).

### Task 2.3: ESF 파일 저장

* 추출한 데이터를 JSON 포맷으로 변환하여 `~/.errordog/snapshots/`에 저장합니다.

### ✅ Phase 2 Runnable Success Criteria & Guarantee

* **테스트:** 의도적으로 에러를 발생시키는 스크립트 실행 후, MCP 서버에 해당 에러가 목록으로 뜨는지 확인.
* **보장 (Guarantee):** **"휘발되지 않는 크래시 컨텍스트"** - 디버거 없이 코드를 돌리다 에러가 나더라도, 그 순간의 변수 상태와 스택이 영구적인 데이터로 박제됩니다.

---

## 🔄 Phase 3: Hybrid DAP Server (Proxy & Mock)

**목표:** IDE와 실제 디버거 사이의 통신을 중계(Proxy)하고, 필요시 저장된 스냅샷을 로드하는 가상(Mock) 서버 역할도 수행합니다.

### Task 3.1: DAP Proxy Router 구현

* 소켓 서버를 열어 IDE(Client)의 연결을 받고, 타겟 디버거로 연결을 맺어 양방향 JSON-RPC 메시지를 포워딩합니다.

### Task 3.2: Debugging State Caching (상태 추적)

* 프록시를 통과하는 메시지 중 `StoppedEvent` 등을 감지하여 현재 멈춰있는 `threadId`, `frameId`를 Errordog 내부 메모리에 캐싱합니다.

### Task 3.3: Mock Mode (Post-Mortem) 분기 처리

* IDE의 `attach` 요청 시, `error_id`가 주어지면 ESF 파일을 로드하여 `stackTrace`, `variables` 요청에 응답하는 가상 서버로 동작하게 만듭니다.

### ✅ Phase 3 Runnable Success Criteria & Guarantee

* **테스트:** 실제 `debugpy`와 Neovim 사이에 Errordog을 두고 브레이크포인트가 정상 작동하는지 확인.
* **보장 (Guarantee):** **"죽은 프로세스의 IDE 시각화"** - 텍스트 로그에 의존하던 에러 분석을 내 로컬 IDE의 GUI 디버거 환경으로 끌어옵니다.

---

## 🔥 Phase 4: AI Hypothesis Testing & Auto-Test Generation (Killer Features)

**목표:** AI가 캡처된 상태를 기반으로 가설을 검증하고, 에러를 재현하는 단위 테스트를 즉시 생성하며, IDE 연동을 자동화합니다.

### Task 4.1: State Evaluation MCP Tool 구현

* `evaluate_expression(expression, frame_id)`: AI가 멈춰있는 상태(Live 또는 Mock)에서 특정 파이썬 표현식을 실행해 보고 결과를 받아보는 도구. (예: AI가 "이 변수를 int로 캐스팅하면 어떻게 될까?"를 스스로 테스트).

### Task 4.2: Automated Test Generator 구현

* `generate_reproduction_test(error_id)`: AI가 ESF 데이터를 분석하여, 크래시가 발생했던 함수의 진입점 파라미터(Arguments)와 이전 상태를 모킹(Mocking)하는 `pytest` 스크립트를 생성하여 파일로 저장하는 도구.

### Task 4.3: IDE Automation & Post-Mortem Trigger

* `reproduce_error_in_ide(error_id)`: Neovim RPC를 통해 Neovim이 자동으로 Errordog Mock 모드에 `attach` 하도록 명령 전송.

### ✅ Phase 4 Runnable Success Criteria & Guarantee (Final)

* **테스트 1 (가설 검증):** 에러 스냅샷 로드 후 AI에게 "왜 이 함수가 실패했는지 원인을 찾고, 디버그 환경에서 evaluate를 통해 수정 가설을 검증해 봐"라고 명령하여 정확한 리포트를 받음.
* **테스트 2 (테스트 생성):** AI에게 "이 에러를 재현하는 pytest를 만들어줘"라고 명령했을 때, 실행 가능한 테스트 코드가 디렉토리에 생성됨.
* **보장 (Guarantee):** **"AI 주도형 근본 원인 분석 및 Zero-Effort 테스트 생성"** - 에러 재현을 위해 수동으로 입력값을 세팅하고 앱을 다시 켤 필요 없이, 즉시 TDD 사이클로 진입할 수 있습니다.
