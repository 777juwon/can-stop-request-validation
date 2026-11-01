"""고정 기준선 B 방식의 거리 수신 및 순번 갱신 감시 상태 기계다."""

import struct

from tools.g4_controller_core import (
    ARMED, INIT_INHIBITED, MAX_DISTANCE_CM, NEAR_DISTANCE, NEAR_DISTANCE_CM,
    RX_TIMEOUT, RX_TIMEOUT_NS, DistanceTimeoutController,
)


NO_SEQUENCE_PROGRESS = 3


class SequenceProgressController(DistanceTimeoutController):
    """유효 수신과 신규 순번 인정을 구분한다. A의 기동/잠금 규칙을 유지한다."""

    def __init__(self, run_token, started_ns):
        self.last_progress_rx_ns = None
        super().__init__(run_token, started_ns)

    def snapshot(self):
        return {**super().snapshot(), "variant": "B", "last_progress_rx_ns": self.last_progress_rx_ns}

    def _evaluate(self, now_ns):
        if self.state != ARMED:
            return
        if now_ns - self.last_valid_rx_ns >= RX_TIMEOUT_NS:
            self._latch(RX_TIMEOUT, now_ns)
        elif now_ns - self.last_progress_rx_ns >= RX_TIMEOUT_NS:
            self._latch(NO_SEQUENCE_PROGRESS, now_ns)
        elif self.distance_cm <= NEAR_DISTANCE_CM:
            self._latch(NEAR_DISTANCE, now_ns)

    def arm(self, now_ns):
        self._advance_clock(now_ns)
        if (self.state == INIT_INHIBITED and self.last_progress_rx_ns is not None
                and now_ns - self.last_progress_rx_ns >= RX_TIMEOUT_NS):
            self._reject_arm(now_ns, "STALE_PROGRESS", "마지막 인정 순번이 200ms 미만으로 신선해야 합니다")
        super().arm(now_ns)

    def on_frame(self, raw, received_ns):
        """반복/거절 순번은 유효 수신 시각만 갱신하고 거리와 인정 순번은 유지한다."""
        if not isinstance(raw, bytes):
            raise TypeError("raw는 bytes 타입이어야 합니다")
        self._advance_clock(received_ns)
        self._evaluate(received_ns)
        event = {"event": "rx", "host_monotonic_ns": received_ns, "received_ns": received_ns,
                 "run_token": self.run_token, "raw_frame_hex": raw.hex(), "accepted": False}
        if len(raw) != 16:
            event["action"] = "REJECT_LENGTH"
        else:
            can_id, dlc, payload = struct.unpack("=IB3x8s", raw)
            event.update(can_id=can_id, dlc=dlc)
            if can_id & ~0x7FF:
                event["action"] = "REJECT_FLAGS"
            elif dlc != 8:
                event["action"] = "REJECT_DLC"
            elif can_id == 0x101:
                event["action"] = "IGNORE_BACKGROUND"
            elif can_id != 0x100:
                event["action"] = "IGNORE_ID"
            else:
                distance, counter, valid, token = struct.unpack("<HBBI", payload)
                event.update(distance_cm=distance, counter=counter, valid=valid, input_run_token=token)
                if token != self.run_token:
                    event["action"] = "REJECT_TOKEN"
                elif valid != 1:
                    event["action"] = "REJECT_VALID"
                elif distance > MAX_DISTANCE_CM:
                    event["action"] = "REJECT_DISTANCE"
                else:
                    self.last_valid_rx_ns = received_ns
                    delta = None if self.last_counter is None else (counter - self.last_counter) % 256
                    event.update(valid_input=True, delta=delta)
                    if delta is None or 1 <= delta <= 127:
                        self.last_progress_rx_ns = received_ns
                        self.distance_cm, self.last_counter = distance, counter
                        if distance > NEAR_DISTANCE_CM:
                            self.valid_normal_count += 1
                        event.update(action="ACCEPT_FIRST" if delta is None else "ACCEPT_PROGRESS", accepted=True)
                    else:
                        event["action"] = "IGNORE_REPEAT" if delta == 0 else "REJECT_SEQUENCE"
        self.events.append(event)
        self._evaluate(received_ns)
        event.update(state=self.state, reason=self.reason, stop=self.stop,
                     last_valid_rx_ns=self.last_valid_rx_ns,
                     last_progress_rx_ns=self.last_progress_rx_ns,
                     last_accepted_counter=self.last_counter, accepted_distance_cm=self.distance_cm,
                     valid_normal_count=self.valid_normal_count)
        return event
