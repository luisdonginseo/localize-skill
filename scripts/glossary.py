"""플랫폼 용어집 —— 받고, 색인을 만들고, 이번 번들에 실제로 걸리는 항목만 뽑는다.

  python glossary.py status                                  # 무엇이 있나 · 언어별로 빠진 것
  python glossary.py langs                                   # 아는 언어 코드와 각 소스의 이름
  python glossary.py fetch  --lang ko de ja                  # Microsoft · AOSP 를 받는다(사람이 내려받기를 허락한 뒤)
  python glossary.py import-apple ~/Downloads                # Apple 용어집 DMG(사람이 계정으로 받은 것)를 푼다
  python glossary.py index  --lang ko de ja                  # 언어마다 색인(~/.cache/localize/glossaries/index/<lang>.json)
  python glossary.py lookup --lang de --source work/de.json --out work/de.glossary.md
  python glossary.py term   --lang de "Settings" "Forget This Device"

캐시(스킬 안에 넣어 배포하지 않는다 —— references/glossaries.md 의 까닭):
  ~/.cache/localize/glossaries/microsoft/MicrosoftTermCollection.zip · <lang>.tbx
  ~/.cache/localize/glossaries/aosp/<app>/values[-xx]/strings.xml       (framework · settings)
  ~/.cache/localize/glossaries/apple/dmg/<Name>.dmg · apple/<Name>/**/*.lg

규칙: 우선순위는 금지어 > 프로젝트 용어집 > 플랫폼 용어집 > 모델 판단. 플랫폼 용어집이
답하는 낱말은 모델이 고르지 않는다 —— 대상 플랫폼의 낱말을 쓴다(윈도우 문장은 Microsoft,
맥 · iOS · iPadOS 는 Apple, 안드로이드는 AOSP). 표면이 여럿에 걸치면 그 표면의 주 플랫폼을 따른다.
세 소스가 다르면 셋을 다 보이고(빈도 순), 프로젝트 용어집에 하나로 고정한다.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common  # noqa: F401,E402  —— 콘솔 인코딩

ROOT = Path.home() / ".cache" / "localize" / "glossaries"
INDEX = ROOT / "index"

MS_URL = "https://download.microsoft.com/download/b/2/d/b2db7a7c-8d33-47f3-b2c1-ee5e6445cf45/MicrosoftTermCollection.zip"
AOSP_RAW = "https://raw.githubusercontent.com/aosp-mirror/{repo}/main/{path}/{values}/strings.xml"
AOSP_APPS = {"framework": ("platform_frameworks_base", "core/res/res"),
             "settings": ("platform_packages_apps_settings", "res")}
APPLE_PAGE = "https://developer.apple.com/download/all/?q=Glossaries%20-%20iOS"

# 언어 표: references/platform-languages.json —— 코드마다 {microsoft: zip 안 .tbx 이름, aosp: values 폴더,
# apple: iOS 용어집 DMG 이름, apple_loc: .lg 의 loc}. 소스에 없는 언어는 null. 새 언어는 그 파일에 한 줄을 더한다.
_TABLE = json.loads((Path(__file__).resolve().parent.parent / "references" / "platform-languages.json").read_text(encoding="utf-8"))
LANGS: dict[str, tuple] = {k: (v["microsoft"], v["aosp"], v["apple"], v["apple_loc"]) for k, v in _TABLE.items()}
ALIASES = {"zh_Hant": "zh_TW", "zh_Hans": "zh_CN", "zh-TW": "zh_TW", "zh-CN": "zh_CN", "pt-BR": "pt_BR",
           "es-419": "es_419", "pt": "pt_BR", "zh": "zh_CN"}

STOP = {"a", "an", "the", "and", "or", "of", "to", "in", "on", "at", "for", "by", "with", "from", "it", "is",
        "be", "this", "that", "you", "your", "no", "not", "yes", "if", "as", "can", "will", "do"}
MAX_WORDS = 6          # 원문에서 찾는 낱말 묶음의 최대 길이
MAX_PER_TERM = 3       # 한 낱말 · 한 소스에 남길 번역 수(빈도 순)
MAX_LEN = 60           # 이보다 긴 원문은 문장이라 용어로 보지 않는다


def code(lang: str) -> str:
    lang = ALIASES.get(lang, lang)
    if lang not in LANGS:
        sys.exit(f"모르는 언어 코드: {lang} —— `glossary.py langs` 를 보고 LANGS 에 한 줄을 더한다")
    return lang


def norm(text: str) -> str:
    text = text.replace("…", "").replace("&", "").replace("_", "")
    text = re.sub(r"%\d*\$?[@sdlf]+|\{[^}]*\}", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower().rstrip(".:?!")


class Builder:
    """낱말 → 소스(microsoft · apple · aosp) → 번역의 빈도. 많이 쓰인 번역이 앞에 온다."""

    def __init__(self) -> None:
        self.data: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))

    def add(self, en: str, tr: str, src: str) -> None:
        key, tr = norm(en), (tr or "").strip()
        if key and tr and len(key) <= MAX_LEN:
            self.data[key][src][tr] += 1

    def result(self) -> dict:
        return {k: {s: [t for t, _ in c.most_common(MAX_PER_TERM)] for s, c in srcs.items()}
                for k, srcs in self.data.items()}


# ── 받기 ────────────────────────────────────────────────────────────────────

def _download(url: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("curl"):          # 파이썬 인증서 묶음이 없는 설치(python.org 판 맥 등)에서도 OS 인증서로 받는다
        r = subprocess.run(["curl", "-sSLf", "-o", str(dest), url], capture_output=True, text=True)
        if r.returncode == 0:
            return True
        print(f"  ! 받지 못함 {url}: {r.stderr.strip()[:120]}")
        dest.unlink(missing_ok=True)
        return False
    try:
        with urllib.request.urlopen(url, timeout=120) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
        return True
    except Exception as e:  # noqa: BLE001 —— 받기 실패는 보고하고 다음으로
        print(f"  ! 받지 못함 {url}: {e}")
        dest.unlink(missing_ok=True)
        return False


def cmd_fetch(a) -> int:
    langs = [code(l) for l in a.lang]
    ms = ROOT / "microsoft"
    zip_path = ms / "MicrosoftTermCollection.zip"
    if not zip_path.exists():
        print(f"Microsoft 용어 모음(약 170 MB) 받는 중 → {zip_path}")
        _download(MS_URL, zip_path)
    for l in langs:
        if not LANGS[l][0]:
            print(f"  microsoft {l}: 이 소스에 없는 언어")
        else:
            src = _ms_source(l)
            print(f"  microsoft {l}: " + ("있음(zip 안에서 읽는다)" if src else "zip 에 없음 —— platform-languages.json 의 이름을 맞춘다"))
            if src:
                src.close()
    for app, (repo, path) in AOSP_APPS.items():
        for values in ["values"] + [LANGS[l][1] for l in langs if LANGS[l][1]]:
            out = ROOT / "aosp" / app / values / "strings.xml"
            if not out.exists():
                _download(AOSP_RAW.format(repo=repo, path=path, values=values), out)
        print(f"  aosp/{app}: " + ", ".join(f"{l}={'있음' if LANGS[l][1] and (ROOT / 'aosp' / app / LANGS[l][1] / 'strings.xml').exists() else '없음'}" for l in langs))
    missing = [l for l in langs if LANGS[l][2] and not (ROOT / "apple" / "dmg" / f"{LANGS[l][2]}.dmg").exists()]
    if missing:
        print("\nApple 용어집은 Apple 개발자 계정(무료)으로 사람이 받는다 —— 자동으로 받지 않는다:")
        print(f"  1) {APPLE_PAGE} 에서 'View Details'")
        print("  2) 받을 DMG: " + ", ".join(f"{LANGS[l][2].replace('_', ' ')}.dmg" for l in missing))
        print("  3) python glossary.py import-apple ~/Downloads")
    return 0


def cmd_import_apple(a) -> int:
    """사람이 받은 Apple 용어집 DMG 를 캐시로 옮긴다. 풀지 않고 DMG 로 둔다 —— index 가 그때 붙여 읽는다.
    --extract 면 풀어 둔다(자주 색인을 다시 만들 언어만. 인도 언어 .tmx 는 언어당 약 270 MB)."""
    src = Path(a.path).expanduser()
    dmgs = [src] if src.is_file() else sorted(src.glob("*.dmg"))
    known = {v[2] for v in LANGS.values() if v[2]}
    keep_dir = ROOT / "apple" / "dmg"
    keep_dir.mkdir(parents=True, exist_ok=True)
    moved = 0
    for dmg in dmgs:
        name = re.sub(r" \(\d+\)$", "", dmg.stem).replace(" ", "_").replace("(", "").replace(")", "")
        if name not in known:
            continue
        keep = keep_dir / f"{name}.dmg"
        if dmg.resolve() != keep.resolve():
            if keep.exists():
                dmg.unlink()                       # 같은 이름이 이미 있으면 새로 받은 사본은 지운다
                print(f"  apple {name}: 이미 있음 —— 받은 사본을 지움")
                continue
            shutil.move(str(dmg), keep)
        moved += 1
        print(f"  apple {name}: {keep}")
        if a.extract:
            out = ROOT / "apple" / name
            mp = Path(tempfile.mkdtemp())
            try:
                subprocess.run(["hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint", str(mp), str(keep)],
                               check=True, capture_output=True)
                shutil.copytree(mp, out, dirs_exist_ok=True)
            finally:
                subprocess.run(["hdiutil", "detach", str(mp)], capture_output=True)
                shutil.rmtree(mp, ignore_errors=True)
    if not moved:
        print("  옮긴 DMG 가 없다(이름이 platform-languages.json 의 apple 이름과 맞는지 본다)")
    return 0


# ── 읽기 ────────────────────────────────────────────────────────────────────

def _ms_source(lang: str):
    """언어별 .tbx —— 꺼내 둔 파일이 있으면 그것, 없으면 zip 안에서 바로 읽는다(꺼내지 않아 디스크를 아낀다)."""
    path = ROOT / "microsoft" / f"{lang}.tbx"
    if path.exists():
        return open(path, "rb")
    zip_path = ROOT / "microsoft" / "MicrosoftTermCollection.zip"
    name = LANGS[lang][0]
    if not name or not zip_path.exists():
        return None
    ascii_name = lambda n: re.sub(r"[^A-Z()' ]", "", n.upper())
    z = zipfile.ZipFile(zip_path)
    member = {ascii_name(n[:-4]): n for n in z.namelist() if n.endswith(".tbx")}.get(ascii_name(name))
    return z.open(member) if member else None


def _ms(b: Builder, lang: str) -> int:
    src = _ms_source(lang)
    if src is None:
        return 0
    n = 0
    xml_lang = "{http://www.w3.org/XML/1998/namespace}lang"
    for _, el in ET.iterparse(src, events=("end",)):
        if el.tag != "termEntry":
            continue
        en, tr = [], []
        for ls in el.iter("langSet"):
            terms = [t.text or "" for t in ls.iter("term")]
            (en if ls.get(xml_lang, "").lower().startswith("en") else tr).extend(terms)
        for e in en:
            for t in tr:
                b.add(e, t, "microsoft")
                n += 1
        el.clear()
    return n


def _strings(path: Path) -> dict[str, str]:
    out = {}
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return out
    for s in root.iter("string"):
        name = s.get("name")
        text = "".join(s.itertext()).replace("\\'", "'").replace('\\"', '"').strip()
        if len(text) >= 2 and text[0] == text[-1] == '"':
            text = text[1:-1].strip()          # AOSP 는 앞뒤 공백을 지키려고 값을 따옴표로 감싼다
        if name and text:
            out[name] = text
    return out


def _aosp(b: Builder, lang: str) -> int:
    n = 0
    for app in AOSP_APPS:
        en = _strings(ROOT / "aosp" / app / "values" / "strings.xml")
        if not LANGS[lang][1]:
            return 0
        tr = _strings(ROOT / "aosp" / app / LANGS[lang][1] / "strings.xml")
        for name, text in en.items():
            if name in tr:
                b.add(text, tr[name], "aosp")
                n += 1
    return n


_BAD_XML = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _events(path: Path):
    """XML 끝 이벤트 —— Apple 파일에는 XML 에 쓸 수 없는 제어 글자(\\b 등)가 섞여 있어 걸러 가며 읽는다."""
    parser = ET.XMLPullParser(events=("end",))
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            parser.feed(_BAD_XML.sub(b"", chunk))
            yield from parser.read_events()
    parser.close()
    yield from parser.read_events()


def _apple_files(folder: Path):
    return sorted(list(folder.rglob("*.lg")) + list(folder.rglob("*.tmx")))


def _apple_parse(b: Builder, files, want: str) -> int:
    n = 0
    for path in files:
        try:
            if path.suffix == ".lg":
                for _, el in _events(path):
                    if el.tag != "TranslationSet":
                        continue
                    base, tran = el.find("base"), el.find("tran")
                    if base is not None and tran is not None and base.text and tran.text \
                            and (tran.get("loc") or "").lower().replace("_", "-") == want:
                        b.add(base.text, tran.text, "apple")
                        n += 1
                    el.clear()
            else:                                   # .tmx —— 인도 언어들은 이 꼴로 온다(언어당 약 270 MB)
                xml_lang = "{http://www.w3.org/XML/1998/namespace}lang"
                for _, el in _events(path):
                    if el.tag != "tu":
                        continue
                    segs = {}
                    for tuv in el.iter("tuv"):
                        seg = tuv.find("seg")
                        segs[(tuv.get(xml_lang) or "").lower()] = "".join(seg.itertext()) if seg is not None else ""
                    if segs.get("en") and segs.get(want):
                        b.add(segs["en"], segs[want], "apple")
                        n += 1
                    el.clear()
        except ET.ParseError:
            print(f"  ! 읽지 못함: {path.name}", file=sys.stderr)
    return n


def _apple(b: Builder, lang: str) -> int:
    name = LANGS[lang][2]
    if not name:
        return 0
    want = (LANGS[lang][3] or lang).lower().replace("_", "-")
    folder = ROOT / "apple" / name
    if folder.exists() and _apple_files(folder):
        return _apple_parse(b, _apple_files(folder), want)
    dmg = ROOT / "apple" / "dmg" / f"{name}.dmg"
    if not dmg.exists():
        return 0
    mp = Path(tempfile.mkdtemp())               # 풀어 두지 않은 언어는 DMG 를 잠깐 붙여 읽는다(디스크를 아낀다)
    try:
        subprocess.run(["hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint", str(mp), str(dmg)],
                       check=True, capture_output=True)
        return _apple_parse(b, _apple_files(mp), want)
    finally:
        subprocess.run(["hdiutil", "detach", str(mp)], capture_output=True)
        shutil.rmtree(mp, ignore_errors=True)


# ── 명령 ────────────────────────────────────────────────────────────────────

def cmd_langs(_a) -> int:
    print("코드     Microsoft(zip 안 .tbx)       AOSP values          Apple DMG")
    for l, (ms, aosp, apple, _) in LANGS.items():
        print(f"{l:15s} {ms or '-':28s} {aosp or '-':20s} {(apple + '.dmg') if apple else '-'}")
    print("\n새 언어: LANGS 에 한 줄 → fetch --lang <코드> → (Apple DMG 받기 → import-apple) → index --lang <코드>")
    return 0


def cmd_status(_a) -> int:
    print(f"캐시: {ROOT}")
    rows = []
    for l in LANGS:
        have = [("microsoft", bool(LANGS[l][0]) and ((ROOT / "microsoft" / f"{l}.tbx").exists() or (ROOT / "microsoft" / "MicrosoftTermCollection.zip").exists())),
                ("aosp", bool(LANGS[l][1]) and (ROOT / "aosp" / "framework" / LANGS[l][1] / "strings.xml").exists()),
                ("apple", bool(LANGS[l][2]) and ((ROOT / "apple" / LANGS[l][2]).exists() or (ROOT / "apple" / "dmg" / f"{LANGS[l][2]}.dmg").exists())),
                ("index", (INDEX / f"{l}.json").exists())]
        if any(h for _, h in have):
            rows.append(f"  {l:7s} " + "  ".join(f"{n} {'✓' if h else '·'}" for n, h in have))
    print("\n".join(rows) if rows else "  아무것도 없음 —— fetch 부터(사람이 내려받기를 허락한 뒤)")
    return 0


def cmd_index(a) -> int:
    INDEX.mkdir(parents=True, exist_ok=True)
    bad = 0
    for l in [code(x) for x in a.lang]:
        b = Builder()
        counts = {"microsoft": _ms(b, l), "aosp": _aosp(b, l), "apple": _apple(b, l)}
        data = b.result()
        (INDEX / f"{l}.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"{l}: 낱말 {len(data)}개 —— " + " · ".join(f"{k} {v}" for k, v in counts.items()))
        has = {"microsoft": LANGS[l][0], "aosp": LANGS[l][1], "apple": LANGS[l][2]}
        missing = [k for k, v in counts.items() if not v and has[k]]
        if missing:
            print(f"  ⚠️ 없음: {', '.join(missing)} —— fetch / import-apple 로 채운다")
            bad += 1
    return 1 if bad else 0


def _load(lang: str) -> dict:
    path = INDEX / f"{lang}.json"
    if not path.exists():
        sys.exit(f"색인 없음: {path} —— 먼저 `glossary.py index --lang {lang}`")
    return json.loads(path.read_text(encoding="utf-8"))


def _hits(idx: dict, text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z'’\-]*", text.replace("…", " "))
    found, taken = [], set()
    for size in range(min(MAX_WORDS, len(words)), 0, -1):          # 긴 것부터 —— "Receive folder" 가 "folder" 를 이긴다
        for i in range(len(words) - size + 1):
            if any(j in taken for j in range(i, i + size)):
                continue
            key = norm(" ".join(words[i:i + size]))
            if key in idx and (size > 1 or (len(key) > 2 and key not in STOP)):
                found.append(key)
                taken.update(range(i, i + size))
    whole = norm(text)
    if whole in idx and whole not in found:
        found.insert(0, whole)
    return found


def _fmt(entry: dict) -> str:
    order = ["apple", "microsoft", "aosp"]
    return " · ".join(f"{s}: {' / '.join(entry[s])}" for s in order if s in entry)


def cmd_lookup(a) -> int:
    lang = code(a.lang)
    idx = _load(lang)
    bundle = json.loads(Path(a.source).read_text(encoding="utf-8"))
    sources = sorted({it["source"] for it in bundle["items"]})
    terms = sorted({k for s in sources for k in _hits(idx, s)})
    lines = [f"# 플랫폼 용어집 —— {lang} ({len(terms)}개 낱말, 원문 {len(sources)}줄에서)", "",
             "표면의 플랫폼을 따른다: 맥 · iOS · iPadOS = apple, 윈도우 = microsoft, 안드로이드 = aosp.",
             "금지어 · 프로젝트 용어집이 먼저다. 소스마다 빈도 순(앞이 가장 많이 쓰인 번역).", ""]
    lines += [f"- **{k}** —— {_fmt(idx[k])}" for k in terms]
    text = "\n".join(lines) + "\n"
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"{lang}: {len(terms)}개 낱말 → {a.out}")
    else:
        print(text)
    return 0


def cmd_term(a) -> int:
    lang = code(a.lang)
    idx = _load(lang)
    for t in a.terms:
        k = norm(t)
        print(f"{t}: {_fmt(idx[k]) if k in idx else '(없음)'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("langs")
    p = sub.add_parser("fetch"); p.add_argument("--lang", nargs="+", required=True)
    p = sub.add_parser("import-apple"); p.add_argument("path"); p.add_argument("--extract", action="store_true")
    p = sub.add_parser("index"); p.add_argument("--lang", nargs="+", required=True)
    p = sub.add_parser("lookup"); p.add_argument("--lang", required=True); p.add_argument("--source", required=True); p.add_argument("--out")
    p = sub.add_parser("term"); p.add_argument("--lang", required=True); p.add_argument("terms", nargs="+")
    a = ap.parse_args()
    return {"status": cmd_status, "langs": cmd_langs, "fetch": cmd_fetch, "import-apple": cmd_import_apple,
            "index": cmd_index, "lookup": cmd_lookup, "term": cmd_term}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
