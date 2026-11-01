# 직접 실행하는 검사 안내

이 안내는 Ubuntu 프로젝트에서 G1~G4를 직접 재현하는 방법이다. 최신 G4는 A/T-03 최소 연결 PASS이며 사용자 직접 재현은 아직 기록이 없다. [G4 최소 연결](G4_MINIMUM_CHAIN.md)에 코드와 판정 방법을 정리했다. 앞으로 실제 실행은 사용자가 맡고 Codex는 코드 준비와 결과 검토를 맡는다.

## 1. 시작 위치와 한글 설명 규칙

최신 다음 단계는 [메시지 예비시험8개](REMAINING_STEPS.md)다. `bash tools/run_self_checks.sh preliminary`로 사용자가 실행하고 경로를 전달한다. CARLA 서버는 필요하지 않다.

```bash
cd /home/parkjuwon/can-stop-request-validation
bash tools/run_self_checks.sh --help
```

새로 작성하거나 수정하는 코드 설명, 주석과 docstring은 한글로 작성한다. 외부 API 이름과 기존 JSON 키는 그대로 사용한다. 당시 소스 해시를 보존해야 하는 과거 실행 증거는 번역하지 않는다.

## 2. 코드와 의존성 검사

```bash
bash tools/run_self_checks.sh check
```

현재 단위 검사238개, 격리된 Python의 pip check, 셸 문법과 Git 공백 검사를 실행한다. 단위 검사OK와 의존성 오류 없음, 종료코드0을 확인한다. 실제CAN/CARLA와 구분한다. 과거80개/G3의119개/G4의208개와 최신238개는 다른 시점의 기록이다.

## 3. G1 실제 vCAN 송수신

먼저 인터페이스를 조회한다.

```bash
ip -details link show dev vcan0
```

장치 종류가 vcan이고 UP이어야 한다. 설치가 완료된 현재 호스트에서 장치가 없거나 DOWN이면 아래 명령으로 가상 장치만 준비한다. 관리자 비밀번호가 필요하며 apt/dpkg를 사용하지 않는다.

```bash
sudo bash tools/prepare_vcan0.sh
```

다른 프로젝트 검사 프로그램이 vcan0를 사용하지 않는 상태에서 실행한다.

```bash
bash tools/run_self_checks.sh g1
```

화면에 새 증거 폴더와 최종 status가 표시된다. PASS와 종료코드 0을 확인한다. 출력 폴더의 verdict.json이 최종 판정이며 sender.jsonl과 receiver.jsonl이 원시 근거다. 거리 20개와 배경 심박 40개를 검사하고, 후반에는 거리만 중단한다. 정지 요청이나 차량 제어를 검사하는 단계는 아니다.

## 4. G2 실제 CARLA 주행과 제동

두 터미널을 사용한다. 다른 CARLA 검사, 수동 제어와 동기 tick 프로그램을 먼저 종료한다. 기존 서버가 있는지 확인한 뒤 전용 서버를 시작한다.

터미널 A:

```bash
cd /home/parkjuwon/can-stop-request-validation
ss -ltn 'sport = :2000 or sport = :2001'
bash tools/start_carla_0915.sh
```

조회에서 이미 포트가 사용 중이면 소유자를 확인하고 충돌을 해소한 뒤 시작한다. 서버는 화면 없이 실행되며, 창이 보이지 않는 것만으로 실패를 판단하지 않는다.

터미널 B:

```bash
cd /home/parkjuwon/can-stop-request-validation
bash tools/run_self_checks.sh g2 --exclusive-server --allow-world-load
```

두 옵션은 다른 제어 프로그램이 없는 전용 서버 사용과 빈 서버의 Town04 로드를 명시적으로 허용한다. 기존 차량이나 센서가 있는 서버에서는 검사가 중단된다. Python client는 기본 ~/carlaCache를 사용하므로 일반 사용자 터미널에서 실행한다. 프로젝트 Python을 sudo로 실행하지 않는다.

출력 폴더의 result.json에서 status=PASS를 확인한다. vehicle_states.jsonl에는 실제 차속, 적용 제어, frame과 두 종류의 시각이 남는다. 핵심 검사는 5.0 +/- 0.5 km/h를 1초 유지한 뒤 실제 제동을 적용하고, 2초의 시뮬레이션 창 안에서 속도 0.1 m/s 이하를 0.5초 유지하는 것이다.

검사가 끝나면 자신의 차량을 제거하고 설정과 날씨를 복구한다. 허용한 Town04 로드는 원래 맵으로 복구하지 않는다. 다른 프로그램이 없는 것을 확인한 뒤 터미널 A에서 Ctrl+C로 서버를 종료한다. G2 두 번과 G3/G4 각 한 번에서 Signal 11/exit 139가 관측됐으며 정상 종료 문제는 미해결이다. 검사 PASS와 서버 종료 성공을 구분한다.

```bash
ss -ltn 'sport = :2000 or sport = :2001'
```

서버 종료 후 두 포트가 더 이상 LISTEN 상태가 아닌지 확인한다.

## 5. 결과 위치와 다음 단계

최신 G4 실행과 사용자/에이전트 바톤터치는 [G4 안내 3절과 6절](G4_MINIMUM_CHAIN.md)을 따른다. G4 전용 서버까지 포함한 종료 Signal 11/139는 총 네 건이다. 아래 G3 안내는 당시 기록이다.

스크립트는 매번 evidence/manual 아래에 시각과 프로세스 번호를 포함한 새 폴더를 만든다. 기존 증거를 덮어쓰지 않는다. PASS가 아닌 경우 출력 폴더를 보존하고 result.json 또는 verdict.json 및 error.txt가 있으면 함께 확인한다. G1의 TOOL_ERROR와 환경 오류도 통과로 간주하지 않는다.

이 진입점의 G1과 검사 모드는 실제로 재실행해 통과를 확인했다. G2 호출 연결은 도움말과 인자 검사로 확인했으며, 이 스크립트를 통한 G2 재실행은 별도 기록이 필요하다. [진입점 확인 기록](../evidence/setup/2026-10-19/manual_entrypoint_checks.json), 기존 직접 G2 실행 근거는 [최종 run04](../evidence/g2/g2-20261019-04/result.json)에 있다.

## 6. G3 첫 단계: 차량 연결 전 요청 송수신

2026-10-31 최초에는 vcan0 부재로 사전검사가 ENV_ERROR였으나 사용자 장치 준비 후 실제 송수신 PASS를 확인했다. 현재 장치가 UP이면 바로 실행할 수 있다. 장치가 없으면 위 3절의 준비 스크립트를 먼저 사용한다.

```bash
bash tools/run_self_checks.sh g3-can
```

정상 요청 5개와 정지 요청 5개를 독립 프로그램 사이에서 보내고 관측한다. 출력 폴더의 verdict.json과 sender.jsonl/receiver.jsonl을 확인한다. `scope=G3_STAGE1_REQUEST_TRANSPORT_ONLY`의 PASS는 CAN 요청 송수신만 뜻한다. 실제 차량 제동이나 전체 G3의 통과는 아니다.

adapter 핵심 코드와 가짜 콜백 예제는 [G3_ADAPTER_STEP](G3_ADAPTER_STEP.md)에서 직접 실행할 수 있다. 이전 45~90분 예상은 전체 G3 작업의 계획 추정이며 완료 보장이나 실측 결과가 아니다.

## 7. G3 실제 차량 연결

위 3절의 vcan0 준비와 4절 터미널 A의 전용 CARLA 서버 시작을 먼저 수행한다. 다른 tick/제어 프로그램이 없는 상태에서 터미널 B에서 실행한다.

```bash
bash tools/run_self_checks.sh g3 --exclusive-server --allow-world-load
```

정상 5개, 정지 5개, 정상 복원 10개를 독립 송신하고 수신/제동 호출/적용/차속을 분리 기록한다. 화면에 출력한 폴더의 result.json에서 status=PASS, cleanup_status=PASS와 세 구성 요소 PASS를 확인한다. 매번 새 폴더를 만들며 실패 기록도 보존한다. 상세 로그 읽기와 코드 검토는 [G3_INTEGRATION](G3_INTEGRATION.md)을 따른다. Codex가 이 진입점으로 실제 PASS를 확인했다. 사용자 직접 재현과 G4/본시험 완료는 별도다.
