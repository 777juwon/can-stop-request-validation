# Public source audit

Audit date: 2026-10-13

Evidence level: **source code and published test inspection only**. No code in this audit has been executed in the user's Ubuntu environment.

## 1. Yes, CARLA CAN

Repository: https://github.com/luigiluz/yes-carla-can
First reproduction source candidate: eee3c5224ab2941edb08dfa8f4a4f735e7f981d6
License reported by upstream: MIT

The source candidate is a CAN-focused earlier revision. The inspected main at audit time was 765c9be154da3b23efadaf94dcae9905e630e5e2, which adds AVTP-related startup configuration. Do not treat latest main and the earlier source candidate as interchangeable.

### Confirmed code paths

- [can_network/network.py](https://github.com/luigiluz/yes-carla-can/blob/eee3c5224ab2941edb08dfa8f4a4f735e7f981d6/can_network/network.py): python-can SocketCAN bus, DBC encode/decode and received VehicleControl construction.
- [gui/keyboard_control.py](https://github.com/luigiluz/yes-carla-can/blob/eee3c5224ab2941edb08dfa8f4a4f735e7f981d6/gui/keyboard_control.py): receives controls and calls world.player.apply_control.
- [sensors/radar.py](https://github.com/luigiluz/yes-carla-can/blob/eee3c5224ab2941edb08dfa8f4a4f735e7f981d6/sensors/radar.py): CARLA radar detections are forwarded as CAN target messages.
- [data/carla.dbc](https://github.com/luigiluz/yes-carla-can/blob/eee3c5224ab2941edb08dfa8f4a4f735e7f981d6/data/carla.dbc): example message/signals, not an OEM vehicle specification.
- [requirements.txt](https://github.com/luigiluz/yes-carla-can/blob/eee3c5224ab2941edb08dfa8f4a4f735e7f981d6/requirements.txt): carla 0.9.15, python-can 4.6.1, cantools 40.7.1.
- [README](https://github.com/luigiluz/yes-carla-can/blob/eee3c5224ab2941edb08dfa8f4a4f735e7f981d6/README.md): author reports Ubuntu 22.04/Debian tests and Python 3.9.
- [startup script](https://github.com/luigiluz/yes-carla-can/blob/eee3c5224ab2941edb08dfa8f4a4f735e7f981d6/1_up_environment.sh): simulator startup and virtual interfaces. Extra cybersecurity networking is not needed here.

### Limitations and adaptation work

- Radar transmission follows detections, not a guaranteed periodic health/status message.
- Missing radar detections cannot alone prove communication interruption.
- The existing distance schema does not provide the thesis counter/validity contract.
- The receiver keeps the last control when no new frame is received; the desired stop watchdog is not already provided.
- Decode/dispatch exception handling must be reviewed before adding new or malformed message IDs.
- The client uses no-rendering mode; camera output behavior must not be confused with a sensor implementation failure.
- Upstream tests mock CARLA and SocketCAN. They are not local end-to-end simulator proof.
- Installation scripts change the system and may use external download mirrors. Inspect them and prefer official simulator distribution.
- We are not using the attack, flooding or IDS features as thesis requirements.

## 2. Autoware Safety Island

Repository: https://github.com/autowarefoundation/autoware-safety-island
Inspected revision: 243af978c47f1020295b1a03e722cc4604b759da
License reported by upstream: Apache-2.0

### Confirmed files

- [bridge.py](https://github.com/autowarefoundation/autoware-safety-island/blob/243af978c47f1020295b1a03e722cc4604b759da/demo/can_carla_bridge/bridge.py): SocketCAN RX, monotonic watchdog, conversion to VehicleAckermannControl and vehicle.apply_ackermann_control.
- [decoder.py](https://github.com/autowarefoundation/autoware-safety-island/blob/243af978c47f1020295b1a03e722cc4604b759da/demo/can_carla_bridge/decoder.py): command-batch completeness, sequence progress/replay rejection, receive-timeout safe-stop state.
- [test_decoder.py](https://github.com/autowarefoundation/autoware-safety-island/blob/243af978c47f1020295b1a03e722cc4604b759da/demo/can_carla_bridge/test_decoder.py): missing component, duplicate/stale sequence, payload length, wrap and watchdog assertions.
- [test_vcan_roundtrip.py](https://github.com/autowarefoundation/autoware-safety-island/blob/243af978c47f1020295b1a03e722cc4604b759da/demo/can_carla_bridge/test_vcan_roundtrip.py): Linux PF_CAN receive of C++ sender frames and decoder/watchdog assertions.
- [integration design](https://github.com/autowarefoundation/autoware-safety-island/blob/243af978c47f1020295b1a03e722cc4604b759da/documentation/design/can_carla_integration.rst): CARLA 0.9.16 reference and explicit statement that CI does not launch CARLA.

### Limitations

- This validates control-command messages, not our obstacle-distance stop-decision function.
- The design documentation includes broader planned layers. Do not infer all diagrams are proven local runtime configurations.
- Full RTOS/DDS/Autoware integration is outside this thesis's initial scope.
- Upstream recovery behavior is not automatically our approved recovery policy.
- The watchdog uses wall-clock monotonic time; it does not automatically implement simulation-time fault injection.

## 3. python-can

Repository: https://github.com/hardbyte/python-can
Inspected revision: b4f82abede25ff83376be793a2935c41f81c3869

- [test/test_cyclic_socketcan.py](https://github.com/hardbyte/python-can/blob/b4f82abede25ff83376be793a2935c41f81c3869/test/test_cyclic_socketcan.py): independent SocketCAN sender/receiver, repetition, modification and stopping periodic tasks.
- [examples/cyclic.py](https://github.com/hardbyte/python-can/blob/b4f82abede25ff83376be793a2935c41f81c3869/examples/cyclic.py): periodic sending and stop/modify/restart examples.
- [examples/crc.py](https://github.com/hardbyte/python-can/blob/b4f82abede25ff83376be793a2935c41f81c3869/examples/crc.py): cyclic frames containing a changing counter.
- [CI](https://github.com/hardbyte/python-can/blob/b4f82abede25ff83376be793a2935c41f81c3869/.github/workflows/ci.yml): Ubuntu SocketCAN test configuration.
- [test/open_vcan.sh](https://github.com/hardbyte/python-can/blob/b4f82abede25ff83376be793a2935c41f81c3869/test/open_vcan.sh): virtual interface preparation.

This proves component implementations are available. It does not provide our stop-request semantics or oracle. The inspected current Python requirement differs from the older CARLA reference environment; choose compatible library versions deliberately.

## 4. Official technical references

- [Linux SocketCAN and vCAN](https://docs.kernel.org/networking/can.html#the-virtual-can-driver-vcan)
- [CARLA 0.9.15 documentation](https://carla.readthedocs.io/en/0.9.15/)
- [CARLA synchronization and time step](https://carla.readthedocs.io/en/0.9.15/adv_synchrony_timestep/)
- [CARLA rendering options](https://carla.readthedocs.io/en/0.9.15/adv_rendering_options/)
- [python-can SocketCAN interface](https://python-can.readthedocs.io/en/stable/interfaces/socketcan.html)
- [cantools](https://cantools.readthedocs.io/en/latest/)

## Reuse discipline

Record the upstream repository, commit, original files, license and our modifications before importing code. Preserve required notices. Cite the implementation in the thesis and state which parts were directly implemented for this study.

A source path or upstream expected test output is not evidence that we ran it. Future local reproduction must have a separate dated record, commands, exit status and logs.
