# G4 최소 거리 중단 대응 연결

후속 사용자 직접 재현도 PASS: [사용자 실행 결과](../evidence/manual/g4-20261101T090038689401166Z-95119/result.json). client/server 0.9.15와 자원 복구를 확인했고 사용자가 보낸 종료 후 ss 출력에는 LISTEN 항목이 없다. 아래 최초 작성 시점의 재현 미기록과 구분한다. 창이 없는 것은 launcher의 -RenderOffScreen 설정이며 사용자 코드 검토 완료를 뜻하지는 않는다.

2026-11-01, **A 방식 T-03 한 번의 실제 연결 PASS**. [최종 결과](../evidence/manual/g4-20261101T084459538960446Z-57997/result.json). Codex가 구현 및 실행했다. 사용자 자신의 코드 검토와 G4 직접 재현은 아직 기록이 없다. B 방식, 8개 조합 예비시험과 본시험 80회는 미실행이다.

이후 사용자 요청에 따라 실제 서버와 시험 실행은 사용자가 맡는다. Codex는 코드/명령 준비와 필요한 로그만 검토한다. 계정 5시간 잔여율은 이 도구에서 자동 감시할 수 없으므로 사용자가 /status의 값을 알려준다. 잔여 20% 이하에서는 추가 작업을 중단한다.

## 1. G3에서 추가한 부분

G3는 정해진 StopRequest를 직접 보냈다. G4는 별도 제어기가 실제 거리 입력을 받아 수신 만료를 판단하고 StopRequest를 생성한다. 입력 송신기, SUT와 독립 관측기는 별도 프로세스다. coordinator만 CARLA 제어와 tick을 담당한다.

| 코드 | 역할과 검토할 지점 |
| --- | --- |
| [g4_controller_core.py](../tools/g4_controller_core.py) | A 방식. INIT_INHIBITED → 명시적 arm → ARMED → STOP_LATCHED. 199/200 ms 경계와 최초 원인 유지 |
| [g4_can_workers.py](../tools/g4_can_workers.py) | 실제 입력/요청 송수신. 관측기 원시 로그, 준비 신호와 독립 프로세스 |
| [g4_carla_smoke.py](../tools/g4_carla_smoke.py) | 관측기 준비 후 SUT 시작, arm 후 차량 준비, 단일 제어/tick, 종료와 복구 |
| [g4_oracle.py](../tools/g4_oracle.py) | 기대 바이트와 독립 관측, W-FAULT, 제동 호출과 실제 차량 반응을 각각 판정 |

A는 유효 거리 수신마다 시각을 갱신한다. 동일 counter라도 갱신하며 B의 순번 감시는 구현하지 않았다. 잘못된 ID/길이/플래그/token/valid/범위는 거리 입력을 갱신하지 않는다. 배경 심박도 거리 감시 시각을 갱신하지 않는다. 늦은 복원이 이미 지난 만료 기한을 숨기지 못하도록 새 입력 처리 전에 만료를 평가한다.

## 2. 기동과 실제 입력

INIT에서는 stop=1/reason=4를 송신하고 coordinator가 차량을 제동한다. 정상 원거리 입력 5개 이상과 신선도를 확인한 뒤 명시적으로 arm한다. arm은 기동 억제를 해제할 뿐 이미 잠긴 정지는 해제하지 않는다.

arm 직후 정상 요청 송신 완료를 확인하고 초기 CAN 큐를 adapter_prearm_rx.jsonl에 보존한 뒤 G3 adapter core를 새로 만든다. 기동 억제 요청을 G3의 영구 정지 잠금으로 잘못 처리하지 않기 위한 경계다. 이후 실제 정지 잠금은 해제하지 않는다.

준비 중에도 50 ms 명목 간격으로 거리 1000 cm와 배경 심박을 계속 보낸다. 실제 5.0 +/- 0.5 km/h를 1초 유지한 뒤 다음 정상 counter=0 송신부터 T0를 시작한다. counter를 임의로 되돌리지 않고 255→0 회전을 사용한다. 이번에는 준비 256슬롯 후 전역 슬롯 256에서 시작했다. 준비와 T0 시작은 30초 안에 완료해야 한다.

T0는 최초 본 구간 거리 프레임의 실제 s_begin이다. 이후 400슬롯, 20초를 고정한다. T-03 규칙대로 n=100~159에서 거리 0x100만 생략하고 배경 0x101은 계속 보낸다. n=160부터 거리를 복원한다. 마지막 신규 거리 n=99의 실제 송신 경계로 W-FAULT를 계산한다. 복원 후에도 SUT 요청과 실제 제동을 유지한다.

## 3. 직접 실행

이미 패키지가 설치된 이 호스트에서 vcan0가 없거나 DOWN이면 아래 준비 명령만 사용한다. 설치가 처음 필요한 호스트는 기존 setup_g1_host.sh 절차를 따른다.

```bash
cd /home/parkjuwon/can-stop-request-validation
bash tools/run_self_checks.sh check
ip -details link show dev vcan0
# 장치가 없거나 DOWN일 때만 관리자 권한으로 준비한다.
sudo bash tools/prepare_vcan0.sh
```

prepare_vcan0.sh는 apt/dpkg를 사용하지 않는다. 이번 기존 설치 확인 스크립트는 자동 업데이트의 dpkg 잠금 때문에 중단됐으나, 패키지와 모듈 설치를 확인한 뒤 이 경로로 vcan0를 준비했다. 잠금 파일 삭제나 업데이트 강제 종료는 하지 않았다.

다른 제어 및 tick 프로그램이 없는 전용 서버를 두 터미널로 사용한다. 포트가 이미 사용 중이면 소유 서버의 사용 상태를 먼저 확인한다.

터미널 A:

```bash
cd /home/parkjuwon/can-stop-request-validation
ss -ltn 'sport = :2000 or sport = :2001'
bash tools/start_carla_0915.sh
```

터미널 B:

```bash
cd /home/parkjuwon/can-stop-request-validation
bash tools/run_self_checks.sh g4 --exclusive-server --allow-world-load
```

서버는 offscreen이므로 창이 없다. 설치된 CARLA 0.9.15를 사용하며 프로젝트 Python을 sudo로 실행하지 않는다. 출력한 새 evidence/manual/g4-... 폴더를 확인한다. 이번 실행은 준비를 포함해 약 36초였으며 실행 시간 보장은 아니다.

## 4. 결과 읽기

```bash
.venv/bin/python -I -m json.tool evidence/manual/g4-20261101T084459538960446Z-57997/result.json
```

자신이 재현한 결과는 위 경로를 새 출력 폴더로 바꾼다.

| 근거 | 확인할 값 |
| --- | --- |
| result.json | status=PASS, execution_status=COMPLETE, cleanup_status=PASS. transport/request/adapter/motion 각각 PASS |
| metadata.json | 4개 PID, 소스 SHA, arm/T0 시각, 초기 속도 준비, worker COMPLETE/exit0과 자원 복구 |
| input_events.jsonl | 준비 512프레임. 본 구간 거리 340개와 심박 400개, 생략 60개는 별도 진단 |
| can_observer.jsonl | 준비와 본 구간의 입력 및 SUT 요청 원시 바이트. 최초 INIT 요청도 포함 |
| sut_events.jsonl | 입력 진단/상태 전이는 보조 근거. 실제 request_tx와 독립 요청 관측을 대조 |
| adapter_prearm_rx.jsonl | 초기 억제 구간과 첫 정상 요청의 큐 처리 근거 |
| adapter_rx.jsonl / adapter_events.jsonl | 활성화 이후 수신과 제동 호출의 actor, 원인과 호스트 시각 |
| vehicle_states.jsonl | 실제 velocity, 적용 제어, frame과 두 시계. 명령만으로 정지 판정하지 않음 |

## 5. 실제 결과와 실패 보존

| 항목 | 최종 실행 관측값 |
| --- | --- |
| 환경 | client/server 0.9.15, Town04, Model3, ClearNoon, spawn 143 |
| 식별 | coordinator 57997, observer 58237, controller 58239, sender 58241 |
| 입력/관측 | 입력 1252개, 요청 595개, 독립 관측 1847개, 활성 adapter 수신/이벤트 588개, 초기 큐 7개 |
| 차량 상태 | 653개 연속 표본 |
| 초기 준비 | 약 8.275초에 최초 안정화, T0까지 정상 입력 및 주행 유지 |
| 정지 요청 | 마지막 신규 거리 송신 완료 뒤 200.191233 ms에 독립 관측. W-FAULT 만족 |
| 제동 호출 | 수신부터 완료까지 최대 1.445615 ms |
| 실제 정지 | 최초 적용 frame 32125, 정지 유지 frame 32126~32136. 명목 0.55초에 유지 조건 완료 |
| 복원과 종료 | 거리 복원 후 run 끝까지 정지 요청/제동 유지. 자신의 actor 제거, 날씨와 설정 복구 |

요청 명목 주기는 50 ms이며 실제 요청 송신의 최대 간격 60.183816 ms도 기록했다. 임의의 지터 허용값을 새로 만들지 않았으며 W-FAULT와 adapter 50 ms 한계는 원래 값 그대로 판정했다. 한 번의 기능 연결 근거이며 반복 주기성이나 본시험 성능 통계가 아니다.

첫 실행은 독립 관측기가 bind되기 전 최초 INIT 요청 counter=0이 송신돼 전체 FAIL이었다. 요청 595개 중 594개만 독립 관측했다. [첫 FAIL](../evidence/manual/g4-20261101T084234152151642Z-51525/result.json), [원인과 당시 소스 보존](../evidence/manual/g4-20261101T084234152151642Z-51525/failure_audit.json). 관측기 ready 확인 후 SUT를 시작하도록 수정하고 회귀 검사를 추가했다. 첫 판정을 바꾸지 않고 새 폴더에서 재실행했다.

전체 단위 검사 **208개 PASS**, 의존성/셸 문법/공백 검사 통과. [수정 후 검사](../evidence/g4/2026-11-01/after_startup_fix_checks.json). 초기 207개 검사도 별도 보존한다. 합성 로그 검사를 실제 차량 연결 근거로 대체하지 않는다.

검사 후 자신의 서버를 Ctrl+C로 종료하고 포트가 닫혔는지 확인한다. 이번에도 서버 Signal 11/139가 관측돼 총 네 번째이며 원인은 미해결이다. 차량 및 설정 복구와 서버 정상 종료는 구분한다. [호스트와 서버 기록](../evidence/g4/2026-11-01/host_and_server.json).

다음은 사용자 코드 검토와 직접 G4 재현, B의 순번 감시 구현 및 A/B 전체 시험 체계 완성이다. 예비 8개 조합과 본시험 80회, 결과 분석 및 논문 작성은 남아 있다.

## 6. 바톤터치와 전달할 출력

사용자는 위 3절의 코드 검사, 필요시 가상 장치 준비, 터미널 A의 서버 시작과 터미널 B의 G4 명령을 순서대로 실행한다. 중간에 Codex가 실행해야 할 단계는 없다. 이 진입점이 준비/arm과 20초 입력/복원/차량 정리까지 수행한다.

검사가 끝나면 **출력 폴더 경로와 마지막 status 한 줄만** Codex에 전달한다. 전체 단위 검사 목록과 원시 로그를 대화에 붙이지 않는다. 같은 작업 폴더이므로 Codex가 result.json과 필요한 로그 일부만 읽어 검토할 수 있다. 실패라면 바로 재실행하지 말고 해당 폴더를 보존한다. 수정이 필요하면 Codex가 작은 수정과 새 명령을 준비하고 사용자가 다시 실행한다.

사용자가 터미널 A에서 Ctrl+C로 자신의 서버를 종료하고 다음을 확인한다. 알려진 Signal 11/139도 결과와 함께 알린다. 포트가 닫히지 않았다면 임의 kill 대신 상태를 전달한다.

```bash
ss -ltn 'sport = :2000 or sport = :2001'
```

이 직접 재현은 이미 기록된 Codex 실행과 구분하며 본시험 80회에 포함하지 않는다.
