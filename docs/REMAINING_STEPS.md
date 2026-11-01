# 남은 순서와 바톤터치

2026-11-01. G4 A/T-03과 사용자 직접 재현PASS. B/DBC/예비 도구를 구현했고 최초 시도 중 시험기 시작신호 경로 지연을 수정했다. 전체242개 검사PASS. **실제 예비 정상완료0/8, 본시험0/80회다.** 첫 INPUT_ERROR 원본은 보존하며 새 폴더에서 재시도한다.

| 순서 | 담당과 행동 | 다음 단계 조건 |
| --- | --- | --- |
| 1 | Codex: B 핵심/DBC/고정 입력/독립 판정 준비 | 단위 검사242개 PASS. 실제 실행과 구분 |
| 2 | 사용자: 아래 명령으로 메시지 예비시험8개 실행 | 출력 폴더와 마지막status 전달 |
| 3 | Codex: summary와 필요한 원시 근거 검토/수정 | 8개 실행 상태와 요구사항별 결과 확인 |
| 4 | Codex: CARLA 실행기/고정 설정/80개 원래run ID 준비 | 코드 검사와 실제 명령을 따로 제공. 아직 준비 전 |
| 5 | 사용자: 준비된 명령으로 CARLA 본시험80회 | 중간점검/재개 기준 포함. 현재 명령은 아직 없음 |
| 6 | Codex와 사용자: 실패를 포함한 분석/표/그래프/추적표 검토 | 모든 원래 시도 보존 |
| 7 | 논문 본문 작성과 교수 피드백 반영 | 실행/분석과 별도 |

각 단계의 결과를 확인한 뒤 다음 명령을 제공한다. 아직 없는 미래 명령을 추정해 실행하지 않는다. 실제 서버/CAN 실행은 사용자가 맡고 Codex는 필요한 파일만 검토한다. 기본은 단일 에이전트다. 사용자가 알린5시간 잔여율이20%이하이면 추가 작업을 중단한다.

## 지금 실행할 명령

이번 단계에는 CARLA 서버가 필요하지 않다. 다른 vcan0 시험 프로그램이 없는 상태에서 실행한다.

```bash
cd /home/parkjuwon/can-stop-request-validation
bash tools/run_self_checks.sh check
ip -details link show dev vcan0
```

check는242개OK와 의존성 오류 없음을 확인한다. vcan0가 없거나 DOWN일 때만 아래 명령을 실행한다. apt/dpkg를 사용하지 않는다.

```bash
sudo bash tools/prepare_vcan0.sh
```

한 명령으로8개 조합을 실행한다.

```bash
bash tools/run_self_checks.sh preliminary
```

T-01 A/B → T-02 A/B → T-03 A/B → T-04 A/B 순서다. 매번 새 프로세스/token을 사용한다. 정상5개 후arm, 준비counter회전을 기다려T0를 시작하고20초 입력을 실행한다. 예상 약4~5분이며 소요시간 보장은 아니다. 환경/입력/증거 오류면 이후 조합을 강행하지 않는다. 출력 폴더를 재사용하지 않는다.

끝나면 **출력 폴더 경로와 마지막status만** 전달한다. 같은 작업 폴더의 summary.json과 각조합 verdict.json, 필요한 로그만 Codex가 읽는다. 전체 로그를 대화에 붙이거나 실패 폴더를 지우고 PASS까지 반복하지 않는다.

요약의 cases_attempted는 시도 수, cases_completed는 COMPLETE 수, cases_not_started는 시작하지 않은 수다. INPUT_ERROR로 첫 조합이 중단되면 시도1/완료0/미시작7이며8개가 끝난 것이 아니다.

## 완료와 요구사항 PASS의 차이

아래는 설계상 예상이며 실측 결과가 아니다.

| 입력 | A 수신 감시 | B 수신+순번 감시 |
| --- | --- | --- |
| T-01 정상 원거리 | 정지 요청 없음 | 정지 요청 없음 |
| T-02 정상 근거리 | 근거리 정지 요청 | 근거리 정지 요청 |
| T-03 거리 중단 | 수신 만료 정지 요청 | 수신 만료 정지 요청 |
| T-04 과거 반복 | 미요청으로 R-04 FAIL 가능 | 순번 갱신 만료 정지 요청 |

summary.status=COMPLETE_WITH_REQUIREMENT_FAILURES, 종료코드0이 나올 수 있다. 기록 가능한 예비시험을 완료했으나 요구사항 FAIL이 남았다는 뜻이다. A/T-04를 억지로 PASS로 바꾸지 않고 다른 실패도 그대로 검토한다. COMPLETE는 모든 요구사항PASS가 아니다.

R-06/R-07과 차량을 포함한 R-09 전체는N/A이며 차량 상태 파일을 만든 척하지 않는다. carla_executed=false, main_trials_executed=0을 유지한다. 기존 G4를80번 돌리는 것으로 본시험을 대체하지 않는다.

코드: [B 핵심](../tools/sequence_controller_core.py), [선택 가능한 worker](../tools/g4_can_workers.py), [독립 판정](../tools/message_trial_oracle.py), [예비 실행기](../tools/run_message_preliminary.py), [자체 DBC](../config/stop_request_v1.dbc). B는 delta1~127만 거리/인정순번/갱신 시각을 바꾸고 나머지 유효 입력은 수신 시각만 갱신한다. 최초 원인과 정지 잠금은 유지한다.
