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
