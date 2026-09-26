#!/usr/bin/env python3
"""번역을 검사한다.

  python check.py --source work/de.json --config <프로젝트>/.i18n.json [--json]

여섯 가지를 본다. **앞의 셋은 사람 눈으로 못 잡고 역번역으로도 안 잡힌다** ——
플레이스홀더가 사라지면 런타임에 문자열이 깨지고, HTML 태그가 빠지면 화면이
깨지고, 브랜드가 번역되면 제품 이름이 사라진다. 그래서 기계가 잡아야 한다.

종료 코드는 오류 건수다(0 이면 통과). 경고는 종료 코드를 바꾸지 않는다 ——
길이 초과는 "봐야 한다"는 신호이지 오류가 아니기 때문이다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import (budget_for, html_tags, load_config, load_glossary,   # noqa: E402
                     placeholders, read_bundle, tag_names)

ERROR, WARN = "error", "warn"


def check(bundle_path: str, cfg: dict) -> tuple[list[dict], dict]:
    _, items = read_bundle(bundle_path)
    gloss = load_glossary(cfg)
    dnt = [w for w in gloss.get("do_not_translate", []) if w]
    findings: list[dict] = []

    def add(level, kind, item, detail):
        findings.append({"level": level, "check": kind, "id": item.id,
                         "source": item.source, "target": item.target or "",
                         "unit": item.unit, "detail": detail})

    # 용어 일관성은 전체를 봐야 하므로 먼저 모은다
    term_map: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

    for it in items:
        tgt = (it.target or "").strip()

        # 1. 누락 —— 배치가 뒤쪽을 빠뜨렸을 때 여기서 걸린다
        if not tgt:
            add(ERROR, "missing", it, "번역이 비어 있다")
            continue
        if tgt == it.source and len(it.source) > 3 and it.source not in dnt:
            add(WARN, "unchanged", it, "원문과 같다 —— 번역이 안 된 것일 수 있다")

        # 2. 플레이스홀더 —— 사라지거나 번호가 바뀌면 런타임에 깨진다
        ps, pt = placeholders(it.source, it.fmt), placeholders(tgt, it.fmt)
        if sorted(ps) != sorted(pt):
            add(ERROR, "placeholder", it, f"원문 {ps} → 번역 {pt}")
        elif ps and ps != pt and not any(re.search(r"\d", p) for p in ps):
            # 번호 없는 것(%s · {})은 순서가 곧 의미다. 순서가 바뀌면 값이 뒤바뀐다
            add(ERROR, "placeholder-order", it,
                f"번호 없는 플레이스홀더의 순서가 바뀌었다: {ps} → {pt}")

        # 3. HTML —— 빠지면 화면이 깨지는데 눈으로는 잘 안 보인다
        hs, ht = tag_names(html_tags(it.source)), tag_names(html_tags(tgt))
        if sorted(hs) != sorted(ht):
            add(ERROR, "html", it, f"태그 {hs} → {ht}")

        # 4. 번역 금지어 —— 뚫리면 브랜드가 사라진다
        for w in dnt:
            if w in it.source and w not in tgt:
                add(ERROR, "do-not-translate", it, f"'{w}' 가 번역문에 그대로 없다")

        # 5. 길이 —— 경보이지 오류가 아니다
        ratio = budget_for(cfg, it.kind)
        if it.source and len(tgt) > len(it.source) * ratio:
            add(WARN, "length", it,
                f"{len(it.source)} → {len(tgt)}자 (상한 {int(len(it.source) * ratio)}, "
                f"{it.kind} 기준 {ratio}배)")

        # 6. 용어 일관성 재료 모으기
        for term in gloss.get("terms", {}):
            if re.search(rf"\b{re.escape(term)}\b", it.source, re.I):
                term_map[term][tgt].append(it.id)

    # 6. 같은 용어가 화면마다 다르게 번역됐나 —— 사용자는 다른 기능으로 읽는다
    for term, variants in term_map.items():
        if len(variants) > 1:
            shown = " / ".join(f"{len(v)}건" for v in variants.values())
            findings.append({
                "level": WARN, "check": "term-consistency", "id": f"term:{term}",
                "source": term, "target": "", "unit": "",
                "detail": f"'{term}' 이 {len(variants)}가지로 번역됐다 ({shown}) —— "
                          f"용어집에 고정하거나 하나로 통일하라"})

    summary = {
        "items": len(items),
        "errors": sum(1 for f in findings if f["level"] == ERROR),
        "warnings": sum(1 for f in findings if f["level"] == WARN),
        "by_check": {},
    }
    for f in findings:
        summary["by_check"][f["check"]] = summary["by_check"].get(f["check"], 0) + 1
    return findings, summary


def report(findings: list[dict], summary: dict) -> None:
    # 몇 건을 봤는지 반드시 적는다 —— "문제 없음"만 말하면 검사가 빈 입력을 받았을
    # 때와 구분이 안 된다
    print(f"# 검사 결과 — {summary['items']}건 검사\n")
    print(f"오류 {summary['errors']} · 경고 {summary['warnings']}\n")

    if not findings:
        print("통과. 병합해도 된다.")
        return

    order = ["missing", "placeholder", "placeholder-order", "html", "do-not-translate",
             "unchanged", "term-consistency", "length"]
    for kind in order:
        rows = [f for f in findings if f["check"] == kind]
        if not rows:
            continue
        mark = "🔴" if rows[0]["level"] == ERROR else "⚠️"
        print(f"\n## {mark} {kind} — {len(rows)}건\n")
        for f in rows[:50]:
            print(f"- `{f['source'][:70]}`")
            if f["target"]:
                print(f"  → `{f['target'][:70]}`")
            print(f"  {f['detail']}")
        if len(rows) > 50:
            print(f"\n… 외 {len(rows) - 50}건")

    if summary["errors"]:
        print(f"\n---\n\n🔴 **오류 {summary['errors']}건이 남아 있다. 병합하지 마라.**")
        print("해당 항목만 다시 번역해서 다시 검사하라.")
    else:
        print("\n---\n\n오류는 없다. 경고는 판단 사항이다 —— "
              "독일어는 원래 길어서 길이 초과가 정상인 경우가 많다.")


def main() -> int:
    ap = argparse.ArgumentParser(description="번역 검사")
    ap.add_argument("--source", required=True, help="번역이 채워진 번들 JSON")
    ap.add_argument("--config", required=True)
    ap.add_argument("--json", action="store_true", help="사람용 리포트 대신 JSON")
    a = ap.parse_args()

    cfg = load_config(a.config)
    findings, summary = check(a.source, cfg)
    if a.json:
        print(json.dumps({"summary": summary, "findings": findings},
                         ensure_ascii=False, indent=2))
    else:
        report(findings, summary)
    return summary["errors"]


if __name__ == "__main__":
    raise SystemExit(main())
