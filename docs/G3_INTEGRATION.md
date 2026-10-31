# G3 실제 CAN과 CARLA 연결

2026-11-01 한국 시각에 첫 실제 실행 **PASS**. [최종 판정](../evidence/manual/g3-20261031T151442436312880Z-11071/result.json), [원시 자료 재계산](../evidence/manual/g3-20261031T151442436312880Z-11071/observation_audit.json), [호스트와 서버 기록](../evidence/g3/integration-20261101-01/host_and_server.json).

Codex가 구현하고 실행했다. Juwon님의 새 통합 코드 검토와 직접 G3 재실행은 아직 기록이 없다. 이전 사용자 검사 80개 OK와 가짜 콜백 예제 실행은 별도 근거다. G4, 거리 판단 SUT와 본시험은 아직 미실행이다.

새 통합 관련 단위 검사 39개를 추가했고 전체 119개와 의존성/셸 문법/공백 검사가 통과했다. [검사 기록](../evidence/g3/integration-20261101-01/gate_checks.json). 합성 로그와 API 대역을 쓰는 단위 검사를 실제 연결 성공의 근거로 대체하지 않는다.

## 1. 이번 연결의 범위

독립 송신기 → vcan0 → adapter 수신 및 제동 호출 → CARLA 적용 제어와 실제 속도를 확인한다. 별도 관측기는 같은 버스의 원시 요청을 기록한다. 차량 제어와 동기 tick은 상위 실행기 하나가 소유한다.

차량이 초기 5.0 +/- 0.5 km/h를 1초 유지한 후에만 입력을 시작한다. 입력은 50 ms 간격의 정상 5개 → 정지 5개 → 정상 복원 10개, 총 20개다. 복원 뒤에도 정지 잠금을 유지한다. 이 입력은 G3 연결 확인용이며 본시험 시나리오나 거리 판단 결과가 아니다. 기존 g3-can의 10개 입력과 구분한다.

기존 v1.0 값과 sticky_control=true, batch 제동 경로를 유지했다. 호스트 수신부터 호출 완료까지 50 ms, 적용 frame부터 40개 간격 이내에 속도 0.1 m/s 이하 11개 연속 표본을 요구한다. 시뮬레이션의 float32 경계 때문에 2초 창은 고정 0.05초 frame 수로 확인한다. 서로 다른 시계의 타임스탬프를 빼지 않는다.

## 2. Juwon님이 검토할 코드

| 파일 | 확인할 내용 |
| --- | --- |
| [g3_carla_smoke.py](../tools/g3_carla_smoke.py) | 준비 완료 후 arm, 단일 제어/tick, 잠금 이후 Ackermann 중지, 자원 복구 |
| [g3_integration_can.py](../tools/g3_integration_can.py) | 독립 송신과 관측, 20개 입력, 원시 바이트와 호스트 시각 |
| [g3_adapter_core.py](../tools/g3_adapter_core.py) | 정상 입력 무제어, 정지 잠금과 최초 원인 유지, 제동 콜백 |
| [g3_integration_oracle.py](../tools/g3_integration_oracle.py) | 별도 기대 바이트, 실제 호출 시각, 적용 제어와 속도 기반 판정 |

지원 범위 밖 요청은 실행을 중단하고 기록한다. 본시험용 잘못된 요청의 차량 대응이나 요청 watchdog을 확정한 것은 아니다. 이 실행기의 준비 후 arm은 전체 SUT의 INIT_INHIBITED와 arm 전이를 검증하지 않는다.

## 3. 직접 실행 명령

먼저 프로젝트 검사와 가상 장치를 확인한다. 가상 장치가 없거나 DOWN이면 준비 스크립트를 실행한다. 준비 스크립트는 can-utils/vulkan-tools 설치 확인과 vcan0 생성 및 UP 설정을 수행한다.

```bash
cd /home/parkjuwon/can-stop-request-validation
bash tools/run_self_checks.sh check
ip -details link show dev vcan0
# 가상 장치가 없거나 DOWN일 때 실행한다.
sudo bash tools/setup_g1_host.sh
```

다른 CARLA 제어 및 tick 프로그램을 종료한다. 터미널 A에서 포트가 비어 있는지 확인하고 전용 서버를 시작한다. 조회 결과에 LISTEN 항목이 있으면 기존 서버의 사용 상태를 먼저 확인한다.

```bash
cd /home/parkjuwon/can-stop-request-validation
ss -ltn 'sport = :2000 or sport = :2001'
bash tools/start_carla_0915.sh
```

서버는 offscreen으로 실행되어 창이 없다. 터미널 B에서 실행한다. 전용 빈 서버와 Town04 로드를 두 옵션으로 명시한다. 프로젝트 Python을 sudo로 실행하지 않는다.

```bash
cd /home/parkjuwon/can-stop-request-validation
bash tools/run_self_checks.sh g3 --exclusive-server --allow-world-load
```

출력한 새 `evidence/manual/g3-...` 폴더를 확인한다. 초기 서버와 맵 로드를 포함한 이번 실행은 약 14초였으며, 반복 실행의 소요시간을 보장하지 않는다. 오류면 같은 폴더를 재사용하지 않고 기존 로그를 보존한다.

## 4. 결과를 직접 확인하는 방법

아래 경로를 자신의 실행에서 출력한 폴더로 바꾼다. 이 예시는 이미 기록된 Codex 실행 결과를 조회한다.

```bash
.venv/bin/python -I -m json.tool evidence/manual/g3-20261031T151442436312880Z-11071/result.json
.venv/bin/python -I -m json.tool evidence/manual/g3-20261031T151442436312880Z-11071/metadata.json
```

| 파일 또는 필드 | 판정 방법 |
| --- | --- |
| result.json | status=PASS, execution_status=COMPLETE, cleanup_status=PASS |
| checks | transport_status/adapter_status/motion_status=PASS, failures와 missing_evidence가 빈 목록 |
| input_events.jsonl / can_observer.jsonl / adapter_rx.jsonl | 각각 20개, ID 0x200/DLC8/바이트/token/순서 일치 |
| adapter_events.jsonl | 최초 5개 무제어, 이후 15개 제동. 정상 복원 이후에도 stop_latched=true와 first_reason=1 |
| vehicle_states.jsonl | 실제 velocity에서 차속 재계산 가능. 적용 제동과 연속 frame, 정지 유지 확인 |
| metadata.json | 버전 0.9.15, 서로 다른 worker PID, 소스 SHA, actor 제거 및 설정/날씨 복구 |

이번 실행의 별도 원시 자료 재계산도 코드로 남겼다. 출력만 생성하며 기존 증거를 덮어쓰지 않는다. 향후 코드 변경으로 소스 SHA가 달라지면 이 과거 실행 전용 검사가 실패할 수 있다.

```bash
.venv/bin/python -I evidence/manual/g3-20261031T151442436312880Z-11071/audit_observations.py evidence/manual/g3-20261031T151442436312880Z-11071
```

## 5. 관측값과 남은 작업

| 항목 | 첫 실제 실행 |
| --- | --- |
| 환경 | CARLA client/server 0.9.15, Town04, Model3, ClearNoon, spawn 143 |
| 원시 관측 | 송신/독립 관측/adapter 수신/adapter 이벤트 각각 20개, 차량 표본 206개 |
| 초기 속도 유지 | 21개 표본, 4.575~4.964 km/h, 준비 7.862초 |
| 제동 호출 | 15회, 호스트 수신부터 호출 완료까지 최대 0.429085 ms |
| 적용과 정지 | 최초 적용 frame 8685, 정지 유지 frame 8686~8696, 적용 후 명목 0.55초에 유지 조건 완료 |
| 복원 이후 | 정상 요청 10개 뒤에도 제동 유지, frame 8725까지 관측 |
| 시험 후 복구 | 자신의 actor 제거, 날씨/설정 복구, 비동기 상태와 관련 actor 0개 재조회 |

이 수치는 한 번의 G3 연결 시험이며 R-01~R-09 전체 준수, 반복 성능이나 논문 본시험 통계가 아니다. 실행 폴더 시각은 UTC이고 문서 날짜는 한국 시각이다.

시험 후 터미널 A에서 Ctrl+C로 자신의 서버를 종료하고 포트를 조회한다.

```bash
ss -ltn 'sport = :2000 or sport = :2001'
```

이번에도 서버가 Signal 11/exit 139로 종료됐다. G2의 두 건에 이어 세 번째 관측이며 원인은 미해결이다. 포트와 GPU의 CARLA 프로세스는 종료 후 남지 않았다. 장시간 무인 시험 전에는 이 문제를 별도 점검한다.

다음은 사용자 코드 검토와 같은 명령의 직접 재현이다. 이후 G4를 위한 최소 거리 메시지 제어기와 기동/arm 전이를 작은 단계로 구현한다. 거리 중단 → SUT 정지 요청 → adapter → 실제 차량의 근거를 연결해야 한다. 현재 G4 NOT_RUN, 본시험 0/80회다.
