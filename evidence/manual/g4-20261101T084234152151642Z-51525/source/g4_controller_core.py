"""G4의 A 방식 거리 판단을 담당하는 순수 상태 기계다.

호출자가 제공하는 호스트 monotonic 시각만 사용한다. CAN 송수신, CARLA 제어,
주기 실행과 독립 판정은 포함하지 않는다. 새 run은 새 객체로 시작한다.
"""

from __future__ import annotations

import struct


RX_TIMEOUT_NS = 200_000_000
STARTUP_LIMIT_NS = 30_000_000_000
MIN_NORMAL_INPUTS = 5
NEAR_DISTANCE_CM = 200
MAX_DISTANCE_CM = 10_000

INIT_INHIBITED = "INIT_INHIBITED"
ARMED = "ARMED"
STOP_LATCHED = "STOP_LATCHED"

NORMAL = 0
NEAR_DISTANCE = 1
RX_TIMEOUT = 2
INIT_REASON = 4


class G4ArmError(ValueError):
    """명시적 arm의 상태 또는 준비 조건을 충족하지 못했다."""


class DistanceTimeoutController:
    """유효 거리 수신의 중단을 감시하고 최초 정지 원인을 유지한다.

    A 방식이므로 같은 counter의 반복도 유효 수신으로 인정한다. 원거리
    입력은 누적 수를 세되 arm 시점의 마지막 거리도 원거리여야 한다.
    모든 시각은 started_ns 이후이며 메서드 호출 순서대로 비감소해야 한다.
    """

    def __init__(self, run_token: int, started_ns: int):
        if type(run_token) is not int or not 0 <= run_token <= 0xFFFFFFFF:
            raise ValueError("run_token은 uint32 정수여야 합니다")
        if type(started_ns) is not int or started_ns < 0:
            raise ValueError("started_ns는 음수가 아닌 호스트 monotonic 정수여야 합니다")
        self.run_token = run_token
        self.started_ns = started_ns
        self.state = INIT_INHIBITED
        self.reason = INIT_REASON
        self.stop = True
        self.valid_normal_count = 0
        self.last_valid_rx_ns: int | None = None
        self.distance_cm: int | None = None
        self.last_counter: int | None = None
        self._last_clock_ns = started_ns
        self.events: list[dict] = []
        self._record_transition(None, started_ns)

    def _advance_clock(self, now_ns: int) -> None:
        """잘못된 시각은 상태를 바꾸기 전에 거부한다."""
        if type(now_ns) is not int or now_ns < 0:
            raise ValueError("시각은 음수가 아닌 호스트 monotonic 정수여야 합니다")
        if now_ns < self._last_clock_ns:
            raise ValueError("호스트 monotonic 시각이 역행했습니다")
        self._last_clock_ns = now_ns

    def snapshot(self) -> dict:
        """현재 판단을 복사한다. 시각 경과에 따른 평가는 poll이 담당한다."""
        return {
            "run_token": self.run_token,
            "started_ns": self.started_ns,
            "last_clock_ns": self._last_clock_ns,
            "state": self.state,
            "reason": self.reason,
            "stop": self.stop,
            "valid_normal_count": self.valid_normal_count,
            "last_valid_rx_ns": self.last_valid_rx_ns,
            "distance_cm": self.distance_cm,
            "last_counter": self.last_counter,
        }

    def _record_transition(self, previous: str | None, now_ns: int) -> None:
        self.events.append({
            "event": "state_transition",
            "host_monotonic_ns": now_ns,
            "from_state": previous,
            **self.snapshot(),
        })

    def _latch(self, reason: int, now_ns: int) -> None:
        if self.state != ARMED:
            return
        previous = self.state
        self.state = STOP_LATCHED
        self.reason = reason
        self.stop = True
        self._record_transition(previous, now_ns)

    def _evaluate(self, now_ns: int) -> None:
        if self.state != ARMED:
            return
        # 수신 만료를 먼저 검사해 동시에 참인 근거리보다 우선한다.
        if now_ns - self.last_valid_rx_ns >= RX_TIMEOUT_NS:
            self._latch(RX_TIMEOUT, now_ns)
        elif self.distance_cm <= NEAR_DISTANCE_CM:
            self._latch(NEAR_DISTANCE, now_ns)

    def poll(self, now_ns: int) -> None:
        """입력이 없어도 만료를 검사한다. 기동 억제와 정지 잠금은 유지한다."""
        self._advance_clock(now_ns)
        self._evaluate(now_ns)

    def _reject_arm(self, now_ns: int, action: str, message: str) -> None:
        self.events.append({
            "event": "arm_rejected",
            "host_monotonic_ns": now_ns,
            "action": action,
            **self.snapshot(),
        })
        raise G4ArmError(message)

    def arm(self, now_ns: int) -> None:
        """준비된 INIT에서만 정지 억제를 해제하며 정지 잠금은 해제하지 않는다."""
        self._advance_clock(now_ns)
        self._evaluate(now_ns)
        if self.state != INIT_INHIBITED:
            self._reject_arm(now_ns, "NOT_INIT_INHIBITED", "INIT_INHIBITED 상태에서만 arm할 수 있습니다")
        if now_ns - self.started_ns >= STARTUP_LIMIT_NS:
            self._reject_arm(now_ns, "STARTUP_EXPIRED", "기동 준비의 30초 한도가 지났습니다")
        if self.valid_normal_count < MIN_NORMAL_INPUTS:
            self._reject_arm(now_ns, "INSUFFICIENT_NORMAL_INPUTS", "유효 원거리 입력 5개 이상이 필요합니다")
        if self.last_valid_rx_ns is None or now_ns - self.last_valid_rx_ns >= RX_TIMEOUT_NS:
            self._reject_arm(now_ns, "STALE_INPUT", "마지막 유효 거리 입력이 200ms 미만으로 신선해야 합니다")
        if self.distance_cm <= NEAR_DISTANCE_CM:
            self._reject_arm(now_ns, "NEAR_INPUT", "현재 입력이 원거리일 때만 arm할 수 있습니다")
        previous = self.state
        self.state = ARMED
        self.reason = NORMAL
        self.stop = False
        self._record_transition(previous, now_ns)

    def on_frame(self, raw: bytes, received_ns: int) -> dict:
        """원시 Classic CAN 입력을 진단하고 A 방식으로 유효 수신을 갱신한다.

        수신 시각의 만료를 새 입력보다 먼저 검사한다. 기한 뒤 복원된 입력은
        값과 수신 시각을 기록해도 이미 발생한 정지를 취소하지 못한다.
        """
        if not isinstance(raw, bytes):
            raise TypeError("raw는 bytes 타입이어야 합니다")
        self._advance_clock(received_ns)
        self._evaluate(received_ns)
        event = {
            "event": "rx",
            "host_monotonic_ns": received_ns,
            "received_ns": received_ns,
            "run_token": self.run_token,
            "raw_frame_hex": raw.hex(),
            "accepted": False,
        }
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
                event.update(distance_cm=distance, counter=counter, valid=valid,
                             input_run_token=token)
                if token != self.run_token:
                    event["action"] = "REJECT_TOKEN"
                elif valid != 1:
                    event["action"] = "REJECT_VALID"
                elif distance > MAX_DISTANCE_CM:
                    event["action"] = "REJECT_DISTANCE"
                else:
                    self.last_valid_rx_ns = received_ns
                    self.distance_cm = distance
                    self.last_counter = counter
                    if distance > NEAR_DISTANCE_CM:
                        self.valid_normal_count += 1
                    event.update(action="ACCEPT_DISTANCE", accepted=True)
        self.events.append(event)
        self._evaluate(received_ns)
        event.update(state=self.state, reason=self.reason, stop=self.stop,
                     last_valid_rx_ns=self.last_valid_rx_ns,
                     valid_normal_count=self.valid_normal_count)
        return event
