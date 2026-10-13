# Validation plan

Status: **PROPOSED / NOT_EXECUTED**

All requirements and numerical thresholds below are pending definition. No response time, safe-stop threshold or production safety claim is approved by this document.

## Research question

In a low-speed stop-request demonstrator, can receive-timeout monitoring distinguish normal input from missing distance messages? What happens if frames keep arriving but the distance information's sequence does not advance? How does adding a sequence/freshness check change the observed response?

This compares explicitly defined software behaviors under controlled application-level message faults. It is not a claim to diagnose an actual physical sensor failure.

## Requirements draft

| Draft ID | Requirement intent | Needed evidence | Values/policy |
| --- | --- | --- | --- |
| R-NORMAL-01 | Do not request stop when input is healthy and no stop condition exists | Normal input, SUT output and sink log | TBD |
| R-NORMAL-02 | Generate stop request when valid input satisfies the defined distance condition | Distance history and request timestamp | TBD |
| R-MISSING-01 | Perform the defined response after target distance updates cease | Last accepted input, injection boundary and request time | Timeout and permitted delay TBD |
| R-REPEAT-01 | Do not count identical sequence repetitions as new distance updates | Payload/counter history and accepted-update log | Counter width and rules TBD |
| R-DELIVERY-01 | Demonstrate request reception and application separately | Sent request ID, sink receive/apply record | Application response contract TBD |
| R-RECOVERY-01 | Respond to restored fresh input according to an explicit policy | Restore event and state transition history | Policy TBD |
| R-MOTION-01 | If vehicle motion is claimed, confirm it using simulator state | CARLA velocity and control/frame history | Speed criterion and observation window TBD |

These are draft requirement intents, not final acceptance criteria. The user and advisor must review the scope and relevant decisions.

## Controlled comparison

Candidate A: target-message receive-timeout monitoring.

Candidate B: the same timeout monitoring plus a defined sequence-progress check.

Use identical scenario inputs and the same predefined oracle. Change only the monitoring behavior being compared. Hold the message contract and other operating conditions constant where applicable.

Do not repair Candidate A after seeing the result merely to make the demonstration pass. It is legitimate for the simpler design to fail a requirement it cannot observe, provided the scope and interpretation are stated.

An alive counter can show transmission progress. It does not independently prove fresh physical sensing unless the sender's sampling behavior or measurement timestamp is also defined.

## Core cases

### T-NORMAL-FAR: Negative control

Distance messages and their counter advance normally; the stop condition is absent.

Check that the controller does not make an unnecessary stop request. A controller that always stops cannot pass solely because fault cases lead to stopping.

### T-NORMAL-NEAR: Normal obstacle approach

Healthy distance data crosses the defined stop condition.

Check request occurrence and downstream application. If claiming actual vehicle stop, check the simulator's actual state, not only a brake command.

### T-MISSING: Target input stops

Stop the target distance publisher while any other required normal messages remain present.

Check the target-message deadline and response. A bus-wide receive timeout can be masked by unrelated frames and is not automatically equivalent to target-message monitoring.

### T-REPEAT: Same old frame continues

Freeze the target payload and counter at a previously valid value while frames continue arriving.

Check whether each design distinguishes frame arrival from new information. Sending a constant distance while incrementing the counter is not this fault.

## Boundary and robustness cases to consider

- Constant distance with increasing counter should not be classified as repetition solely because distance is unchanged.
- Counter rollover should follow the documented wrap rule.
- Normal arrival variation should be characterized before selecting a timeout margin.
- Unsupported IDs and malformed payloads should not crash the receiver.
- Restored information must follow a stated recovery/re-enable policy.
- No-target state must be distinct from missing communication.

Do not expand the thesis to every candidate case before the feasibility gates and core comparison work.

## Independent oracle

The test runner/logger must record observable events and compare them to requirements. Do not use only the SUT's internal PASS label or state variable as the expected result.

Useful evidence fields:

- Run ID, case ID, implementation variant and configuration hash
- Target CAN ID, DLC, payload, decoded distance/status/counter
- Host monotonic send and receive times where observed
- Accepted fresh-input time and reason for rejection
- Fault injection begin/end events
- Stop request ID/reason and send time
- Sink receive and apply times
- Application response, clearly distinguished from CAN ACK
- CARLA actor ID, frame, simulation elapsed time and actual velocity
- PASS/FAIL with violated requirement and supporting evidence paths

Exact fields and formats should be finalized during implementation.

## Time model

Initial reference bridges use host monotonic time for watchdogs. This is a starting reference, not a finalized thesis clock strategy.

If synchronous CARLA is used, document who owns world.tick and how host-time CAN events relate to simulation frames. Do not subtract timestamps from different time bases or assume a 50 ms simulation step implies 50 ms of real time.

Characterize simulator/host stalls and scheduling effects before interpreting response times. A rendering stall is not automatically a sensor-communication fault.

## Metrics and reporting candidates

- Requirement pass/fail counts by case and implementation
- Request response latency on a consistently defined clock
- Unnecessary stop requests in normal conditions
- Missed or late requests
- Request delivery and sink application evidence
- Vehicle speed evolution if the physical simulation is included

Trial counts, aggregation and timing tolerances are TBD. No measured results exist yet.

## Interpretation limits

vCAN verifies application-level message transport and software response. It does not reproduce physical arbitration timing, controller hardware faults, electrical noise or bus-off.

A received application response does not prove real ECU execution. CARLA braking behavior does not prove production vehicle braking performance.

The conclusion should identify which requirements were satisfied, where the simpler monitor was insufficient, and what remains outside the test model.
