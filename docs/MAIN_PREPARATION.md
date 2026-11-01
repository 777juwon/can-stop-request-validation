# CARLA 본시험 준비와 직접 실행

2026-11-01. 실행기, 고정 설정과 원래80개 ID 구현 및 전체273개 코드 검사PASS. **새 실행기의 실제 CARLA 통합 확인은 미실행, 본시험0/80회다.** 사용자 요청으로 중단 지점부터 준비를 재개했으며 실제 서버/CAN 실행은 사용자가 맡는다.

## 준비한 것과 근거

| 파일 | 역할 |
| --- | --- |
| [고정 설정](../config/main_v1.json) | CARLA0.9.15, Town04, Model3, ClearNoon, spawn143, 속도/주기/판정값 고정 |
| [80개 원래 ID](../config/main_runs_v1.json) | T-01~04별 A/B 각각10회. 홀수 반복A→B, 짝수B→A |
| [계획과 동결 검사](../tools/main_plan.py) | 설정/입력/소스 SHA 대조. 수정된 구현을 같은 계획에 섞어 재개하지 않음 |
| [실행기](../tools/main_campaign.py) | prepare/status/check/run, 원래 시도 예약, 실행 수 제한과 재개 |
| [차량 연결](../tools/g4_carla_smoke.py) | 독립 worker와 단일 tick/제어 소유. 기존 G4 기본값은 A/T-03 유지 |
| [독립 판정](../tools/main_trial_oracle.py) | 원시 CAN과 adapter 호출, 실제 velocity/적용 제어/frame을 별도로 판정 |

spawn143과 물리/Ackermann 설정은 [사용자 G4 관측](../evidence/manual/g4-20261101T090038689401166Z-95119/metadata.json)을 근거로 본시험 전에 선택했다. wheel의 절대 position만 해시에서 제외하고 질량/토크/마찰 등 나머지는 대조한다. 실제 맵/차량 설정이 다르면 ENV_ERROR로 남기며 결과에 맞춰 위치나 기준을 바꾸지 않는다. v1.0 요구사항과 제출한 작성계획서는 변경하지 않았다.

273개 검사는 기존242개와 새31개다. 80개 배정, 실패/중단 보존, 소스 변경 차단, 실제 실행기 preflight 오류 기록, R-06의50ms 경계, 다음tick 제동, R-07의40frame/연속11표본, 정지 잠금, 관측 누락과 초기 큐 경계를 확인했다. [검사 기록](../evidence/implementation/main-preparation-20261101-01/checks.json). 합성 로그와 mock 검사는 실제 CARLA/vCAN 성공을 뜻하지 않는다.

## 첫 바톤터치: 본시험 밖에서 2개 확인

아래 실제 시험 명령은 **사용자 실행 예정**이다. 기존 메시지 예비8개를 다시 실행할 필요는 없다. 먼저 코드와 장치를 확인한다.

```bash
cd /home/parkjuwon/can-stop-request-validation
bash tools/run_self_checks.sh check
ip -details link show dev vcan0
```

vcan0가 없거나 DOWN일 때만 실행한다. apt/dpkg는 사용하지 않는다.

```bash
sudo bash tools/prepare_vcan0.sh
```

터미널 A에서 서버를 시작한다. 다른 CARLA 제어/tick/시험 프로그램은 종료한 상태여야 한다. 이 서버는 화면 없는 offscreen 실행이다. A의 터미널은 그대로 둔다.

```bash
cd /home/parkjuwon/can-stop-request-validation
bash tools/start_carla_0915.sh
```

터미널 B에서 접속 포트를 확인한다. 2000의 LISTEN은 접속 준비의 일부이며 전체 시험 PASS를 뜻하지 않는다.

```bash
cd /home/parkjuwon/can-stop-request-validation
ss -ltn 'sport = :2000 or sport = :2001'
```

아래는 별도로 실행할 **개발 확인2개**다. 둘 다 main_trials_executed=0이며80개 원래 ID를 소비하지 않는다. 첫 결과를 확인한 뒤 두 번째를 실행한다. 폴더가 이미 있으면 덮어쓰지 말고 `-02` 등 새 이름을 사용한다.

A/B는 시험 유형이 아니라 감시 방식이다. A는 수신 타임아웃, B는 수신 타임아웃과 순번 갱신을 감시한다. 본시험에서는 두 방식 모두 같은4개 시나리오를 각각10회씩 수행한다. 여기서 B/T-04는 반복 순번에 대한 요청/정지 경로, A/T-01은 불필요하게 멈추지 않는 주행 경로를 먼저 확인하기 위해 골랐다. 이 두 번만으로 A/B 성능을 비교하지 않는다.

```bash
.venv/bin/python -I tools/main_campaign.py check \
  --output-dir runs/check-B-T04-01 --variant B --scenario T-04 \
  --exclusive-server --allow-world-load
```

기대: B가 반복 순번을 감지하고 요청/실제 제동/정지를 확인. 마지막 status=PASS, result.json의 execution_status=COMPLETE, cleanup_status=PASS, checks.evidence_valid=true. 오류면 다음 명령을 멈추고 폴더 경로와 마지막 출력을 전달한다.

```bash
.venv/bin/python -I tools/main_campaign.py check \
  --output-dir runs/check-A-T01-01 --variant A --scenario T-01 \
  --exclusive-server --allow-world-load
```

기대: 정상 원거리에서 계속 움직이며 불필요한 요청이 없음. R-01/R-05/R-09 PASS, R-06/R-07 N/A. 체크 명령은 전체 status=PASS일 때만 종료코드0이다. 두 폴더와 마지막 status만 Codex에 전달한다. 새 실행기의 실제 정상/정지 경로와 정리 결과를 검토한 뒤 본시험으로 넘어간다.

## 원래80개 계획 생성과 조회

아래 prepare/status는 서버와 CAN을 실행하지 않는다. prepare는 **한 번만**, 존재하지 않는 폴더에 실행한다. 생성하면80개 ID와 고유 token, 설정/입력/소스 해시, 소스 사본을 manifest.json에 고정한다. `runs/` 원시 자료는 로컬 보존 대상이며 Git 업로드에서 제외했다.

**현재 로컬에서는 이미 생성 완료**: 코드 커밋09332f8 뒤 `runs/main-v1-20261101`을 만들었고 status는 시도0/완료0/미시작80이다.20개 소스/설정 사본의 SHA와 동결 대조도PASS다. 이 장치에서는 아래 prepare를 다시 실행하지 않고 status만 사용한다. [생성 명령과 검증 기록](../evidence/implementation/main-preparation-20261101-01/plan_prepared.json), [생성한 manifest 사본](../evidence/implementation/main-preparation-20261101-01/prepared_manifest.json). 별도 장치의 계획은 해당 장치에서 따로 준비하며 로컬 원시 결과가 Git으로 자동 공유되지는 않는다.

```bash
.venv/bin/python -I tools/main_campaign.py prepare \
  --output-dir runs/main-v1-20261101
.venv/bin/python -I tools/main_campaign.py status \
  --output-dir runs/main-v1-20261101
```

계획만 생성했으면 prepared_original_ids=80, original_attempted=0, original_completed=0, not_started=80이다. 이미 생성된 계획에는 prepare를 반복하지 않고 status부터 사용한다. 설정/ID 파일 작성과 계획 생성은 실제 시험 완료가 아니다.

## 본시험 시작과 재개

다음은 **개발 확인2개 검토 뒤 사용자 실행 예정**이다. 처음에는 한 번만 실행해 기록을 확인한다. 첫 ID는 M-T-01-R01-A, 다음은 같은 쌍 B다. 한 번 더 같은 명령을 실행하면 다음 미시작 ID 한 개를 수행한다.

```bash
.venv/bin/python -I tools/main_campaign.py run \
  --output-dir runs/main-v1-20261101 --max-runs 1 \
  --exclusive-server --allow-world-load
.venv/bin/python -I tools/main_campaign.py status \
  --output-dir runs/main-v1-20261101
```

첫 A/B 쌍까지 검토한 뒤 여러 개씩 진행하려면 --max-runs를 바꾼다. 이는 이번 명령에서 시작할 최대 시도 수이며 PASS 목표 수가 아니다. 예를 들어 --max-runs 4는 다음 미시작 ID를 최대4개 실행한다.80까지 허용하지만 서버 종료 문제가 미해결이므로 처음부터 장시간 무인 실행하지 않는다.

각 ID의 attempts/<ID>.json을 preflight 전에 기록한다. ENV_ERROR나 중단도 원래 시도로 세고 해당 ID를 재사용하지 않는다. 같은 run 명령으로 재개하면 이미 예약한 ID는 모두 건너뛴다. 프로세스와 서버 상태를 먼저 확인하고 오류 원인을 검토한 뒤 재개한다. 잠금 파일을 지우거나 기존 폴더/claim을 수정해 재시도하지 않는다.

코드/설정/입력이 바뀌면 동결 대조가 재개를 거부한다. 이미 본시험을 시작했다면 새 구현을 기존80개에 섞지 말고 영향을 검토하고 기준선/추가 실행의 처리 결정을 남긴다. 추가 재실행 자동화는 이번 범위에 없으며, 별도 ID와 원본 ID/이유를 기록하고80회와 별도 집계해야 한다.

## 결과 위치와 중단 판단

| 위치/필드 | 의미 |
| --- | --- |
| manifest.json | 사전 배정과 동결 근거. 수정하지 않음 |
| attempts/<ID>.json | 원래 시도 예약. preflight 실패도 보존 |
| runs/<ID>/metadata.json | 설정/commit/actor/시각/worker 및 정리 상태 |
| runs/<ID>/result.json, verdict.json | 실행 상태와 요구사항별 판정 |
| 같은 ID의 *.jsonl | 입력/독립 CAN 관측/SUT/adapter/차량 원시 기록 |
| status 명령 | 원래 시도/COMPLETE/미시작과 요구사항 FAIL 수 재계산 |
| status.json | run 명령이 만든 조회용 사본. 최신 상태는 status로 확인 |

- COMPLETE는 모든 요구사항PASS가 아니다. A/T-04 R-04 FAIL도 본시험 비교 결과로 남기며 이것만으로 배치를 중단하지 않는다. 미요청이면 R-07은N/A다.
- batch_halted=true 또는 실행 상태 오류, evidence_valid=false, cleanup 오류나 주행 전제 위반이면 후속 시도를 멈춘다. 이미 관측한 요구사항 FAIL은 오류 분류로 감추지 않는다.
- RESULT_NOT_RECORDED는 claim은 있지만 결과 파일이 없다는 뜻이다. 실행 중이거나 비정상 중단일 수 있다. 이 파일 부재만으로 중단을 확정하지 않으며 해당 ID는 재사용하지 않는다.
- original_attempted는 시도 수, original_completed는 COMPLETE 수, not_started는 미시작 수다.80번 시도와80번 성공을 혼동하지 않는다.
- 호스트 monotonic은 메시지/호출 판정, CARLA frame/시뮬레이션 시간은 정지 판정에 쓴다. 서로 빼서 지연을 만들지 않는다.

시험 중 Ctrl+C는 worker/actor/날씨/설정 정리를 시도하고 중단 결과를 남긴다. 강제 종료라면 근거가 부족한 ID도 그대로 남긴다. 실제 장치와 서버가 정리됐는지 확인한 뒤 이어간다. 실행기는 서버를 자동 시작/재시작/종료하지 않는다. 모든 시험과 결과 기록이 끝난 뒤 터미널 A의 서버를 종료한다. 기존 Ctrl+C Signal11/139는 미해결이며 actor/settings 정리PASS와 서버 정상 종료를 구분한다.

## 본시험 후 논문 사진 촬영 계획

80개 원래 시도를 기록한 뒤 별도 촬영 실행에서 화면을 켜고 차량을 보는 spectator 시점을 설정해 캡처할 수 있다. 현재 offscreen launcher와 동결 설정을 본시험 동안 유지하고, 촬영용 실행 절차는 이후 별도로 준비한다. 화면 표시와 시점 제어 도구는 아직 구현하거나 이 장치에서 확인하지 않았다.

- 정상 주행 장면과 정지 요청 뒤 차량 상태 장면을 준비한다.
- 같은 T-04 입력에서 A/B의 요청과 제동 상태를 함께 설명할 수 있도록 run ID, 경과 시각과 실제 속도 등 확인된 값을 표시한다.
- 그림 캡션은 본시험 후 별도로 수행한 시각화 재현임을 밝히고80개 원래 실행의 사진으로 표시하지 않는다. 정량 결과는 본시험 로그와 판정/그래프를 사용한다.
- 거리 입력은 사전 수치 시퀀스임을 유지한다. 촬영 장면을 실제 장애물 거리 측정이나 충돌 회피 검증으로 설명하지 않는다.

근거: [CARLA0.9.15 rendering](https://carla.readthedocs.io/en/0.9.15/adv_rendering_options/)의 offscreen 구분과 [spectator](https://carla.readthedocs.io/en/0.9.15/core_actors/#spectator)의 시점 이동 API다. 카메라 센서를 본시험에 추가하지 않고도 창의 시점을 바꿀 수 있다.

## 다음 작업자가 확인할 순서

README → STATUS → LINUX_HANDOFF → 이 문서 → main_v1.json/main_runs_v1.json → main_campaign.py/main_trial_oracle.py → checks.json. 실행했다면 해당 계획 status와 개별 result/metadata부터 읽는다. 이 대화의 기억 대신 파일과 원시 근거를 인수인계 기준으로 사용한다.
