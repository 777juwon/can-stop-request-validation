# Work log

## 2026-10-13: Initial planning handoff

- Preserved the bachelor's thesis purpose and validation-focused scope.
- Recorded the proposed vCAN input/controller/sink/logger architecture.
- Separated confirmed goals, proposed design and unexecuted work.
- Recorded public implementation references with fixed source commits.
- Added Linux-first feasibility gates and instructions for the next Codex session.
- Did not install CARLA, create a Linux vCAN interface, run fault scenarios or obtain thesis measurements.
- Did not copy company code, private data or the full conversation.
- Next task: Ubuntu environment inspection, followed by minimal vCAN and CARLA reproduction.

This entry documents repository preparation only. It is not experimental evidence.

## 2026-10-15: Initial thesis analysis

- Starting Git commit: `62a193ae252925fcbac3e6371a373adda8800848`.
- Read AGENTS.md, README.md and all five existing documents in docs/ before analysis.
- Confirmed an initially clean working tree and documentation-only tracked contents.
- Confirmed the GitHub HEAD and main matched the local commit using a read-only remote query. No fetch, pull, branch change, commit or push was performed.
- The user confirmed advisor review has not yet taken place and no unrecorded implementation or CARLA/vCAN execution results exist.
- Added [THESIS_REVIEW](THESIS_REVIEW.md): research question, contribution candidate, thesis structure, comparison logic, missing response policy, independent evidence and timing concerns.
- Updated STATUS.md without advancing any runtime gate. G0 through G4 remain NOT_RUN.

Commands and observed results before documentation edits:

| Command / action | Result |
| --- | --- |
| `pwd` | Exit 0; project root `/home/parkjuwon/can-stop-request-validation` |
| `git status --short --branch` | Exit 0; clean main tracking origin/main |
| `git ls-files` | Exit 0; nine tracked documentation/configuration files, no implementation or test suite |
| `git log -5 --date=iso-strict --format='%h %ad %s'` | Exit 0; one bootstrap commit dated 2026-10-13 |
| `git rev-parse HEAD` | Exit 0; starting commit recorded above |
| `cat AGENTS.md README.md docs/STATUS.md docs/LINUX_HANDOFF.md` | Exit 0; read required scope and handoff |
| `cat docs/VALIDATION_PLAN.md docs/SOURCE_AUDIT.md docs/WORKLOG.md` | Exit 0; read proposed requirements, prior source audit and history |
| `cat .gitignore .gitattributes` | Exit 0; inspected repository configuration |
| `rg --files --hidden -g '!.git/**' -g '!AGENTS.md' -g '!README.md' -g '!docs/**'` | Exit 0; only .gitattributes and .gitignore beyond the listed documents |
| `rg -n '^#{1,3} \|TBD\|NOT_RUN\|NOT_EXECUTED\|DOCS_ONLY\|counter\|oracle\|deadline\|마감\|요구사항\|미구현\|미실행' README.md docs` | Exit 0; located research scope, unexecuted gates and unresolved definitions |
| Browser open of the user-provided GitHub repository | Failed with cache miss; not used as remote-content evidence |
| `git ls-remote https://github.com/777juwon/can-stop-request-validation.git HEAD refs/heads/main` | Exit 0; both remote references matched the starting commit |

Evidence paths: README.md, docs/VALIDATION_PLAN.md, docs/SOURCE_AUDIT.md, docs/THESIS_REVIEW.md and the command result summaries in this entry. No experiment logs were generated.

Documentation validation:

- `git diff --check`: exit 0, no whitespace errors in tracked changes.
- `python3 -` with inline Markdown validation: exit 0; seven README/docs Markdown files and 15 local links checked, no missing link targets, trailing whitespace or missing final newlines. Included the new untracked analysis document.
- The same inline check confirmed STATUS still contains DOCS_ONLY and all five gate rows retain NOT_RUN with no runtime evidence.
- `git diff -- docs/STATUS.md docs/WORKLOG.md`: exit 0; reviewed scoped state and history updates. Reviewed the new analysis document separately for consistency with the source documents.
- `git status --short --branch`: exit 0; only STATUS.md and WORKLOG.md modified, THESIS_REVIEW.md added, main unchanged.
- No lint/typecheck/test/docs-index commands are provided by the repository. Runtime tests could not be run because no implementation or test suite exists; the documentation checks above are not experiment results.

Remaining assumptions: institutional deadlines are taken from README and were not separately verified; referenced upstream source claims were not re-audited; academic novelty and advisor acceptance remain unverified. Numerical requirements and recovery policy remain proposals/TBD.

Next task, planned and not executed: advisor scope review and the existing G0 environment inspection, followed by separately evidenced G1 and G2 reproduction.

## 2026-10-16: Final implementation and validation documents v1.0

- User direction: leave the already submitted proposal unchanged and finalize study documents for implementation.
- Added RESEARCH_BASELINE.md and THESIS_OUTLINE.md; replaced the proposed validation outline with an explicit requirements and test specification.
- Fixed four scenarios, A/B definitions, scripted distance fixtures, message layouts, research-only design values, latched-stop policy and separated clocks.
- Specified independent request observation, adapter call completion and CARLA motion criteria. Kept predicted mechanism behavior distinct from observed results.
- Assigned eighty original main-test attempts and explicit failure, environment, input and evidence reporting; no rerun-until-pass policy.
- Updated README, STATUS, AGENTS and Linux handoff to point to the fixed baseline without claiming runtime success.
- Read official Linux vCAN and CARLA 0.9.15 time/control documentation. These support APIs, not the study's chosen numerical limits.
- No HWP proposal was changed. No code, simulator installation, vCAN execution or thesis measurements were created.
- Changes are local only; no commit or GitHub push is implied by this entry.
- Next task: review the v1.0 choices with the user, sync when authorized, then inspect Ubuntu and execute G0~G4 without silently changing the test criteria.

## 2026-10-16: Publication authorized and completion boundary clarified

- The user accepted the v1.0 document direction and explicitly authorized GitHub publication.
- Added a completion checklist: requirements, test specifications and thesis structure are complete; implementation and preliminary experiments are not.
- Publication target: origin/main in 777juwon/can-stop-request-validation. Only the scoped Markdown documents are included.
- Local checks: git diff --check and document/formula consistency checks. These are documentation checks, not vCAN or CARLA experiments.
- No requirement or test result is changed to PASS by publishing a commit.
- Next task on Linux: inspect the environment, reproduce vCAN and CARLA minimum paths, implement the bounded test system, then execute and summarize preliminary trials.

## 2026-10-19: Published v1.0 re-analysis and handoff review

- User request: re-read the updated GitHub repository, analyze its current direction and understand the organized reading order and handoff.
- Original checkout HEAD: `62a193ae252925fcbac3e6371a373adda8800848`. Initial working changes were exactly the earlier analysis edits to STATUS.md and WORKLOG.md plus THESIS_REVIEW.md. Preserved these known changes.
- Verified GitHub HEAD and main at `94411a45aac647a0b9b0c811606d74c8f30d1df2`, the 2026-10-16 v1.0 document baseline.
- Read the latest revision in isolated checkout `/tmp/can-stop-request-review-20261019.psmWNM`; did not pull into the original folder, reset, stash, change its branch, commit or push.
- Read all latest Markdown documents, including the new RESEARCH_BASELINE.md and THESIS_OUTLINE.md. Compared the two commits: eight files changed, 420 insertions and 120 deletions.
- Added [REVISION_REVIEW_2026-10-19.md](REVISION_REVIEW_2026-10-19.md) with fixed-revision links, reading order, updated decisions, two implementation interpretation boundaries and an execution-session handoff prompt.
- Added a latest-revision notice to STATUS.md and a historical notice to THESIS_REVIEW.md. The old analysis body is preserved. The original local folder is still not a synchronized v1.0 checkout.
- Corrected the current understanding from provisional design to DESIGN_BASELINED / IMPLEMENTATION_NOT_STARTED. No fixed value or scenario was changed; no execution gate advanced.

Commands and observed results:

| Command / action | Result |
| --- | --- |
| `git status --short --branch` in original checkout | Exit 0; main with the known prior analysis changes |
| `git log -8 --date=iso-strict --format='%h %ad %s'` in original checkout | Exit 0; local history still at bootstrap commit |
| `git ls-remote https://github.com/777juwon/can-stop-request-validation.git HEAD refs/heads/main` | Exit 0; both remote references at 94411a45aac647a0b9b0c811606d74c8f30d1df2 |
| `mktemp -d /tmp/can-stop-request-review-20261019.XXXXXX` | Exit 0; created the isolated review directory recorded above |
| `git clone --depth 20 --single-branch --branch main https://github.com/777juwon/can-stop-request-validation.git /tmp/can-stop-request-review-20261019.psmWNM` | Exit 0; obtained latest main without modifying the original checkout |
| `git log -10 --date=iso-strict --format='%h %ad %s'` in isolated checkout | Exit 0; latest v1.0 commit and bootstrap commit |
| `git diff --stat 62a193ae252925fcbac3e6371a373adda8800848 HEAD` in isolated checkout | Exit 0; eight changed files, including two new design/writing documents |
| `cat AGENTS.md README.md docs/STATUS.md docs/LINUX_HANDOFF.md` in isolated checkout | Exit 0; read latest policy, overview, state and handoff |
| `cat docs/RESEARCH_BASELINE.md docs/VALIDATION_PLAN.md docs/THESIS_OUTLINE.md` in isolated checkout | Exit 0; read fixed design, test specification and thesis structure |
| `cat docs/SOURCE_AUDIT.md docs/WORKLOG.md` in isolated checkout | Exit 0; read source limits and publication history |
| `nl -ba docs/VALIDATION_PLAN.md`, `nl -ba docs/THESIS_OUTLINE.md`, `nl -ba docs/RESEARCH_BASELINE.md` | Exit 0 each; inspected detailed time boundaries, fixture and chapter references |
| `git ls-files` in isolated checkout | Exit 0; eleven tracked documentation/configuration files |
| `python3 -` with inline document/link/formula checks in isolated checkout | Exit 0; nine Markdown files, twenty local links, nine requirements and four scenarios; formula checks passed |
| `git diff --exit-code 62a193ae252925fcbac3e6371a373adda8800848 HEAD -- docs/SOURCE_AUDIT.md` | Exit 0; the prior source audit is unchanged, not a new external-source verification |
| `git status --short --branch` in isolated checkout | Exit 0; clean main at the reviewed revision |

The formula checks covered T-02 first near input at n=260/13.0 s, last-new input at 4.95 s, nominal expiry at 5.15 s, sixty fault slots, restored delta=61, 255-to-0 delta=1, eighty planned runs and eleven samples spanning 0.5 s. These are document consistency checks, not simulated trials or measured performance.

Remaining risks: the original local checkout still needs integration of the published revision before implementation. Actual dependency compatibility, CARLA behavior, vCAN operation and all numerical performance remain unverified. Preparation-period requests and repeated-request correspondence need consistent implementation and oracle interpretation without changing the baseline.

Next task, planned and not executed: preserve local analysis while obtaining the latest baseline in the implementation checkout, then G0 environment inspection and separate G1/G2 reproduction.

Validation of this session's local documentation updates:

- `git diff --check`: exit 0.
- `python3 -` with inline local Markdown checks: exit 0; nine Markdown files, eighteen local links and nine fixed-revision reference links, with whitespace/final-newline checks. Confirmed latest-state notice, historical boundary and all five unchanged NOT_RUN gate rows.
- `git diff -- docs/STATUS.md docs/THESIS_REVIEW.md`: exit 0; reviewed the tracked state notice. The untracked review documents were inspected separately.
- `git status --short --branch`: exit 0; only the prior analysis files and the new revision review are changed/untracked; original main remains at the prior commit.
- `git rev-parse HEAD` in the isolated checkout: exit 0; confirmed full reviewed hash 94411a45aac647a0b9b0c811606d74c8f30d1df2.
- No repository runtime gates exist in the reviewed snapshot, and no vCAN/CARLA execution was performed.

## 2026-10-19: Latest checkout synchronized, G0 inspected and installation items selected

- User-authorized scope: obtain latest documents, inspect and record the environment, then decide required installations. Package installation and simulator/transport execution were outside this session's scope.
- Verified remote HEAD/main remained at `94411a45aac647a0b9b0c811606d74c8f30d1df2` and the original checkout was still at `62a193ae252925fcbac3e6371a373adda8800848` with the known prior analysis changes.
- Preserved STATUS.md, WORKLOG.md, THESIS_REVIEW.md and REVISION_REVIEW_2026-10-19.md verbatim under evidence/g0/2026-10-19/pre_sync with a SHA-256 manifest. Verified copies before temporarily matching the two tracked analysis files to their old HEAD with apply_patch.
- `git pull --ff-only`: exit 0; advanced the same main branch to 94411a4, adding the published design and thesis outline without conflicts. No reset, stash, branch switch, commit or push.
- Reintegrated all original WORKLOG sections and both upstream 2026-10-16 entries. The full pre-sync STATUS and previous worklog also remain in the verified archive.
- Read the published project instructions and handoff. Inspected hardware, OS, kernel CAN support, Python packages, project venv candidates, standard CARLA paths and public dependency metadata.
- Added [G0 environment report](G0_ENVIRONMENT_2026-10-19.md), updated README/STATUS/Linux handoff and annotated the earlier revision review as historical.

Executed checks and observed results:

| Check / command | Result and evidence |
| --- | --- |
| `cat /etc/os-release`, `uname -srm`, filtered `lscpu`, `free -h`, `df -h` | Ubuntu 22.04.5, kernel 6.8.0-138, Ryzen 7 8845HS 8C/16T, 14 GiB RAM, 200 GiB disk available; hardware.json |
| `nvidia-smi --query-gpu=name,driver_version,memory.total,memory.free --format=csv,noheader` | Default sandbox exit 9; explicitly approved escalated query exit 0: RTX 4060 Laptop, driver 570.211.01, 8188 MiB total; both outcomes retained in hardware.json |
| Command availability and selected `dpkg-query` | can-utils/vulkan-tools absent; iproute2 and python3.10-venv installed; software.json |
| `python3 --version`, `python3 -m pip --version`, package metadata | Python 3.10.12, pip 25.3; existing carla 0.9.14 and numpy 1.26.4; python-can/cantools absent; software.json |
| `modinfo vcan`, kernel config, `ip -details link show type vcan` | Module/config available, no vCAN interface; software.json |
| PF_CAN raw socket create/close probe | Exit 0; support probe only, no frames exchanged. May trigger kernel autoload of CAN modules; no explicit modprobe executed |
| `ip -details link show dev vcan0` | Exit 1, device does not exist; additional_checks.json |
| `git --version`, CARLA package/PATH/standard-path checks, ABI query | Git 2.34.1; no server found in checked paths/package/PATH; x86_64/glibc 2.35/cp310; additional_checks.json |
| Official PyPI JSON and CARLA release API queries | CPython 3.10 Linux wheel exists for 0.9.15; CAN package versions support Python >=3.9; package/release metadata retained in dependency_metadata.json |
| HEAD of official release's Linux archive URL | HTTP 200, Content-Length 8,386,636,048 bytes; no archive body downloaded; carla_download_probe.json |

Inspection commands, arguments, output and exit statuses are recorded in the JSON files under [evidence/g0/2026-10-19](../evidence/g0/2026-10-19/checkout_sync.json). Only project files, standard system information and explicit installation-path candidates were inspected. No company repository or general personal-folder search was performed.

Decisions:

- Use existing CPython 3.10.12 in a project .venv. No Python 3.9 installation, system Python downgrade or driver reinstall is indicated.
- Install can-utils for G1, python-can 4.6.1 and cantools 40.7.1 in the project environment. Prepare the existing vcan driver and create vcan0 only after rechecking absence.
- Recommend vulkan-tools for G2 diagnostics. Prepare a separate official CARLA 0.9.15 server and matching cp310 client; preserve the existing user carla 0.9.14.
- Official client release files, Python requirements and recent library release activity were checked. Full dependency resolution and runtime compatibility are still untested.
- G0 changed from NOT_RUN to PASS for completed inspection only. G1~G4 remain NOT_RUN; all v1.0 numerical requirements and test scenarios are unchanged.

No apt/pip installation, project venv creation, explicit module load, interface creation, CAN frame transmission, CARLA launch or package/archive download occurred. Public metadata and a HEAD response were fetched. Planned installation commands in the report were not executed.

Next task, planned and not executed: install the small system tools and project dependencies, prepare vcan0 and run independent G1 transport; then prepare the roughly 8.39 GB official CARLA archive for G2 with its download and system changes explained in advance.

Validation of the G0 handoff changes:

- `git diff --check`: exit 0.
- `git diff --exit-code -- AGENTS.md docs/RESEARCH_BASELINE.md docs/VALIDATION_PLAN.md docs/THESIS_OUTLINE.md docs/SOURCE_AUDIT.md`: exit 0; published policy, numerical design, scenarios, thesis outline and source audit unchanged.
- `python3 -` with inline evidence/document checks: exit 0; latest HEAD and main verified, all four archived SHA-256 values matched, twelve active Markdown files and forty-five local links checked, seven JSON files parsed. Confirmed G0 PASS only, G1~G4 NOT_RUN, successful host GPU evidence, cp310 wheel metadata and HEAD-only archive probe. Project .venv and third_party remained absent. Evidence files totalled 66,758 bytes at that check.
- Worklog preservation check: exit 0; all three pre-sync sections and both upstream 2026-10-16 sections retained, with the new G0 entry added.
- Read-only review of the environment report and handoff found no blocking overstatement; clarified the G2 Python instruction to use the inspected 3.10.12 venv path.
- `git status --short --branch`: only intended documentation updates, prior analysis files and the new evidence directory; main remains at published 94411a4. No commit or push performed.
- No SUT runtime tests are available or were run. These checks establish record consistency, not transport, simulator execution or numerical requirement performance.

## 2026-10-19: Python setup, authorized 0.9.14 removal and actual G1 transport

- User authorized the next stage, CARLA 0.9.15 installation, and removal of the existing 0.9.14 environment; user-terminal commands were allowed where password entry was needed.
- Preserved all existing project edits. Added fixed direct requirements, an isolated working-version lock, host/server start and project-check scripts, and bounded G1/G2 feasibility tools with unit checks. No SUT/controller or CAN/CARLA adapter was implemented.
- `sudo -n apt-get install --no-install-recommends -y can-utils vulkan-tools` outside sandbox: exit 1, password required. Prepared and syntax-checked tools/setup_g1_host.sh and sent its exact sudo command to the user.
- User reported host script completion. Independent dpkg-query and ip JSON then confirmed can-utils 2020.11.0-1, vulkan-tools 1.3.204.0+dfsg1-1, and real vcan0 of kind vcan with UP flag. Saved evidence/setup/2026-10-19/host_setup.json.
- `python3.10 -m venv .venv`: exit 0. Initial pip install using --report failed before installation because bundled pip 22.0.2 lacks that option. Reissued against public PyPI with a local command-result record and binary wheels; installation exited 0.
- Actual imports verified python-can 4.6.1, cantools 40.7.1 and carla 0.9.15 from the project .venv.
- Unisolated pip check/freeze included inherited external ROS metadata. Did not install ROS packages. Corrected project commands to Python -I; isolated pip check exited 0 and lock now contains only the thirteen installed environment/tooling distributions. Isolated unittest discovery uses explicit project top-level (-t .) and a tests package.
- Recorded twelve files belonging only to the detected user carla 0.9.14 and its dist-info. With user-authorized outside-workspace access, `python3 -m pip uninstall --yes carla` exited 0. A subsequent Python -E check found no global client and neither original package directory remained. The new .venv client still imports correctly. No unidentified runtime folder was removed.
- Started the user-authorized official 8.39 GB CARLA server archive download to ignored third_party/downloads. It is still in progress at this entry; no server install or launch is yet claimed.
- Read-only host Vulkan query exited 0, enumerating NVIDIA, AMD and llvmpipe; retained the loader warning about a skipped ICD. UUID fields excluded. Added per-process NVIDIA PRIME priority to the future server wrapper, supported by the official driver documentation.

Actual G1 execution:

```bash
.venv/bin/python -I tools/g1_vcan_smoke.py --interface vcan0 --output-dir evidence/g1/g1-20261019-01
```

- Exit 0, PASS. Independent receiver and sender worker exits were both 0. Observer recorded exactly twenty distance and forty background frames with expected IDs, DLC, raw payload and order.
- Distance publication stopped while twenty further background frames were observed. The observer's first-to-last post-stop heartbeat interval was 949.955037 ms. This is a connection observation, not SUT response latency.
- Evidence: evidence/g1/g1-20261019-01/verdict.json, commands.json, sender.jsonl and receiver.jsonl. G1 advanced to PASS; G2~G4 remain NOT_RUN and main comparison runs remain zero.

Tool verification before G1:

- `bash tools/check_project.sh`: exit 0; twenty-nine unit checks, isolated pip check, shell syntax and git diff whitespace checks passed.
- Cross-review found and fixed coordinator SIGTERM evidence loss, G2 post-tick preparation-deadline overrun, and cleanup errors hiding an existing motion FAIL. Added regression checks. Unit checks are not actual vCAN/CARLA evidence.
- `git check-ignore .venv third_party/downloads/CARLA_0.9.15.tar.gz.part`: exit 0; runtime directories ignored.
- Updated README, STATUS and Linux handoff to reflect actual installation and G1 evidence; the historical G0 record now points to the current setup record.

Next ongoing task: finish and verify official server download, inspect its startup script, extract the package and run G2 on a dedicated server. No thesis numerical threshold or main-test scenario was changed.

## 2026-10-19: Resume after usage interruption, CARLA installation and actual G2

Resume point and installation evidence:

- User requested checking the interrupted state and continuing the already authorized installation/runtime work. Rechecked branch main, HEAD 94411a45aac647a0b9b0c811606d74c8f30d1df2 and all known project edits; no unrelated changes found.
- The archive installer had completed in the background at 11:28:04 UTC. server_install.json was COMPLETE, archive size was 8,386,636,048 bytes and launcher/binary were present. Did not redownload or reinstall. Updated stale progress records only after checking actual files.
- Locally observed archive SHA-256: 7b2f432ce74b251593f95dcc8dee6d99ad9625c2a71a2d6d48f24d879de19ef7. No upstream checksum comparison is claimed. Data-filtered extraction recorded 36,163 members and 20,205,989,874 logical regular-file bytes. The installer has seven unit checks, including traversal, required executable validation and atomic no-replace destination handling.
- Read the extracted CarlaUE4.sh before execution; ldd resolved the required libraries. Confirmed ports 2000/2001 were free and vcan0 remained UP. Existing G1 evidence was retained without rerunning it.
- Started an owned dedicated server with `bash tools/start_carla_0915.sh > third_party/carla-server.log 2>&1`, outside sandbox for GPU/runtime access. First readiness query timed out after 5 s; the next hit the client's default ~/carlaCache write restriction. Approved outside-sandbox query then returned exact client/server 0.9.15 and Town10HD_Opt.
- NVIDIA pmon observed the server PID 36908 on GPU 0, type C+G, framebuffer 2623 MB. The separately queried device was RTX 4060 Laptop, driver 570.211.01. This is GPU process evidence, not an engine log or performance benchmark.

G2 commands and preserved attempts:

```bash
.venv/bin/python -I tools/g2_carla_smoke.py --host 127.0.0.1 --port 2000 --exclusive-server --allow-world-load --output-dir evidence/g2/g2-20261019-01
.venv/bin/python -I tools/g2_carla_smoke.py --host 127.0.0.1 --port 2000 --exclusive-server --allow-world-load --output-dir evidence/g2/g2-20261019-02
.venv/bin/python -I tools/g2_carla_smoke.py --host 127.0.0.1 --port 2000 --exclusive-server --allow-world-load --output-dir evidence/g2/g2-20261019-03
.venv/bin/python -I tools/g2_carla_smoke.py --host 127.0.0.1 --port 2000 --exclusive-server --allow-world-load --output-dir evidence/g2/g2-20261019-04
```

- run01: exit 1 / FAIL. Initial speed held, but all 45 brake observations had brake=0 and throttle>0. CARLA 0.9.15 Vehicle.cpp showed repeated VehicleControl calls can be skipped by a cache that Ackermann does not invalidate. Initial settling and later braking used identical values, matching this failure.
- run02: exit 2 / ENV_ERROR. Disabling sticky_control did not establish motion and exceeded the unchanged 30 s host preparation deadline. Official server AI source showed the setting also injects default control and can cancel Ackermann. Rejected this approach; preserved the entire attempt.
- Final control fix: retain sticky_control=true; send explicit brake through client.apply_batch_sync / ApplyVehicleControl with do_tick_cue=False. Check exactly one response, no error and matching actor ID. Tick once separately and verify actual applied control and velocity. Added a faithful client-cache transition regression model plus response-rejection tests. Read-only peer source review confirmed the batch path bypasses the Vehicle client cache without changing control values.
- run03: exit 0 / PASS. Independent raw-state review confirmed actor149, 199 continuous observations, actual velocity, applied brake and stop hold. Preserved execution source in the run folder before a later observation-only boundary fix.
- Review found CARLA float32 0.05 s totals 2.0000000298 s across 40 intervals. Fixed the nominal exact 2 s window to use the inclusive 40 fixed-frame intervals. Added tests that accept the 40-interval boundary and reject 41. No design threshold was relaxed; the run03 stop was already well inside the window.
- Restarted the server and ran the final source as run04: exit 0 / PASS. Town04, Model3, ClearNoon, spawn143, actor147, 199 consecutive frame observations. Host preparation 7.863144249 s. Actual speed held 4.575182694~4.964107976 km/h for 21 observations. First applied brake frame2608; stop hold completed 0.550000008 simulation seconds later with 11 consecutive low-speed observations. Maximum tick duration 3.241051 ms, schedule lateness 0.126838 ms. These are feasibility observations, not main-trial statistics.
- Recomputed speed from vx/vy, verified all frame/time transitions, batch actor/error/no-auto-tick fields, applied controls and hold limits independently from raw logs. Matched archived run01/run02/run03 source hashes and final run04 current-source hash. Evidence: each run's result.json and vehicle_states.jsonl, plus run03/run04 observation_audit.json.
- Cleanup calls succeeded for own actor, weather and settings. Separate post_cleanup.json in run03 and run04 confirmed no relevant actors, asynchronous world and fixed_delta_seconds=null. Explicitly permitted Town04 load was not undone. Spawn coordinates remain a G2 candidate, not approved/frozen main-trial coordinates.

Server lifecycle issue, kept separate from G2:

- Ctrl+C on each owned server PTY produced Signal 11 / exit 139 after G2 cleanup. Recorded both as shutdown crashes, not normal shutdown. Cause remains unresolved. The first crash excerpt was captured before the restart reused the ignored stdout log; no engine device-selection log was available.
- A shutdown-alternative probe found installed Python libcarla.command has no ConsoleCommand attribute (exit 1); no quit command was sent. Used Ctrl+C to stop the second owned server and retained that failure too.
- Both final ports were closed and approved NVIDIA pmon showed no remaining CARLA GPU process. vcan0 was retained UP. Details: evidence/setup/2026-10-19/server_runtime.json.

Verification and handoff:

- A direct `python -I -m unittest tests.test_g2_carla_smoke` invocation could not import the project tests because isolated mode excludes the current-directory import path. Used the established `unittest discover -s tests -t .` command; no runtime/environment change was needed.
- `bash tools/check_project.sh`: exit 0, 39 unit checks, isolated pip check, shell syntax and git whitespace checks passed. Unit/model checks remain distinct from actual G1/G2 evidence. Final document/evidence validation is recorded in evidence/setup/2026-10-19/project_checks.json.
- Updated README, STATUS, LINUX_HANDOFF, SETUP_AND_SMOKE and machine-readable progress. Preserved historical G0 records, failed attempts and v1.0 baseline documents. No submitted proposal/HWP changes, new commit, push or branch switch.
- Gates now G0/G1/G2 PASS; G3/G4 NOT_RUN; main comparison runs 0/80. Next functional task is G3: independent vCAN StopRequest sender and one adapter, with reception, call, applied frame and actual velocity recorded separately. Investigate the repeatable shutdown crash before long unattended trials.

## 2026-10-19: 한글 코드 설명 규칙과 사용자 직접 검사 진입점

- 사용자 요청: 앞으로 생성하거나 수정하는 코드의 설명과 주석을 한글로 작성하고, 직접 실행할 검사 코드를 정리한다. Git 반영 상태와 지금 G3를 시작할 때의 예상 시간도 질문했다.
- Git 상태 확인: main의 HEAD는 94411a4, 이전에 최신 기준선을 git pull로 받은 상태다. 이후 설치, 도구, G1/G2 결과와 문서 변경은 로컬 미커밋 상태다. 이번 질문을 업로드 지시로 해석해 commit/push를 실행하지 않았다.
- AGENTS.md에 새 코드 설명, 주석과 docstring의 한글 작성 규칙 및 직접 재현 명령 제공 규칙을 추가했다. 기존 API 이름과 JSON 키는 호환성을 유지하고, 과거 실행 소스와 증거는 해시 보존을 위해 수정하지 않는다. 연구 수치와 시험 명세는 변경하지 않았다.
- tools/run_self_checks.sh를 추가했다. check는 기존 검사, g1은 실제 vcan0 송수신, g2는 명시적 전용 서버 옵션을 요구하는 CARLA 검사 호출이다. 출력은 evidence/manual의 새 폴더에 저장한다. sudo 설치나 서버 시작은 이 스크립트가 자동 실행하지 않는다.
- docs/SELF_CHECK.md에 사용자 터미널의 사전 확인, G1/G2 실행 명령, 결과 위치, 판정 방법과 기존 서버 종료 문제를 한글로 정리했다. README, STATUS와 LINUX_HANDOFF에 연결했다.
- `bash tools/run_self_checks.sh check`: 종료코드 0. 단위 검사 39개, pip check, 셸 문법과 git diff 공백 검사 통과.
- `bash tools/run_self_checks.sh g1`: 종료코드 0, 실제 G1 PASS. 증거: evidence/manual/g1-20261019T120658753058546Z-20. 기존 G1 및 G2 결과는 보존했다.
- 도움말과 G2 도움말 조회는 종료코드 0. 전용 서버 옵션 없는 g2와 알 수 없는 모드는 의도대로 종료코드 2. 새 진입점을 통한 G2 서버 실행은 하지 않았으며 기존 직접 run04의 PASS와 구분한다. 전체 명령, 출력 및 결과: evidence/setup/2026-10-19/manual_entrypoint_checks.json.
- G3 작업 시간은 현재 도구 재사용을 가정해 구현, 실제 연동 검사와 사용자 안내까지 45~90분으로 추정했다. 서버 종료 crash 조사 범위가 커지면 더 걸릴 수 있다. 실행 약속이나 실측 소요 시간이 아니며, G3는 아직 NOT_RUN이다.

## 2026-10-31: G3 첫 단계의 요청 송수신 코드와 단위 검사

- 사용자 요청에 따라 한 작업에서 전체 G3를 끝내지 않고 단계적으로 진행했다. 이번 완료 경계는 CARLA 없는 StopRequest 전송 형식, 독립 송수신 도구, 단위 검사와 실제 환경 사전검사다.
- README, STATUS, LINUX_HANDOFF 및 기준선/검증 명세/소스 조사 문서를 다시 읽었다. main/HEAD 94411a4와 이전 로컬 변경이 유지됐고, 새 외부 변경이나 충돌은 발견하지 않았다. 문서 인덱스 스크립트와 추가 프로젝트 검사 설정은 없다.
- 환경 재확인: kernel 6.8.0-138-generic, 프로젝트 CPython 3.10.12, 패키지 메타데이터 python-can 4.6.1/cantools 40.7.1/carla 0.9.15 유지. 현재 vcan0 없음, 포트 2000/2001은 비어 있음. 가상 장치가 없어진 원인은 확인하지 않았다. 재부팅으로 단정하지 않았다.
- tools/g3_request_smoke.py와 tests/test_g3_request_smoke.py를 추가했다. 표준 Classic CAN ID 0x200/DLC8, `<BBBBI` 계약과 고정 바이트를 확인한다. 연결 확인용 5개 정상/5개 정지 입력과 counter 0~9는 본시험이나 adapter 정책으로 확정한 것이 아니다.
- 독립 worker의 송수신 로그, 원시 프레임 및 해석, token, 호스트 monotonic 시각을 상위 판정에서 대조한다. 송신 호출 전/성공 반환/수신 관측을 구분한다. CARLA, SUT 판단과 자동 재출발은 구현하지 않았다. parser는 미정의 필드를 진단용으로 보존하며 새로운 요청 watchdog이나 오류 대응 정책을 만들지 않았다.
- 첫 단위 검사에서 subprocess.Popen 대역이 metadata용 subprocess.run까지 영향을 줘 환경 오류 검사 1건이 실패했다. 테스트의 Git 조회 대역을 분리해 수정했다. 제품 코드의 성공으로 감추지 않았으며 이후 해당 검사도 통과했다.
- 별도 읽기 전용 검토에서 직접 worker 호출의 장치 검증 누락, 최적화에서 assert 판정 소실, receiver 조기 종료 분류 손실을 찾았다. worker별 vcan 사전검사, 명시 조건 판정과 원래 분류 전달로 보완했다. `-O` 하위 프로세스, 물리 장치 거부, 오류 분류 및 PASS 상속 차단 회귀 검사를 추가했다. 최종 읽기 검토에서 이번 구현/단위검사 범위의 추가 중요 결함은 발견하지 못했다.

실제 실행한 사전검사:

```bash
.venv/bin/python -I tools/g3_request_smoke.py --interface vcan0 --output-dir evidence/g3/g3-stage1-20261031-01
bash tools/run_self_checks.sh g3-can
```

- 둘 다 종료코드 2, ENV_ERROR. ip 조회는 종료코드 1, `Device "vcan0" does not exist.`였다. 송수신 worker는 시작하지 않았고 전송 프레임은 0개다. 이 결과를 실제 요청 송수신 PASS로 기록하지 않았다.
- 첫 사전검사의 당시 소스를 evidence/g3/g3-stage1-20261031-01/g3_request_smoke.py에 보존했다. 첫 metadata SHA와 일치한다. 최종 wrapper 실행 기록은 evidence/g3/2026-10-31/entrypoint_preflight.json, 출력은 evidence/manual/g3-can-20261031T104121341777662Z-4다.
- 새 단위 검사 23개와 기존 39개, 총 62개를 `bash tools/run_self_checks.sh check`로 확인한다. 최종 명령과 출력, 문서 링크, 기준선 및 증거 hash 검사는 evidence/g3/2026-10-31/checks.json에 기록한다. 단위 검사와 실제 사전검사는 구분한다.
- 사용자 실행 진입점에 g3-can을 추가하고, G3_PROGRESS.md/SELF_CHECK.md/README/STATUS/LINUX_HANDOFF를 갱신했다. 코드 설명, 주석과 docstring은 한글로 작성했다. G0/G1/G2의 과거 기록과 고정 연구 문서는 보존했다.
- 이번 단계에 새 의존성 설치, sudo/장치 생성, CARLA 시작, Git commit/push나 브랜치 변경은 없다. 기존 G1/G2는 과거 실행 PASS이고 현재 전체 G3/G4는 NOT_RUN, 본시험은 0/80회다.

다음 단계: 기존 `sudo bash tools/setup_g1_host.sh`로 vcan0를 준비한 뒤 g3-can에서 실제 10개 프레임을 확인한다. 그 후에 단일 CARLA adapter를 연결한다. 새 오류 대응 정책이 필요하면 근거와 제안을 먼저 남기고, 서버 종료 Signal 11도 별도 미해결 항목으로 유지한다.

## 2026-10-31: 사용자 장치 준비 후 실제 StopRequest 송수신

- 사용자가 준비 완료를 알렸다. 기존 README/STATUS/LINUX_HANDOFF 및 G3 진행 기록과 코드를 읽고 main/HEAD 94411a4, 이전 로컬 변경만 있는 상태를 재확인했다.
- `ip -details -json link show dev vcan0`: 종료코드 0, 종류 vcan, flags UP/LOWER_UP. can-utils 2020.11.0-1과 vulkan-tools 1.3.204.0+dfsg1-1도 재조회했다. 사용자의 sudo 실행 출력 자체를 관측했다고 주장하지 않는다. 증거: evidence/g3/2026-10-31/host_ready_recheck.json.

```bash
bash tools/run_self_checks.sh g3-can
```

- 실제 실행 종료코드 0, scope G3_STAGE1_REQUEST_TRANSPORT_ONLY, PASS. 출력 폴더: evidence/manual/g3-can-20261031T104807355660618Z-2.
- 독립 receiver PID 8과 sender PID 10의 종료코드 모두 0. 정상 5개와 정지 5개, 총 10프레임을 관측했다. 이 PID는 해당 실행에서 기록된 식별값이다.
- 원시 ID 0x200, DLC8, 표준 데이터 플래그, payload, token, counter 0~9 및 순서가 일치했다. 16바이트 Classic CAN 구조를 확인했으며 장치 MTU72를 CAN-FD 전송 증거로 해석하지 않았다.
- 기존 판정 함수와 별도로 고정 바이트를 직접 구성해 송수신 로그를 재계산했다. 송신 시작/반환과 수신 시각을 구분하고, 실제 worker 식별과 source SHA도 대조했다. 당시 소스와 observation_audit.json을 해당 실행 폴더에 보존했다.
- 명목 50 ms에 대한 최대 송신 시작 지연 0.108531 ms, 실제 송신 시작 간격 49.955525~50.032410 ms. 이는 이 연결 입력 일정의 관측이며 물리 CAN 전달 지연, adapter 처리 시간이나 본시험 성능 통계가 아니다.
- 이전 vcan0 부재 ENV_ERROR 2건과 당시 단위 검사 기록은 그대로 보존했다. 제품 코드는 수정하지 않았다. README/STATUS/LINUX_HANDOFF/SELF_CHECK/G3_PROGRESS를 실제 송수신 PASS와 다음 adapter 단계에 맞춰 갱신했다.
- `bash tools/run_self_checks.sh check`: 종료코드 0. 전체 단위 검사 62개, pip check, 셸 문법과 Git 공백 검사 통과. 문서 링크 96개와 고정 연구 문서 무변경도 확인했다. 명령/출력 및 검증 결과는 evidence/g3/2026-10-31/transport_checks.json에 기록했다.
- 이번 작업은 G3의 요청 전달 부분만 완료했다. CARLA 서버나 adapter는 실행하지 않았고 포트 2000/2001은 비어 있었다. 전체 G3/G4는 NOT_RUN, 본시험은 0/80회다. 인터페이스는 UP으로 유지했다. 새 commit/push나 브랜치 변경은 없다.
- 다음 작업: 단일 CARLA adapter 구현과 단위 검사. 이후 수신, 제어 호출, 최초 적용 frame과 실제 차속을 분리해서 확인한다. 미정인 요청 오류 처리와 기존 서버 종료 문제는 구현 및 장시간 실행 전에 따로 검토한다.

## 2026-10-31: 요청 송수신 단계의 기록 마감

- 사용자의 기록 진행 요청에 따라 기존 실행 기록과 현재 인수인계를 점검했다. main/HEAD 94411a4와 이전 로컬 변경을 유지했으며 새 코드나 실험은 추가하지 않았다.
- docs/CHECKPOINT_2026-10-31.md에 실제 완료 범위, 증거 읽기 순서, 사용자 재실행 명령과 다음 adapter 작업의 완료 기준을 정리했다. STATUS와 LINUX_HANDOFF에서 연결했다.
- 실제 요청 전달 PASS, 전체 G3/G4 NOT_RUN과 본시험 0/80회를 구분했다. 초기 ENV_ERROR 2건과 기존 서버 종료 Signal 11도 보존했다. 미정인 adapter 정책을 승인된 규칙으로 변경하지 않았다.
- evidence/g3/2026-10-31/checkpoint_manifest.json에 증거 및 관련 소스 37개 파일의 경로, 크기와 로컬 SHA-256을 기록했다. 세 실행 폴더의 당시 소스와 최종 실행/현재 소스의 해시를 대조했다. 원시 로그와 기존 검사 결과는 덮어쓰지 않았다.
- 제품 코드 변경이 없어 단위 검사와 요청 송수신은 재실행하지 않는다. 최신 단위 검사 62개 PASS는 transport_checks.json의 기존 실행 결과다. 이번 확인 범위는 문서 링크, Git 공백, 고정 연구 문서 무변경 및 증거/소스 해시 대조다.
- 문서 16개에서 로컬 링크 112개가 유효했고, Git 공백 검사와 고정 연구 문서 무변경 검사가 종료코드 0이었다. 체크포인트 목록의 record_status는 VERIFIED다.
- 새 commit/push나 브랜치 변경은 없다. 다음 작업은 CARLA adapter의 최소 정상 수신 경로와 단위 검사다.

## 2026-10-31: 중간점검 보고서와 로컬 체크포인트 커밋 준비

- 사용자가 커밋 여부, push 및 지금까지의 진행과 남은 작업을 질문했다. 작업 시작 시 새 커밋은 없었고 파일 변경만 저장돼 있었음을 명확히 설명했다.
- git log와 status를 확인했다. 로컬 HEAD와 `git ls-remote --exit-code origin refs/heads/main`의 실제 원격 main은 모두 94411a45aac647a0b9b0c811606d74c8f30d1df2였다. origin/main 비교만으로 최신 원격을 확인했다고 주장하지 않았다.
- docs/MIDTERM_REVIEW_2026-10-31.md에 완료한 일, 남은 여섯 작업 묶음, 검증 범위와 직접 점검 순서를 정리했다. G0~G2의 3/5 gate 통과를 논문 전체 완료율로 환산하지 않았고 본시험 0/80회를 명시했다.
- README/STATUS/LINUX_HANDOFF에서 연결했고, 과거 체크포인트의 미커밋 표시는 그 당시 상태로 설명했다. 새 실험이나 기능 구현은 추가하지 않았다.
- 기존 untracked 파일은 117개였으며 증거 약 1.50 MB, 가장 큰 파일 약 499 KB였다. CARLA 패키지와 .venv는 제외 대상임을 확인하고, 코드/문서/작은 실행 증거를 로컬 중간점검 커밋 대상으로 정리한다.
- 커밋 전 프로젝트 검사, 문서 링크, 증거 해시 및 파일 범위를 확인한다. 실제 명령과 결과는 evidence/review/2026-10-31/pre_commit_checks.json에 기록한다. 준비를 마친 뒤 Conventional Commit으로 저장하며, 원격 push는 이번 로컬 저장과 구분한다.
- 커밋 전 검사 결과: 단위 검사 62개와 pip check 통과, 문서 17개/로컬 링크 120개 정상, 마감 목록의 37개 파일 해시 일치, 고정 연구 문서 무변경. 별도 읽기 전용 검토에서도 공개를 막는 credential/개인자료/비공개 URL/큰 런타임 혼입은 발견하지 못했다.
- 중간점검 커밋은 기능 전체 완료를 뜻하지 않는다. 정상적인 Git commit/push로 스냅샷을 공유하며 실제 저장 및 전달 결과는 Git commit과 원격 ref로 확인한다. 강제 push나 브랜치 변경은 수행하지 않는다.

## 2026-10-31: G3 adapter 핵심과 직접 검토 및 실행 안내

- 앞선 중간점검은 commit 9109b3c1d7208f570aeb681fb62a122f1dc0d898로 저장하고 origin/main push가 성공했다. 직접 원격 조회의 SHA도 일치했고 작업 폴더는 깨끗했다.
- 사용자가 다음 G3 진행과 자신이 직접 할 일을 질문했다. 진행 방식을 물었고, Codex가 구현하고 Juwon님이 검토 및 직접 실행하는 방식을 선택했다. 이어 구현을 진행하도록 확인했다. 코드 작성, 검토와 실행의 담당은 구분해서 기록한다.
- README/STATUS/LINUX_HANDOFF, 기준선과 검증 명세 및 소스 조사를 읽고 기존 G2/G3 코드를 확인했다. vcan0가 UP인 상태를 조회했으나 이번 작업에서 새 CAN/CARLA 실험은 하지 않았다.
- tools/g3_adapter_core.py를 추가했다. 정상 요청의 최소 지원 범위, 정지 잠금/최초 원인 유지, 제동 콜백, 호스트 수신/호출 완료 기록을 구현했다. stop=0은 가속하지 않고 기존 제어를 유지한다. 실제 G2 제동 함수를 콜백에 연결할 수 있다.
- 지원 범위 밖 입력은 G3InputError로 호출자에게 전달한다. 실제 차량의 오류 대응 정책을 확정한 것은 아니다. counter는 기록만 하며 요청 watchdog을 만들지 않았다. core는 arm 이후 구간용이며 INIT_INHIBITED→arm/reset은 지원하지 않는다.
- callback 오류와 잘못된 응답, 시각 역행은 기록하고 객체 재사용을 막는다. 50 ms 초과는 호출 완료와 별도로 기록하며 환경 오류로 바꾸지 않는다. 사용자 취소는 상위로 전파하고 재사용을 막는 회귀 검사를 추가했다.
- tests/test_g3_adapter_core.py의 새 검사 18개가 통과했다. G2 helper 연결 검사도 가짜 client/API를 사용한다. 이 검사를 실제 G3 또는 R-06/R-07 통과로 표현하지 않는다.
- 별도 읽기 전용 코드/기준선 검토에서 이번 범위를 막는 중요 결함은 발견하지 못했다. 기동/arm 전이의 미구현과 가짜 콜백 시간의 한계를 문서에 명시했다.

실행한 예제:

```bash
.venv/bin/python -I tools/g3_adapter_core.py --demo
```

- 종료코드 0. 정상→정지→정상 입력에서 기존 제어 유지→제동→제동, 가짜 콜백 2회. scope=G3_ADAPTER_DEMO_ONLY, actual_can=false, carla_executed=false. 예제 actor77과 시간은 실제 차량 검증 결과가 아니다.
- docs/G3_ADAPTER_STEP.md에 코드 검토 질문, 지금 실행할 단위 검사/예제와 기존 G2 수동 재현 절차를 정리했다. 사용자 자신의 검토 및 재실행은 아직 완료 기록이 없다. 현재 offscreen 서버는 창이 표시되지 않는다는 점도 안내했다.
- STATUS/G3_PROGRESS/SELF_CHECK/README/LINUX_HANDOFF를 갱신하고 중간점검 보고서는 9109b3c 당시 기록임을 명시했다. 고정 연구 수치와 제출한 계획서는 변경하지 않았다.
- 전체 프로젝트 검사와 실행 근거는 evidence/g3/adapter-core-20261031-01/checks.json 및 demo.json에 저장한다. 해당 기록은 핵심 코드/가짜 콜백 확인이며 실제 CAN/CARLA 통합은 아니다.
- 최종 검사 종료코드 0: 단위 검사 80개, pip check, 셸 문법과 Git 공백 검사 통과. 문서 18개/로컬 링크 130개 유효, 고정 연구 문서 무변경. 결과와 source SHA를 위 checks.json에 보존했다. 사용자 검토와 사용자 재실행 완료는 아직 기록하지 않았다.
- 이번 구현과 안내는 검증 후 별도 로컬 커밋으로 저장한다. 이번 단계의 원격 push는 수행하지 않으며 저장 상태는 git log/status로 확인한다.
- 다음 작업은 CAN 수신 루프, 이번 core와 G2 제동 함수를 단일 실행기에 연결하는 것이다. 준비와 arm 경계, 실제 적용 frame/속도, 파일 로그와 자원 정리를 확인해야 한다. 전체 G3/G4는 NOT_RUN이며 본시험은 0/80회다.

## 2026-10-31: 사용자 adapter 예제 실행 출력 검토

- 사용자가 직접 실행한 터미널 출력을 제공하고 정상 여부 확인을 요청했다. 제공된 출력 기준으로 판정했으며 같은 실행을 agent가 직접 관측했다고 주장하지 않는다.
- `bash tools/run_self_checks.sh`에는 check 인자가 없어 도움말만 표시됐다. 사용자 단위 검사 80개 완료로 기록하지 않았다. 다음 실행 명령은 `bash tools/run_self_checks.sh check`다.
- `.venv/bin/python -I tools/g3_adapter_core.py --dem`의 예제 출력은 기대 동작과 일치했다. 정상 입력은 KEEP_EXISTING_CONTROL, 정지 이후와 후속 정상 입력은 APPLY_FULL_BRAKE였다. stop_latched는 false/true/true, 최초 reason=1 유지, 가짜 콜백 2회였다. 정식 재현 옵션은 --demo로 안내한다.
- actual_can=false, carla_executed=false를 유지했다. 예제의 call_within_50ms를 실제 R-06 또는 차량 제동 성능으로 해석하지 않았다. 사용자 종료코드와 소스 해시, 소스 검토 완료는 제공되지 않아 추정하지 않았다.
- 사용자 출력의 의미 요약을 evidence/g3/adapter-core-20261031-01/user_demo_review.json에 저장했다. 전체 대화와 셸 프롬프트는 복사하지 않았다. STATUS/G3_ADAPTER_STEP/LINUX_HANDOFF의 사용자 실행 상태를 갱신했다.
- 제품 코드 변경은 없다. 문서 링크 132개, JSON 구문과 Git 공백 검사를 확인했다. 단위 검사는 재실행하지 않았다. 전체 G3와 실제 차량 연결은 여전히 미실행이다.

## 2026-11-01: 중단 지점 복구와 첫 실제 G3 통합 PASS

- 사용자가 작업 재개를 요청했다. README/STATUS/LINUX_HANDOFF와 기준선/검증 명세/소스 조사를 확인했고, main/HEAD d2957713523261f4f3b3710fd6aa733bb9ab4d9a, origin/main 대비 로컬 커밋 2개와 예상한 G3 변경만 있는 상태를 확인했다. 끊긴 지점은 통합 실행기/worker/독립 판정 구현 후 실제 실행 전이었다. 기존 로컬 변경을 이어받았으며 제출한 계획서와 v1.0 수치는 유지했다.
- 이전 사용자의 `bash tools/run_self_checks.sh check` 출력은 80개 OK, 0.187초, 의존성 오류 없음이었다. 중단 전 생성한 evidence/g3/adapter-core-20261031-01/user_check_review.json과 관련 문서 변경을 이번에 함께 마감했다. 사용자 출력의 검토이며 당시 사용자 종료코드나 소스 SHA를 확인했다고 주장하지 않는다.
- tools/g3_carla_smoke.py, g3_integration_can.py, g3_integration_oracle.py와 단위 검사 39개를 완성했다. worker 13개, 실행기 9개, 독립 판정 17개다. 독립 기대 바이트와 수신 관측, 호출 시각, 실제 적용 제어 및 velocity를 분리한다. 단일 제어/tick, 초기 준비 후 arm, 정지 잠금과 정상 복원 후 제동 유지, worker 종료 근거와 자원 복구를 검사한다. 지원 범위 밖 요청은 중단하고 기록하며 본시험 오류 대응 정책으로 확정하지 않았다.
- 중단 전 검토에서 제동 적용의 귀속을 보완했다. Ackermann의 이전 제동을 CAN 효과로 잡지 않도록 실행기는 잠금 이후, 독립 판정은 첫 정지 요청의 실제 호출 완료 이후 tick에서만 최초 적용을 인정한다. 회귀 검사로 이전 제동만 있는 자료의 통과를 막았다. 완료 선언과 실제 worker 종료코드/PID/역할도 대조한다. 재개 후 별도 읽기 전용 최종 검토에서 실행을 막는 추가 결함은 발견하지 못했다. 이 검토 자체는 실제 실행 증거가 아니다.
- 시작 시 vcan0가 없었고 포트 2000/2001은 비어 있었다. `sudo -n bash /home/parkjuwon/can-stop-request-validation/tools/setup_g1_host.sh`는 비밀번호 필요로 종료코드 1이었다. 사용자에게 원래 sudo 명령을 요청했고 완료 응답 후 vcan0/vcan/UP/LOWER_UP을 직접 재조회했다. 사라진 원인을 재부팅으로 단정하지 않았다. 근거: evidence/g3/integration-20261101-01/host_and_server.json.
- 기존 launcher와 upstream CarlaUE4.sh를 읽고 설치된 0.9.15 전용 서버를 시작했다. 명령은 `bash tools/start_carla_0915.sh > third_party/carla-g3-20261101-server.log 2>&1`. client/server 0.9.15와 초기 Town10HD_Opt를 조회했다. 호스트 NVIDIA 조회는 RTX 4060 Laptop/570.211.01, pmon은 CARLA PID 10900과 GPU 메모리 2619 MiB를 관측했다. 샌드박스 내 별도 compute 조회 실패와 호스트 조회 성공은 구분해 남겼다.

```bash
bash tools/run_self_checks.sh g3 --exclusive-server --allow-world-load
```

- 실제 실행 종료코드 0, 전체 G3 PASS. evidence/manual/g3-20261031T151442436312880Z-11071에 원시 로그와 판정을 보존했다. 폴더/로그는 UTC 2026-10-31이며 한국 시각은 2026-11-01이다. 실행 소요 약 14초, 준비 7.862초다. 다음 실행의 시간 보장은 아니다.
- 전용 빈 Town04/Model3/ClearNoon/spawn 143, sticky_control=true와 기존 batch 제동을 사용했다. 정상 5개/정지 5개/정상 복원 10개, 총 20개의 0x200/DLC8 입력이다. coordinator 11071, sender 11105, observer 11104가 분리됐다. 송신/독립 관측/adapter 수신/adapter 이벤트가 각각 20개, 차량 상태 206개다.
- 초기 차속은 21개 연속 표본에서 4.575182694~4.964107976 km/h였다. 제동 호출은 15회, 호스트 수신부터 완료까지 최대 0.429085 ms. 최초 적용 frame 8685 뒤 정지 유지 frame 8686~8696의 11개 연속 표본을 확인했고 적용 후 명목 0.55초에 유지 조건이 완료됐다. frame 8725까지 40간격 관측을 완료했다. 정상 복원 뒤에도 잠금과 제동을 유지했다. 이번 한 번의 연결 시험이며 본시험 통계나 SUT 전체 요구사항 준수로 확대하지 않는다.
- adapter/worker/oracle 모듈을 가져오지 않는 별도 audit_observations.py로 원시 바이트, PID, 시각, 실제 차속, 연속 frame, 잠금, 정지 유지와 정리를 재계산했다. 종료코드 0, observation_audit.json과 일치했다. metadata의 소스 SHA 6개를 현재 파일과 대조하고 source/에 동일 바이트를 보존했다. wrapper 사본은 실행 후 설명 주석만 고친 버전임을 source_archive.json에 구분했다.
- 자신의 actor 제거와 날씨/설정 복구가 완료됐고 서버를 별도 재조회해 비동기/고정 간격 없음/관련 actor 0개를 확인했다. 허용한 Town04 맵은 복구하지 않는다. 전용 서버에 Ctrl+C를 전달하자 다시 Signal 11/exit 139였다. G2 2건에 이어 세 번째 관측이며 원인은 미해결이다. 종료 후 포트 LISTEN과 GPU의 CARLA 프로세스가 남지 않았음을 확인했다. 종료 원문 일부는 server_shutdown_excerpt.txt에 보존했다. G3 연결 PASS와 정상 서버 종료 실패를 구분한다.
- `bash tools/run_self_checks.sh check`: 종료코드 0, 전체 119개 OK, pip check/셸 문법/Git 공백 검사 통과. 실제 명령/출력은 evidence/g3/integration-20261101-01/gate_checks.json. 합성 로그와 API 대역의 단위 검사를 실제 G3 관측으로 대체하지 않았다.
- docs/G3_INTEGRATION.md에 검토 코드, 두 터미널 직접 실행, 결과 파일과 판정 방법을 추가했다. README/STATUS/LINUX_HANDOFF/SELF_CHECK/G3_PROGRESS/G3_ADAPTER_STEP를 현재 단계로 갱신했다. 새 코드 설명과 주석/docstring은 한글이다. 과거 raw 증거와 소스는 번역하지 않았다. 최종 문서/JSON/해시 및 공개 범위 점검 결과는 같은 evidence/g3/integration-20261101-01/final_review.json에 기록한다.
- 이번 범위는 G3 첫 실제 통합까지다. 새 설치/의존성 변경, 연구 수치 변경, 거리 입력 A/B SUT나 G4, 예비/본시험 구현과 실행은 하지 않았다. G4 NOT_RUN, 본시험 0/80회. Juwon님의 새 코드 검토와 직접 G3 재현은 아직 기록이 없다. 이후 최소 거리 메시지 제어기와 기동/arm 전이를 단계적으로 구현한다. 장시간 무인 시험 전에는 서버 종료 문제를 별도 점검한다.
- 검증한 코드/문서/작은 증거를 Conventional Commit으로 로컬 저장한다. 이번 작업은 push와 브랜치 변경을 하지 않는다. 실제 커밋 결과는 git log/status로 확인한다.
- 최종 문서 로컬 링크 159개, 변경/추가 자료 49개(점검 기록 자체를 쓰기 전 목록), JSON/JSONL 23개를 확인했다. 6개 실행 모듈은 현재/보존 소스 모두 metadata SHA와 일치했다. Git 공백, 새 파일 후행 공백, 고정 연구 문서 무변경과 credential 형태 혼입 검사를 통과했다. 점검 대상 최대 파일은 차량 원시 로그 178251바이트다. evidence_manifest.json에는 실제 실행 및 이번 마감 근거의 경로/크기/SHA를 기록한다.

## 2026-11-01: 사용자 요청에 따른 G3 게시와 다음 작업 인수인계

- 사용자가 G3까지 push하고 G4는 다음날 진행하도록 요청했다. 작업 시작 시 main은 origin/main보다 3개 커밋 앞이었고 작업 폴더는 깨끗했다. 대상은 cf5f98b, d295771, 4815250이며 새 G4 구현이나 실험은 추가하지 않았다.
- README/STATUS/LINUX_HANDOFF와 기존 검사 근거를 확인했다. G3 실제 판정 PASS, 전체 검사 119개 종료코드 0 및 최종 검토 PASS를 확인했다. 코드 변경이 없는 게시 작업이므로 단위 검사와 CARLA 실행을 반복하지 않았다.
- `git ls-remote --exit-code origin refs/heads/main`의 시작 SHA는 9109b3c1d7208f570aeb681fb62a122f1dc0d898였다. `git push origin main`은 종료코드 0, 9109b3c..4815250 main -> main으로 완료됐다. 이후 직접 원격 조회는 4815250f531bcabcb7dce1d676b4ab5a838a038d로 로컬 HEAD와 일치했고, git status는 변경 없이 main/origin/main 동기 상태였다.
- STATUS/LINUX_HANDOFF에서 이전 작업 당시의 push 미수행 표시를 실제 게시 결과로 갱신했다. 이 기록과 다음날 재개 안내를 별도 문서 커밋으로 저장하고 같은 main에 push한다. 변경은 세 문서뿐이며 Git 공백과 문서 링크를 점검한다. 강제 push, 브랜치 변경이나 새 설치는 하지 않는다.
- 다음 재개 범위: 현재 Git/vcan0/서버 상태 확인, 사용자 G3 검토 및 직접 재현 상태 확인, 이후 G4 최소 거리 입력 제어기와 기동/arm 전이를 작은 단계로 진행한다. G4 NOT_RUN, 본시험 0/80회와 서버 종료 Signal 11/139 미해결을 유지한다.
- 문서 점검 결과: `git diff --check` 종료코드 0, 변경 문서 3개의 로컬 링크 39개 정상. 기능 코드와 기존 실행 증거는 변경하지 않았다.

## 2026-11-01: 20쪽 본문을 위한 목차 축소

- 사용자가 진행 상태를 확인하고 기존 목차의 중복과 과도한 세분화를 줄이도록 요청했다. 사용자는 앞선 확인에서 완료 범위를 G3까지로 명확히 했다.
- GitHub main `bcfa487a6e546e045c21ebb44ae30dd03df1b284`의 README/STATUS/LINUX_HANDOFF, 설계 기준선, 검증 명세, 기존 목차와 G3 실행 근거를 검토했다. G3 연결 PASS와 G4 미실행, 거리 판단 SUT 미구현, 본시험 0/80회를 구분했다. 서버 종료 Signal 11/139는 미해결로 유지한다.
- docs/THESIS_OUTLINE.md를 6장에서 5장, 10개 절로 줄였다. 서론 2절, 관련 기술 2절, 검증 시스템 및 시험 방법 4절, 시험 결과 및 분석 2절, 결론은 절 구분 없이 구성한다.
- 기존 설계와 시험 방법을 제3장으로 합쳤다. 기술 원리/본 연구 설계/실제 결과의 역할을 나눠 요구사항, 시나리오와 판정 설명의 중복을 줄였다. 설치 및 실행 로그 전체와 코드 목록은 본문에 옮기지 않는다.
- 표와 그림을 포함한 본문 목표를 2+2+8+7+1=20쪽으로 배분했다. 결과 분량은 시험 완료 후 집필 계획이며, 학과의 최소 분량 산정 규정을 새로 확인했다는 뜻은 아니다.
- 제출한 작성계획서와 HWP 원본, RESEARCH_BASELINE.md와 VALIDATION_PLAN.md의 v1.0 설계 및 수치는 변경하지 않았다. 기능 코드, 과거 실행 증거와 실험 상태도 변경하지 않았다.
- 로컬의 `git status --short --branch`에서 기존 체크아웃의 변경 없음과 이전 기준선 HEAD를 확인했다. `git fetch origin main`은 DNS 해석 실패(exit 1)로 완료되지 않았다. GitHub 연결 도구로 최신 main과 세 문서의 원문을 읽고 해당 head에 대한 문서 변경만 준비했다. 로컬 체크아웃 동기화 성공으로 표현하지 않는다.
- 변경 문서의 목차 수, 목표 분량 합계, 상태 유지, 로컬 상대 링크와 공백을 정적으로 확인한 뒤 GitHub 연결 도구로 문서 3개를 한 커밋에 게시한다. 문서만 변경하므로 단위 검사나 CARLA/vCAN 실험을 재실행하지 않는다. 실제 게시 여부는 도구 결과와 원격 ref로 확인한다.
- 다음 구현 단계는 기존 인수인계대로 사용자 G3 검토/직접 재현 상태 확인 후 G4 최소 거리 메시지 판단 연결이다. 집필은 새 목차에 맞춰 기존 1장과 3장 내용을 재배치하고 실측 결과는 확보한 범위까지만 적는다.

## 2026-11-01: 새 목차에 따른 제1~3장 본문 작성

- 사용자가 축소한 목차의 본문을 요청했고, 비동기 범위 확인에서 현재 작성 가능한 1~3장을 한 번에 받기를 선택했다.
- 새 5장 목차를 기준으로 docs/THESIS_CHAPTERS_1_3.md를 작성했다. 1장은 배경과 목적, 2장은 필요한 기술 원리, 3장은 요구사항/구조, 메시지/로직, 환경/시나리오, 지표/판정으로 구성했다.
- 연구 설계 v1.0의 메시지 바이트, 50 ms 송신, 200 ms 만료, 200 cm 판단, arm/정지 잠금, 네 시나리오, 80개 원래 시도와 시간 경계를 대조했다. 논문 구성 축소를 이유로 판정 기준을 삭제하거나 바꾸지 않았다.
- SocketCAN 공식 문서, AUTOSAR CP R24-11 E2E Library, CARLA 원 논문과 0.9.15 API/동기 문서 및 고정 커밋의 Yes, CARLA CAN 소스를 확인했다. 참고문헌의 번호와 접속일을 정리했다. AUTOSAR 프로파일 구현이나 실차 센서 최신성 검증을 주장하지 않았다.
- 실제 환경은 기존 G3 문서와 증거를 인용하고, 거리 판단 SUT/G4/예비/본시험은 미수행 상태에 맞춰 설계와 계획으로 서술했다. G3 연결 성공을 네 시나리오 검증 결과로 확대하지 않았다.
- 제출한 계획서/HWP, RESEARCH_BASELINE.md, VALIDATION_PLAN.md와 과거 실행 증거는 변경하지 않았다. 기능 코드와 새 실험도 추가하지 않았다.
- 본문을 기준선 및 시험명세와 독립 대조하여 정상 Ackermann 경로, 입력 종료 후 관측 범위와 신규 타임아웃 제외, T-02 경계 슬롯의 설명을 보완했다. 환경 수치의 출처는 최초 점검/설치 기록과 G3 기록으로 나누었다.
- 본문의 장/절 수, 표와 수식 번호, 인용/참고문헌 대응 및 기존 설계값을 정적으로 점검한 뒤 STATUS와 WORKLOG를 함께 한 문서 커밋으로 공유한다. 실제 HWP 편집이나 페이지 수 확인은 수행하지 않았다.
- 다음 구현은 기존 G4 인수인계를 따른다. 집필 후속은 실제 코드/시험 결과와 본문 대조 및 확보한 결과에 대한 제4장 작성이다.
