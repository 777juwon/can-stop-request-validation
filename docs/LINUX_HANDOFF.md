# Linux Codex handoff

## 현재 인수인계: 2026-11-01

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

> AGENTS.md, README.md, docs/STATUS.md, docs/LINUX_HANDOFF.md, docs/G3_INTEGRATION.md와 기준선/검증 명세/소스 조사를 읽고 상태를 요약해줘. 제출한 계획서와 v1.0 수치는 유지해. 실제 G3는 첫 실행 PASS이고 전체 검사 119개가 통과했어. 사용자 검토와 직접 재현 완료 여부는 별도로 확인해. 다음 구현은 G4용 최소 거리 입력 제어기와 기동/arm 전이를 작은 단계로 진행하는 것이야. 서버 종료 Signal 11/139 세 건은 미해결로 유지하고, G4/본시험을 실행한 것으로 표현하지 마. 새 코드 설명과 직접 실행 명령은 한글로 남겨줘.

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
