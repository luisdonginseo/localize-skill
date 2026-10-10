#!/usr/bin/env python3
"""번역 금지어(do_not_translate) 처리의 자체 시험. 표준 라이브러리만 쓴다.

  python selftest_dnt.py

목록 형태(기존) · 언어별 예외({"term", "except"}) · 섞은 목록 · 예외가 아닌 언어에서의
계속되는 보호 · 잘못된 설정의 거부를 본다. 하나라도 틀리면 종료 코드가 0 이 아니다.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import (dnt_for_lang, load_config, load_glossary,        # noqa: E402
                     parse_do_not_translate, write_bundle, Item)
from check import check                                              # noqa: E402


def run_check(dnt, lang, pairs, glossary=None):
    """pairs: [(원문, 번역)] 을 검사해 do-not-translate 오류 메시지 목록을 돌려준다."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        cfg = {"source": "en", "targets": [lang], "do_not_translate": dnt, "units": []}
        if glossary is not None:
            (root / "g.json").write_text(json.dumps(glossary), encoding="utf-8")
            cfg["project_glossary"] = "g.json"
        (root / ".i18n.json").write_text(json.dumps(cfg), encoding="utf-8")
        c = load_config(root / ".i18n.json")
        items = [Item(id=f"k{n}", source=s, target=t, fmt="json", kind="body")
                 for n, (s, t) in enumerate(pairs)]
        write_bundle(root / "b.json", c, lang, items)
        findings, _ = check(str(root / "b.json"), c)
        return [f["detail"] for f in findings if f["check"] == "do-not-translate"]


class DntTests(unittest.TestCase):
    # 1. 기존 목록 형태는 그대로
    def test_plain_list(self):
        self.assertEqual(run_check(["Acme"], "de", [("Open Acme", "Acme öffnen")]), [])
        self.assertEqual(len(run_check(["Acme"], "de", [("Open Acme", "Spitze öffnen")])), 1)
        c = parse_do_not_translate(["Acme", "Acme Studio"])
        self.assertEqual(c, (["Acme", "Acme Studio"], {}))

    # 2. de 에서는 WLAN 이어야 한다
    def test_exception_in_de(self):
        dnt = [{"term": "Wi-Fi", "except": {"de": "WLAN"}}]
        self.assertEqual(run_check(dnt, "de", [("Turn on Wi-Fi", "WLAN einschalten")]), [])
        left = run_check(dnt, "de", [("Turn on Wi-Fi", "Wi-Fi einschalten")])
        self.assertEqual(len(left), 2)                      # 대체어 없음 + 원문 남음
        self.assertTrue(any("WLAN" in m for m in left))
        missing = run_check(dnt, "de", [("Turn on Wi-Fi", "Funknetz einschalten")])
        self.assertEqual(len(missing), 1)                   # 대체어 없음만
        # 원문에 용어가 없으면 아무것도 요구하지 않는다
        self.assertEqual(run_check(dnt, "de", [("Turn on Bluetooth", "Bluetooth einschalten")]), [])

    # 3. 예외가 아닌 언어는 계속 원문 그대로를 요구한다
    def test_other_language_still_enforced(self):
        dnt = [{"term": "Wi-Fi", "except": {"de": "WLAN"}}]
        self.assertEqual(run_check(dnt, "fr", [("Turn on Wi-Fi", "Activer le Wi-Fi")]), [])
        self.assertEqual(len(run_check(dnt, "fr", [("Turn on Wi-Fi", "Activer le WLAN")])), 1)
        self.assertEqual(len(run_check(dnt, "ja", [("Turn on Wi-Fi", "WLAN をオン")])), 1)

    # 4. 문자열과 객체를 섞은 목록
    def test_mixed_list(self):
        dnt = ["Acme", {"term": "Wi-Fi", "except": {"de": "WLAN"}}, "Acme Studio"]
        terms, exc = parse_do_not_translate(dnt)
        self.assertEqual(terms, ["Acme", "Wi-Fi", "Acme Studio"])
        self.assertEqual(exc, {"Wi-Fi": {"de": "WLAN"}})
        pairs = [("Acme Wi-Fi", "Acme WLAN")]
        self.assertEqual(run_check(dnt, "de", pairs), [])
        self.assertEqual(len(run_check(dnt, "de", [("Acme Wi-Fi", "Spitze WLAN")])), 1)
        self.assertEqual(len(run_check(dnt, "fr", pairs)), 1)    # fr 에서는 Wi-Fi 필요

    # 5. 대체어가 원문 용어를 품은 경우 (Wi-Fi → Wi-Fi-Netz 같은)
    def test_replacement_contains_term(self):
        dnt = [{"term": "Wi-Fi", "except": {"xx": "Wi-Fi-Netz"}}]
        self.assertEqual(run_check(dnt, "xx", [("Wi-Fi", "Wi-Fi-Netz")]), [])
        self.assertEqual(len(run_check(dnt, "xx", [("Wi-Fi on", "Wi-Fi-Netz und Wi-Fi")])), 1)

    # 6. 언어 코드 표기 차이 · 부분 일치 안 함
    def test_lang_key(self):
        cfg = {"do_not_translate": ["Wi-Fi"], "do_not_translate_except": {"Wi-Fi": {"pt-BR": "Wi‑Fi"}}}
        self.assertEqual(dnt_for_lang(cfg, "pt_br"), ([], {"Wi-Fi": "Wi‑Fi"}))
        self.assertEqual(dnt_for_lang(cfg, "pt"), (["Wi-Fi"], {}))

    # 7. 프로젝트 용어집 쪽 목록에서도 같은 형식
    def test_glossary_file(self):
        g = {"do_not_translate": [{"term": "Wi-Fi", "except": {"de": "WLAN"}}], "terms": {}}
        self.assertEqual(run_check([], "de", [("Wi-Fi", "WLAN")], glossary=g), [])
        self.assertEqual(len(run_check([], "de", [("Wi-Fi", "Wi-Fi")], glossary=g)), 2)
        self.assertEqual(len(run_check([], "fr", [("Wi-Fi", "WLAN")], glossary=g)), 1)

    # 8. 번들에 이 언어의 규칙이 실린다
    def test_bundle_carries_rules(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"source": "en", "do_not_translate": ["Acme"], "do_not_translate_except": {},
                   "_root": d}
            cfg["do_not_translate"], cfg["do_not_translate_except"] = parse_do_not_translate(
                ["Acme", {"term": "Wi-Fi", "except": {"de": "WLAN"}}])
            write_bundle(Path(d) / "de.json", cfg, "de", [])
            write_bundle(Path(d) / "fr.json", cfg, "fr", [])
            de = json.loads((Path(d) / "de.json").read_text(encoding="utf-8"))
            fr = json.loads((Path(d) / "fr.json").read_text(encoding="utf-8"))
            self.assertEqual((de["do_not_translate"], de["do_not_translate_replace"]),
                             (["Acme"], {"Wi-Fi": "WLAN"}))
            self.assertEqual((fr["do_not_translate"], fr["do_not_translate_replace"]),
                             (["Acme", "Wi-Fi"], {}))

    # 9. 잘못된 설정은 조용히 넘기지 않는다
    def test_bad_config_rejected(self):
        for bad in ([{"term": ""}], [{"except": {"de": "WLAN"}}], [{"term": "A", "except": {"de": ""}}],
                    [{"term": "A", "except": ["de"]}], [{"term": "A", "exept": {}}], [5], "Acme"):
            with self.assertRaises(SystemExit, msg=repr(bad)):
                parse_do_not_translate(bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
