# Project status

Updated: 2026-11-01 (한국 시각)

## Current state

사용자 직접 재현 확인: g4-20261101T090038689401166Z-95119의 result.json/metadata.json을 읽어 G4 A/T-03 전체 PASS와 client/server 0.9.15, 실제 차량 상태 및 자원 복구를 확인했다. 사용자가 제공한 종료 후 포트 조회에는 LISTEN 항목이 없다. 화면이 없는 것은 launcher의 -RenderOffScreen 설정이다. 사용자 코드 검토 완료와 서버 정상 종료코드까지 확인한 것으로 확대하지 않는다.

**DESIGN_BASELINED / G0_G1_G2_G3_G4_MINIMUM_PASSED / AB_CORE_UNIT_TESTED / PRELIMINARY_NOT_RUN**

후속 구현: B 순번 감시, 자체DBC와4개 시나리오×A/B 메시지 예비 도구를 준비했다. 전체238개 검사와 의존성/셸 문법/공백 통과. 실제CAN/CARLA는 추가 실행하지 않았다. 다음은 사용자가 `bash tools/run_self_checks.sh preliminary`로8개 조합을 실행하고 경로를 전달하는 단계다. [순서와 명령](REMAINING_STEPS.md), [검사 근거](../evidence/implementation/preliminary-20261101-01/checks.json). CARLA 본시험 실행기/80개ID는 다음 단계이며 본시험0/80회다.

최신 G4: A 방식의 T-03 거리 중단 한 번이 실제 PASS했다. 기동 억제, 정상 입력 5개 뒤 명시적 arm, 준비 중 연속 입력과 실제 차속, 20초 본 구간의 거리만 중단/복원, 정지 잠금을 연결했다. B 방식과 A/B 전체 요구사항 검증, 예비 8개 조합 및 본시험 80회는 남아 있다. [코드와 직접 실행](G4_MINIMUM_CHAIN.md), [G4 판정](../evidence/manual/g4-20261101T084459538960446Z-57997/result.json).

최초 실행은 관측기 bind 전 INIT 요청 1개가 누락돼 FAIL이었다. 관측기 ready를 먼저 확인하도록 수정하고 회귀 검사를 추가했다. 첫 FAIL과 당시 소스를 보존하고 새 실행에서 PASS를 확인했다. 전체 단위 검사 208개 통과. 마지막 신규 거리 송신 완료 뒤 200.191233 ms에 정지 요청이 관측됐고 제동 적용 후 명목 0.55초에 정지 유지 조건을 완료했다. 차량 표본 653개다. 이 한 번의 최소 연결을 본시험 결과로 집계하지 않는다.

직전 G3 단계: 전체 G3 첫 실제 실행 PASS. 독립 송신기/관측기/adapter가 원시 요청 20개를 대조했고, CARLA 제동 적용과 실제 차속, 정상 요청 복원 뒤 제동 유지까지 확인했다. Codex가 구현 및 실행했다. Juwon님의 통합 코드 검토와 직접 재현은 아직 기록이 없다. [결과와 직접 실행](G3_INTEGRATION.md), [최종 판정](../evidence/manual/g3-20261031T151442436312880Z-11071/result.json).

제동 콜백 15회, 수신부터 호출 완료까지 최대 0.429085 ms. 최초 적용 frame 8685 이후 명목 0.55초에 정지 유지 조건을 완료했다. 차량 표본 206개와 원시 CAN을 별도 재계산했고 소스 SHA도 대조했다. 이번 한 번의 연결 시험 수치이며 전체 요구사항 검증이나 본시험 통계가 아니다. 실행 폴더는 UTC 2026-10-31, 문서 날짜는 한국 시각이다.

사용자 재현: 예제 출력의 잠금/콜백 2회 일치에 이어, 사용자가 check로 실행한 80개 OK 및 의존성 검사 통과 출력을 확인했다. 초기 인자 없는 도움말 출력과 구분해 기록한다. [예제 검토](../evidence/g3/adapter-core-20261031-01/user_demo_review.json), [전체 검사 재실행](../evidence/g3/adapter-core-20261031-01/user_check_review.json).

기록 마감: [2026-10-31 체크포인트](CHECKPOINT_2026-10-31.md)에 증거 읽기 순서, 재실행 명령과 다음 adapter 작업의 완료 기준을 정리했다. 이 기록 정리에서는 새 실험이나 구현을 추가하지 않았다.

중간점검: [MIDTERM_REVIEW_2026-10-31](MIDTERM_REVIEW_2026-10-31.md)에 완료한 일, 남은 여섯 작업 묶음과 Git 저장 상태를 정리했다.

The user requested final implementation documents without modifying the already submitted thesis proposal. RESEARCH_BASELINE.md, VALIDATION_PLAN.md and THESIS_OUTLINE.md define v1.0. These documents fix research-only design values and test criteria, not advisor sign-off. G3 and the A-only G4 minimum chain have passed; B and the full comparison framework remain unfinished.

The user authorized publishing this document baseline to GitHub on 2026-10-16. A Linux checkout must fetch this revision before relying on it; a shared repository does not automatically update another local checkout.

On 2026-10-19 this working tree was fast-forwarded to published commit `94411a45aac647a0b9b0c811606d74c8f30d1df2`, preserving prior analysis in a verified backup and reintegrating its worklog entries. The [G0 environment report](G0_ENVIRONMENT_2026-10-19.md) is the initial snapshot before the installations below.

The user authorized setup, removal of the detected CARLA 0.9.14 client and resumption after a usage interruption. Python packages and the official 0.9.15 server are installed. G1 passed with independent SocketCAN processes. G2 first failed on a client control-cache transition, then timed out with a rejected configuration change; both attempts are preserved. The corrected batch-control path passed twice, most recently with the final source in run04. See [setup and smoke results](SETUP_AND_SMOKE_2026-10-19.md).

Server lifecycle limitation: G2 서버 2건, G3와 이번 G4 서버가 각각 차량/설정 복구 후 Ctrl+C에서 Signal 11 / code 139로 종료됐다. 총 4건이며 원인은 미해결이다. 포트 2000/2001과 GPU의 CARLA 프로세스는 남지 않았다. 정상 서버 종료 PASS로 기록하지 않는다. [G2 기록](../evidence/setup/2026-10-19/server_runtime.json), [G3 기록](../evidence/g3/integration-20261101-01/host_and_server.json), [G4 기록](../evidence/g4/2026-11-01/host_and_server.json).

## Completion checklist

| Work item | Status | Evidence |
| --- | --- | --- |
| Study scope and requirements fixed | DONE | RESEARCH_BASELINE.md and R-01~R-09 |
| Test scenarios and pass/fail rules fixed | DONE | VALIDATION_PLAN.md, T-01~T-04 |
| Thesis chapter structure fixed | DONE | THESIS_OUTLINE.md |
| G0 environment inspection and install plan | DONE | G0_ENVIRONMENT_2026-10-19.md and evidence/g0/2026-10-19 |
| Python/host/CARLA package setup | DONE | requirements.lock.txt and evidence/setup/2026-10-19 |
| Minimum transport and standalone simulator | G1/G2 PASS | Separate actual evidence below |
| CAN-to-vehicle and minimum stop chain | G3 PASS / G4 MINIMUM PASS | A/T-03 실제 거리 중단 대응 연결 |
| G1/G2 feasibility tools | IMPLEMENTED / UNIT_TESTED | tools/g1_vcan_smoke.py, tools/g2_carla_smoke.py and tests |
| G3 request transport tool | IMPLEMENTED / UNIT_TESTED / TRANSPORT_PASS | tools/g3_request_smoke.py, 새 단위 검사 23개와 실제 10프레임 송수신 |
| G3 adapter core | IMPLEMENTED / UNIT_TESTED / CONNECTED | tools/g3_adapter_core.py와 핵심 검사 18개. G3 실행기에서 실제 제동 연결 |
| G3 integration runner and oracle | IMPLEMENTED / LOCALLY_VERIFIED | tools/g3_carla_smoke.py, g3_integration_can.py, g3_integration_oracle.py와 실제 20프레임/차량 관측 |
| SUT implementation and unit tests | AB_CORE_UNIT_TESTED | A/B 핵심과 DBC 구현 및 단위 검사. B 실제 실행과 전체 CARLA 시험 체계는 남음 |
| Thesis preliminary test execution and result summary | NOT_RUN | G1~G4 연결 확인만 실행. 예비 8개 조합 미실행 |
| Main comparison runs and result analysis | NOT_RUN | No experimental results |

Writing a scenario, checklist or expected result does not complete an experiment. G1/G2 feasibility runs do not count as thesis preliminary or main trials.

## Evidence levels

| Item | Evidence | What is not proved |
| --- | --- | --- |
| Ubuntu and base tools | Local Ubuntu 22.04.5, kernel 6.8.0-138, Python 3.10.12 and Git 2.34.1 inspected | vCAN transport or CARLA execution |
| Laptop GPU | RTX 4060 Laptop, driver 570.211.01, 8188 MiB; Vulkan enumeration and CARLA process observed on NVIDIA GPU | Main-trial performance or normal server shutdown |
| vCAN transport | 2026-10-19 G1에서 60프레임 확인. 2026-10-31 vcan0 UP 재확인 및 StopRequest 10프레임 확인 | SUT decision or vehicle control |
| Python/CARLA environment | Isolated CPython 3.10.12; carla 0.9.15, python-can 4.6.1, cantools 40.7.1; pip check and matching server connection passed; old 0.9.14 client removed | 본시험 반복 성능 |
| Standalone vehicle | G2 run04 actual velocity, applied brake, continuous frames, hold window and post-cleanup state checked | R-01~R-09 compliance, repeated main-trial performance |
| CARLA / vCAN adapter | G3 및 G4 A의 실제 호출/제동/차속과 잠금 유지 PASS | B와 전체 본시험 요구사항 |
| Watchdog / sequence logic | A 수신 만료 및 기동/arm을 G4에서 확인 | B 순번 감시와 전체 입력 조합 검증 |
| Fault injection / logging | Existing component code inspected | Our full scenario runner and oracle |
| Current repository | v1.0 기준선 이후 설치/도구/증거를 중간점검 스냅샷으로 관리. 해시는 git log로 확인 | 원격 반영은 push 및 원격 ref로 별도 확인 |

## Feasibility gates

G0 inspection, G1 transport, G2 standalone motion, G3 CAN-to-vehicle and G4 minimum A chain have separate evidence. G4 does not complete the thesis trials. Server shutdown crashes are tracked separately from actor/settings cleanup.

| Gate | Description | Status | Evidence |
| --- | --- | --- | --- |
| G0 | Inspect Ubuntu, GPU, disk, Python and git | PASS | [Report](G0_ENVIRONMENT_2026-10-19.md), evidence/g0/2026-10-19 |
| G1 | Independent vCAN publisher and receiver exchange known frames | PASS | [Actual transport verdict](../evidence/g1/g1-20261019-01/verdict.json) |
| G2 | CARLA standalone vehicle control and actual velocity query | PASS | [Final run04](../evidence/g2/g2-20261019-04/result.json), [raw-state audit](../evidence/g2/g2-20261019-04/observation_audit.json), [post-cleanup](../evidence/g2/g2-20261019-04/post_cleanup.json); earlier failures retained |
| G3 | vCAN control reception changes CARLA vehicle state | PASS | [실제 연결](../evidence/manual/g3-20261031T151442436312880Z-11071/result.json), [원시 자료 재계산](../evidence/manual/g3-20261031T151442436312880Z-11071/observation_audit.json). 사용자 직접 재현 대기 |
| G4 | Distance-message interruption causes defined stop request and sink application | MINIMUM PASS | [A/T-03 실측](../evidence/manual/g4-20261101T084459538960446Z-57997/result.json), [독립 재계산](../evidence/manual/g4-20261101T084459538960446Z-57997/observation_audit.json). 첫 FAIL 보존 |

Passing G4 is a minimum proof of the chain, not completion of all thesis experiments.

## Fixed study decisions in v1.0

- Scripted distance input, not physical or CARLA sensor measurements.
- Classic CAN IDs 0x100, 0x101 and 0x200 with an explicit eight-byte contract.
- 50 ms input period, 10 ms polling, 200 ms timeout, 200 cm threshold.
- A receive-timeout monitor versus B receive-timeout plus sequence-progress monitor.
- Four main scenarios, ten original attempts per scenario and variant: eighty planned runs.
- Latched stop, no automatic restart; request, adapter and motion verdicts are separated.
- Host monotonic message timing; CARLA simulation-time motion window.
- A 거리 중단의 요청 관측 지연은 G4에서 한 번 확인했다. 모든 SUT 요구사항이나 반복 성능을 확인한 것은 아니다. 본시험 실행: 0/80.

## Remaining execution records and approvals

- Advisor feedback, without inventing individual parameter approval
- Resolve or bound the repeatable CARLA shutdown crash before long unattended experiments; do not reinstall drivers or change versions without evidence
- Actual map/spawn and vehicle-physics records before main testing
- 사용자 코드 검토 및 직접 재현, B 순번 감시와 전체 시험 체계, 이후 예비/본시험
- Project license for original future code

## Next task

작업 방식 변경: 사용량 절약을 위해 앞으로 실제 서버와 CAN/CARLA 시험은 사용자가 터미널에서 실행한다. 에이전트는 코드/명령 준비와 출력 폴더의 필요한 결과만 검토하며 기본은 단일 에이전트다. 사용자가 알린 5시간 잔여 20% 이하에서는 추가 작업을 중단한다. 현재 공유된 47%는 한 번의 화면 확인 값이며 자동 감시는 불가능하다. [직접 실행과 바톤터치](G4_MINIMUM_CHAIN.md).

사용자 직접 실행 안내: [SELF_CHECK.md](SELF_CHECK.md), [G4_MINIMUM_CHAIN.md](G4_MINIMUM_CHAIN.md), 진입점 `bash tools/run_self_checks.sh`. 실제 G4 진입점은 PASS했고 사용자 직접 재현은 대기 중이다. 전체 단위 검사 208개와 의존성/셸 문법/공백 검사가 통과했다. 사용자 과거 검사 80개, G3 때의 119개, 이번 208개는 별도 기록한다. [수정 후 검사](../evidence/g4/2026-11-01/after_startup_fix_checks.json). 새 코드 설명과 주석은 한글로 작성한다.

Git 공유: 사용자 요청으로 G3 완료 commit `4815250`까지 로컬 커밋 3개를 `git push origin main`으로 게시했다. 직접 원격 조회에서도 main SHA `4815250f531bcabcb7dce1d676b4ab5a838a038d`가 일치했다. 이 게시 결과와 재개 안내는 별도 문서 커밋으로 함께 공유한다. 사용자는 G4를 다음날 이어가기로 했으며 이번 작업에서는 시작하지 않는다.

그 뒤 인수인계 commit bcfa487도 게시됐고, 이번 G4 작업은 해당 main에서 변경 없이 시작했다. G4는 별도 로컬 커밋으로 저장하며 추가 push 요청은 아직 없다. 위 G3 게시 기록의 다음날 재개 계획에 따라 이번에 G4를 실행했다.

다음은 사용자 코드 검사와 메시지 예비시험8개다. 결과 검토 뒤 CARLA 본시험 실행기/고정 설정/80개 원래ID를 준비한다. 잘못된 StopRequest의 본시험 차량 대응은 미정이며 필요한 결정을 이유와 함께 제시한다. B 단위 검사를 실제 B 실행이나 본시험 완료로 확대하지 않는다. sticky_control=true와 batch 제동을 유지하고 서버 종료 문제는 장시간 무인 시험 전에 별도 점검한다.

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
