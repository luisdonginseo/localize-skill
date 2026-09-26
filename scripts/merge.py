#!/usr/bin/env python3
"""번역을 원래 포맷으로 되쓴다.

  python merge.py --input work/de.json --config <프로젝트>/.i18n.json --lang de [--force]

**검사를 통과하지 않은 상태로 병합하지 마라.** 기본적으로 check.py 를 먼저 돌려
오류가 있으면 멈춘다. --force 는 그 안전장치를 끄는 것이므로, 사용자가 명시적으로
요청했을 때만 쓴다.
"""

from __future__ import annotations

import argparse
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _adapters import ADAPTERS                                      # noqa: E402
from _common import Item, load_config, read_bundle, unit_paths      # noqa: E402
from check import check                                             # noqa: E402


def merge(bundle_path: str, cfg: dict, lang: str, force: bool) -> int:
    findings, summary = check(bundle_path, cfg)
    if summary["errors"] and not force:
        print(f"🔴 오류 {summary['errors']}건이 남아 있어 병합하지 않는다.")
        print("   python check.py --source ... --config ... 로 무엇이 문제인지 보라.")
        print("   (의도한 것이라면 --force)")
        return 1

    _, items = read_bundle(bundle_path)
    by_unit: dict[str, list[Item]] = {}
    for i in items:
        by_unit.setdefault(i.unit, []).append(i)

    src_lang = cfg.get("source", "en")
    total = 0
    for unit in cfg["units"]:
        mine = [i for i in by_unit.get(unit["path"], []) if i.target]
        if not mine:
            continue
        fmt = unit["format"]
        if fmt not in ADAPTERS:
            print(f"  {unit['path']}: 모르는 포맷 '{fmt}' —— 건너뛴다")
            continue
        write_fn = ADAPTERS[fmt][1]
        kwargs = {}
        if "src_lang" in inspect.signature(write_fn).parameters:
            kwargs["src_lang"] = src_lang
        n = write_fn(unit_paths(cfg, unit), lang, mine, unit, **kwargs)
        print(f"  {unit['path']} ({fmt}): {n}건")
        total += n

    print(f"\n{lang}: {total}건 병합" + (f" · 경고 {summary['warnings']}건은 남아 있다"
                                        if summary["warnings"] else ""))
    if total:
        print("\n원본 파일이 바뀌었다. 커밋 전에 diff 를 확인하라 ——")
        print("번역 줄 외에 구조가 바뀌었다면 어댑터가 뭔가를 망가뜨린 것이다.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="번역 병합")
    ap.add_argument("--input", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--lang", required=True)
    ap.add_argument("--force", action="store_true",
                    help="검사 오류가 있어도 병합 (사용자가 명시 요청했을 때만)")
    a = ap.parse_args()
    return merge(a.input, load_config(a.config), a.lang, a.force)


if __name__ == "__main__":
    raise SystemExit(main())
