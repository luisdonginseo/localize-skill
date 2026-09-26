# 포맷별 안내

목차
1. [플레이스홀더 문법 — 한눈에](#1-플레이스홀더-문법--한눈에)
2. [qt-ts](#2-qt-ts--qt--pyside6)
3. [gettext](#3-gettext--po--pot--slint-포함)
4. [android](#4-android--stringsxml)
5. [apple](#5-apple--strings--xcstrings)
6. [json](#6-json--i18next-등)
7. [js-object](#7-js-object--js-소스-안의-로케일-객체)
8. [markdown](#8-markdown--문서--랜딩)
9. [새 포맷을 추가할 때](#9-새-포맷을-추가할-때)

---

## 1. 플레이스홀더 문법 — 한눈에

**포맷마다 다르다.** 이걸 섞으면 런타임에 문자열이 깨진다.

| 포맷 | 문법 | 예 |
|---|---|---|
| qt-ts | `%1` `%2` … | `"%1 개 파일"` |
| gettext (Slint) | `{}` · `{0}` | `@tr("Hello, {}", name)` |
| gettext (전통) | `%s` `%d` · `%1$s` | `"%s not found"` |
| android | `%1$s` `%2$d` | `"%1$s 개"` |
| apple | `%@` `%1$@` `%d` | `"%1$@ files"` |
| json / js-object | 라이브러리마다 다름 — `{{name}}` · `{name}` · `%s` | 프로젝트를 보고 판단 |

**공통 규칙**
- 개수와 표기를 **그대로** 둔다
- 번호가 붙은 것(`%1` · `%1$s` · `{0}`)은 **어순이 바뀌면 번호도 따라간다.** 독일어·일본어는
  어순이 달라서 이게 실제로 필요하다 — 번호를 지우고 순서만 바꾸면 값이 뒤바뀐다
- 번호가 없는 것(`%s` · `{}`)은 **순서를 바꿀 수 없다.** 어순을 바꿔야 하면 문장을 다시 짜거나
  개발자에게 번호 있는 형태로 바꿔 달라고 해야 한다

---

## 2. qt-ts — Qt · PySide6

**원본은 `.ts`(XML), 배포본은 `.qm`(바이너리).** `.qm` 만 있으면 원본이 없는 것이다.

```xml
<context>
  <name>SearchWindow</name>
  <message>
    <location filename="search_window.py" line="271"/>
    <source>Enter open   ·   Ctrl+Enter folder</source>
    <extracomment>하단 힌트 바. 한 줄에 들어가야 한다</extracomment>
    <translation type="unfinished"></translation>
  </message>
  <message numerus="yes">
    <source>%n file(s)</source>
    <translation><numerusform></numerusform></translation>
  </message>
</context>
```

| 요소 | 뜻 |
|---|---|
| `<name>` | **맥락.** 보통 클래스명. 같은 원문이라도 맥락이 다르면 다른 항목이다 |
| `<source>` | 원문 |
| `<comment>` | 동음이의 구분(disambiguation). 같은 원문을 구분하는 열쇠의 일부 |
| `<extracomment>` | **개발자 주석.** 소스의 `//:` 가 여기로 온다. 번역에 가장 유용하다 |
| `type="unfinished"` | 미번역. 이게 있으면 증분 대상 |
| `type="vanished"` | 소스에서 사라진 문자열. 건드리지 않는다 |
| `numerus="yes"` | 복수형. `<numerusform>` 이 언어별 개수만큼 필요하다 |

**원본 생성·갱신**
```bash
pylupdate6 <소스…> -ts translations/app_de.ts     # PySide6
lupdate <프로젝트>.pro                              # C++ Qt
lrelease translations/app_de.ts                   # .ts → .qm (배포용)
```

**소스에서 맥락 주석 다는 법**
```python
#: 버튼 라벨. 최대 12자
self.tr("Open folder")
```
`#:` 로 시작하는 주석이 `<extracomment>` 로 들어간다. (C++ 은 `//:`)

⚠️ 복수형은 언어마다 형태 수가 다르다(영어 2 · 한국어 1 · 러시아어 3 · 아랍어 6).
`<numerusform>` 개수를 임의로 바꾸지 마라 — Qt 가 언어별로 정한다.

---

## 3. gettext — .po / .pot (Slint 포함)

```
#. 개발자 주석 (extracted comment)
#: src/main.rs:42
msgctxt "Toolbar"
msgid "Open"
msgstr ""

msgid "%n file"
msgid_plural "%n files"
msgstr[0] ""
msgstr[1] ""
```

| 요소 | 뜻 |
|---|---|
| `#.` | **개발자 주석.** 번역에 가장 유용 |
| `#:` | 소스 위치 |
| `msgctxt` | 맥락. 같은 `msgid` 를 구분한다 |
| `msgstr ""` | 미번역 |
| `#, fuzzy` | 원문이 바뀌어 재검토 필요. **증분 대상으로 본다** |

**Slint**

Slint 1.1+ 는 `@tr()` 매크로 + gettext 다.

```slint
Text { text: @tr("Hello, {}", name); }
Text { text: @tr("Toolbar" => "Open"); }   // 맥락 붙이기
```

```bash
slint-tr-extractor ui/*.slint -o translations/app.pot
msginit --input=app.pot --locale=de --output=de/LC_MESSAGES/app.po
msgfmt de/LC_MESSAGES/app.po -o de/LC_MESSAGES/app.mo   # 런타임은 .mo
```

Rust 쪽은 `slint` 크레이트의 `gettext` 피처를 켜고 `slint::init_translations!` 로
`.mo` 위치를 지정한다.

🔴 **`@tr()` 로 감싸지 않은 문자열은 추출되지 않는다.** `.slint` 에 `@tr(` 이 0곳이면
번역 인프라가 없는 것이고, **번역이 아니라 마킹 작업이 먼저**다.

---

## 4. android — strings.xml

```
res/values/strings.xml        기본(보통 영어)
res/values-de/strings.xml     독일어
res/values-ja/strings.xml     일본어
res/values-zh-rTW/strings.xml 번체  ← 지역 코드는 r 접두사
```

```xml
<string name="app_name" translatable="false">Acme</string>
<string name="files_found">%1$d 개 파일</string>
<plurals name="file_count">
  <item quantity="one">%d file</item>
  <item quantity="other">%d files</item>
</plurals>
<string-array name="modes">
  <item>Fast</item>
</string-array>
```

| 주의 | |
|---|---|
| `translatable="false"` | **번역 대상에서 뺀다.** 금지어를 여기에 표시해두면 좋다 |
| 아포스트로피 | `'` 는 `\'` 로 이스케이프해야 한다. 프랑스어·이탈리아어에서 자주 터진다 |
| `@string/…` 참조 | 값이 참조면 번역하지 않는다 |
| `<xliff:g>` | 치환 구간 표시. 내용을 건드리지 않는다 |
| 지역 코드 | `values-zh-rTW` 처럼 `r` 접두사가 붙는다 (BCP 47 과 다르다) |

---

## 5. apple — .strings / .xcstrings

**`.strings`(구형)**
```
/* 버튼 라벨 */
"open_folder" = "Open Folder";
```

**`.xcstrings`(String Catalog, Xcode 15+)** — JSON 이다.
```json
{
  "sourceLanguage": "en",
  "strings": {
    "open_folder": {
      "comment": "버튼 라벨",
      "localizations": {
        "de": { "stringUnit": { "state": "translated", "value": "Ordner öffnen" } }
      }
    }
  }
}
```

| 주의 | |
|---|---|
| `state` | `new` · `needs_review` · `translated`. **`new` 와 `needs_review` 가 증분 대상** |
| `shouldTranslate: false` | 번역 대상에서 뺀다 |
| 복수형 | `variations.plural.{one,other}` 아래에 들어간다 |
| 플레이스홀더 | `%@` 가 객체, `%d` 가 정수. 번호형은 `%1$@` |

---

## 6. json — i18next 등

```json
{ "search": { "placeholder": "Search files", "hint": "{{count}} results" } }
```

- **중첩 키를 평탄화**해서 다룬다 (`search.placeholder`)
- 플레이스홀더 문법이 라이브러리마다 다르다. **`en` 파일을 먼저 보고 실제 쓰이는 형태를
  확인**한 뒤 그 규칙으로 검사한다
- 복수형은 키 접미사로 표현되는 경우가 많다 (`key_one` · `key_other`)

---

## 7. js-object — JS 소스 안의 로케일 객체

```js
const ClientI18N = {
  locales: {
    en: {
      brand_title: "Acme Studio",
      unregistered_sub: "Not authorized.<br>Turn on <strong>[Pairing]</strong> first.",
    },
  },
};
```

🔴 **이 포맷이 가장 위험하다.** 이유가 둘이다.

1. **표준 포맷이 아니라 JS 소스**다. 파싱이 깨지면 **앱이 통째로 안 뜬다**
2. **값에 HTML 이 들어 있다.** 태그가 빠지거나 늘면 화면이 깨지는데 눈으로는 잘 안 보인다

`extract.py` 의 `js-object` 어댑터는 `locales: { <lang>: { key: "value" } }` 모양만
다루고, **이해하지 못하는 구조를 만나면 조용히 넘어가지 않고 멈춘다.** 망가뜨리는
것보다 멈추는 편이 낫기 때문이다.

**권고**: 장기적으로 로케일을 **별도 JSON 파일로 분리**하는 편이 낫다. 소스와 데이터가
섞여 있으면 번역 도구를 못 쓰고, 번역자가 코드를 건드리게 된다.

---

## 8. markdown — 문서 · 랜딩

- **코드 블록 · 인라인 코드 · URL · 프런트매터 키는 번역하지 않는다.** 값만 번역한다
- 링크는 `[텍스트](url)` 에서 **텍스트만**
- 제목의 앵커가 바뀌면 내부 링크가 깨진다. 앵커를 명시해 두는 편이 안전하다
- 웹사이트라면 **언어별 URL 구조와 `hreflang`** 을 처음부터 잡아야 한다. 나중에 고치면
  검색 순위를 잃는다

---

## 9. 새 포맷을 추가할 때

`scripts/extract.py` 의 `ADAPTERS` 에 이름을 등록하고 두 함수를 쓴다.

```python
def read_<fmt>(path, lang, cfg) -> list[Item]      # 원문 + 맥락 + 기존 번역
def write_<fmt>(path, lang, items, cfg) -> None    # 원래 구조를 보존하며 되쓰기
```

`Item` 에 채워야 하는 것:

| 필드 | 설명 |
|---|---|
| `id` | 같은 항목을 다시 찾을 안정된 열쇠 |
| `source` | 원문 |
| `target` | 기존 번역 (없으면 `None`) |
| `context` | 클래스명 · `msgctxt` · 파일 경로 등 |
| `comment` | 개발자 주석 |
| `kind` | `button` · `menu` · `body` · `unknown` — 길이 예산이 이걸 본다 |
| `status` | `untranslated` · `needs_review` · `translated` |

**되쓰기는 원본 구조를 보존해야 한다.** 주석·순서·들여쓰기가 바뀌면 diff 가 터지고
리뷰가 불가능해진다.
