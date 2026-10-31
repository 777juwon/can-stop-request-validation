# G3 단계별 진행 기록

갱신일: 2026-11-01. 설계 기준 commit `94411a4`, 기준선 v1.0. 실제 실행 당시 Git HEAD와 소스 SHA는 각 metadata에 기록한다. 최신 실제 연결 결과와 직접 실행은 [G3_INTEGRATION](G3_INTEGRATION.md)을 따른다. [중간점검 스냅샷](MIDTERM_REVIEW_2026-10-31.md)은 10월 31일 당시 기록이다.

## 1. 이번 작업의 완료 경계

사용자가 한 번에 전체 구현을 끝내지 말고 단계적으로 진행하도록 요청했다. 첫 작업은 CARLA 없는 StopRequest 송수신 도구와 단위 검사로 제한했다.

| 단계 | 범위 | 현재 상태 |
| --- | --- | --- |
| 1 | 0x200 바이트 생성, 필드 해석, 독립 송수신 도구와 관측 판정 | 구현 및 단위 검사 완료 |
| 2 | 실제 vcan0에서 요청 송신과 독립 수신 | PASS. 사용자 장치 준비 후 실제 10개 프레임 확인 |
| 3 | adapter 핵심 및 콜백 연결 | 구현 및 핵심 검사 18개 완료, 통합 실행기에 연결 |
| 4 | 실제 제동 호출, 적용 frame 및 차속 | 첫 실제 G3 PASS. 사용자 코드 검토와 직접 재현 대기 |

전체 G3는 **PASS**다. G4와 본시험은 미실행이다. 아래 2~5절은 10월 31일의 요청 송수신 단계와 핵심 구현 기록이다. 새 실제 통합은 정상 5개/정지 5개/정상 복원 10개를 사용하며 과거 10개 송수신과 구분한다.

## 2. 구현한 코드와 검증 범위

[g3_request_smoke.py](../tools/g3_request_smoke.py)는 표준 11-bit Classic CAN ID 0x200, DLC 8을 사용한다. payload는 `<BBBBI`, 즉 stop, reason, counter, 예약 0, little-endian uint32 run_token이다. 고정 예시 `stop=1, reason=1, counter=0xAB, token=0x12345678`의 payload는 `0101ab0078563412`다.

연결 확인용 입력은 50 ms 명목 슬롯 10개다. 처음 5개는 stop=0/reason=0, 다음 5개는 stop=1/reason=1이다. counter 0~9와 이 입력 순서는 연결 확인용 선택이며, 본시험이나 adapter 순번 정책으로 확정한 것이 아니다.

독립 송신 및 수신 프로세스를 준비하고, 상위 프로그램이 원시 ID/DLC/플래그/payload, 수량, 순서, token과 시각 경계를 비교한다. 송신 호출 직전, 성공 반환과 수신 관측의 호스트 monotonic 시각을 분리한다. 수신이 송신 호출 반환보다 먼저 관측되는 경우도 허용한다. 실제 차속이나 CARLA 시각은 이 단계에 생성하지 않는다.

장치는 이미 존재하는 UP 상태의 vcan만 사용한다. 상위 프로그램과 각 worker가 모두 확인하며 물리 CAN을 열거나 인터페이스를 생성하지 않는다. 출력 폴더는 매번 새로 만들고, 실패와 예외도 판정 및 진단 파일에 남긴다.

## 3. 이번에 확인한 환경과 실행 결과

2026-10-31 첫 작업의 사전확인 결과다. 이후 사용자 장치 준비와 실제 송수신 결과는 아래에 이어 기록한다.

- 기존 로컬 변경만 있으며 main/HEAD 94411a4 유지.
- kernel 6.8.0-138-generic, 프로젝트 Python 3.10.12.
- python-can 4.6.1, cantools 40.7.1, carla 0.9.15 메타데이터 확인.
- 당시 vcan0는 존재하지 않았음. 소멸 원인은 확인하지 않았으며 재부팅이라고 단정하지 않음.
- 포트 2000/2001은 LISTEN 상태가 아님. CARLA 서버를 시작하지 않음.

첫 실제 사전검사:

```bash
.venv/bin/python -I tools/g3_request_smoke.py --interface vcan0 --output-dir evidence/g3/g3-stage1-20261031-01
```

종료코드 2, [ENV_ERROR](../evidence/g3/g3-stage1-20261031-01/verdict.json). [ip 조회](../evidence/g3/g3-stage1-20261031-01/preflight.json)의 종료코드는 1이며 `Device "vcan0" does not exist.`였다. 송수신 worker를 시작하지 않았고 commands.json은 빈 목록이다. 당시 소스는 해당 폴더에 보존했다.

코드 검토 후 최종 진입점도 실행했다.

```bash
bash tools/run_self_checks.sh g3-can
```

동일한 장치 부재로 종료코드 2, ENV_ERROR. [실행 기록과 출력 위치](../evidence/g3/2026-10-31/entrypoint_preflight.json). 이 결과는 실패를 기록하는 진입점의 확인이며, 실제 프레임 교환 검증은 아니다.

사용자가 장치 준비 완료를 알린 뒤 다시 조회했다. vcan0의 실제 종류는 vcan, flags는 UP/LOWER_UP이었다. MTU 72는 장치 능력이며 이번 원시 기록은 모두 16바이트 Classic CAN 프레임이었다. [호스트 재확인](../evidence/g3/2026-10-31/host_ready_recheck.json).

같은 `bash tools/run_self_checks.sh g3-can`을 실행해 종료코드 0, [실제 요청 송수신 PASS](../evidence/manual/g3-can-20261031T104807355660618Z-2/verdict.json)를 확인했다. 독립 receiver PID 8과 sender PID 10의 종료코드는 모두 0이다. 정상 5개와 정지 5개, 총 10개의 ID/DLC/플래그/raw payload/token/순서가 일치했다. PID는 이 실행에서 기록된 프로세스 식별값이다.

원시 로그를 별도로 다시 계산해 확인했다. 명목 50 ms 대비 송신 시작의 최대 지연은 0.108531 ms, 실제 송신 시작 간격은 49.955525~50.032410 ms였다. 이는 한 번의 연결 입력 일정 관측이며 물리 CAN 지연이나 본시험 성능 통계가 아니다. [독립 재계산](../evidence/manual/g3-can-20261031T104807355660618Z-2/observation_audit.json), [원시 수신](../evidence/manual/g3-can-20261031T104807355660618Z-2/receiver.jsonl). 당시 소스를 해시 확인 후 실행 폴더에 보존했다. 이전 ENV_ERROR도 유지한다.

## 4. 단위 검사와 검토에서 보완한 부분

요청 송수신 도구 작성 당시 새 단위 검사 23개와 기존 39개, 총 62개가 통과했다. 이후 adapter 검사 18개로 80개, 새 통합 관련 검사 39개 추가 후 현재 전체는 119개다. `bash tools/run_self_checks.sh check`로 재현한다. 송수신 검사는 고정 바이트, 정수 범위, 프레임 길이, 알려지지 않은 필드의 진단 보존, 수신 누락/중복/순서, raw/decoded 불일치, token, 플래그와 시각 경계를 다룬다.

읽기 전용 코드 검토에서 찾은 세 경로를 수정하고 회귀 검사를 추가했다.

1. 숨김 worker를 직접 호출해도 물리 CAN을 사용할 수 없도록 bind 전에 재확인.
2. `assert`에 의존하던 관측 판정을 명시 조건문으로 바꿔 Python `-O`에서도 유지.
3. receiver 조기 종료 시 TOOL_ERROR/INPUT_ERROR/ENV_ERROR 등의 원래 분류를 보존. 조기 종료의 PASS 상속도 차단.

최적화 Python 하위 프로세스 실행, 물리 장치 거부 시 socket 미호출, 조기 종료 분류 보존을 실제 단위 검사 경로로 확인했다. 테스트 대역을 사용하는 이 확인은 실제 vCAN 송수신을 대신하지 않는다. [검사 기록](../evidence/g3/2026-10-31/checks.json).

## 5. 아직 정하지 않은 adapter 정책

현재 parser는 8바이트를 필드로 읽을 뿐 유효 요청으로 승인하지 않는다. 미정의 stop/reason과 예약 byte도 진단용으로 보존한다. 잘못된 요청을 받았을 때의 adapter 대응, StopRequest counter의 수신 순번 정책, 요청 watchdog은 이 단계에서 추가하지 않았다. 거리 입력의 B 방식 규칙과 200 ms를 요청 수신기에 자동 적용하지 않는다.

adapter 핵심은 G3 정상 지원 범위를 정하고 범위 밖 입력은 예외로 호출자에게 전달한다. 이 검사를 실제 차량의 안전 대응 정책으로 확정하지 않는다. 기동 억제와 arm 전이, 잘못된 요청의 전체 취급은 통합 전에 구분하고 추가 결정이 필요하면 이유를 제시한다.

## 6. 다음 단계와 사용자 실행 명령

요청 송수신, adapter 핵심과 실제 CARLA 통합 실행기를 구현했다. 첫 실제 G3와 전체 검사 119개가 PASS했다. 다음은 사용자 코드 검토와 직접 G3 재현이다. 이후 최소 거리 입력 제어기를 작은 단계로 구현한다. 새로운 수신 오류 정책이 필요하면 구현 전에 이유와 제안을 정리한다.

현재 UP인 vcan0에서 사용자가 요청 송수신을 다시 확인하는 명령이다.

```bash
cd /home/parkjuwon/can-stop-request-validation
ip -details link show dev vcan0
bash tools/run_self_checks.sh g3-can
```

장치가 없다면 기존 `sudo bash tools/setup_g1_host.sh`를 사용자 터미널에서 먼저 실행한다. 이 명령은 시스템 패키지 설치 확인과 가상 장치 준비를 하며 물리 CAN을 변경하지 않는다. 마지막 검사 명령은 매번 새로운 evidence/manual 폴더를 출력한다. verdict.json의 scope가 G3_STAGE1_REQUEST_TRANSPORT_ONLY, status가 PASS이면 요청 송수신 부분만 통과다.

실제 통합에서는 수신, 호출 완료, 최초 적용 frame과 차속을 각각 기록했다. adapter 이벤트도 파일에 남겼다. 기존 서버 종료 Signal 11은 이번에 다시 관측해 별도 기록했다. [G3 원시 관측](../evidence/manual/g3-20261031T151442436312880Z-11071/result.json), [호스트 및 종료 상태](../evidence/g3/integration-20261101-01/host_and_server.json).
