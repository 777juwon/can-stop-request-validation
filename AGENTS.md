# Project instructions for Codex

## Read before acting

Read README.md, docs/STATUS.md and docs/LINUX_HANDOFF.md before task work.
Read docs/RESEARCH_BASELINE.md, docs/VALIDATION_PLAN.md and docs/SOURCE_AUDIT.md before implementation or experiment design. Read docs/THESIS_OUTLINE.md for thesis writing.
Use the repository files, code and recorded evidence as the durable handoff, not an assumed shared chat ID.

## Purpose and scope

- This is a bachelor's thesis focused on requirements-based vehicle software verification.
- The proposed subject is message-fault responses of a low-speed stop-request function over virtual CAN.
- Programs imitate ECU roles; this is not real ECU firmware, production brake control or a vehicle safety certification.
- The first Linux task is environment inspection and minimum CARLA/vCAN reproduction, not full feature implementation.
- CARLA 0.9.15 is a proposed first reproduction baseline, not an already validated installation.
- Do not add ROS2, full Autoware, RTOS, CAN-FD, cybersecurity attack features or new control algorithms just because references contain them.

## Truthfulness and decisions

- Distinguish planned, implemented, locally executed and verified.
- Do not convert a public code review or mock unit-test into a claim of local CARLA/vCAN integration success.
- Do not fabricate measurements, pass rates, requirements, test counts or advisor approvals.
- The user requested a finalized implementation document on 2026-10-16. docs/RESEARCH_BASELINE.md and docs/VALIDATION_PLAN.md fix the v1.0 design, including research-only values and a latched stop policy. This is not advisor approval, a production safety requirement or runtime evidence.
- Do not silently relax this baseline or add scenarios. If feasibility requires a change, explain the evidence and seek the user's decision before versioning the baseline and rerunning affected tests.
- Do not edit the already submitted thesis proposal or its HWP original.
- Preserve failures and explain their causes. Do not change acceptance criteria after seeing results to force a pass.
- A stable distance value with an advancing counter can be normal. A repeated frame with the same counter can be stale. v1.0 uses scripted distance fixtures, not a physical or CARLA range sensor. Do not claim obstacle avoidance or physical stopping-distance validation.
- Receiving a CAN frame, generating a stop request, delivering it, applying it and slowing the vehicle are separate checks.
- Application response messages are not physical CAN ACK.
- Never claim physical CAN fault coverage or actual ultrasonic-sensor fault diagnosis from vCAN experiments.

## Timing and verification

- Do not subtract host monotonic timestamps from CARLA simulation timestamps.
- Use the v1.0 host monotonic clock for message timing and CARLA simulation time only for motion windows. Log both clocks and the relevant frame IDs.
- Account for host/GPU slowdown so it is not silently classified as injected communication faults.
- The test oracle must use independent observed evidence and requirements, not only the SUT's internal verdict.
- Use CARLA vehicle state directly for vehicle-motion evidence, rather than assuming a sent command was executed.

## Repository safety

- Work only in this project. Do not access or copy company repositories, private DBCs, job application records or personal documents.
- Do not upload tokens, credentials, full chat exports, raw personal data, simulator packages or generated large logs.
- Inspect external installation scripts before running them. Explain substantial downloads and system-level changes.
- Keep external dependencies in separate environments and record exact versions or commits.
- Retain upstream license and copyright notices when reusing code.
- Use apply_patch for local edits where available. Preserve unrelated user edits.
- Never force-push, broadly delete files, reset user changes or reboot without explicit user authorization.

## Working style and handoff

- Communicate in Korean unless the user asks otherwise. Avoid the middle-dot character in user-facing writing.
- 이 프로젝트에서 새로 작성하거나 수정하는 코드의 설명, 주석과 docstring은 한글로 작성한다. 외부 API 이름과 기존 로그의 키는 호환성을 유지하며, 과거 실행 증거와 당시 소스 사본은 번역하지 않는다.
- 검사 기능을 추가할 때 사용자가 터미널에서 직접 재현할 명령, 결과 위치와 판정 방법도 함께 정리한다.
- Explain each decision as problem, evidence, judgment, change and verification.
- Keep scope small and verifiable. Report a failed prerequisite before expanding work.
- After each substantive task, update docs/STATUS.md and append docs/WORKLOG.md.
- Record commands, versions, observed results, evidence paths and the next task.
- Keep unexecuted commands clearly labeled as planned. Do not mark documentation readiness as experiment completion.
- 사용자 사용량 절약 선호: 기본은 단일 에이전트로 코드와 명령을 준비하고, CARLA 서버 및 실제 CAN/차량 시험은 사용자가 터미널에서 실행한다. 사용자가 직접 실행을 다시 위임한 경우에만 에이전트가 실행한다. 사용자는 출력 폴더 경로를 전달하고 에이전트는 필요한 결과와 로그만 읽어 검토한다.
- 계정 5시간 잔여율은 현재 도구에서 자동 조회할 수 없다. 사용자가 /status 등으로 잔여 20% 이하를 알려주면 추가 작업을 중단하고 짧은 인수인계만 남긴다. 확인하지 못한 잔여율이나 자동 중지를 보장했다고 주장하지 않는다.
