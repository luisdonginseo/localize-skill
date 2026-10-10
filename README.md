# localize

앱과 웹사이트를 **AI로 번역하되 믿을 수 있게** 만드는 Claude Code 스킬입니다.

번역 자체는 누구나 시킬 수 있습니다. 어려운 건 두 가지입니다.

- **직접 읽을 수 없는 언어의 품질을 어떻게 확인하는가**
- **기계가 잡아야 할 사고를 기계가 잡게 하는가**

AI 번역에서 실제로 터지는 건 어색한 문장이 아니라 이런 것들입니다.

- `%1` 이 사라져서 **런타임에 문자열이 깨진다**
- `<br>` `<strong>` 이 빠져서 **화면 레이아웃이 무너진다**
- 제품명이 번역돼서 **브랜드가 사라진다** (`Swift` → `빠른`)
- 같은 단어가 화면마다 다르게 번역돼서 **다른 기능으로 읽힌다**
- 배치 뒤쪽이 통째로 빠졌는데 **아무도 모른다**

전부 눈으로는 잘 안 보이고 역번역으로도 안 잡힙니다. 그래서 스크립트가 잡습니다.

## 설치

```bash
git clone https://github.com/luisdonginseo/localize-skill.git ~/.claude/skills/localize
```

Windows (Git Bash / PowerShell):

```bash
git clone https://github.com/luisdonginseo/localize-skill.git "$HOME/.claude/skills/localize"
```

파이썬 3.9+ 만 있으면 됩니다. **의존성이 없습니다** — 표준 라이브러리만 씁니다.

## 하는 일

```
0. 준비 상태 진단     문자열이 마킹돼 있나 · 원본 파일이 있나 · 맥락 주석은 있나
1. 첫 실행 인터뷰      대상 언어 · 번역 금지어 · 고유 용어집  (후보를 뽑아 O/X 만 받는다)
2. 추출               미번역 항목만. 릴리스마다 전체를 다시 하지 않는다
3. 용어집 준비         번역 금지 > 프로젝트 > 플랫폼(MS·Apple·AOSP) 순
4. 번역               언어 사이는 병렬, 언어 안은 순차 (일관성 때문에)
5. 기계 검사          아래 여섯 가지
6. 역번역 검증         읽을 수 없는 언어를 검증하는 방법
7. 병합               원본 구조를 보존하며 되쓴다
```

별도로 **의사 현지화**(번역 없이 UI 깨짐 먼저 찾기)와 **맥락 주석 제안**이 있습니다.

## 검사하는 것

| 검사 | 무엇을 막나 |
|---|---|
| **플레이스홀더** | `%1` `{}` `%1$s` 가 사라지거나 번호가 바뀌면 런타임에 깨진다 |
| **HTML 태그** | `<br>` `<strong>` 이 빠지면 화면이 깨진다 |
| **번역 금지어** | 브랜드가 번역되면 제품 이름이 사라진다 |
| 길이 초과 | 단추가 잘린다 (`Einstellu…`) |
| 용어 일관성 | 같은 단어가 화면마다 다르면 다른 기능으로 읽힌다 |
| 누락 · 빈 값 | 배치가 뒤쪽을 빠뜨렸을 때 |

앞의 셋은 **오류**(병합을 막습니다), 뒤의 셋은 **경고**(판단 사항입니다).
독일어는 원래 길어서 길이 초과가 정상인 경우가 많습니다.

## 지원 포맷

| 포맷 | 쓰는 곳 | 플레이스홀더 |
|---|---|---|
| `qt-ts` | Qt · PySide6 (`.ts`) | `%1` `%n` |
| `gettext` | Slint · 그 외 (`.po` / `.pot`) | `{}` `%s` `%1$s` |
| `android` | `res/values/strings.xml` | `%1$s` |
| `apple` | `.strings` · `.xcstrings` | `%@` `%1$@` |
| `json` | i18next 등 | `{{name}}` `{name}` |
| `js-object` | JS 소스 안의 로케일 객체 | 프로젝트마다 다름 |

새 포맷은 `scripts/_adapters.py` 에 읽기·쓰기 한 쌍을 더하면 됩니다
(`references/formats.md` §9).

## 설정

프로젝트 루트에 `.i18n.json` 을 둡니다. **스킬에는 프로젝트 얘기가 한 줄도 없습니다** —
그래야 여러 프로젝트에서 같은 스킬을 씁니다.

```json
{
  "source": "en",
  "targets": ["de", "ja", "zh_Hant", "fr"],
  "project_glossary": "i18n/glossary.json",
  "do_not_translate": ["Acme", "Acme Studio"],
  "length_budget": { "button": 1.3, "menu": 1.5, "default": 1.6, "body": 3.0 },
  "units": [
    { "path": "desktop/translations", "format": "qt-ts",     "platform": ["windows"] },
    { "path": "mobile/res",           "format": "android",   "platform": ["android"] },
    { "path": "web/src/i18n.js",      "format": "js-object", "platform": ["apple"] }
  ]
}
```

**플랫폼은 대상 파일 단위로 붙습니다.** 한 리포지토리에 윈도우 호스트와 안드로이드
클라이언트가 같이 있는 경우가 흔하기 때문입니다. 프로젝트 용어집과 금지어만 전체
공통입니다.

## 용어집

우선순위가 있고 **충돌하면 위가 이깁니다.**

```
1. 번역 금지 목록      제품명 · 브랜드
2. 프로젝트 용어집      우리 고유 개념 —— 플랫폼과 무관하게 하나로 고정
3. 플랫폼 용어집        그 OS 관례
4. 없으면 모델 판단
```

플랫폼 용어는 **달라도 됩니다** — 맥 사용자는 맥 단어를, 윈도우 사용자는 윈도우
단어를 봐야 자연스럽습니다. 문제는 **우리 고유 개념**입니다. 같은 기능이 플랫폼마다
다른 단어가 되면 사용자가 다른 기능으로 읽습니다.

| 소스 | 받는 곳 | 조건 |
|---|---|---|
| Microsoft | [Microsoft Terminology](https://learn.microsoft.com/en-us/globalization/reference/microsoft-terminology) | 무료 · `.tbx` · 약 100개 언어 |
| Apple | [developer.apple.com/localization/resources](https://developer.apple.com/localization/resources) | **무료 개발자 계정** · `.lg` |
| AOSP | [platform_frameworks_base](https://github.com/aosp-mirror/platform_frameworks_base) | Apache-2.0 · 실제 시스템 문자열 |

구글은 대역 용어집을 배포하지 않아서 **AOSP 의 실제 문자열**을 씁니다. 정리된
용어집보다 오히려 정확합니다.

용어집은 **처음 쓸 때 받아 로컬에 캐시**하고 리포지토리에 넣지 않습니다
(`~/.cache/localize/glossaries/`). 각자 자기 컴퓨터에서 받습니다 —— Apple 은 자기 개발자 계정으로.

```bash
python scripts/glossary.py fetch --lang ko de ja        # Microsoft · AOSP (명령 하나)
# Apple: developer.apple.com/download/all/?q=Glossaries%20-%20iOS 에서 언어별 DMG 를 받은 뒤
python scripts/glossary.py import-apple ~/Downloads
python scripts/glossary.py index  --lang ko de ja
python scripts/glossary.py status                       # 언어마다 무엇이 있나
python scripts/glossary.py lookup --lang de --source work/de.json --out work/de.glossary.md
```

언어 코드 ↔ 각 소스의 이름은 `references/platform-languages.json`(119개 언어 —— Microsoft 110 · AOSP 83 ·
Apple 51)에 있고, 필요한 언어만 색인하면 됩니다. Microsoft 는 zip 안에서, Apple 은 DMG 를 잠깐 붙여 읽으므로
풀어 둘 필요가 없습니다(Apple 읽기는 맥의 `hdiutil` 이 필요합니다 —— 윈도우에서는 맥에서 만든 `index/<code>.json` 을 복사해 씁니다).

## 스크립트 직접 쓰기

스킬 없이도 돌아갑니다.

```bash
python scripts/extract.py --diagnose --root .
python scripts/extract.py --config .i18n.json --lang de --out work/de.json
python scripts/check.py   --source work/de.json --config .i18n.json
python scripts/merge.py   --input work/de.json --config .i18n.json --lang de
python scripts/pseudo.py  --config .i18n.json --lang qps --expand 1.4
```

`check.py` 의 종료 코드는 오류 건수입니다(0이면 통과). CI 에 걸기 좋습니다.

## 알아둘 것

- **`js-object` 가 가장 위험합니다.** 표준 포맷이 아니라 JS 소스라 파싱이 깨지면 앱이
  통째로 안 뜹니다. 어댑터는 이해하지 못하는 구조를 만나면 **조용히 넘어가지 않고
  멈춥니다.** 장기적으로는 로케일을 별도 JSON 으로 분리하는 편이 낫습니다.
- **복수형은 자동 병합하지 않습니다.** 언어마다 형태 수가 다릅니다(영어 2 · 한국어 1 ·
  러시아어 3 · 아랍어 6). 사람이 봐야 합니다.
- **길이 검사는 글자 수를 세지만 화면은 픽셀을 씁니다.** CJK 는 글자 수가 줄어도
  전각이라 넓습니다. 길이 검사를 통과해도 의사 현지화로 한 번 봐야 합니다.
- **markdown 은 문자열 단위로 뽑지 않습니다.** 문단을 쪼개면 맥락이 끊겨 번역이
  나빠집니다.

## 라이선스

MIT
