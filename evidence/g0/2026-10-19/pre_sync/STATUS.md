# Project status

Updated: 2026-10-19

## Latest published state and checkout alignment

GitHub main was verified at `94411a45aac647a0b9b0c811606d74c8f30d1df2` on 2026-10-19. Its current state is **DESIGN_BASELINED / IMPLEMENTATION_NOT_STARTED**. v1.0 fixes the study values, message contract, four scenarios, eighty planned main-test attempts and latched-stop policy. Implementation and runtime evidence remain absent; G0 through G4 remain NOT_RUN.

The original local checkout still has HEAD `62a193ae252925fcbac3e6371a373adda8800848` and the prior uncommitted analysis. The latest published revision was reviewed in an isolated temporary checkout to preserve those changes. It has not been pulled into this original working tree. Read [REVISION_REVIEW_2026-10-19.md](REVISION_REVIEW_2026-10-19.md) for permanent revision links, the reading order and current handoff.

The sections below preserve the 2026-10-15 local analysis. Their DOCS_ONLY label and unresolved-design list are historical and are superseded by the published v1.0 decisions above. Next technical work is to obtain the published baseline without losing local edits, then perform G0 followed by G1 and G2.

## Historical local state (2026-10-15)

**DOCS_ONLY**

The thesis planning and source audit are recorded. No thesis implementation, Linux setup or runtime integration has been performed by this project.

On 2026-10-15, the repository was reviewed for thesis scope, comparison validity and missing definitions. The user confirmed that advisor review has not yet taken place and that no additional implementation or CARLA/vCAN results exist. See [THESIS_REVIEW](THESIS_REVIEW.md). This is documentation analysis, not runtime validation; all feasibility gates remain NOT_RUN.

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

## Historical unresolved decisions (superseded by v1.0)

- Advisor approval and final title (user confirmed advisor review has not yet taken place on 2026-10-15)
- Distance-input source and normal no-detection representation
- Message IDs, payloads, counter width and units
- Transmission period and timeout
- Stop threshold, initial speed and permitted response delay
- Recovery, latching and re-enable policy
- Clock strategy under the actual simulator execution mode
- Number of trials and statistical summary
- Final Python/dependency versions and CARLA version
- Project license for original future code

## Historical next task (2026-10-15)

Review the proposed thesis question, contribution and scope with the advisor. The documentation analysis is available in [THESIS_REVIEW](THESIS_REVIEW.md).

Next technical task: start on Ubuntu in this repository, read the handoff documents and perform G0.
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
