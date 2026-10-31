# 2026-10-31 작업 마감과 다음 작업 인수인계

상태: **요청 송수신 기록 정리 완료 / 전체 G3 미완료**

이 문서는 이미 실행한 결과를 찾기 위한 마감 기록이다. 새 실험 결과나 요구사항 승인을 추가하지 않는다. 진행 과정은 [G3_PROGRESS](G3_PROGRESS.md), 전체 상태는 [STATUS](STATUS.md)를 따른다.

## 1. 확인된 범위

| 항목 | 상태 | 근거 |
| --- | --- | --- |
| 기준선 | v1.0, Git HEAD 94411a4 | 연구 수치와 시험 명세 변경 없음 |
| G0/G1/G2 | 과거 실행 PASS | 2026-10-19 설치 및 실행 기록 |
| G3 요청 송수신 | 실제 PASS | 2026-10-31 정상 5개와 정지 5개를 독립 프로그램 간 전달 |
| CARLA adapter | 미구현 | 다음 작업 |
| 전체 G3 / G4 | NOT_RUN | CAN 요청에 의한 차량 제동 증거 없음 |
| 본시험 | 0/80회 | 연결 확인 실행은 본시험에 포함하지 않음 |

이 체크포인트 작성 당시에는 프로그램과 실행 환경을 바꾸지 않고 기록만 정리했고, 자료는 로컬 미커밋 상태였다. 이후 Git 저장 상태는 [중간점검](MIDTERM_REVIEW_2026-10-31.md)의 명령으로 확인한다.

## 2. 증거를 읽는 순서

1. [최종 요청 송수신 판정](../evidence/manual/g3-can-20261031T104807355660618Z-2/verdict.json): 범위와 PASS, 두 worker의 종료코드.
2. [실행 명령과 프로세스](../evidence/manual/g3-can-20261031T104807355660618Z-2/commands.json): 독립 receiver/sender 및 격리 Python 실행.
3. [원시 송신](../evidence/manual/g3-can-20261031T104807355660618Z-2/sender.jsonl)과 [원시 수신](../evidence/manual/g3-can-20261031T104807355660618Z-2/receiver.jsonl): 실제 ID/DLC/payload/token과 호스트 시각.
4. [독립 재계산](../evidence/manual/g3-can-20261031T104807355660618Z-2/observation_audit.json): 원시 바이트와 프로세스, 시각 경계 대조.
5. [장치 준비 후 재확인](../evidence/g3/2026-10-31/host_ready_recheck.json): vcan0 종류/UP 및 패키지 버전.
6. [검사 기록](../evidence/g3/2026-10-31/transport_checks.json): 단위 검사 62개, 의존성, 문서 링크 96개를 확인한 당시 명령과 출력.
7. [이전 첫 ENV_ERROR](../evidence/g3/g3-stage1-20261031-01/verdict.json)와 [최종 도구의 장치 부재 기록](../evidence/g3/2026-10-31/entrypoint_preflight.json): 사용자 장치 준비 이전의 실패 이력.
8. [증거 목록과 SHA-256](../evidence/g3/2026-10-31/checkpoint_manifest.json): 파일 경로와 로컬 관측 해시. 원본의 진위를 인증하는 서명은 아님.

원시 실행 기록을 새 결과로 덮어쓰지 않는다. 같은 코드를 재실행할 때도 새 출력 폴더를 사용한다. 당시 소스 사본은 실행 metadata의 SHA-256과 대조할 수 있다.

## 3. 직접 확인하는 명령

```bash
cd /home/parkjuwon/can-stop-request-validation
bash tools/run_self_checks.sh check
ip -details link show dev vcan0
bash tools/run_self_checks.sh g3-can
```

이는 사용자 재실행용 명령이다. 이번 기록 정리 작업에서 새 요청 송수신 시험을 실행했다는 뜻이 아니다. 가상 장치가 없다면 [SELF_CHECK](SELF_CHECK.md)의 준비 절차를 먼저 사용한다. g3-can의 PASS는 CARLA 차량 연결을 뜻하지 않는다.

## 4. 다음 작업의 완료 기준

- [ ] 기준선을 다시 읽고 정상 StopRequest의 최소 수용 조건과 잘못된 요청의 처리 제안을 정리한다. 미정 정책을 승인된 규칙처럼 구현하지 않는다.
- [ ] 단일 adapter의 수신과 제동 제어 호출을 구현하고 단위 검사한다. 새 설명과 주석은 한글로 작성한다.
- [ ] G2에서 확인한 sticky_control=true와 batch 제동 경로를 사용한다. 단일 프로세스가 제어와 동기 tick을 소유한다.
- [ ] 실제 CAN 수신, 제어 호출 완료, 최초 제동 적용 frame과 실제 평면 속도를 각각 기록한다. 호스트 시각과 시뮬레이션 시각을 직접 빼지 않는다.
- [ ] 해당 증거를 얻은 뒤 전체 G3를 판정한다. 실패도 보존하고, G4와 80회 본시험은 별도로 진행한다.

## 5. 남은 문제

CARLA 서버는 이전 Ctrl+C 종료에서 Signal 11/exit 139가 두 번 발생했다. 정상 주행 및 actor/settings 정리의 성공과 서버 종료 문제를 구분한다. [기존 실행 기록](../evidence/setup/2026-10-19/server_runtime.json)을 보존하고 장시간 무인 실행 전에 점검한다.

StopRequest의 미정의 stop/reason, 예약 byte 불일치, 다른 token과 순번에 대한 adapter 대응은 아직 확정하지 않았다. 현재 parser의 필드 보존을 유효 요청 승인으로 해석하지 않는다.
