#!/usr/bin/env python3
"""번역 단위를 뽑는다.

  python extract.py --diagnose --root <프로젝트>
  python extract.py --config <프로젝트>/.i18n.json --lang de --out work/de.json [--all]
  python extract.py --suggest-comments --config <프로젝트>/.i18n.json

기본은 **미번역 항목만** 뽑는다. 릴리스마다 전체를 다시 번역하면 유지비를 감당할 수
없기 때문이다. 전체가 필요하면 --all.
"""

from __future__ import annotations

import argparse
import inspect
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _adapters import ADAPTERS, NOT_EXTRACTED                    # noqa: E402
from _common import (Item, budget_for, html_tags, iter_files,     # noqa: E402
                     load_config, placeholders, unit_paths, write_bundle)


# ── 진단 ─────────────────────────────────────────────────────────────────────

MARKERS = {
    "qt-ts":     [r"\bself\.tr\(", r"\bQCoreApplication\.translate\(", r"QT_TRANSLATE_NOOP\("],
    "gettext":   [r"@tr\(", r"\bgettext\(", r"\b_\("],
    "android":   [r"<string\s+name="],
    "apple":     [r"NSLocalizedString\(", r"String\(localized:"],
}
SOURCE_GLOBS = {"qt-ts": "*.py", "gettext": "*.slint", "apple": "*.swift"}


def diagnose(root: Path) -> int:
    print(f"# 번역 준비 상태 — {root}\n")
    found_any = False

    for fmt, pats in MARKERS.items():
        glob = SOURCE_GLOBS.get(fmt)
        if not glob:
            continue
        files = list(iter_files(root, glob))
        if not files:
            continue
        found_any = True
        hits = 0
        for p in files:
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            hits += sum(len(re.findall(pat, text)) for pat in pats)
        state = "OK" if hits else "🔴 0곳"
        print(f"- {fmt:9} 소스 {len(files):4}개 · 번역 마킹 {hits:5}곳   {state}")
        if not hits:
            print(f"    → 문자열이 하드코딩돼 있다. **번역이 아니라 마킹 작업이 먼저**다.")

    print()
    pairs = [("*.ts", "*.qm", "qt-ts 원본(.ts)"), ("*.po", "*.mo", "gettext 원본(.po)"),
             ("*.pot", None, "gettext 템플릿(.pot)")]
    for src_glob, bin_glob, label in pairs:
        srcs = list(iter_files(root, src_glob))
        if src_glob == "*.ts":
            srcs = [p for p in srcs if not p.name.endswith(".d.ts")]
        bins = list(iter_files(root, bin_glob)) if bin_glob else []
        if srcs or bins:
            found_any = True
            print(f"- {label}: {len(srcs)}개" + (f" · 컴파일본 {len(bins)}개" if bin_glob else ""))
            if bins and not srcs:
                print(f"    🔴 컴파일 결과만 있고 원본이 없다. 추출 도구로 먼저 생성해야 한다.")

    comments = 0
    for glob, pat in (("*.py", r"^\s*#:"), ("*.slint", r"^\s*//:"), ("*.swift", r"^\s*//:")):
        for p in iter_files(root, glob):
            try:
                comments += len(re.findall(pat, p.read_text(encoding="utf-8", errors="ignore"), re.M))
            except OSError:
                pass
    print(f"\n- 맥락 주석(#: · //:): {comments}곳" +
          ("   🔴 0곳 —— 짧은 문자열의 뜻을 AI 가 못 맞춘다. --suggest-comments 를 돌려라"
           if comments == 0 else ""))

    if not found_any:
        print("\n번역 관련 파일을 찾지 못했다. --root 가 맞는지 확인하라.")
    print("\n이 결과를 사용자에게 그대로 보고하고, 진행할지 정하게 하라.")
    return 0


# ── 추출 ─────────────────────────────────────────────────────────────────────

def _read(unit: dict, base: Path, lang: str, src_lang: str) -> list[Item]:
    fmt = unit["format"]
    if fmt in NOT_EXTRACTED:
        raise SystemExit(f"'{fmt}' 은 문자열 단위로 뽑지 않는다. references/formats.md §8 참조.")
    if fmt not in ADAPTERS:
        raise SystemExit(f"모르는 포맷 '{fmt}'. references/formats.md §9 를 보고 어댑터를 추가하라.")
    read_fn = ADAPTERS[fmt][0]
    kwargs = {}
    if "src_lang" in inspect.signature(read_fn).parameters:
        kwargs["src_lang"] = src_lang
    return read_fn(base, lang, unit, **kwargs)


def extract(cfg: dict, lang: str, out: str, include_all: bool) -> int:
    src_lang = cfg.get("source", "en")
    items: list[Item] = []
    for unit in cfg["units"]:
        got = _read(unit, unit_paths(cfg, unit), lang, src_lang)
        if not include_all:
            got = [i for i in got if i.status in ("untranslated", "needs_review")]
        items.extend(got)

    # 번역에 필요한 것을 항목에 붙여 둔다 —— 모델이 파일을 다시 열지 않아도 되도록
    for i in items:
        i.extra.update({
            "placeholders": placeholders(i.source, i.fmt),
            "html": html_tags(i.source),
            "max_ratio": budget_for(cfg, i.kind),
            "max_chars": int(len(i.source) * budget_for(cfg, i.kind)),
        })

    write_bundle(out, cfg, lang, items)
    by_unit: dict[str, int] = {}
    for i in items:
        by_unit[i.unit] = by_unit.get(i.unit, 0) + 1
    scope = "전체" if include_all else "미번역·재검토"
    print(f"{lang}: {len(items)}개 ({scope}) → {out}")
    for u, n in by_unit.items():
        print(f"  {u}: {n}")
    if not items:
        print("  (뽑을 것이 없다. 이미 다 번역됐거나 --all 이 필요하다)")
    return 0


# ── 맥락 주석 제안 ───────────────────────────────────────────────────────────

AMBIGUOUS = {"open", "close", "copy", "cut", "paste", "new", "save", "load", "run",
             "stop", "start", "clear", "reset", "back", "next", "done", "edit",
             "view", "show", "hide", "move", "find", "set", "add", "remove", "link"}


def suggest_comments(cfg: dict) -> int:
    src_lang = cfg.get("source", "en")
    rows = []
    for unit in cfg["units"]:
        for i in _read(unit, unit_paths(cfg, unit), src_lang, src_lang):
            if i.comment:
                continue
            w = i.source.strip().lower().rstrip(".:")
            if w in AMBIGUOUS or (len(i.source) <= 12 and " " not in i.source.strip()):
                rows.append(i)

    print("# 맥락 주석을 달 곳\n")
    if not rows:
        print("짧고 모호한 미주석 문자열이 없다.")
        return 0
    print(f"{len(rows)}개. 짧은 문자열은 맥락이 없으면 AI 가 품사조차 못 맞춘다 —")
    print("`Open` 이 동사인지 이름표인지 모른다. **한 번 달면 이후 모든 언어가 덕을 본다.**\n")
    print("| 원문 | 맥락 | 대상 |")
    print("|---|---|---|")
    for i in rows[:200]:
        print(f"| `{i.source}` | {i.context or '—'} | {i.unit} |")
    if len(rows) > 200:
        print(f"\n… 외 {len(rows) - 200}개")
    print("\n달 때는 **품사와 길이 제약**을 적는 것이 가장 도움이 된다:")
    print("```python\n#: 버튼 라벨(동사). 최대 12자\nself.tr(\"Open\")\n```")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="번역 단위 추출")
    ap.add_argument("--config")
    ap.add_argument("--lang")
    ap.add_argument("--out")
    ap.add_argument("--all", action="store_true", help="이미 번역된 것도 포함")
    ap.add_argument("--diagnose", action="store_true")
    ap.add_argument("--root")
    ap.add_argument("--suggest-comments", action="store_true")
    a = ap.parse_args()

    if a.diagnose:
        return diagnose(Path(a.root or ".").resolve())
    if not a.config:
        ap.error("--config 가 필요하다 (또는 --diagnose --root)")
    cfg = load_config(a.config)
    if a.suggest_comments:
        return suggest_comments(cfg)
    if not (a.lang and a.out):
        ap.error("--lang 과 --out 이 필요하다")
    return extract(cfg, a.lang, a.out, a.all)


if __name__ == "__main__":
    raise SystemExit(main())
