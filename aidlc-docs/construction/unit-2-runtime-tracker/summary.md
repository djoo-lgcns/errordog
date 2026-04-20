# Unit 2 Summary: Python Runtime Tracker

## 개요

Python 런타임에서 미처리 예외를 자동 캡처하여 ESF 스냅샷으로 저장하는 트래커 모듈이다. `sys.excepthook`을 오버라이드하여, import만으로 활성화되며 별도 설정 없이 동작한다.

---

## 목적

- 프로그램 크래시 시 스택 프레임과 로컬 변수를 자동으로 ESF 형식으로 저장
- MCP 서버를 통해 AI 에이전트가 사후(post-mortem) 에러 분석에 활용할 수 있는 데이터 확보
- 개발자의 추가 코드 작성 없이 `import errordog.tracker` 한 줄로 동작

---

## 효과

- 크래시가 사라지지 않는다 — 미처리 예외 발생 시 개발자 개입 없이 자동으로 ESF 스냅샷이 저장된다.
- 캡처 과정이 안전하다 — repr 실패, 디스크 에러 등 어떤 상황에서도 트래커 자체가 크래시하지 않고, 원래 traceback 출력을 보존한다.

---

## 새로운 엔티티

없음. Unit 1의 `Frame`, `ErrorSnapshot`, `SnapshotStore`를 그대로 재사용한다.

### 설정 상수
| 상수 | 기본값 | 설명 |
|------|--------|------|
| `MAX_FRAMES` | 50 | 캡처할 최대 스택 프레임 수 |
| `MAX_REPR_LENGTH` | 1000 | 변수 repr() 최대 문자 수 |

---

## 핵심 비즈니스 룰

### 트래커 활성화
- `import errordog.tracker` 시 즉시 `sys.excepthook` 설치
- 원래 excepthook을 보존하여 일반 traceback 출력은 유지
- 멱등(idempotent): 여러 번 import해도 중복 설치 없음

### 예외 캡처 범위
- `sys.excepthook`에 도달한 미처리 예외만 캡처
- `KeyboardInterrupt`, `SystemExit`은 무시 (진짜 에러가 아님)

### 스택 프레임 추출
- traceback 객체의 `tb.tb_next` 체인을 순회
- 최대 `MAX_FRAMES`개까지, 가장 안쪽(crash point) 프레임 우선 캡처
- 프레임 순서: innermost-first (ESF 포맷과 동일)

### 변수 직렬화 안전성
- `repr()` 실패 시 `<unrepresentable: {type}>` 폴백
- `MAX_REPR_LENGTH` 초과 시 잘라내기 + `...` 접미사
- 직렬화 과정에서 절대 크래시하지 않음

### 오류 안전성
- 스냅샷 캡처/저장 전 과정이 try/except로 보호
- 어떤 실패든 경고 로그 후 원래 excepthook으로 전달
- **트래커는 절대 상황을 악화시키지 않음**

---

## 생성된 파일

### 소스 코드
| 파일 | 역할 |
|------|------|
| `src/errordog/tracker.py` | sys.excepthook 오버라이드, 프레임 추출, 안전한 변수 직렬화 |

### 테스트
| 파일 | 범위 |
|------|------|
| `tests/test_tracker.py` | 18개 테스트: safe_repr, serialize_locals, extract_frames, excepthook 동작, 오류 안전성, 멱등 설치 |

### 스크립트
| 파일 | 역할 |
|------|------|
| `scripts/test_tracker_integration.py` | E2E 테스트: 의도적 ValueError -> 스냅샷 캡처 -> MCP로 조회 확인 |

---

## 동작 흐름

```
미처리 예외 발생
    │
    ▼
sys.excepthook(exc_type, exc_value, exc_tb) 호출
    │
    ├─ KeyboardInterrupt/SystemExit → 건너뜀
    │
    ▼
예외 정보 추출 (type, message)
    │
    ▼
traceback 프레임 순회 (최대 50개)
    │  각 프레임: file_path, line_number, function_name, locals(repr)
    │
    ▼
ErrorSnapshot 구성 + SnapshotStore.save_snapshot()
    │
    ├─ 실패 시: 경고 로그
    │
    ▼
원래 excepthook 호출 (정상 traceback 출력)
```

---

## 테스트 결과

- **Unit 2 테스트**: 18/18 통과
- **누적 전체 테스트 (Unit 1+2)**: 52/52 통과
- **통합 테스트**: 의도적 에러 → 스냅샷 생성 → MCP 도구로 조회 성공

---

## 사용법

```python
import errordog.tracker  # 이 한 줄로 후크 활성화

# 이후 미처리 예외 발생 시 자동으로
# ~/.errordog/snapshots/ 에 ESF 스냅샷 저장
```

---

## 후속 Unit과의 관계

- **Unit 1** (Core MCP & ESF): models.py, store.py를 그대로 재사용
- **Unit 3** (Hybrid DAP Server): tracker가 저장한 스냅샷을 Mock 모드에서 DAP 응답으로 변환
- **Unit 4** (AI Hypothesis Testing): tracker가 저장한 스냅샷을 기반으로 표현식 평가 및 테스트 생성
