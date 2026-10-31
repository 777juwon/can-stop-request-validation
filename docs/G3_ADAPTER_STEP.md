# G3 adapter 구현과 직접 검토 및 실행

작성일: 2026-10-31. **핵심 코드와 단위 검사 완료 / 실제 차량 연결 미실행**.

사용자는 Codex가 구현하고 Juwon님이 코드를 검토하고 직접 실행해 확인하는 방식을 선택했다. 이번 작업은 그 방식의 첫 구현 단계다.

## 1. 역할과 현재 수행 범위

| 작업 | 담당 | 상태 |
| --- | --- | --- |
| 기존 환경 준비 명령 실행 | Juwon님 | 실행 완료 보고 후 vcan0 UP 재조회 기록 있음 |
| 요청 송수신 및 이번 adapter 핵심 작성 | Codex | 코드와 작업 이력 있음 |
| 이번 단위 검사와 예제 실행 | Codex | 새 18개 검사 통과, 예제 실행 |
| 설계와 코드 검토 | Juwon님 | 아래 질문을 직접 확인할 단계 |
| 예제 재실행과 출력 확인 | Juwon님 | 직접 실행 출력 제공, 기대 동작과 일치 확인. 전체 단위 검사 출력은 아직 없음 |
| 실제 CAN → CARLA 제동 | 다음 통합 작업 | 실행기 구현과 실제 실행 필요 |

직접 모든 코드를 다시 작성할 필요는 없다. 설계 선택, 입력과 출력, PASS의 근거와 한계를 설명할 수 있도록 검토하고 재현한다. 작성, 검토와 실행의 담당은 기록에서 구분한다. 사용자가 아직 실행하거나 검토하지 않은 일을 완료했다고 기록하지 않는다.

## 2. 검토할 코드와 질문

[g3_adapter_core.py](../tools/g3_adapter_core.py)의 흐름은 원시 프레임 → 지원 범위 확인 → 정지 잠금 → 기존 제어 유지 또는 제동 콜백 → 호출 기록이다.

| 코드 | 역할 | 검토 질문 |
| --- | --- | --- |
| parse_supported_request | ID/DLC, 예약 byte, token과 정상 지원 범위 확인 | 다른 run의 요청을 혼동하지 않는가? |
| BrakeAdapterCore.on_frame | 정상 요청과 정지 요청 분리, 최초 원인 유지 | 정상 요청이 차량을 다시 가속하는가? |
| apply_brake 콜백 | 기존 G2 제동 함수를 연결할 지점 | 호출 성공과 차량 적용을 구분하는가? |
| events | 수신과 호출 완료를 따로 보존 | 같은 호스트 시각끼리 계산하는가? |

stop=0은 가속 명령을 만들지 않고 기존 제어를 유지한다. stop=1 이후에는 정지 잠금과 최초 원인을 유지하며 후속 정상 요청에서도 제동을 요청한다. 콜백 오류는 기록하고 전달하며 자동 재시도하지 않는다. 사용자 취소도 다른 오류로 바꾸지 않는다.

지원 범위 밖 입력의 G3InputError는 호출자에게 전달하는 인터페이스다. 실제 차량의 오류 대응 정책으로 확정한 것이 아니다. 다음 실행기는 이 경우 시험을 중단하고 근거를 남기도록 연결해야 한다. 본시험의 잘못된 요청 처리와 watchdog 정책은 미정이다.

이 core는 명시적 arm 이후 구간용이다. 기동 억제 → arm 전이와 reset은 없다. INIT_INHIBITED도 이 객체에서는 정지 잠금에 들어가므로 전체 기동 상태 기계를 구현했다고 설명하지 않는다.

## 3. 지금 직접 실행할 수 있는 코드

```bash
cd /home/parkjuwon/can-stop-request-validation
bash tools/run_self_checks.sh check
.venv/bin/python -I tools/g3_adapter_core.py --demo
```

전체 단위 검사 80개 중 이번 adapter 검사는 18개다. demo에서 확인할 값은 다음과 같다.

- scope=G3_ADAPTER_DEMO_ONLY, actual_can=false, carla_executed=false.
- 정상 → 정지 → 정상 입력의 action은 KEEP_EXISTING_CONTROL → APPLY_FULL_BRAKE → APPLY_FULL_BRAKE.
- brake_callback_count=2. 실제 차량이 아닌 가짜 콜백의 호출 횟수다.

actor_id=77은 예제용 값이다. 예제의 call_within_50ms는 가짜 콜백 시간이며 실제 R-06 판정에 쓰지 않는다. events는 메모리 및 콘솔 출력이고 실제 CAN 수신 파일 로그는 다음 통합 실행기에 연결해야 한다.

사용자가 예제 실행 출력을 제공했고 정상 → 정지 → 정상에서 잠금과 제동 유지, 가짜 콜백 2회를 확인했다. [사용자 출력 검토 기록](../evidence/g3/adapter-core-20261031-01/user_demo_review.json). 함께 실행한 `bash tools/run_self_checks.sh`는 인자가 없어 도움말만 표시됐다. 전체 검사는 위 명령처럼 `check`를 붙여 실행한다. 예제 옵션은 정식 이름인 `--demo`를 사용한다.

기존 실제 CAN 요청 전달을 다시 확인하려면 `bash tools/run_self_checks.sh g3-can`을 사용한다. 이 PASS는 새 adapter의 실제 연결을 뜻하지 않는다.

## 4. CARLA를 직접 실행해 보는 방법

새 G3 통합 실행기는 아직 없다. 먼저 기존 G2를 재현해 서버와 실제 차속 확인 절차를 익힐 수 있다. 다른 차량 제어 및 동기 tick 프로그램을 종료하고 두 터미널을 사용한다.

터미널 A:

```bash
cd /home/parkjuwon/can-stop-request-validation
ss -ltn 'sport = :2000 or sport = :2001'
bash tools/start_carla_0915.sh
```

포트가 사용 중이면 소유자를 확인하고 충돌을 해소한 뒤 시작한다. 현재 실행기는 offscreen이라 창 없이 실행된다.

터미널 B:

```bash
cd /home/parkjuwon/can-stop-request-validation
bash tools/run_self_checks.sh g2 --exclusive-server --allow-world-load
```

출력 폴더의 result.json과 vehicle_states.jsonl에서 차속, 제동과 frame을 확인한다. 이것은 G2 재현이며 G3 성공으로 기록하지 않는다. 사용자 자신의 실행 여부와 결과는 별도 기록이 필요하다. 종료는 [SELF_CHECK](SELF_CHECK.md)의 절차를 따른다. 기존 Ctrl+C 종료 Signal 11/exit 139는 미해결이다.

## 5. 다음 작업

실제 CAN 수신 루프, 이번 core와 기존 G2 제동 함수를 단일 실행기에 연결한다. 준비와 arm 경계, 수신, 제어 호출 완료, 적용 frame과 실제 속도를 따로 기록한다. 실행기가 준비된 뒤 Juwon님이 같은 명령으로 재현하고 결과를 검토한다.

전체 G3/G4는 NOT_RUN이고 본시험은 0/80회다. 이번 근거는 [adapter core 검사 기록](../evidence/g3/adapter-core-20261031-01/checks.json)에 남긴다.
