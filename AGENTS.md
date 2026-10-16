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
- Explain each decision as problem, evidence, judgment, change and verification.
- Keep scope small and verifiable. Report a failed prerequisite before expanding work.
- After each substantive task, update docs/STATUS.md and append docs/WORKLOG.md.
- Record commands, versions, observed results, evidence paths and the next task.
- Keep unexecuted commands clearly labeled as planned. Do not mark documentation readiness as experiment completion.
