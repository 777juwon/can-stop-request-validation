# Linux Codex handoff

## 현재 인수인계: 2026-11-01 G4

최신 준비: 끊긴 본시험 도구를 이어서 구현/검증했다. main_v1.json, main_runs_v1.json의80개 원래ID, main_campaign.py의 계획/실행/재개, main_trial_oracle.py의 전체 독립 판정을 준비했고 전체273개 검사PASS다. [MAIN_PREPARATION](MAIN_PREPARATION.md)에 서버 시작부터 결과 전달과 재개까지 명령이 있다. 실제CAN/CARLA는 이번에 실행하지 않았고 본시험0/80회다. 다음은 사용자의 별도 B/T-04 및 A/T-01 CARLA 개발 확인과 에이전트의 결과 검토다. 아래 중단/준비 전/검사 대기 표시는 과거 기록이다.

본시험 처리 원칙: prepare가80개ID/token과 코드/설정/입력 해시 및 소스를 동결한다. preflight 전 claim부터 원래 시도로 기록한다. 실패/중단 ID도 재사용하지 않고 동일 계획으로 재개하면 건너뛴다. RESULT_NOT_RECORDED는 실행 중/중단 여부 미확정인 결과 부재다. 요구사항FAIL과 실행 오류를 구분하고 A/T-04의R-04 FAIL을 유지한다. 코드를 바꾸면 동결 대조가 재개를 거부한다. 새 CARLA 통합과 실제80회 성공으로 확대하지 않는다.

이미 준비한 로컬 계획: `runs/main-v1-20261101/manifest.json`, 코드 커밋09332f8, 시도0/완료0/미시작80.20개 사본 SHA와 동결 대조PASS. 준비를 반복하지 말고 main_campaign.py status부터 조회한다. 생성 명령/원본 manifest 사본은 evidence/implementation/main-preparation-20261101-01에 보존했다. 이후 문서만 수정하는 커밋은 동결 소스의 해시를 바꾸지 않는다. 실제 개발 확인/본시험은 미실행이다.

최신 공유: 사용자 요청과 충돌 해결 승인으로5장 최종 목차 및 원격 제1~3장 본문을 유지하고 STATUS/WORKLOG의 양쪽 이력을 병합했다.5f8fab7까지 GitHub main에 게시했고 ls-remote와 로컬HEAD 일치를 확인했다. publication.json에 근거를 보존하며 이 인수인계 기록도 함께 공유한다.6장 목차는 현재안에서 대체됐고 연구 설계/수치/제출 계획서는 유지한다. 다음은 MAIN_PREPARATION의 B/T-04 개발 확인을 사용자가 실행하고 경로를 전달하는 것이다.

최신 중단: 사용자5시간 잔여15% 통보로20%기준에 따라 추가 구현을 멈췄다. 본시험 준비 코드는 아직 시작하지 않았다. 예비8/8완료, A/T-04 R-04 FAIL 보존, 본시험0/80회다. 사용량 초기화/사용자 재개 요청 뒤 CARLA 본시험 실행기/고정 설정/80개 원래ID부터 진행한다. 잔여율 자동 감시는 불가능하며 실제실행은 사용자담당이다.

최신: 사용자 메시지 예비시험8개 모두COMPLETE, 실제 완료8/8이다. [결과 해석](PRELIMINARY_RESULTS_2026-11-01.md). 유일한 요구사항FAIL은A/T-04의R-04 미요청이고 B/T-04는PASS다. 모든실행 evidence_valid=true, 입력+요청과 독립관측 raw수량/소스SHA 대조도 일치했다. COMPLETE_WITH_REQUIREMENT_FAILURES를 중단으로 해석하지 않는다. 다음은 CARLA 본시험 실행기/고정 설정/80개 원래ID 준비다. 본시험0/80회와 실제실행 사용자담당 선호를 유지한다. 아래 첫실패/대기 표시는 과거 기록이다.

최신 오류 수정: 첫 메시지 예비 시도는 T-01/A 첫슬롯의 신호파일 게시 경로 지연으로 INPUT_ERROR, 완료0/8이다. 실패 원본과 당시소스9개를 해당폴더에 보존했다. 같은슬롯의 거리/심박을 모두 보낸 뒤 신호를 게시하고 fsync를 제거했으며 회귀 포함242개 검사PASS다. actual CAN 재실행은 에이전트가 하지 않았다. 사용자가 check 후 preliminary를 새 폴더로 재실행해 경로만 전달하면 된다. 요약은 cases_attempted/cases_completed/cases_not_started를 구분한다. 기존 summary의 cases_completed=1은 과거 시도 수 표기 오류이며 원본은 수정하지 않았다.

최신 후속: B 핵심/자체DBC/메시지 예비8개 실행기를 구현했고238개 검사PASS다. 실제 예비시험은 실행하지 않았다. 사용자가 check, 필요시vcan0준비, `bash tools/run_self_checks.sh preliminary`를 실행하고 경로만 전달한다. [전체 순서](REMAINING_STEPS.md). A/T-04 R-04 FAIL 가능성을 보존하고 COMPLETE를 모든 요구사항PASS로 해석하지 않는다. CARLA 요구사항은 이 단계N/A, 본시험0/80회. CARLA 본시험 실행기와80개 원래ID는 그 다음 준비할 항목이다.

후속 사용자 재현: g4-20261101T090038689401166Z-95119를 사용자가 직접 실행했고 result/metadata의 전체 PASS와 자원 복구를 확인했다. 아래의 직접 재현 미기록은 그 이전 시점이며 현재 G4 직접 실행은 확인됐다. 사용자 코드 검토 완료는 별도다. 이번 확인에서는 파일만 읽고 새 실험을 하지 않았다.

최신 사용자 선호: 계정 사용량 절약을 위해 단일 에이전트로 코드와 명령만 준비하고 CARLA/CAN 실제 실행은 사용자가 맡는다. 명시적 재위임 없이는 에이전트가 실행하지 않는다. 사용자는 출력 폴더 경로와 마지막 status를 전달하고 에이전트는 필요한 결과만 검토한다. /status로 사용자가 알린 5시간 잔여율이 20% 이하이면 추가 작업을 중단한다. 현재 알려준 값은 47%이며 자동 갱신/감시되는 값이 아니다. 직접 명령과 바톤터치는 [G4 안내 3절과 6절](G4_MINIMUM_CHAIN.md)을 따른다.

G0/G1/G2/G3와 G4 최소 A/T-03 연결 PASS. A의 기동 억제, 정상 입력 5개 후 명시적 arm, 준비 중 연속 입력과 실제 속도 안정화, 거리 중단/복원과 정지 잠금을 구현했다. B 순번 감시와 전체 A/B 시험 체계, 예비 8개 조합 및 본시험 80회는 남아 있다. 사용자 자신의 새 코드 검토와 직접 재현은 아직 기록이 없다.

최신 읽기 순서: [G4_MINIMUM_CHAIN](G4_MINIMUM_CHAIN.md) → [G4 최종 판정](../evidence/manual/g4-20261101T084459538960446Z-57997/result.json) → 같은 폴더 metadata와 원시 로그 → [별도 재계산](../evidence/manual/g4-20261101T084459538960446Z-57997/observation_audit.json) → [검사 208개](../evidence/g4/2026-11-01/after_startup_fix_checks.json) → [호스트/서버](../evidence/g4/2026-11-01/host_and_server.json).

첫 G4는 관측기 bind 전 최초 INIT 요청 누락으로 FAIL이었다. 당시 소스와 원시 자료를 보존했다. 관측기 준비를 먼저 확인하도록 고치고 회귀 검사 후 새 실행에서 PASS했다. startup과 T0, SUT 종료 뒤 adapter drain과 마지막 tick의 경계를 유지한다. 초기 큐는 adapter_prearm_rx에 보존하고 기동 억제와 arm 후 정지 잠금을 구분한다.

기존 설치 스크립트는 unattended-upgrades의 dpkg 잠금으로 멈췄다. 패키지 설치를 확인한 뒤 사용자에게 `sudo bash tools/prepare_vcan0.sh` 한 번을 요청했고 vcan0 UP을 재조회했다. 앞으로 설치 완료 호스트의 가상 장치 준비에는 이 스크립트를 사용한다. 잠금 파일 삭제나 자동 업데이트 강제 종료는 하지 않는다.

서버는 종료됐으며 포트/GPU CARLA 프로세스가 남지 않았다. Ctrl+C Signal 11/139는 총 네 번째 관측으로 미해결이다. 이번 G4는 G3 게시 후 main/bcfa487에서 시작했고 별도 로컬 커밋으로 저장한다. 이번 G4 push는 요청받지 않았다. 다음은 사용자 검토/재현과 B 및 전체 시험 체계다.

## G3 완료 당시 인수인계

G0/G1/G2/G3 PASS, 거리 입력 A/B SUT 미구현, G4 NOT_RUN, 본시험 0/80회. 중단된 지점은 G3 통합 코드 작성 후 실제 실행 전이었다. 재개 후 vcan0 부재를 확인했고 사용자 sudo 준비 후 실제 통합까지 검증했다. [G3_INTEGRATION](G3_INTEGRATION.md)에 읽을 코드, 재현 명령과 결과 판정 방법이 있다.

실행 근거 읽기 순서:

1. [G3 result.json](../evidence/manual/g3-20261031T151442436312880Z-11071/result.json): 세 구성 요소 PASS와 정리 PASS.
2. [metadata.json](../evidence/manual/g3-20261031T151442436312880Z-11071/metadata.json): 버전, 소스 SHA, arm/worker/차량 및 복구 상태.
3. 같은 폴더의 input_events/can_observer/adapter_rx/adapter_events/vehicle_states.jsonl: 원시 바이트, 호출과 실제 상태.
4. [별도 재계산](../evidence/manual/g3-20261031T151442436312880Z-11071/observation_audit.json): 20개 요청, 제동 15회, 차량 표본 206개와 소스 SHA 대조.
5. [검사 기록](../evidence/g3/integration-20261101-01/gate_checks.json): 전체 단위 검사 119개, 의존성/셸 문법/공백 통과.
6. [호스트와 서버 종료](../evidence/g3/integration-20261101-01/host_and_server.json): Ctrl+C에서 Signal 11/139 재발. 포트/GPU 프로세스는 종료됨.

Codex가 구현 및 실제 실행했다. 사용자가 제공한 과거 80개 검사 OK와 가짜 콜백 예제는 확인됐지만, 사용자의 새 통합 코드 검토와 직접 G3 재현은 아직 기록이 없다. 다음은 이 검토/재현 후 G4용 최소 거리 판단 제어기와 기동/arm 전이를 단계적으로 구현하는 것이다. 이번 G3의 준비 후 arm은 전체 SUT 기동 상태 기계의 검증이 아니다. 서버 종료 crash는 세 번째 관측이며 장시간 무인 시험 전 별도 점검한다. 새 의존성, 수치 변경이나 G4/본시험 추가 실행은 하지 않았다.

중단 후 재개할 때는 Git status, vcan0 UP 여부와 포트 2000/2001을 다시 확인한다. 실행은 `.venv/bin/python -I` 및 기존 진입점을 사용한다. 사용자 요청으로 G3 완료 commit `4815250`까지 GitHub main에 push했고 직접 원격 SHA도 확인했다. 게시 결과와 이 재개 안내는 별도 문서 커밋으로 공유한다. 사용자는 G4를 다음날 이어가기로 했으며 이번에는 시작하지 않는다. 현재 Git 상태는 `git log`와 `git status`로 확인한다.

## What the previous conversation established

The user wants to learn CAN and demonstrate vehicle SW validation ability through a bachelor's thesis. They prefer verification and evaluation to developing another autonomous-driving algorithm.

The project should be small, reproducible and grounded in actual implementations. The user's central concern is avoiding a detailed plan whose simulator/communication integration cannot actually be reproduced.

The Windows-side investigation confirmed public CARLA/vCAN bridge source code and component tests. It did not run them on this laptop. Environment verification must precede a full thesis implementation.

On 2026-10-16 the user asked to finalize implementation documents without changing the submitted proposal. Read RESEARCH_BASELINE.md, VALIDATION_PLAN.md and THESIS_OUTLINE.md as v1.0. Their design values are fixed for implementation, not proven runtime performance. Do not introduce new tests, automatic restart or actual sensor modeling without a versioned decision.

On 2026-10-19 the original Linux checkout was fast-forwarded to published v1.0. G0 inspection, Python/host setup and actual independent vCAN G1 are complete. The detected user CARLA 0.9.14 client was removed with authorization. Matching CARLA 0.9.15 client/server are installed and standalone G2 passed in run03 and final-source run04; failed run01/run02 remain preserved. Use Python -I to exclude inherited external Python paths. See [SETUP_AND_SMOKE](SETUP_AND_SMOKE_2026-10-19.md). G3 is next. Both server processes crashed on Ctrl+C after G2 cleanup; normal server shutdown remains unverified and no server is left running.

2026-10-31 당시: [G3_PROGRESS](G3_PROGRESS.md)의 첫 단계 요청 송수신 도구 및 새 단위 검사 23개를 구현했다. 초기 장치 부재 ENV_ERROR는 보존했고, 사용자가 준비한 뒤 vcan0 UP과 `bash tools/run_self_checks.sh g3-can`의 실제 10프레임 송수신 PASS를 확인했다. 당시에는 전체 G3, G4와 본시험이 미실행이었다. 이후 G3 완료는 위 최신 인수인계를 따른다.

과거 마감 기록: [CHECKPOINT_2026-10-31](CHECKPOINT_2026-10-31.md). 10월 31일 단계의 증거 읽기 순서와 당시 다음 단계 완료 기준이다.

전체 중간점검은 [MIDTERM_REVIEW_2026-10-31](MIDTERM_REVIEW_2026-10-31.md)에서 확인한다. 설치 및 부분 연결 검증의 완료와 핵심 SUT/본시험/집필의 남은 범위를 구분한다.

후속 구현: [G3_ADAPTER_STEP](G3_ADAPTER_STEP.md)의 adapter 핵심과 새 단위 검사 18개를 추가했고 이후 실제 통합까지 완료했다. Codex가 구현하고 Juwon님이 검토 및 직접 재현하기로 선택했다. 사용자 예제 출력이 기대와 일치했고, 당시 전체 검사 80개 OK 및 의존성 검사 통과 출력도 확인했다. 소스 검토 완료와 실제 통합 실행은 별도로 확인한다.

## Start here on Ubuntu

Clone this repository into a dedicated Linux project directory, not inside the company's DMS repository. For a public repository:

```bash
git clone https://github.com/777juwon/can-stop-request-validation.git
cd can-stop-request-validation
codex
```

If Codex is not installed, use current official Codex installation guidance. Do not assume the Windows Codex installation is shared with a dual-boot Ubuntu installation.

A Windows chat ID alone is not the handoff mechanism for this repository. The official CLI supports resuming saved sessions, but the new worker should not assume the other operating system's session data is available. Use these files even if conversation continuation is available.

## First message to Linux Codex

> AGENTS.md, README.md, docs/STATUS.md, docs/LINUX_HANDOFF.md, docs/G4_MINIMUM_CHAIN.md와 기준선/검증 명세/소스 조사를 읽고 상태를 요약해줘. 제출한 계획서와 v1.0 수치는 유지해. G4는 A의 T-03 최소 연결 PASS, 전체 검사 208개가 통과했어. 첫 관측 누락 FAIL도 보존돼 있어. 사용자 검토와 직접 재현 완료 여부는 별도로 확인해. 다음 구현은 B의 순번 감시와 전체 A/B 시험 체계야. 서버 종료 Signal 11/139 네 건은 미해결이며, 예비 8개 조합과 본시험 80회는 아직 미실행이야. 새 코드 설명과 직접 실행 명령은 한글로 남겨줘.

## G0: Read-only environment inspection

Inspect available commands first. Do not treat missing commands as installed.

The initial inspection was completed on 2026-10-19 and its actual commands/results are in the G0 record. The following are generic recheck examples, not a claim that every command below was executed verbatim:

```bash
uname -a
cat /etc/os-release
python3 --version
git --version
free -h
df -h .
command -v nvidia-smi
command -v vulkaninfo
command -v candump
command -v modinfo
ip -details link show
```

If available, run nvidia-smi and inspect the GPU/driver. modinfo vcan can check module metadata, but it does not prove an interface or transport works.

Record CPU/RAM, GPU/VRAM, free disk, Ubuntu version, kernel, Python, existing virtual environments, CARLA installation state, can-utils and vCAN state.

Prior Windows evidence identified an RTX 4060 Laptop GPU with about 8 GB VRAM. This is not evidence that the Ubuntu driver works or that a chosen CARLA scenario meets a timing requirement.

## G1: Independent vCAN transport

사용자 직접 재실행 절차는 [SELF_CHECK.md](SELF_CHECK.md)와 tools/run_self_checks.sh에 정리한다. 새로 작성하거나 수정하는 코드의 설명, 주석과 docstring은 한글로 작성하고 과거 실행 증거는 보존한다.

After inspecting the system and explaining needed system changes:

- Use Linux SocketCAN, not python-can's in-memory VirtualBus as a substitute for this gate.
- Prepare vcan0 only if absent. Do not delete or replace an existing interface blindly.
- Run a sender and a separate receiver.
- Verify known CAN ID, DLC and payload bytes.
- Check periodic transmission and intentional stopping of the target message.
- Record commands and output.

This gate proves virtual frame transport. It does not prove ECU firmware, physical ACK, stop decision or vehicle motion.

## G2: CARLA standalone

- Start with the official CARLA 0.9.15 packaged server as the first reproduction candidate.
- Use a matching Python client in an isolated environment.
- Use the Python 3.10.12 project venv selected by G0; imports and exact 0.9.15 client/server compatibility have passed locally.
- Do not downgrade the Ubuntu system Python.
- Do not download CARLA from a mirror blindly or execute an upstream all-in-one installer without reading it.
- Avoid building the engine from source initially.
- Spawn one ego vehicle, apply a simple control, query actual velocity and verify changes.
- No full road navigation, cameras, ROS2 or Autoware are required for this gate.

Record server/client versions, launch parameters, GPU used, command output and actual vehicle-state evidence.

Local findings to preserve: the 0.9.15 client can omit a repeated VehicleControl after Ackermann because its cached earlier control is identical. Disabling sticky_control also affects server AI and prevented movement in run02. The working G2 uses sticky_control=true and client.apply_batch_sync with ApplyVehicleControl and do_tick_cue=False, checks the response and actor ID, then advances world.tick once. Keep observed applied controls and velocity as the motion evidence. Fixed-step windows use frame counts at their float32 time boundary. Ctrl+C caused a shutdown crash twice; do not describe it as normal cleanup.

## G3: vCAN to vehicle control

Use the public bridge as a source reference, not an unexplained full-stack dependency.

A separate sender transmits a known control message; the adapter receives and decodes it, then applies control to the selected CARLA vehicle. Verify the vehicle actor identity and actual speed change.

Ensure only one process owns vehicle actuation. Keyboard/manual/autopilot control must not overwrite the command during the test.

The existing Yes, CARLA CAN startup includes extra interfaces and cybersecurity support. We only need the transport and actuation path. Do not enable unrelated attack or IDS components.

## G4: Minimum stop-request chain

Before implementing the full matrix:

- Implement the minimum v1.0 distance-message and stop-request contract from RESEARCH_BASELINE.md.
- Establish periodic normal input and verify the negative control.
- Interrupt only the target distance message.
- Observe SUT decision, CAN request reception, sink application and actual vehicle state separately.
- Record independent evidence.
- Follow the v1.0 research-only timing limits. Do not represent them as production safety requirements or silently relax them after seeing results.

This is an integration feasibility test against the fixed design. It is not execution of the eighty main comparison runs.

## Timing and rendering cautions

CARLA simulation time and host monotonic time are different clocks. v1.0 uses host monotonic time for message and request timing and CARLA simulation time for the vehicle-stop window. A fixed simulation step does not align wall-clock deadlines automatically. Log both clocks with frame IDs and retain scheduling overruns.

Only one process should drive synchronous world ticks. Detect/record simulator stalls so normal slowdown is not mislabeled as an intended message fault.

The inspected Yes, CARLA CAN client uses no-rendering mode. Empty camera output may therefore be expected. Do not add a camera dependency just for the stop-request experiment. If visualization is required, verify rendering settings and resource demand.

## Reporting back to the Windows discussion

After each work session:

1. Update docs/STATUS.md.
2. Append docs/WORKLOG.md.
3. Save small, relevant evidence without secrets or personal data.
4. Commit the scoped changes.
5. Push when authorized in the Linux session.

The user can then return to the Windows discussion with the repository link, commit and issue to review. Neither Codex session should assume it has silently received the other's newest local files.

## Official Codex references

- [Codex CLI](https://learn.chatgpt.com/docs/codex/cli)
- [Developer commands, including codex resume](https://learn.chatgpt.com/docs/developer-commands?surface=cli)

The documentation establishes saved-session continuation. It does not by itself establish that this Windows conversation is automatically available in a separate Ubuntu CLI.
