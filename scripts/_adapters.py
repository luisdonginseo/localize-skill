"""포맷별 읽기·쓰기.

원칙 두 가지.

1. **되쓰기는 원본 구조를 보존한다.** 주석·순서·들여쓰기가 바뀌면 diff 가 터져서
   사람이 리뷰할 수 없게 된다. 번역 한 줄 바꾸려고 파일 전체가 바뀌면 안 된다.
2. **이해하지 못하는 구조를 만나면 멈춘다.** 조용히 넘어가면 번역이 빠진 채로
   통과하거나, 더 나쁘게는 파일을 망가뜨린다.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from _common import Item, guess_kind


# ── 로케일 코드 변환 ─────────────────────────────────────────────────────────
# 우리는 BCP 47 비슷한 표기를 쓰고(zh_Hant), 플랫폼마다 다르게 부른다.

def android_qualifier(lang: str) -> str:
    table = {"zh_Hant": "zh-rTW", "zh_Hans": "zh-rCN", "pt_BR": "pt-rBR", "es_419": "b+es+419"}
    if lang in table:
        return table[lang]
    return lang.replace("_", "-r")


def apple_lproj(lang: str) -> str:
    table = {"zh_Hant": "zh-Hant", "zh_Hans": "zh-Hans", "pt_BR": "pt-BR", "es_419": "es-419"}
    return table.get(lang, lang.replace("_", "-"))


# ── qt-ts ────────────────────────────────────────────────────────────────────

def _ts_file(base: Path, lang: str) -> Path:
    if base.is_file():
        return base
    hits = sorted(base.glob(f"*_{lang}.ts"))
    if hits:
        return hits[0]
    # 새 언어 —— 기존 파일의 이름 규칙을 따른다 (app_de.ts 가 있으면 app_<lang>.ts).
    # 디렉터리 이름을 쓰면 translations_de.ts 같은 엉뚱한 파일이 생긴다.
    existing = _ts_any(base)
    if existing is not None and "_" in existing.stem:
        return base / f"{existing.stem.rsplit('_', 1)[0]}_{lang}.ts"
    return base / f"{base.name or 'app'}_{lang}.ts"


def _ts_any(base: Path) -> Path | None:
    """아무 .ts 나. `<source>` 는 어느 언어 파일에 있든 같기 때문에 원문만 필요할 때 쓴다.

    Qt 에는 `app_en.ts` 가 없다 —— 영어(원문)는 `<source>` 안에 들어 있고 .ts 는
    **대상 언어별로만** 만들어진다. 의사 현지화처럼 원문만 필요한 경우가 여기 걸린다.
    """
    if base.is_file():
        return base
    hits = sorted(p for p in base.glob("*.ts") if not p.name.endswith(".d.ts"))
    return hits[0] if hits else None


def read_qt_ts(base: Path, lang: str, unit: dict) -> list[Item]:
    path = _ts_file(base, lang)
    borrowed = False
    if not path.exists():
        alt = _ts_any(base)
        if alt is not None:
            # 원문만 빌려 온다. 남의 언어 번역을 이 언어 것으로 쓰면 안 되므로
            # 아래에서 target 을 비운다.
            path, borrowed = alt, True
    if not path.exists():
        raise SystemExit(
            f"{path} 가 없다.\n"
            f"  .ts 는 원본이고 .qm 은 컴파일 결과다. .qm 만 있으면 원본이 없는 것이다.\n"
            f"  pylupdate6 <소스…> -ts {path}  로 먼저 생성해야 한다."
        )
    tree = ET.parse(path)
    items: list[Item] = []
    for ctx in tree.getroot().findall("context"):
        cname = (ctx.findtext("name") or "").strip()
        for msg in ctx.findall("message"):
            src = msg.findtext("source") or ""
            if not src:
                continue
            tr = msg.find("translation")
            disamb = (msg.findtext("comment") or "").strip()
            extra = (msg.findtext("extracomment") or "").strip()
            ttype = (tr.get("type") if tr is not None else None) or ""
            if ttype == "vanished":
                continue                      # 소스에서 사라진 것 —— 건드리지 않는다
            target = (tr.text or "") if tr is not None else ""
            if borrowed:
                target = ""          # 다른 언어 파일에서 원문만 빌려 왔다
            status = "untranslated" if (ttype == "unfinished" or not target) else "translated"
            items.append(Item(
                id=f"{cname}|{disamb}|{src}",
                source=src, target=target or None,
                context=cname, comment=extra or disamb,
                kind=guess_kind(extra, cname, "", src),
                status=status, unit=unit["path"], fmt="qt-ts",
                plural=msg.get("numerus") == "yes",
            ))
    return items


def write_qt_ts(base: Path, lang: str, items: list[Item], unit: dict) -> int:
    path = _ts_file(base, lang)
    if not path.exists():
        # 새 언어다. 기존 .ts 의 구조를 베끼되 번역은 비운다 —— 남의 언어 번역이
        # 새 파일에 섞여 들어가면 조용히 틀린 번역이 배포된다.
        src = _ts_any(base)
        if src is None:
            raise SystemExit(
                f"{path} 를 만들 기준이 없다. 기존 .ts 가 하나도 없으면\n"
                f"  pylupdate6 <소스…> -ts {path}  로 먼저 생성해야 한다."
            )
        tree = ET.parse(src)
        for tr in tree.getroot().iter("translation"):
            tr.text = ""
            tr.set("type", "unfinished")
        root = tree.getroot()
        root.set("language", lang)
        path.parent.mkdir(parents=True, exist_ok=True)
        tree.write(path, encoding="utf-8", xml_declaration=True)
    tree = ET.parse(path)
    by_id = {i.id: i for i in items if i.target}
    n = 0
    for ctx in tree.getroot().findall("context"):
        cname = (ctx.findtext("name") or "").strip()
        for msg in ctx.findall("message"):
            src = msg.findtext("source") or ""
            disamb = (msg.findtext("comment") or "").strip()
            item = by_id.get(f"{cname}|{disamb}|{src}")
            if not item:
                continue
            tr = msg.find("translation")
            if tr is None:
                tr = ET.SubElement(msg, "translation")
            if msg.get("numerus") == "yes":
                continue                      # 복수형은 형태 수가 언어마다 달라 자동 병합하지 않는다
            tr.text = item.target
            if "type" in tr.attrib:
                del tr.attrib["type"]
            n += 1
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return n


# ── gettext (.po / .pot) ─────────────────────────────────────────────────────

_PO_LINE = re.compile(r'^(msgctxt|msgid|msgid_plural|msgstr(?:\[\d+\])?)\s+"(.*)"$')


def _po_unescape(s: str) -> str:
    return s.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t").replace("\\\\", "\\")


def _po_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")


def _po_file(base: Path, lang: str) -> Path:
    if base.is_file():
        return base
    for cand in (base / lang / "LC_MESSAGES", base / lang, base):
        hits = sorted(cand.glob("*.po"))
        if hits:
            return hits[0]
    return base / lang / "LC_MESSAGES" / "messages.po"


def _po_parse(text: str) -> list[dict]:
    """블록 단위로 읽는다. 줄 번호를 들고 있어야 되쓰기에서 구조를 보존할 수 있다."""
    blocks, cur = [], {"comments": [], "start": 0}
    lines = text.splitlines()
    key = None
    for n, raw in enumerate(lines):
        line = raw.rstrip("\n")
        if not line.strip():
            if cur.get("msgid") is not None:
                cur["end"] = n
                blocks.append(cur)
            cur, key = {"comments": [], "start": n + 1}, None
            continue
        if line.startswith("#"):
            cur["comments"].append(line)
            continue
        m = _PO_LINE.match(line)
        if m:
            key = m.group(1)
            cur[key] = _po_unescape(m.group(2))
            cur.setdefault("_lines", {})[key] = n
        elif line.startswith('"') and key:
            cur[key] = cur.get(key, "") + _po_unescape(line.strip()[1:-1])
    if cur.get("msgid") is not None:
        cur["end"] = len(lines)
        blocks.append(cur)
    return blocks


def read_gettext(base: Path, lang: str, unit: dict) -> list[Item]:
    path = _po_file(base, lang)
    if not path.exists():
        raise SystemExit(
            f"{path} 가 없다.\n"
            f"  .pot 에서 먼저 만들어야 한다:\n"
            f"  msginit --input=<app>.pot --locale={lang} --output={path}"
        )
    items = []
    for b in _po_parse(path.read_text(encoding="utf-8")):
        src = b.get("msgid", "")
        if not src:
            continue                          # 헤더 블록
        dev = " ".join(c[2:].strip() for c in b["comments"] if c.startswith("#."))
        fuzzy = any(c.startswith("#,") and "fuzzy" in c for c in b["comments"])
        tgt = b.get("msgstr", "")
        status = "needs_review" if fuzzy else ("translated" if tgt else "untranslated")
        ctx = b.get("msgctxt", "")
        items.append(Item(
            id=f"{ctx}|{src}", source=src, target=tgt or None,
            context=ctx, comment=dev,
            kind=guess_kind(dev, ctx, "", src),
            status=status, unit=unit["path"], fmt="gettext",
            plural="msgid_plural" in b,
        ))
    return items


def write_gettext(base: Path, lang: str, items: list[Item], unit: dict) -> int:
    path = _po_file(base, lang)
    lines = path.read_text(encoding="utf-8").splitlines()
    by_id = {i.id: i for i in items if i.target}
    n = 0
    for b in _po_parse("\n".join(lines)):
        src, ctx = b.get("msgid", ""), b.get("msgctxt", "")
        if not src or b.get("msgid_plural"):
            continue                          # 복수형은 자동 병합하지 않는다
        item = by_id.get(f"{ctx}|{src}")
        if not item:
            continue
        ln = b.get("_lines", {}).get("msgstr")
        if ln is None:
            continue
        # 이어지는 "..." 줄을 먼저 지운다
        j = ln + 1
        while j < len(lines) and lines[j].startswith('"'):
            lines[j] = None
            j += 1
        lines[ln] = f'msgstr "{_po_escape(item.target)}"'
        n += 1
    path.write_text("\n".join(l for l in lines if l is not None) + "\n", encoding="utf-8")
    return n


# ── android ──────────────────────────────────────────────────────────────────

def _android_files(base: Path, lang: str) -> tuple[Path, Path]:
    res = base if base.name == "res" else (base / "res" if (base / "res").is_dir() else base)
    return res / "values" / "strings.xml", res / f"values-{android_qualifier(lang)}" / "strings.xml"


def read_android(base: Path, lang: str, unit: dict) -> list[Item]:
    src_file, tgt_file = _android_files(base, lang)
    if not src_file.exists():
        raise SystemExit(f"{src_file} 가 없다. android 대상의 기본 리소스를 찾지 못했다.")
    existing = {}
    if tgt_file.exists():
        for el in ET.parse(tgt_file).getroot().findall("string"):
            existing[el.get("name")] = "".join(el.itertext())
    items = []
    for el in ET.parse(src_file).getroot().findall("string"):
        if el.get("translatable") == "false":
            continue                          # 금지어를 여기 표시해두는 것이 android 관례다
        name = el.get("name") or ""
        text = "".join(el.itertext())
        if text.startswith("@"):
            continue                          # @string/… 참조는 번역 대상이 아니다
        tgt = existing.get(name)
        items.append(Item(
            id=name, source=text, target=tgt,
            context=unit["path"], comment="",
            kind=guess_kind("", "", name, text),
            status="translated" if tgt else "untranslated",
            unit=unit["path"], fmt="android",
        ))
    return items


def write_android(base: Path, lang: str, items: list[Item], unit: dict) -> int:
    _, tgt_file = _android_files(base, lang)
    tgt_file.parent.mkdir(parents=True, exist_ok=True)
    have = {i.id: i.target for i in items if i.target}
    if tgt_file.exists():
        root = ET.parse(tgt_file).getroot()
    else:
        root = ET.Element("resources")
    present = {el.get("name"): el for el in root.findall("string")}
    n = 0
    for name, value in have.items():
        el = present.get(name)
        if el is None:
            el = ET.SubElement(root, "string")
            el.set("name", name)
        # 아포스트로피를 이스케이프하지 않으면 빌드가 깨진다 (프랑스어·이탈리아어에서 잦다)
        el.text = re.sub(r"(?<!\\)'", r"\\'", value)
        n += 1
    ET.ElementTree(root).write(tgt_file, encoding="utf-8", xml_declaration=True)
    return n


# ── apple ────────────────────────────────────────────────────────────────────

_STRINGS_LINE = re.compile(r'^\s*"((?:[^"\\]|\\.)*)"\s*=\s*"((?:[^"\\]|\\.)*)"\s*;')


def _xcstrings(base: Path) -> Path | None:
    if base.is_file() and base.suffix == ".xcstrings":
        return base
    hits = sorted(base.rglob("*.xcstrings")) if base.is_dir() else []
    return hits[0] if hits else None


def read_apple(base: Path, lang: str, unit: dict) -> list[Item]:
    xc = _xcstrings(base)
    if xc:
        data = json.loads(xc.read_text(encoding="utf-8"))
        src_lang = data.get("sourceLanguage", "en")
        items = []
        for key, entry in (data.get("strings") or {}).items():
            if entry.get("shouldTranslate") is False:
                continue
            locs = entry.get("localizations") or {}
            source = (locs.get(src_lang, {}).get("stringUnit", {}) or {}).get("value") or key
            unit_d = (locs.get(apple_lproj(lang), {}) or {}).get("stringUnit", {}) or {}
            state = unit_d.get("state", "new")
            items.append(Item(
                id=key, source=source, target=unit_d.get("value"),
                context=xc.name, comment=entry.get("comment", ""),
                kind=guess_kind(entry.get("comment", ""), "", key, source),
                status="translated" if state == "translated" else
                       ("needs_review" if state == "needs_review" else "untranslated"),
                unit=unit["path"], fmt="apple", extra={"xcstrings": str(xc)},
            ))
        return items

    src_file = base / "en.lproj" / "Localizable.strings"
    tgt_file = base / f"{apple_lproj(lang)}.lproj" / "Localizable.strings"
    if not src_file.exists():
        raise SystemExit(f"{src_file} 도 .xcstrings 도 찾지 못했다.")
    existing = {}
    if tgt_file.exists():
        for line in tgt_file.read_text(encoding="utf-8").splitlines():
            m = _STRINGS_LINE.match(line)
            if m:
                existing[m.group(1)] = m.group(2)
    items, comment = [], ""
    for line in src_file.read_text(encoding="utf-8").splitlines():
        c = re.match(r"\s*/\*(.*)\*/", line)
        if c:
            comment = c.group(1).strip()
            continue
        m = _STRINGS_LINE.match(line)
        if not m:
            continue
        key, val = m.group(1), m.group(2)
        tgt = existing.get(key)
        items.append(Item(
            id=key, source=val, target=tgt, context="Localizable.strings",
            comment=comment, kind=guess_kind(comment, "", key, val),
            status="translated" if tgt else "untranslated",
            unit=unit["path"], fmt="apple", extra={"strings": str(tgt_file)},
        ))
        comment = ""
    return items


def write_apple(base: Path, lang: str, items: list[Item], unit: dict) -> int:
    xc = _xcstrings(base)
    have = {i.id: i.target for i in items if i.target}
    if xc:
        data = json.loads(xc.read_text(encoding="utf-8"))
        loc = apple_lproj(lang)
        n = 0
        for key, value in have.items():
            entry = (data.setdefault("strings", {})).setdefault(key, {})
            entry.setdefault("localizations", {})[loc] = {
                "stringUnit": {"state": "translated", "value": value}
            }
            n += 1
        xc.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return n

    tgt_file = base / f"{apple_lproj(lang)}.lproj" / "Localizable.strings"
    tgt_file.parent.mkdir(parents=True, exist_ok=True)
    out = []
    for i in items:
        if not i.target:
            continue
        if i.comment:
            out.append(f"/* {i.comment} */")
        out.append(f'"{i.id}" = "{i.target}";')
    tgt_file.write_text("\n".join(out) + "\n", encoding="utf-8")
    return len(have)


# ── json (i18next 등) ────────────────────────────────────────────────────────

def _flatten(d: dict, prefix: str = "") -> dict[str, str]:
    out = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        elif isinstance(v, str):
            out[key] = v
    return out


def _unflatten(flat: dict[str, str]) -> dict:
    root: dict = {}
    for key, val in flat.items():
        cur = root
        parts = key.split(".")
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = val
    return root


def _json_files(base: Path, src_lang: str, lang: str) -> tuple[Path, Path]:
    if base.is_file():
        return base, base.with_name(base.name.replace(src_lang, lang))
    return base / f"{src_lang}.json", base / f"{lang}.json"


def read_json(base: Path, lang: str, unit: dict, src_lang: str = "en") -> list[Item]:
    src_file, tgt_file = _json_files(base, src_lang, lang)
    if not src_file.exists():
        raise SystemExit(f"{src_file} 가 없다.")
    src = _flatten(json.loads(src_file.read_text(encoding="utf-8")))
    tgt = _flatten(json.loads(tgt_file.read_text(encoding="utf-8"))) if tgt_file.exists() else {}
    return [
        Item(id=k, source=v, target=tgt.get(k), context=src_file.name, comment="",
             kind=guess_kind("", "", k, v),
             status="translated" if tgt.get(k) else "untranslated",
             unit=unit["path"], fmt="json", extra={"target_file": str(tgt_file)})
        for k, v in src.items()
    ]


def write_json(base: Path, lang: str, items: list[Item], unit: dict, src_lang: str = "en") -> int:
    _, tgt_file = _json_files(base, src_lang, lang)
    flat = {}
    if tgt_file.exists():
        flat = _flatten(json.loads(tgt_file.read_text(encoding="utf-8")))
    for i in items:
        if i.target:
            flat[i.id] = i.target
    tgt_file.parent.mkdir(parents=True, exist_ok=True)
    tgt_file.write_text(json.dumps(_unflatten(flat), ensure_ascii=False, indent=2), encoding="utf-8")
    return sum(1 for i in items if i.target)


# ── js-object ────────────────────────────────────────────────────────────────
#
# JS 소스 안에 로케일이 박혀 있는 경우. 가장 위험하다 —— 파싱이 깨지면 앱이 안 뜬다.
# 그래서 이해하지 못하는 구조를 만나면 조용히 넘어가지 않고 멈춘다.

_JS_ENTRY = re.compile(r'^\s*([A-Za-z_$][\w$]*)\s*:\s*(["\'])((?:\\.|(?!\2).)*)\2\s*,?\s*$')


def _js_block(text: str, lang: str) -> tuple[int, int] | None:
    """`<lang>: {` 부터 짝이 맞는 `}` 까지의 줄 범위. 못 찾으면 None."""
    lines = text.splitlines()
    start = None
    for n, line in enumerate(lines):
        if re.match(rf'^\s*{re.escape(lang)}\s*:\s*\{{\s*$', line):
            start = n
            break
    if start is None:
        return None
    depth = 0
    for n in range(start, len(lines)):
        depth += lines[n].count("{") - lines[n].count("}")
        if depth == 0 and n > start:
            return start, n
    raise SystemExit(f"js-object: '{lang}' 블록의 중괄호 짝이 안 맞는다. 자동 처리를 멈춘다.")


def read_js_object(base: Path, lang: str, unit: dict, src_lang: str = "en") -> list[Item]:
    path = base if base.is_file() else next(iter(sorted(base.glob("i18n.js"))), None)
    if not path or not path.exists():
        raise SystemExit(f"js-object 대상 파일을 찾지 못했다: {base}")
    text = path.read_text(encoding="utf-8")
    span = _js_block(text, src_lang)
    if span is None:
        raise SystemExit(f"js-object: '{src_lang}' 로케일 블록을 찾지 못했다. 구조가 예상과 다르다.")
    lines = text.splitlines()
    src: dict[str, str] = {}
    for line in lines[span[0] + 1: span[1]]:
        if not line.strip() or line.strip().startswith("//"):
            continue
        m = _JS_ENTRY.match(line)
        if m:
            src[m.group(1)] = m.group(3)
        elif line.strip() not in ("}", "},"):
            raise SystemExit(
                f"js-object: 이해하지 못하는 줄이 있다 —— 망가뜨리지 않으려고 멈춘다.\n"
                f"  {path.name}: {line.strip()[:100]}\n"
                f"  로케일을 별도 JSON 파일로 분리하는 편이 안전하다 (references/formats.md §7)."
            )
    tspan = _js_block(text, lang)
    tgt: dict[str, str] = {}
    if tspan:
        for line in lines[tspan[0] + 1: tspan[1]]:
            m = _JS_ENTRY.match(line)
            if m:
                tgt[m.group(1)] = m.group(3)
    return [
        Item(id=k, source=v, target=tgt.get(k), context=path.name, comment="",
             kind=guess_kind("", "", k, v),
             status="translated" if tgt.get(k) else "untranslated",
             unit=unit["path"], fmt="js-object", extra={"file": str(path)})
        for k, v in src.items()
    ]


def write_js_object(base: Path, lang: str, items: list[Item], unit: dict, src_lang: str = "en") -> int:
    path = Path(items[0].extra["file"]) if items and items[0].extra.get("file") else base
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    have = {i.id: i.target for i in items if i.target}
    if not have:
        return 0

    def render(indent: str) -> list[str]:
        out = [f"{indent}{lang}: {{"]
        for k, v in have.items():
            esc = v.replace("\\", "\\\\").replace('"', '\\"')
            out.append(f'{indent}  {k}: "{esc}",')
        out.append(f"{indent}}},")
        return out

    span = _js_block(text, lang)
    if span:
        indent = re.match(r"\s*", lines[span[0]]).group(0)
        lines[span[0]: span[1] + 1] = render(indent)
    else:
        src_span = _js_block(text, src_lang)
        if src_span is None:
            raise SystemExit("js-object: 기준 로케일 블록을 찾지 못해 새 블록을 넣을 자리를 모른다.")
        indent = re.match(r"\s*", lines[src_span[0]]).group(0)
        lines[src_span[1] + 1: src_span[1] + 1] = render(indent)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(have)


# ── 등록 ─────────────────────────────────────────────────────────────────────

ADAPTERS = {
    "qt-ts":     (read_qt_ts,     write_qt_ts),
    "gettext":   (read_gettext,   write_gettext),
    "android":   (read_android,   write_android),
    "apple":     (read_apple,     write_apple),
    "json":      (read_json,      write_json),
    "js-object": (read_js_object, write_js_object),
}

# markdown 은 문자열 단위가 아니라 문서 단위로 다룬다. 문단을 쪼개면 맥락이 끊겨
# 번역이 나빠지고, 되쓰기에서 구조가 깨진다. references/formats.md §8 참조.
NOT_EXTRACTED = {"markdown"}
