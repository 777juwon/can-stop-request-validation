"""분석한80개 원래 시도의 논문용 정적 그래프를 PNG/SVG/PDF로 저장한다."""

import hashlib
import os
from pathlib import Path
import sys
import tempfile

COLORS = {"A": "#0072B2", "B": "#D55E00"}
STYLES = {"A": "-", "B": "--"}
SCENARIOS = ("T-01", "T-02", "T-03", "T-04")


def render(output, records, cells, examples):
    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "can-stop-matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.patches import Patch
    import numpy as np

    font = Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf")
    if not font.exists():
        raise FileNotFoundError("한글 나눔고딕 글꼴을 찾을 수 없습니다: " + str(font))
    font_manager.fontManager.addfont(str(font))
    plt.rcParams.update({"font.family": font_manager.FontProperties(fname=str(font)).get_name(),
                         "font.size": 10, "axes.unicode_minus": False, "axes.spines.top": False,
                         "axes.spines.right": False, "pdf.fonttype": 42, "svg.fonttype": "path",
                         "svg.hashsalt": "can-stop-v1-analysis", "savefig.dpi": 300})
    figures = output / "figures"
    figures.mkdir(exist_ok=False)
    saved = []

    def save(fig, stem):
        for suffix in ("png", "svg", "pdf"):
            path = figures / (stem + "." + suffix)
            metadata = {"Date": None} if suffix == "svg" else {"CreationDate": None, "ModDate": None} if suffix == "pdf" else None
            fig.savefig(path, bbox_inches="tight", metadata=metadata)
            saved.append({"path": str(path.relative_to(output)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 3.1), layout="constrained")
    x = np.arange(8)
    passed, failed = [c["PASS"] for c in cells], [c["FAIL"] for c in cells]
    ax.bar(x, passed, color=[COLORS[c["variant"]] for c in cells], label="요구사항 충족 실행")
    ax.bar(x, failed, bottom=passed, color="#B2182B", hatch="///", label="요구사항 FAIL 실행")
    for i, (good, bad) in enumerate(zip(passed, failed)):
        ax.text(i, 5, "FAIL 10" if bad else "PASS 10", ha="center", va="center", color="white", fontsize=9)
    ax.set_xticks(x, [c["scenario"] + "\n" + c["variant"] for c in cells])
    ax.set_ylim(0, 12.8)
    ax.set_yticks([0, 5, 10])
    ax.set_ylabel("원래 시도 수")
    ax.set_title("80회 모두 실행 완료 / A/T-04의 R-04 FAIL 10회 보존")
    ax.legend(handles=[Patch(color=COLORS["A"], label="A PASS"), Patch(color=COLORS["B"], label="B PASS"),
                       Patch(facecolor="#B2182B", hatch="///", label="R-04 FAIL")],
              loc="upper center", ncol=3, frameon=False, fontsize=9)
    save(fig, "fig4-1_outcomes")

    fig, axes = plt.subplots(1, 3, figsize=(8, 3), layout="constrained")
    for ax, scenario in zip(axes, SCENARIOS[1:]):
        all_values = []
        for i, variant in enumerate(("A", "B")):
            values = [r["request_latency_ms"] for r in records if r["scenario"] == scenario and r["variant"] == variant and r["request_latency_ms"] is not None]
            if values:
                ax.scatter(i + np.linspace(-.1, .1, len(values)), values, color=COLORS[variant], s=23, alpha=.85)
                ax.hlines(np.median(values), i - .18, i + .18, color="black", linewidth=1.5)
                all_values.extend(values)
            else:
                ax.text(.06, .55, "A: 미요청 10회\nR-04 FAIL", transform=ax.transAxes, color=COLORS[variant], fontsize=9)
        if all_values:
            low, high = min(all_values), max(all_values)
            margin = max((high - low) * .3, .02)
            ax.set_ylim(max(0, low - margin) if scenario == "T-02" else low - margin, high + margin)
        ax.set_xlim(-.4, 1.4)
        ax.set_xticks([0, 1], ["A", "B"])
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
        ax.grid(axis="y", alpha=.2)
        ax.set_title(scenario + (" 근거리" if scenario == "T-02" else " 중단" if scenario == "T-03" else " 반복")
                     + "\n상한 " + ("100" if scenario == "T-02" else "300") + " ms (표시 범위 밖)", fontsize=10)
        ax.set_ylabel("송신 완료 → 요청 관측 (ms)")
    fig.suptitle("요청 관측 분포 확대: 점=원래 시도 / 가로선=중앙값", fontsize=11)
    save(fig, "fig4-2_request_latency")

    fig, ax = plt.subplots(figsize=(7.2, 3.5), layout="constrained")
    for i, cell in enumerate(cells[2:]):
        values = [r["max_adapter_ms"] for r in records if r["scenario"] == cell["scenario"] and r["variant"] == cell["variant"] and r["max_adapter_ms"] is not None]
        if values:
            ax.scatter(i + np.linspace(-.1, .1, len(values)), values, color=COLORS[cell["variant"]], s=26)
            ax.hlines(np.median(values), i - .2, i + .2, color="black", linewidth=1.6)
        else:
            ax.text(i, 7, "미요청\nN/A", ha="center", color="#555555", fontsize=9)
    ax.axhline(50, color="#B2182B", linestyle=":", label="R-06 상한 50 ms")
    ax.set_xticks(range(6), [c["scenario"] + "\n" + c["variant"] for c in cells[2:]])
    ax.set_ylim(0, 57)
    ax.set_ylabel("실행별 adapter 처리 최댓값 (ms)")
    ax.set_title("각 점은 한 실행의 최댓값 / 가로선은 그 중앙값")
    ax.legend(frameon=False, loc="upper left")
    ax.grid(axis="y", alpha=.2)
    save(fig, "fig4-3_adapter_maxima")

    fig, axes = plt.subplots(4, 1, figsize=(7.2, 6.5), sharex=True, layout="constrained")
    for variant in ("A", "B"):
        sample = examples["T-04", variant]
        t0 = sample["meta"]["t0_ns"]
        rows = [r for r in sample["logs"]["can_observer"] if t0 <= r["host_monotonic_ns"] <= sample["meta"]["trial_end_ns"]]
        for identifier in (0x100, 0x101, 0x200):
            selected = [r for r in rows if int.from_bytes(bytes.fromhex(r["raw_frame_hex"])[:4], sys.byteorder) == identifier]
            times = [(r["host_monotonic_ns"] - t0) / 1e9 for r in selected]
            payloads = [bytes.fromhex(r["raw_frame_hex"])[8:] for r in selected]
            style = dict(color=COLORS[variant], linestyle=STYLES[variant], linewidth=1.25, label=variant)
            if identifier == 0x100:
                axes[0].plot(times, [int.from_bytes(v[:2], "little") for v in payloads], **style)
                axes[1].step(times, [v[2] for v in payloads], where="post", **style)
                axes[2].plot(times, [0 if variant == "A" else 1] * len(times), "|", color=COLORS[variant], markersize=5, label=variant)
            elif identifier == 0x101 and variant == "B":
                axes[1].step(times, [v[0] for v in payloads], where="post", color="#777777", alpha=.6, linestyle=":", label="배경 심박")
            elif identifier == 0x200:
                axes[3].step(times, [v[0] for v in payloads], where="post", **style)
    labels = ("수치 거리 (cm)", "counter", "거리 수신", "stop 요청")
    for ax, label in zip(axes, labels):
        ax.axvspan(5, 8, color="#E9AB17", alpha=.18)
        ax.set_ylabel(label)
        ax.grid(axis="y", alpha=.2)
        ax.legend(loc="upper right", frameon=False, ncol=3, fontsize=8)
    axes[0].set_ylim(900, 1100)
    axes[2].set_yticks([0, 1], ["A", "B"])
    axes[2].set_ylim(-.5, 1.5)
    axes[3].set_ylim(-.15, 1.2)
    axes[3].set_yticks([0, 1])
    axes[-1].set_xlim(0, 20)
    axes[-1].set_xlabel("각 run의 T0 기준 호스트 경과시간 (s)")
    fig.suptitle("T-04 첫 반복: 프레임은 도착하지만 거리 counter는 고정\n음영=명목 반복 구간 5~8 s", fontsize=11)
    save(fig, "fig4-4_t04_host_timeline")

    fig, axes = plt.subplots(4, 2, figsize=(7.2, 8.4), layout="constrained")
    for row, scenario in enumerate(SCENARIOS):
        for variant in ("A", "B"):
            sample = examples[scenario, variant]
            vehicle = [r for r in sample["logs"]["vehicle_states"] if r["phase"] == "g4"]
            zero = vehicle[0]["simulation_time_s"]
            times = [r["simulation_time_s"] - zero for r in vehicle]
            speed = [math_speed(r) * 3.6 for r in vehicle]
            for col, values in enumerate((speed, [r["applied_control"]["brake"] for r in vehicle])):
                axes[row, col].plot(times, values, color=COLORS[variant], linestyle=STYLES[variant], label=variant, linewidth=1.3)
        for col in (0, 1):
            ax = axes[row, col]
            ax.set_title(scenario + (" 실제 평면 속도" if col == 0 else " 적용 brake"), fontsize=10)
            ax.set_xlim(left=0)
            ax.grid(alpha=.2)
            ax.legend(loc="upper right", frameon=False, fontsize=8)
            ax.set_xlabel("각 run 첫 본 구간 frame 이후 시뮬레이션 시간 (s)", fontsize=8)
        axes[row, 0].set_ylim(-.15, 5.8)
        axes[row, 0].set_ylabel("km/h")
        axes[row, 1].set_ylim(-.05, 1.2)
        axes[row, 1].set_ylabel("brake")
        axes[row, 1].set_yticks([0, 1])
    fig.suptitle("셀별 첫 반복의 실제 차량 상태\n호스트 시간축과 분리 / 각 run 첫 본 구간 관측을 0 s로 정렬", fontsize=11)
    save(fig, "fig4-5_vehicle_motion")
    return {"matplotlib": matplotlib.__version__, "numpy": np.__version__, "backend": "Agg",
            "font_path": str(font), "font_sha256": hashlib.sha256(font.read_bytes()).hexdigest(), "artifacts": saved}


def math_speed(row):
    """명령 속도를 사용하지 않고 CARLA 원시 속도벡터로 계산한다."""
    import math
    v = row["velocity_mps"]
    return math.hypot(v["x"], v["y"])
