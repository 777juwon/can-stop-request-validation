#!/usr/bin/env python3
"""초록과 제1~5장 원고를 합치고 참고문헌을 끝에 배치한다.

통합본은 파생 파일이다. 기존 통합본 교체는 --overwrite로 명시해야 한다.
제출한 작성계획서와 HWP 원본은 접근하지 않는다.
"""

import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def build(overwrite=False):
    folder = ROOT / "docs"
    first = (folder / "THESIS_CHAPTERS_1_3.md").read_text()
    last = (folder / "THESIS_CHAPTERS_4_5.md").read_text()
    first_body, first_refs = ("# 제1장 서론" + first.split("# 제1장 서론", 1)[1]).split("# 참고문헌\n", 1)
    last_body, last_refs = ("# 제4장 시험 결과 및 분석" + last.split("# 제4장 시험 결과 및 분석", 1)[1]).split("## 참고문헌 추가 항목\n", 1)
    abstract = (folder / "THESIS_ABSTRACT.md").read_text()
    text = ("# 가상 CAN 환경에서 저속 주행 정지 요청 기능의 메시지 이상 대응 검증\n\n"
            "2026-11-02 검토용 통합 원고. tools/build_thesis_draft.py로 생성했다. "
            "최종5장 목차이며 HWP 분량/학교 양식과 지도교수 검토는 별도다.\n\n"
            + abstract + "\n\n" + first_body + "\n\n" + last_body
            + "\n\n# 참고문헌\n\n" + first_refs.strip() + "\n\n" + last_refs.strip() + "\n")
    if re.findall(r"^# 제(\d)장", text, re.M) != list("12345"):
        raise ValueError("5장 구성 불일치")
    destination = folder / "THESIS_DRAFT.md"
    with destination.open("w" if overwrite else "x", encoding="utf-8") as stream:
        stream.write(text)
    print(str(destination))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true", help="파생 통합본 교체 허용")
    args = parser.parse_args()
    build(args.overwrite)
