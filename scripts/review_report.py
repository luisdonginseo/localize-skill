#!/usr/bin/env python3
"""역번역 리포트를 조립한다.

  python review_report.py --input work/de.reviewed.json --out work/de-review.md

입력은 추출 번들에 두 필드가 더해진 것이다.

  "back":    번역문을 원문 언어로 되돌린 것
  "verdict": "ok" | "check"
  "reason":  check 일 때 한 줄 이유

**판정은 모델이 하고 이 스크립트는 배치만 한다.** 의미가 달라졌는지는 기계가
판단할 수 없기 때문이다.

리포트는 플래그된 것을 위에, 나머지를 접어서 아래에 둔다 —— 사용자는 위쪽만 보면
되고, 의심되면 펼쳐 본다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import _common  # noqa: E402,F401  —— import 만으로 콘솔 UTF-8 이 잡힌다(윈도우 cp949)


def build(data: dict) -> str:
    items = data.get("items", [])
    src, tgt = data.get("source_lang", "en"), data.get("target_lang", "?")
    flagged = [i for i in items if i.get("verdict") == "check"]
    ok = [i for i in items if i.get("verdict") != "check"]
    missing_back = [i for i in items if not i.get("back")]

    L: list[str] = []
    L.append(f"# 역번역 검수 — {tgt}\n")
    L.append(f"{len(items)}건 중 **확인 필요 {len(flagged)}건**. "
             f"나머지 {len(ok)}건은 아래에 접어 두었다.\n")
    if missing_back:
        L.append(f"> ⚠️ 역번역이 없는 항목이 {len(missing_back)}건 있다. "
                 f"검수가 그만큼 비어 있다는 뜻이다.\n")
    L.append("> 역번역이 원문과 글자까지 같을 필요는 없다. **뜻이 같으면 된다.**\n")

    if flagged:
        L.append("\n## 🔴 확인 필요\n")
        for i in flagged:
            L.append(f"**{i.get('reason', '이유 없음')}**\n")
            L.append(f"| | |\n|---|---|")
            L.append(f"| 원문 ({src}) | {i.get('source','')} |")
            L.append(f"| 번역 ({tgt}) | {i.get('target','')} |")
            L.append(f"| 역번역 ({src}) | {i.get('back','—')} |")
            ctx = i.get("context") or i.get("unit") or ""
            if ctx:
                L.append(f"| 위치 | `{ctx}` |")
            L.append("")
    else:
        L.append("\n## 확인 필요 항목 없음\n")
        L.append("플래그된 것이 없다. 다만 **판정이 후했을 가능성**도 있으니, "
                 "아래 접힌 목록에서 몇 개를 표본으로 보는 편이 안전하다.\n")

    L.append(f"\n<details>\n<summary>나머지 {len(ok)}건 펼치기</summary>\n")
    L.append("| 원문 | 번역 | 역번역 |")
    L.append("|---|---|---|")
    for i in ok:
        def cell(s: str) -> str:
            return (s or "").replace("|", "\\|").replace("\n", " ")[:90]
        L.append(f"| {cell(i.get('source'))} | {cell(i.get('target'))} | {cell(i.get('back'))} |")
    L.append("\n</details>\n")

    L.append("\n---\n")
    L.append("**판정 기준**: 의미가 좁아지거나 넓어진 것, 어조가 바뀐 것"
             "(명령형 → 평서형), 존대 수준이 달라진 것도 확인 대상이다.")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="역번역 리포트 조립")
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    data = json.loads(Path(a.input).read_text(encoding="utf-8"))
    md = build(data)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")

    items = data.get("items", [])
    flagged = sum(1 for i in items if i.get("verdict") == "check")
    print(f"{len(items)}건 중 확인 필요 {flagged}건 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
