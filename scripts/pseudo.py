#!/usr/bin/env python3
"""의사 현지화 — 번역 없이 UI 깨짐을 먼저 잡는다.

  python pseudo.py --config <프로젝트>/.i18n.json --lang qps [--expand 1.4]

글자를 늘리고 악센트를 섞은 가짜 로케일을 만든다. 앱을 그 로케일로 띄우면
**잘리거나 넘치는 곳이 눈에 보인다.**

번역 **전에** 하는 것이 순서상 맞다. 나중에 고치면 레이아웃이 바뀌어 번역을 다시
해야 할 수도 있다.

🔑 CJK 에서는 길이 검사보다 이쪽이 정확하다. 일본어·중국어는 글자 수가 오히려
줄지만 전각이라 폭은 덜 줄어서, 글자 수 비율만 보면 통과하는데 화면은 깨진다.
--wide 로 전각 문자를 섞으면 그 상황을 흉내 낼 수 있다.
"""

from __future__ import annotations

import argparse
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _adapters import ADAPTERS                                      # noqa: E402
from _common import Item, load_config, placeholders, unit_paths     # noqa: E402

ACCENTS = str.maketrans({
    "a": "á", "b": "ƀ", "c": "ç", "d": "ð", "e": "é", "f": "ƒ", "g": "ǧ", "h": "ĥ",
    "i": "í", "j": "ĵ", "k": "ķ", "l": "ľ", "m": "ɱ", "n": "ñ", "o": "ó", "p": "ƥ",
    "q": "ɋ", "r": "ř", "s": "š", "t": "ť", "u": "ü", "v": "ṽ", "w": "ŵ", "x": "ж",
    "y": "ý", "z": "ž",
    "A": "Á", "B": "Ɓ", "C": "Ç", "D": "Ð", "E": "É", "F": "Ƒ", "G": "Ǧ", "H": "Ĥ",
    "I": "Í", "J": "Ĵ", "K": "Ķ", "L": "Ľ", "M": "Ṁ", "N": "Ñ", "O": "Ó", "P": "Ƥ",
    "Q": "Ǫ", "R": "Ř", "S": "Š", "T": "Ť", "U": "Ü", "V": "Ṽ", "W": "Ŵ", "X": "Ж",
    "Y": "Ý", "Z": "Ž",
})
PAD = "・のかな"          # 전각 —— 폭을 늘린다
PAD_ASCII = "~"


def pseudo(text: str, fmt: str, expand: float, wide: bool) -> str:
    """플레이스홀더와 태그는 건드리지 않는다 —— 그걸 망가뜨리면 앱이 안 뜬다."""
    keep = set(placeholders(text, fmt))
    out = []
    i = 0
    while i < len(text):
        hit = next((k for k in keep if text.startswith(k, i)), None)
        if hit:
            out.append(hit)
            i += len(hit)
            continue
        if text[i] == "<":                       # HTML 태그는 통째로 보존
            j = text.find(">", i)
            if j != -1:
                out.append(text[i:j + 1])
                i = j + 1
                continue
        out.append(text[i].translate(ACCENTS))
        i += 1
    body = "".join(out)
    need = max(0, int(len(text) * expand) - len(text))
    if need:
        filler = (PAD if wide else PAD_ASCII)
        body += " " + (filler * (need // len(filler) + 1))[:need]
    return f"⟦{body}⟧"                           # 잘림을 눈으로 바로 알 수 있게 감싼다


def main() -> int:
    ap = argparse.ArgumentParser(description="의사 현지화 로케일 생성")
    ap.add_argument("--config", required=True)
    ap.add_argument("--lang", default="qps", help="만들 가짜 로케일 코드 (기본 qps)")
    ap.add_argument("--expand", type=float, default=1.4,
                    help="길이 배율 (기본 1.4 —— 독일어 평균보다 약간 위)")
    ap.add_argument("--wide", action="store_true",
                    help="전각 문자를 채워 CJK 폭을 흉내 낸다")
    a = ap.parse_args()

    cfg = load_config(a.config)
    src_lang = cfg.get("source", "en")
    total = 0
    for unit in cfg["units"]:
        fmt = unit["format"]
        if fmt not in ADAPTERS:
            continue
        read_fn, write_fn = ADAPTERS[fmt]
        rk = {"src_lang": src_lang} if "src_lang" in inspect.signature(read_fn).parameters else {}
        wk = {"src_lang": src_lang} if "src_lang" in inspect.signature(write_fn).parameters else {}
        items = read_fn(unit_paths(cfg, unit), src_lang, unit, **rk)
        for i in items:
            i.target = pseudo(i.source, fmt, a.expand, a.wide)
        n = write_fn(unit_paths(cfg, unit), a.lang, items, unit, **wk)
        print(f"  {unit['path']} ({fmt}): {n}건")
        total += n

    print(f"\n{a.lang} 로케일 {total}건 생성 (배율 {a.expand}"
          + (", 전각" if a.wide else "") + ")")
    print("\n앱을 이 로케일로 띄우고 **잘리거나 넘치는 곳**을 찾아라.")
    print("단추에 고정 width 대신 min-width 를 쓰면 대부분 해결된다.")
    print("\n⚠️ 이건 시험용 로케일이다. 배포본에 들어가지 않게 하라.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
