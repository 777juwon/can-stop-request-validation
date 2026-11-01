#!/usr/bin/env python3
"""G3 요청 수신과 제동 호출을 연결하는 핵심 코드다.

차량 생성, 주행 준비, CAN socket과 동기 tick은 다음 통합 실행기가 맡는다.
이 파일의 demo는 가짜 제동 콜백만 사용하며 CAN이나 CARLA를 실행하지 않는다.
지원 범위 밖의 입력은 호출자에게 예외로 전달한다. 그 예외가 실제 차량에서
어떤 안전 대응을 일으킬지는 여기에서 확정하지 않는다.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import struct
import time
from typing import Callable


CALL_LIMIT_NS = 50_000_000


class G3InputError(ValueError):
    """이번 G3에서 지원하는 정상 요청 범위에 속하지 않는 입력이다."""


class AdapterCallError(RuntimeError):
    """호출 또는 관측 근거에 오류가 있어 이번 실행을 계속할 수 없다."""


@dataclass(frozen=True)
class StopRequest:
    stop: bool
    reason: int
    counter: int
    run_token: int


def parse_supported_request(raw: bytes, expected_token: int) -> StopRequest:
    """G3의 정상 입력만 해석한다. 입력 범위 검사를 오류 대응 정책과 구분한다.

    정상 상태는 stop=0/reason=NORMAL, 정지는 stop=1/정의된 정지 원인이다.
    다른 조합을 손상 프레임이라고 진단하지 않고 지원 범위 밖으로 전달한다.
    counter는 기록만 하며 순번 watchdog이나 재생 검사는 추가하지 않는다.
    """
    if type(expected_token) is not int or not 0 <= expected_token <= 0xFFFFFFFF:
        raise ValueError("expected_token은 uint32 정수여야 합니다")
    if not isinstance(raw, bytes) or len(raw) != 16:
        raise G3InputError("16바이트 Classic CAN 프레임이 필요합니다")
    can_id, dlc, payload = struct.unpack("=IB3x8s", raw)
    if can_id != 0x200 or dlc != 8:
        raise G3InputError("표준 데이터 ID 0x200, DLC8 요청만 지원합니다")
    stop, reason, counter, reserved, token = struct.unpack("<BBBBI", payload)
    if reserved != 0 or token != expected_token:
        raise G3InputError("예약 byte 또는 현재 run_token이 일치하지 않습니다")
    if not ((stop == 0 and reason == 0) or (stop == 1 and 1 <= reason <= 4)):
        raise G3InputError("이번 G3의 정상 stop/reason 범위 밖 입력입니다")
    return StopRequest(bool(stop), reason, counter, token)


class BrakeAdapterCore:
    """검사된 요청을 제동 콜백에 연결한다. 스스로 가속하거나 tick하지 않는다.

    콜백은 G2 apply_brake_control과 같은 응답을 반환해야 한다. 응답 성공은
    호출 성공일 뿐 실제 차량 적용 증거가 아니다. 오류 후에는 이 객체를
    재사용하지 않으며, 다음 통합 실행기가 종료와 자원 정리를 담당한다.
    이 객체는 준비와 명시적 arm 이후의 G3 구간에 사용한다. 기동 억제에서
    arm으로 넘어가는 전이와 reset API는 구현하지 않는다.
    """

    def __init__(self, *, actor_id: int, run_token: int,
                 apply_brake: Callable[[], dict], clock: Callable[[], int] = time.monotonic_ns):
        if type(actor_id) is not int or actor_id <= 0:
            raise ValueError("양수 actor_id가 필요합니다")
        if type(run_token) is not int or not 0 <= run_token <= 0xFFFFFFFF:
            raise ValueError("run_token은 uint32 정수여야 합니다")
        self.actor_id = actor_id
        self.run_token = run_token
        self.apply_brake = apply_brake
        self.clock = clock
        self.stop_latched = False
        self.first_reason = None
        self.faulted = False
        self.events: list[dict] = []

    def on_frame(self, raw: bytes, *, received_ns: int | None = None) -> dict:
        """호스트 수신 시각에서 제어 호출 완료까지를 따로 남긴다."""
        if self.faulted:
            raise AdapterCallError("오류가 난 adapter는 새 실행 전까지 재사용할 수 없습니다")
        rx = self.clock() if received_ns is None else received_ns
        if type(rx) is not int or rx < 0:
            raise ValueError("received_ns는 호스트 monotonic 정수여야 합니다")
        event = {"event": "request", "actor_id": self.actor_id, "a_rx_ns": rx,
                 "raw_frame_hex": raw.hex() if isinstance(raw, bytes) else None}
        self.events.append(event)
        try:
            request = parse_supported_request(raw, self.run_token)
        except G3InputError as exc:
            self.faulted = True
            event.update(action="UNSUPPORTED_INPUT", error=str(exc))
            raise
        event["request"] = asdict(request)
        if request.stop and not self.stop_latched:
            self.stop_latched = True
            self.first_reason = request.reason
        event.update(stop_latched=self.stop_latched, first_reason=self.first_reason)
        if not self.stop_latched:
            event["action"] = "KEEP_EXISTING_CONTROL"
            return event

        # 최초 정지 원인을 유지하고 이후 정상 요청에서도 제동만 다시 요청한다.
        event["action"] = "APPLY_FULL_BRAKE"
        try:
            begin = self.clock()
            if type(begin) is not int or begin < rx:
                raise AdapterCallError("호스트 호출 시작 시각이 수신 시각보다 이릅니다")
            event["call_begin_ns"] = begin
            response = self.apply_brake()
            done = self.clock()
            if type(done) is not int or done < begin:
                raise AdapterCallError("호스트 호출 완료 시각이 시작 시각보다 이릅니다")
            event.update(a_done_ns=done, response=response)
            if (not isinstance(response, dict) or response.get("actor_id") != self.actor_id
                    or response.get("error") != "" or response.get("do_tick_cue") is not False):
                raise AdapterCallError("제동 응답의 actor, 오류 또는 자동 tick 설정 불일치")
            event.update(call_completed=True, processing_duration_ns=done - rx,
                         call_within_50ms=done - rx <= CALL_LIMIT_NS)
        except BaseException as exc:
            self.faulted = True
            event.update(call_completed=False, error=str(exc))
            # 사용자의 취소는 다른 오류로 바꾸지 않고 상위 정리 경로로 보낸다.
            if not isinstance(exc, Exception):
                event["interrupted"] = True
                raise
            if isinstance(exc, AdapterCallError):
                raise
            raise AdapterCallError("제동 호출이 실패했습니다: " + str(exc)) from exc
        return event


def demo() -> dict:
    """실제 CAN/CARLA 없이 정상 → 정지 → 정상 입력의 흐름을 보여준다."""
    calls = []

    def fake_brake():
        calls.append("brake")
        return {"actor_id": 77, "error": "", "do_tick_cue": False,
                "transport": "DEMO_CALLBACK"}

    adapter = BrakeAdapterCore(actor_id=77, run_token=0x12345678, apply_brake=fake_brake)
    for counter, (stop, reason) in enumerate(((0, 0), (1, 1), (0, 0))):
        payload = struct.pack("<BBBBI", stop, reason, counter, 0, 0x12345678)
        adapter.on_frame(struct.pack("=IB3x8s", 0x200, 8, payload))
    return {"scope": "G3_ADAPTER_DEMO_ONLY", "actual_can": False, "carla_executed": False,
            "description": "가짜 콜백 예제입니다. 실제 송수신과 차량 적용 결과가 아닙니다.",
            "brake_callback_count": len(calls), "events": adapter.events}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="실제 통신 없는 예제 실행")
    args = parser.parse_args()
    if not args.demo:
        parser.error("이번 파일은 핵심 모듈입니다. 예제는 --demo로 실행하세요")
    print(json.dumps(demo(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
