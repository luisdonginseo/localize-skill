"""localize 스크립트가 공유하는 것들.

여기 있는 규칙이 틀리면 검사 전체가 조용히 무력해진다. 그래서 포맷별 차이를
한곳에 모아 두고, 모르는 포맷을 만나면 추측하지 않고 예외를 던진다.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path


# ── 콘솔 인코딩 ──────────────────────────────────────────────────────────────
#
# 윈도우 콘솔은 기본이 cp949 라 한국어는 물론 —, 🔴 같은 문자에서 터진다.
# 맥·리눅스에서는 안 나는 버그라 한쪽에서만 개발하면 못 본다. 모든 스크립트가
# 이 모듈을 import 하므로 여기서 한 번만 처리한다.

def _force_utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            enc = (getattr(stream, "encoding", "") or "").lower().replace("-", "")
            if enc != "utf8":
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass          # 파이프로 넘길 때 등 —— 출력 인코딩 때문에 죽지는 않게 한다


_force_utf8_console()


# ── 번역 단위 ────────────────────────────────────────────────────────────────

@dataclass
class Item:
    """번역 한 줄. 번역에 필요한 것이 전부 들어 있어야 한다 —— 모델이 파일을
    다시 열어보지 않아도 되도록."""
    id: str                     # 같은 항목을 다시 찾을 안정된 열쇠
    source: str                 # 원문
    target: str | None = None   # 기존 번역
    context: str = ""           # 클래스명 · msgctxt · 파일 경로
    comment: str = ""           # 개발자 주석
    kind: str = "unknown"       # button · menu · body · unknown  → 길이 예산이 본다
    status: str = "untranslated"  # untranslated · needs_review · translated
    unit: str = ""              # 어느 대상에서 왔나
    fmt: str = ""               # 포맷 —— 플레이스홀더 규칙이 이걸 본다
    plural: bool = False
    extra: dict = field(default_factory=dict)  # 포맷별 되쓰기 정보

    def to_json(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_json(d: dict) -> "Item":
        known = {f for f in Item.__dataclass_fields__}
        return Item(**{k: v for k, v in d.items() if k in known})


# ── 플레이스홀더 ─────────────────────────────────────────────────────────────
#
# 포맷마다 문법이 다르다. 섞으면 런타임에 문자열이 깨지는데, 그건 번역 품질
# 문제가 아니라 버그다. 그래서 포맷을 모르면 추측하지 않는다.

PLACEHOLDER_PATTERNS: dict[str, list[str]] = {
    "qt-ts":     [r"%\d+", r"%n"],
    "gettext":   [r"\{\d*\}", r"%\d+\$[sdfi@]", r"%[sdfi]"],
    "android":   [r"%\d+\$[sdfi]", r"%[sdfi]", r"<xliff:g[^>]*>.*?</xliff:g>"],
    "apple":     [r"%\d+\$[@sdfi]", r"%[@sdfi]"],
    "json":      [r"\{\{[^}]+\}\}", r"\{[A-Za-z_][\w.]*\}", r"%[sdfi]"],
    "js-object": [r"\{\{[^}]+\}\}", r"\{[A-Za-z_][\w.]*\}", r"%[sdfi]"],
    "markdown":  [],
}

HTML_TAG = re.compile(r"</?[A-Za-z][\w-]*(?:\s[^<>]*)?/?>")


def placeholders(text: str, fmt: str) -> list[str]:
    """이 문자열에 들어 있는 플레이스홀더를 **나온 순서대로** 돌려준다.

    순서를 보존하는 이유: 번호 없는 플레이스홀더(%s · {})는 순서가 곧 의미다.
    어순을 바꾸면 값이 뒤바뀐다.
    """
    pats = PLACEHOLDER_PATTERNS.get(fmt)
    if pats is None:
        raise ValueError(
            f"모르는 포맷 '{fmt}' —— 플레이스홀더 규칙이 없다. "
            f"references/formats.md 를 보고 PLACEHOLDER_PATTERNS 에 등록해야 한다."
        )
    found: list[tuple[int, str]] = []
    for p in pats:
        for m in re.finditer(p, text):
            found.append((m.start(), m.group(0)))
    found.sort()
    # 겹치는 매치 제거 (%1$s 가 %s 로도 잡히는 경우)
    out: list[str] = []
    last_end = -1
    for start, tok in found:
        if start < last_end:
            continue
        out.append(tok)
        last_end = start + len(tok)
    return out


def html_tags(text: str) -> list[str]:
    """HTML 태그를 나온 순서대로. 태그명만 비교하려면 tag_names() 를 쓴다."""
    return HTML_TAG.findall(text)


def tag_names(tags: list[str]) -> list[str]:
    """`<strong class=x>` → `strong`. 속성이 달라지는 건 허용하고 태그 누락만 잡는다."""
    out = []
    for t in tags:
        m = re.match(r"</?([A-Za-z][\w-]*)", t)
        if m:
            out.append(m.group(1).lower())
    return out


# ── 종류 추정 ────────────────────────────────────────────────────────────────

_KIND_HINTS = {
    "button": ("button", "btn", "단추", "버튼", "label", "action"),
    "menu":   ("menu", "메뉴", "item", "tab"),
    "body":   ("body", "description", "설명", "본문", "message", "paragraph", "help"),
}


def guess_kind(comment: str, context: str, key: str, source: str) -> str:
    """길이 예산이 이걸 본다.

    주석이 있으면 그걸 믿고, 없으면 열쇠 이름과 길이로 짐작한다. 짐작이라
    틀릴 수 있지만, 길이 검사는 경보이지 오류가 아니므로 감당할 수 있다.
    """
    hay = f"{comment} {context} {key}".lower()
    for kind, hints in _KIND_HINTS.items():
        if any(h in hay for h in hints):
            return kind
    if len(source) <= 20 and "." not in source.rstrip("."):
        return "button"       # 짧고 문장이 아니면 대개 라벨이다
    if len(source) > 80:
        return "body"
    return "unknown"


# ── 설정 ─────────────────────────────────────────────────────────────────────

DEFAULT_BUDGET = {"button": 1.3, "menu": 1.5, "default": 1.6, "body": 3.0}


def load_config(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        raise SystemExit(
            f"설정이 없다: {p}\n"
            f"SKILL.md 1단계(첫 실행 인터뷰)를 먼저 해서 .i18n.json 을 만들어야 한다."
        )
    cfg = json.loads(p.read_text(encoding="utf-8"))
    cfg.setdefault("source", "en")
    cfg.setdefault("targets", [])
    cfg.setdefault("do_not_translate", [])
    cfg.setdefault("length_budget", dict(DEFAULT_BUDGET))
    cfg.setdefault("units", [])
    cfg["_root"] = str(p.parent.resolve())
    return cfg


def budget_for(cfg: dict, kind: str) -> float:
    b = cfg.get("length_budget", DEFAULT_BUDGET)
    return float(b.get(kind, b.get("default", DEFAULT_BUDGET["default"])))


def load_glossary(cfg: dict) -> dict:
    """프로젝트 용어집. 없으면 빈 것을 돌려준다 —— 없다고 실패시키지 않는다."""
    rel = cfg.get("project_glossary")
    if not rel:
        return {"do_not_translate": cfg.get("do_not_translate", []), "terms": {}}
    p = Path(cfg["_root"]) / rel
    if not p.exists():
        return {"do_not_translate": cfg.get("do_not_translate", []), "terms": {}}
    g = json.loads(p.read_text(encoding="utf-8"))
    g.setdefault("terms", {})
    g.setdefault("do_not_translate", [])
    # 설정 쪽 금지어와 합친다
    merged = list(dict.fromkeys(g["do_not_translate"] + cfg.get("do_not_translate", [])))
    g["do_not_translate"] = merged
    return g


# ── 입출력 ───────────────────────────────────────────────────────────────────

def write_bundle(path: str | Path, cfg: dict, lang: str, items: list[Item]) -> None:
    payload = {
        "source_lang": cfg.get("source", "en"),
        "target_lang": lang,
        "count": len(items),
        "items": [i.to_json() for i in items],
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_bundle(path: str | Path) -> tuple[dict, list[Item]]:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return d, [Item.from_json(x) for x in d.get("items", [])]


def unit_paths(cfg: dict, unit: dict) -> Path:
    return Path(cfg["_root"]) / unit["path"]


# ── 파일 훑기 ────────────────────────────────────────────────────────────────
#
# 제외 목록이 좁으면 진단이 조용히 거짓말을 한다 —— 가상환경 안의 PySide6 가
# 들고 있는 .qm 수백 개를 "우리 번역본" 으로 세는 식이다. 숫자가 틀리면 판단이
# 틀리므로 여기를 넉넉하게 잡는다.

SKIP_DIRS = {
    ".git", ".hg", ".svn",
    "node_modules", "bower_components", "vendor", "third_party", "Pods",
    "venv", ".venv", "env", ".env", "virtualenv", "site-packages", "dist-packages",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox",
    "build", "dist", "out", "target", ".gradle", ".idea", ".vs", "DerivedData",
}


def iter_files(root: Path, pattern: str):
    """프로젝트 자체 파일만. 남의 라이브러리는 세지 않는다."""
    for p in root.rglob(pattern):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        yield p
