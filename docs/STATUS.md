# Project status

Updated: 2026-10-16

## Current state

**DESIGN_BASELINED / IMPLEMENTATION_NOT_STARTED**

The user requested final implementation documents without modifying the already submitted thesis proposal. RESEARCH_BASELINE.md, VALIDATION_PLAN.md and THESIS_OUTLINE.md now define v1.0. These documents fix research-only design values and test criteria, not measured results or advisor sign-off. No thesis implementation, Linux setup or runtime integration has been performed by this project.

The user authorized publishing this document baseline to GitHub on 2026-10-16. A Linux checkout must fetch this revision before relying on it; a shared repository does not automatically update another local checkout.

## Completion checklist

| Work item | Status | Evidence |
| --- | --- | --- |
| Study scope and requirements fixed | DONE | RESEARCH_BASELINE.md and R-01~R-09 |
| Test scenarios and pass/fail rules fixed | DONE | VALIDATION_PLAN.md, T-01~T-04 |
| Thesis chapter structure fixed | DONE | THESIS_OUTLINE.md |
| Environment setup and minimum integration | NOT_RUN | G0~G4 below |
| Implementation and unit tests | NOT_STARTED | No implementation code |
| Preliminary test execution and result summary | NOT_RUN | No execution logs or measurements |
| Main comparison runs and result analysis | NOT_RUN | No experimental results |

Writing a scenario, checklist or expected result does not complete a preliminary experiment. No preliminary-test result is included in this revision.

## Evidence levels

| Item | Evidence | What is not proved |
| --- | --- | --- |
| Ubuntu 22.04 available | User reports dual-boot installation | Current Linux packages, drivers or vCAN support |
| Laptop GPU | Prior Windows diagnostic: RTX 4060 Laptop, about 8 GB VRAM | Ubuntu driver health or CARLA runtime performance |
| CARLA / vCAN bridge | Public source code inspected | Local end-to-end execution |
| Watchdog / sequence logic | Public source and tests inspected | Our distance-message controller |
| Fault injection / logging | Existing component code inspected | Our full scenario runner and oracle |
| Current repository | Planning and handoff files prepared | A working simulator or passing experiment |

## Feasibility gates

Every gate below is **NOT_RUN**. A future worker must attach actual evidence before changing it.

| Gate | Description | Status | Evidence |
| --- | --- | --- | --- |
| G0 | Inspect Ubuntu, GPU, disk, Python and git | NOT_RUN | None |
| G1 | Independent vCAN publisher and receiver exchange known frames | NOT_RUN | None |
| G2 | CARLA standalone vehicle control and actual velocity query | NOT_RUN | None |
| G3 | vCAN control reception changes CARLA vehicle state | NOT_RUN | None |
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
- No numerical results exist. All feasibility gates above remain NOT_RUN.

## Remaining execution records and approvals

- Advisor feedback, without inventing individual parameter approval
- Actual Python/dependency versions and CARLA server/client compatibility
- Actual map/spawn and vehicle-physics records before main testing
- Implementation, independent logs and every feasibility gate result
- Project license for original future code

## Next task

Start on Ubuntu with the published v1.0 revision of this repository. Read the baseline and handoff documents and perform G0. If a Linux checkout already exists, synchronize without overwriting local changes.
Record the exact environment. Then plan G1 and G2 before large installation or feature development.

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
