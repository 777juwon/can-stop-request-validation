# Project status

Updated: 2026-11-01 (한국 시각)

## Current state

**DESIGN_BASELINED / G0_G1_G2_G3_PASSED / SUT_NOT_STARTED**

2026-11-01 현재: 전체 G3 첫 실제 실행 PASS. 독립 송신기/관측기/adapter가 원시 요청 20개를 대조했고, CARLA 제동 적용과 실제 차속, 정상 요청 복원 뒤 제동 유지까지 확인했다. Codex가 구현 및 실행했다. Juwon님의 통합 코드 검토와 직접 재현은 아직 기록이 없다. [결과와 직접 실행](G3_INTEGRATION.md), [최종 판정](../evidence/manual/g3-20261031T151442436312880Z-11071/result.json).

제동 콜백 15회, 수신부터 호출 완료까지 최대 0.429085 ms. 최초 적용 frame 8685 이후 명목 0.55초에 정지 유지 조건을 완료했다. 차량 표본 206개와 원시 CAN을 별도 재계산했고 소스 SHA도 대조했다. 이번 한 번의 연결 시험 수치이며 전체 요구사항 검증이나 본시험 통계가 아니다. 실행 폴더는 UTC 2026-10-31, 문서 날짜는 한국 시각이다.

사용자 재현: 예제 출력의 잠금/콜백 2회 일치에 이어, 사용자가 check로 실행한 80개 OK 및 의존성 검사 통과 출력을 확인했다. 초기 인자 없는 도움말 출력과 구분해 기록한다. [예제 검토](../evidence/g3/adapter-core-20261031-01/user_demo_review.json), [전체 검사 재실행](../evidence/g3/adapter-core-20261031-01/user_check_review.json).

기록 마감: [2026-10-31 체크포인트](CHECKPOINT_2026-10-31.md)에 증거 읽기 순서, 재실행 명령과 다음 adapter 작업의 완료 기준을 정리했다. 이 기록 정리에서는 새 실험이나 구현을 추가하지 않았다.

중간점검: [MIDTERM_REVIEW_2026-10-31](MIDTERM_REVIEW_2026-10-31.md)에 완료한 일, 남은 여섯 작업 묶음과 Git 저장 상태를 정리했다.

The user requested final implementation documents without modifying the already submitted thesis proposal. RESEARCH_BASELINE.md and VALIDATION_PLAN.md define the v1.0 research design and test criteria, not advisor sign-off. THESIS_OUTLINE.md was editorially revised on 2026-11-01 to five chapters and ten sections for a 20-page body including tables and figures. The research baseline is unchanged. CAN-to-CARLA G3 has now passed; the thesis distance-message SUT is not implemented.

The user authorized publishing this document baseline to GitHub on 2026-10-16. A Linux checkout must fetch this revision before relying on it; a shared repository does not automatically update another local checkout.

On 2026-10-19 this working tree was fast-forwarded to published commit `94411a45aac647a0b9b0c811606d74c8f30d1df2`, preserving prior analysis in a verified backup and reintegrating its worklog entries. The [G0 environment report](G0_ENVIRONMENT_2026-10-19.md) is the initial snapshot before the installations below.

The user authorized setup, removal of the detected CARLA 0.9.14 client and resumption after a usage interruption. Python packages and the official 0.9.15 server are installed. G1 passed with independent SocketCAN processes. G2 first failed on a client control-cache transition, then timed out with a rejected configuration change; both attempts are preserved. The corrected batch-control path passed twice, most recently with the final source in run04. See [setup and smoke results](SETUP_AND_SMOKE_2026-10-19.md).

Server lifecycle limitation: G2의 서버 2건에 이어 G3 서버도 차량/설정 복구 후 Ctrl+C에서 Signal 11 / code 139로 종료됐다. 총 3건이며 원인은 미해결이다. 포트 2000/2001과 GPU의 CARLA 프로세스는 남지 않았다. 정상 서버 종료 PASS로 기록하지 않는다. [G2 기록](../evidence/setup/2026-10-19/server_runtime.json), [G3 기록](../evidence/g3/integration-20261101-01/host_and_server.json).

## 논문 목차 조정: 2026-11-01

사용자가 20쪽 분량에 맞춰 목차의 중복과 세분화를 줄이도록 요청했다. [THESIS_OUTLINE.md](THESIS_OUTLINE.md)를 기존 6장에서 5장, 10개 절로 개정했다. 본문 목표는 표와 그림을 포함해 2/2/8/7/1쪽이며, 학과의 공식 분량 산정 범위를 확인한 것으로 표현하지 않는다. 기존 설계와 시험 방법은 새 제3장에 합치고 결과는 제4장, 결론은 제5장에 둔다. 연구 설계 v1.0과 제출한 작성계획서는 변경하지 않았다. 이번 문서 변경에서 코드나 실험을 추가하지 않았으며 G4 NOT_RUN과 본시험 0/80회는 그대로다.

## 제1~3장 본문 정리: 2026-11-01

사용자 요청으로 [제1~3장 본문](THESIS_CHAPTERS_1_3.md)을 새 5장 목차에 맞춰 정리했다. 표 5개와 수식 2개로 요구사항, 메시지, G3 구축 환경, 시험 시나리오와 독립 판정을 배치했다. 거리 판단 SUT와 G4/예비/본시험은 설계 및 수행 계획으로 서술하고, 실제 환경은 G3 근거로 구분했다. 외부 기술 근거와 연구용 자체 설계값을 구분했다. 본문 작성이 실험 완료나 실제 HWP 페이지 수 확인을 뜻하지 않는다.

## Completion checklist

| Work item | Status | Evidence |
| --- | --- | --- |
| Study scope and requirements fixed | DONE | RESEARCH_BASELINE.md and R-01~R-09 |
| Test scenarios and pass/fail rules fixed | DONE | VALIDATION_PLAN.md, T-01~T-04 |
| Thesis chapter structure fixed | DONE | THESIS_OUTLINE.md |
| G0 environment inspection and install plan | DONE | G0_ENVIRONMENT_2026-10-19.md and evidence/g0/2026-10-19 |
| Python/host/CARLA package setup | DONE | requirements.lock.txt and evidence/setup/2026-10-19 |
| Minimum transport and standalone simulator | G1/G2 PASS | Separate actual evidence below |
| CAN-to-vehicle and minimum stop chain | G3 PASS / G4 NOT_RUN | G3 실제 연결 완료, 거리 판단 SUT 미구현 |
| G1/G2 feasibility tools | IMPLEMENTED / UNIT_TESTED | tools/g1_vcan_smoke.py, tools/g2_carla_smoke.py and tests |
| G3 request transport tool | IMPLEMENTED / UNIT_TESTED / TRANSPORT_PASS | tools/g3_request_smoke.py, 새 단위 검사 23개와 실제 10프레임 송수신 |
| G3 adapter core | IMPLEMENTED / UNIT_TESTED / CONNECTED | tools/g3_adapter_core.py와 핵심 검사 18개. G3 실행기에서 실제 제동 연결 |
| G3 integration runner and oracle | IMPLEMENTED / LOCALLY_VERIFIED | tools/g3_carla_smoke.py, g3_integration_can.py, g3_integration_oracle.py와 실제 20프레임/차량 관측 |
| SUT implementation and unit tests | NOT_STARTED | 거리 입력 A/B 제어기 미구현. adapter는 G3 실행기에 연결 완료 |
| Thesis preliminary test execution and result summary | NOT_RUN | G1/G2/G3 연결 확인만 실행 |
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
| CARLA / vCAN adapter | G3 실제 요청 20개, 제동 호출 15회, 적용과 차속 및 잠금 유지 PASS | 거리 판단, watchdog, 전체 기동/arm과 G4 |
| Watchdog / sequence logic | Public source and tests inspected | Our distance-message controller |
| Fault injection / logging | Existing component code inspected | Our full scenario runner and oracle |
| Current repository | v1.0 기준선 이후 설치/도구/증거를 중간점검 스냅샷으로 관리. 해시는 git log로 확인 | 원격 반영은 push 및 원격 ref로 별도 확인 |

## Feasibility gates

G0 inspection, G1 transport, G2 standalone motion and G3 CAN-to-vehicle integration have separate evidence. G4 remains NOT_RUN. Server shutdown crashes are tracked separately from actor/settings cleanup.

| Gate | Description | Status | Evidence |
| --- | --- | --- | --- |
| G0 | Inspect Ubuntu, GPU, disk, Python and git | PASS | [Report](G0_ENVIRONMENT_2026-10-19.md), evidence/g0/2026-10-19 |
| G1 | Independent vCAN publisher and receiver exchange known frames | PASS | [Actual transport verdict](../evidence/g1/g1-20261019-01/verdict.json) |
| G2 | CARLA standalone vehicle control and actual velocity query | PASS | [Final run04](../evidence/g2/g2-20261019-04/result.json), [raw-state audit](../evidence/g2/g2-20261019-04/observation_audit.json), [post-cleanup](../evidence/g2/g2-20261019-04/post_cleanup.json); earlier failures retained |
| G3 | vCAN control reception changes CARLA vehicle state | PASS | [실제 연결](../evidence/manual/g3-20261031T151442436312880Z-11071/result.json), [원시 자료 재계산](../evidence/manual/g3-20261031T151442436312880Z-11071/observation_audit.json). 사용자 직접 재현 대기 |
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
- SUT 응답시간은 아직 없다. G2 단독 제동과 G3의 CAN 요청 기반 제동은 각각 관측했다. 본시험 실행: 0/80.

## Remaining execution records and approvals

- Advisor feedback, without inventing individual parameter approval
- Resolve or bound the repeatable CARLA shutdown crash before long unattended experiments; do not reinstall drivers or change versions without evidence
- Actual map/spawn and vehicle-physics records before main testing
- 사용자 G3 코드 검토 및 직접 재현, G4 구현과 독립 근거, 이후 예비/본시험
- Project license for original future code

## Next task

사용자 직접 실행 안내: [SELF_CHECK.md](SELF_CHECK.md), [G3_INTEGRATION.md](G3_INTEGRATION.md), 진입점 `bash tools/run_self_checks.sh`. 실제 G3 진입점은 PASS했고 사용자 직접 재현은 대기 중이다. 전체 단위 검사 119개와 의존성/셸 문법/공백 검사가 통과했다. 이전 사용자 검사 80개와 이번 Codex 검사 119개는 별도 기록한다. [검사 근거](../evidence/g3/integration-20261101-01/gate_checks.json). 새 코드 설명과 주석은 한글로 작성한다.

Git 공유: 사용자 요청으로 G3 완료 commit `4815250`까지 로컬 커밋 3개를 `git push origin main`으로 게시했다. 직접 원격 조회에서도 main SHA `4815250f531bcabcb7dce1d676b4ab5a838a038d`가 일치했다. 이 게시 결과와 재개 안내는 별도 문서 커밋으로 함께 공유한다. 사용자는 G4를 다음날 이어가기로 했으며 이번 작업에서는 시작하지 않는다.

다음은 사용자 검토와 G3 직접 재현, 이후 G4를 위한 최소 거리 입력 제어기와 기동/arm 전이 구현이다. 잘못된 요청의 본시험 차량 대응은 미정이며 필요한 결정을 이유와 함께 제시한다. G3의 준비 후 arm을 전체 SUT의 기동/arm 검증으로 확대하지 않는다. 전체 SUT나 80회 시험을 한 번에 구현하지 않는다. sticky_control=true 및 batch 제동 경로를 유지하고 서버 종료 문제는 장시간 무인 시험 전에 별도로 점검한다.

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
