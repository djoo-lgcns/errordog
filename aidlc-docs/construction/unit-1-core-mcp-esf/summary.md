# Unit 1 Summary: Core MCP Server & ESF

## 개요

Errordog의 기반이 되는 ESF(Errordog Snapshot Format) 스키마를 정의하고, 파일 기반 스냅샷 저장소와 FastMCP 서버를 구현한 첫 번째 유닛이다.

---

## 목적

- 에러 스냅샷의 표준 포맷(ESF)을 정의하여 전체 시스템의 데이터 계약을 수립
- MCP 프로토콜을 통해 AI 에이전트(Claude Code 등)가 에러 데이터를 조회할 수 있는 인터페이스 제공
- 이후 Unit(2, 3, 4)이 의존하는 핵심 모델과 저장소 레이어 구축

---

## 효과

> Unit 1 완료 후

- 에러 데이터에 표준이 생겼다 — 어떤 에러든 ESF(Frame + ErrorSnapshot)로 표현할 수 있고, Pydantic이 무결성을 보장한다.
- AI가 에러를 읽을 수 있다 — MCP 도구(list_errors, get_error_details)를 통해 AI 에이전트가 에러 목록 조회와 상세 분석이 가능하다.

---

## 도메인 엔티티

| 엔티티 | 설명 |
|--------|------|
| **Frame** | 예외 발생 시점의 단일 스택 프레임. `file_path`, `line_number`, `function_name`, `locals` 포함 |
| **ErrorSnapshot** | 에러 캡처 전체 데이터. `error_id`, `timestamp`, `exception_type`, `exception_message`, `frames` 포함 |
| **ErrorSummary** | `list_errors()` 반환용 경량 요약. ErrorSnapshot에서 파생(top frame 정보 포함) |

### error_id 포맷
`err_{YYYYMMDD}T{HHMMSS}_{6_random_hex}` (예: `err_20260310T131600_a3f2b1`)

---

## 핵심 비즈니스 룰

- **ESF 검증**: Pydantic 기반 자동 검증. frames는 최소 1개 필수, locals는 `dict[str, str]`
- **저장소**: `~/.errordog/snapshots/` 디렉토리에 `{error_id}.json` 형태로 저장
- **손상 파일 처리**: 파싱/검증 실패 시 경고 로그 후 건너뜀. 파일 삭제하지 않음
- **정렬**: `list_errors()`는 timestamp 내림차순(최신 우선)

---

## 생성된 파일

### 소스 코드
| 파일 | 역할 |
|------|------|
| `src/errordog/models.py` | ESF Pydantic 모델 (Frame, ErrorSnapshot, ErrorSummary, generate_error_id) |
| `src/errordog/store.py` | SnapshotStore: 파일 기반 CRUD |
| `src/errordog/server.py` | FastMCP 서버 + MCP 도구 등록 |
| `src/errordog/__main__.py` | CLI 진입점 (`python -m errordog`) |
| `src/errordog/__init__.py` | 패키지 초기화 |

### 테스트
| 파일 | 범위 |
|------|------|
| `tests/conftest.py` | 공유 픽스처 (sample_frame, sample_snapshot, snapshot_dir 등) |
| `tests/test_models.py` | Frame/ErrorSnapshot 검증, JSON 라운드트립, error_id 생성 |
| `tests/test_store.py` | 저장/목록/조회, 손상 파일 처리, 정렬 |
| `tests/test_server.py` | MCP 도구 동작, 에러 핸들링 |

### 설정
| 파일 | 역할 |
|------|------|
| `pyproject.toml` | uv 프로젝트 설정, Python 3.13+, fastmcp/pydantic 의존성 |

---

## MCP 도구

| 도구 | 설명 |
|------|------|
| `list_errors()` | 모든 저장된 스냅샷의 요약 목록 반환 (timestamp 내림차순) |
| `get_error_details(error_id)` | 특정 스냅샷의 전체 데이터 반환 |

---

## 테스트 결과

- **Unit 1 테스트**: 34/34 통과
- 커버리지: models, store, server 전체 포함

---

## 실행 방법

```bash
uv sync                      # 의존성 설치
uv run pytest                # 테스트 실행
uv run python -m errordog    # MCP 서버 시작 (stdio 전송)
```

---

## 후속 Unit과의 관계

- **Unit 2** (Runtime Tracker): `models.py`의 Frame/ErrorSnapshot과 `store.py`의 SnapshotStore를 재사용하여 예외 자동 캡처
- **Unit 3** (Hybrid DAP Server): `store.py`를 통해 ESF 스냅샷을 로드하여 Mock 모드에서 DAP 응답 생성
- **Unit 4** (AI Hypothesis Testing): `server.py`에 새 MCP 도구를 추가하여 표현식 평가 및 테스트 생성
