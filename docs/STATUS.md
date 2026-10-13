# Project status

Updated: 2026-10-13

## Current state

**DOCS_ONLY**

The thesis planning and source audit are recorded. No thesis implementation, Linux setup or runtime integration has been performed by this project.

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

## Unresolved decisions

- Advisor approval and final title
- Distance-input source and normal no-detection representation
- Message IDs, payloads, counter width and units
- Transmission period and timeout
- Stop threshold, initial speed and permitted response delay
- Recovery, latching and re-enable policy
- Clock strategy under the actual simulator execution mode
- Number of trials and statistical summary
- Final Python/dependency versions and CARLA version
- Project license for original future code

## Next task

Start on Ubuntu in this repository. Read the handoff documents and perform G0.
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
