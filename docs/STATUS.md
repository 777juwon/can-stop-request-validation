# Project status

Updated: 2026-10-31

## Current state

**DESIGN_BASELINED / G0_G1_G2_PASSED / SUT_NOT_STARTED**

2026-10-31 현재: 실제 StopRequest 10프레임 송수신 PASS에 이어 adapter 핵심과 새 단위 검사 18개를 구현했다. 가짜 콜백 예제도 실행했다. 실제 CAN/CARLA 통합과 차량 적용은 아직 없으며 전체 G3는 여전히 NOT_RUN이다. 사용자 선택에 따라 Codex가 구현하고 Juwon님이 검토 및 직접 재현하는 방식으로 진행한다. [단계별 진행](G3_PROGRESS.md), [코드와 직접 실행 안내](G3_ADAPTER_STEP.md).

사용자 재현: Juwon님이 제공한 예제 출력에서 정지 잠금과 가짜 콜백 2회가 기대와 일치했다. 인자 없는 검사 스크립트는 도움말만 표시했으므로 사용자 전체 단위 검사 완료로 기록하지 않는다. [출력 검토](../evidence/g3/adapter-core-20261031-01/user_demo_review.json).

기록 마감: [2026-10-31 체크포인트](CHECKPOINT_2026-10-31.md)에 증거 읽기 순서, 재실행 명령과 다음 adapter 작업의 완료 기준을 정리했다. 이 기록 정리에서는 새 실험이나 구현을 추가하지 않았다.

중간점검: [MIDTERM_REVIEW_2026-10-31](MIDTERM_REVIEW_2026-10-31.md)에 완료한 일, 남은 여섯 작업 묶음과 Git 저장 상태를 정리했다.

The user requested final implementation documents without modifying the already submitted thesis proposal. RESEARCH_BASELINE.md, VALIDATION_PLAN.md and THESIS_OUTLINE.md define v1.0. These documents fix research-only design values and test criteria, not advisor sign-off. Feasibility tools and standalone runs exist; the thesis SUT and CAN-to-CARLA integration are not implemented.

The user authorized publishing this document baseline to GitHub on 2026-10-16. A Linux checkout must fetch this revision before relying on it; a shared repository does not automatically update another local checkout.

On 2026-10-19 this working tree was fast-forwarded to published commit `94411a45aac647a0b9b0c811606d74c8f30d1df2`, preserving prior analysis in a verified backup and reintegrating its worklog entries. The [G0 environment report](G0_ENVIRONMENT_2026-10-19.md) is the initial snapshot before the installations below.

The user authorized setup, removal of the detected CARLA 0.9.14 client and resumption after a usage interruption. Python packages and the official 0.9.15 server are installed. G1 passed with independent SocketCAN processes. G2 first failed on a client control-cache transition, then timed out with a rejected configuration change; both attempts are preserved. The corrected batch-control path passed twice, most recently with the final source in run04. See [setup and smoke results](SETUP_AND_SMOKE_2026-10-19.md).

Server lifecycle limitation: both dedicated servers exited with Signal 11 / code 139 on Ctrl+C after successful actor/settings cleanup. Ports 2000/2001 are closed. This is not a normal-shutdown PASS and its cause remains unresolved. [Runtime evidence](../evidence/setup/2026-10-19/server_runtime.json).

## Completion checklist

| Work item | Status | Evidence |
| --- | --- | --- |
| Study scope and requirements fixed | DONE | RESEARCH_BASELINE.md and R-01~R-09 |
| Test scenarios and pass/fail rules fixed | DONE | VALIDATION_PLAN.md, T-01~T-04 |
| Thesis chapter structure fixed | DONE | THESIS_OUTLINE.md |
| G0 environment inspection and install plan | DONE | G0_ENVIRONMENT_2026-10-19.md and evidence/g0/2026-10-19 |
| Python/host/CARLA package setup | DONE | requirements.lock.txt and evidence/setup/2026-10-19 |
| Minimum transport and standalone simulator | G1/G2 PASS | Separate actual evidence below |
| CAN-to-vehicle and minimum stop chain | G3/G4 NOT_RUN | No integration implementation |
| G1/G2 feasibility tools | IMPLEMENTED / UNIT_TESTED | tools/g1_vcan_smoke.py, tools/g2_carla_smoke.py and tests |
| G3 request transport tool | IMPLEMENTED / UNIT_TESTED / TRANSPORT_PASS | tools/g3_request_smoke.py, 새 단위 검사 23개와 실제 10프레임 송수신 |
| G3 adapter core | IMPLEMENTED / UNIT_TESTED | tools/g3_adapter_core.py와 새 단위 검사 18개. 실제 CAN/CARLA 연결 미실행 |
| SUT implementation and unit tests | NOT_STARTED | A/B 제어기 미구현. adapter는 핵심 콜백 경로만 구현 |
| Thesis preliminary test execution and result summary | NOT_RUN | Only G1/G2 feasibility runs exist |
| Main comparison runs and result analysis | NOT_RUN | No experimental results |

Writing a scenario, checklist or expected result does not complete an experiment. G1/G2 feasibility runs do not count as thesis preliminary or main trials.

## Evidence levels

| Item | Evidence | What is not proved |
| --- | --- | --- |
| Ubuntu and base tools | Local Ubuntu 22.04.5, kernel 6.8.0-138, Python 3.10.12 and Git 2.34.1 inspected | vCAN transport or CARLA execution |
| Laptop GPU | RTX 4060 Laptop, driver 570.211.01, 8188 MiB; Vulkan enumeration and CARLA process observed on NVIDIA GPU | Main-trial performance or normal server shutdown |
| vCAN transport | 2026-10-19 G1에서 60프레임 확인. 2026-10-31 vcan0 UP 재확인 및 StopRequest 10프레임 확인 | SUT decision or vehicle control |
| Python/CARLA environment | Isolated CPython 3.10.12; carla 0.9.15, python-can 4.6.1, cantools 40.7.1; pip check and matching server connection passed; old 0.9.14 client removed | CAN-to-vehicle integration |
| Standalone vehicle | G2 run04 actual velocity, applied brake, continuous frames, hold window and post-cleanup state checked | R-01~R-09 compliance, repeated main-trial performance |
| CARLA / vCAN bridge | Public source code inspected | Local end-to-end execution |
| Watchdog / sequence logic | Public source and tests inspected | Our distance-message controller |
| Fault injection / logging | Existing component code inspected | Our full scenario runner and oracle |
| Current repository | v1.0 기준선 이후 설치/도구/증거를 중간점검 스냅샷으로 관리. 해시는 git log로 확인 | 원격 반영은 push 및 원격 ref로 별도 확인 |

## Feasibility gates

G0 inspection, G1 transport and G2 standalone motion have separate evidence. G3/G4 remain NOT_RUN. Server shutdown crashes are tracked separately from G2 actor/settings cleanup.

| Gate | Description | Status | Evidence |
| --- | --- | --- | --- |
| G0 | Inspect Ubuntu, GPU, disk, Python and git | PASS | [Report](G0_ENVIRONMENT_2026-10-19.md), evidence/g0/2026-10-19 |
| G1 | Independent vCAN publisher and receiver exchange known frames | PASS | [Actual transport verdict](../evidence/g1/g1-20261019-01/verdict.json) |
| G2 | CARLA standalone vehicle control and actual velocity query | PASS | [Final run04](../evidence/g2/g2-20261019-04/result.json), [raw-state audit](../evidence/g2/g2-20261019-04/observation_audit.json), [post-cleanup](../evidence/g2/g2-20261019-04/post_cleanup.json); earlier failures retained |
| G3 | vCAN control reception changes CARLA vehicle state | NOT_RUN | [요청 전달 부분 PASS](../evidence/manual/g3-can-20261031T104807355660618Z-2/verdict.json). CARLA 제어와 차량 적용은 아직 없음 |
| G4 | Distance-message interruption causes defined stop request and sink application | NOT_RUN | None |

Passing G4 is a minimum proof of the chain, not completion of all thesis experiments.

## Fixed study decisions in v1.0

- Scripted distance input, not physical or CARLA sensor measurements.
- Classic CAN IDs 0x100, 0x101 and 0x200 with an explicit eight-byte contract.
- 50 ms input period, 10 ms polling, 200 ms timeout, 200 cm threshold.
- A receive-timeout monitor versus B receive-timeout plus sequence-progress monitor.
- Four main scenarios, ten original attempts per scenario and variant: eighty planned runs.
- Latched stop, no automatic restart; request, adapter and motion verdicts are separated.
- Host monotonic message timing; CARLA simulation-time motion window.
- No SUT response-time or CAN-triggered vehicle-motion results exist. G2 measured standalone CARLA motion only. Main comparison runs executed: 0/80.

## Remaining execution records and approvals

- Advisor feedback, without inventing individual parameter approval
- Resolve or bound the repeatable CARLA shutdown crash before long unattended experiments; do not reinstall drivers or change versions without evidence
- Actual map/spawn and vehicle-physics records before main testing
- G3/G4 implementation and independent evidence, then thesis preliminary and main trials
- Project license for original future code

## Next task

사용자 직접 실행 안내: [SELF_CHECK.md](SELF_CHECK.md), 진입점 `bash tools/run_self_checks.sh`. 현재 전체 단위 검사 80개가 통과했다. 실제 G1 진입점 PASS는 2026-10-19 기록이다. G2 진입점은 도움말 및 필수 인자 검사까지만 확인했다. G3 진입점은 실제 요청 송수신이 PASS했고, 새 adapter는 가짜 콜백 예제까지만 실행했다. 새 코드 설명과 주석은 한글로 작성한다. Git 저장 및 원격 반영 상태는 중간점검 보고서의 명령으로 확인한다.

다음은 실제 CAN 수신 루프, adapter core와 G2 제동 함수를 단일 실행기에 연결하는 단계다. 기동 준비와 arm 경계를 명시하고 수신, 제어 호출, 최초 적용 frame과 실제 차속을 분리 기록한다. 잘못된 요청의 차량 대응은 미정이며 필요한 결정을 이유와 함께 제시한다. 전체 SUT나 80회 시험을 한 번에 구현하지 않는다. sticky_control=true 및 batch 제동 경로를 유지하고, 서버 종료 문제는 장시간 무인 시험 전에 별도로 점검한다.

Read [G0_ENVIRONMENT_2026-10-19.md](G0_ENVIRONMENT_2026-10-19.md) for observed versions, planned commands and execution limits. Earlier analysis is retained in [THESIS_REVIEW](THESIS_REVIEW.md) and [REVISION_REVIEW](REVISION_REVIEW_2026-10-19.md), with original pre-sync snapshots under evidence/g0/2026-10-19/pre_sync.

## Update format for future work

For every completed task record:

- Date and current Git commit
- What changed
- Exact commands executed
- Exit status and observed output summary
- Evidence file paths
- Remaining failures or assumptions
- Gate status changes
- Next smallest verifiable task

Do not replace NOT_RUN with PASS on the basis of source review alone.
