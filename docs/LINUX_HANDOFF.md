# Linux Codex handoff

## What the previous conversation established

The user wants to learn CAN and demonstrate vehicle SW validation ability through a bachelor's thesis. They prefer verification and evaluation to developing another autonomous-driving algorithm.

The project should be small, reproducible and grounded in actual implementations. The user's central concern is avoiding a detailed plan whose simulator/communication integration cannot actually be reproduced.

The Windows-side investigation confirmed public CARLA/vCAN bridge source code and component tests. It did not run them on this laptop. Environment verification must precede a full thesis implementation.

On 2026-10-16 the user asked to finalize implementation documents without changing the submitted proposal. Read RESEARCH_BASELINE.md, VALIDATION_PLAN.md and THESIS_OUTLINE.md as v1.0. Their design values are fixed for implementation, not proven runtime performance. Do not introduce new tests, automatic restart or actual sensor modeling without a versioned decision.

On 2026-10-19 the original Linux checkout was fast-forwarded to published v1.0. G0 inspection, Python/host setup and actual independent vCAN G1 are complete. The detected user CARLA 0.9.14 client was removed with authorization. Matching CARLA 0.9.15 client/server are installed and standalone G2 passed in run03 and final-source run04; failed run01/run02 remain preserved. Use Python -I to exclude inherited external Python paths. See [SETUP_AND_SMOKE](SETUP_AND_SMOKE_2026-10-19.md). G3 is next. Both server processes crashed on Ctrl+C after G2 cleanup; normal server shutdown remains unverified and no server is left running.

2026-10-31 추가: [G3_PROGRESS](G3_PROGRESS.md)의 첫 단계 요청 송수신 도구 및 새 단위 검사 23개를 구현했다. 초기 장치 부재 ENV_ERROR는 보존했고, 사용자가 준비한 뒤 vcan0 UP과 `bash tools/run_self_checks.sh g3-can`의 실제 10프레임 송수신 PASS를 확인했다. 다음은 CARLA adapter 구현과 연결이다. 전체 G3, G4와 본시험은 미실행이다.

최신 마감 기록: [CHECKPOINT_2026-10-31](CHECKPOINT_2026-10-31.md). 증거 읽기 순서와 다음 단계 완료 기준을 확인한 뒤 구현을 이어간다.

전체 중간점검은 [MIDTERM_REVIEW_2026-10-31](MIDTERM_REVIEW_2026-10-31.md)에서 확인한다. 설치 및 부분 연결 검증의 완료와 핵심 SUT/본시험/집필의 남은 범위를 구분한다.

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

> AGENTS.md, README.md, docs/STATUS.md, docs/LINUX_HANDOFF.md, docs/G3_PROGRESS.md, docs/SETUP_AND_SMOKE_2026-10-19.md, docs/RESEARCH_BASELINE.md, docs/VALIDATION_PLAN.md, docs/SOURCE_AUDIT.md를 읽고 현재 상태를 요약해줘. 제출한 계획서는 수정하지 않고 v1.0 기준으로 진행해. G0/G1/G2는 과거 실행 증거가 있고, 2026-10-31 사용자 장치 준비 후 G3의 실제 요청 송수신 부분도 PASS했어. 다음은 CARLA adapter 구현과 단위 검사, 이후 실제 차량 연결이야. 현재 vcan0 상태는 다시 조회해줘. Python은 -I로 실행하고, 새 코드 설명은 한글로 작성해. 단계별 명령과 결과를 STATUS와 WORKLOG에 기록해줘.

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
