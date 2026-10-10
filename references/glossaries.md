# 용어집

## 우선순위 — 충돌하면 위가 이긴다

```
1. 번역 금지 목록      제품명 · 브랜드              절대 건드리지 않는다
2. 프로젝트 용어집      우리 고유 개념               플랫폼과 무관하게 하나로 고정
3. 플랫폼 용어집        그 OS 관례                  대상마다 다르다
4. 없으면 모델 판단
```

**왜 이 순서인가**: 플랫폼 용어는 **달라도 된다.** 맥 사용자는 맥 단어를, 윈도우
사용자는 윈도우 단어를 봐야 자연스럽다. 문제는 **우리 고유 개념**이다 — 같은 기능이
플랫폼마다 다른 단어가 되면 사용자가 다른 기능으로 읽는다. 그래서 2가 3을 이긴다.

⚠️ **용어집 전체를 프롬프트에 넣지 마라.** 이번 배치의 문자열에 실제로 걸리는 항목만
추린다. 다 넣으면 컨텍스트만 먹고 엉뚱한 항목이 섞인다.

---

## 캐시 규칙

**처음 쓸 때 받아서 로컬에 캐시하고, 스킬 안에 넣어 배포하지 않는다.** 받기 · 풀기 · 색인은 `scripts/glossary.py` 가 한다.

```
~/.cache/localize/glossaries/
├── microsoft/MicrosoftTermCollection.zip   ← 약 170 MB, 100개 언어 전부. 꺼내지 않고 zip 안에서 바로 읽는다
├── aosp/{framework,settings}/values[-xx]/strings.xml   ← 모든 언어 합쳐 약 15 MB
├── apple/dmg/<Name>.dmg                    ← 사람이 받은 원본 51개(약 420 MB). 풀지 않고 index 가 잠깐 붙여 읽는다
└── index/<code>.json                       ← index 가 만든 색인(언어당 수십 MB, 쓰는 언어만)
```

(`import-apple --extract` 로 풀어 둘 수도 있다 —— 인도 언어 10개는 `.lg` 가 아니라 `.tmx` 한 파일(언어당 약 270 MB)이라 풀지 않는 것이 낫다.)

언어 코드 ↔ 각 소스의 이름은 **`references/platform-languages.json`**(119개 언어 —— Microsoft 110 · AOSP 83 · Apple 51,
모두 실제 파일 · 폴더와 맞춰 확인했다). 소스에 없는 언어는 `null`. 모든 언어가 표에 있으니 **필요한 언어만** 색인하면 된다.

| 소스 | 라이선스 · 배포 | 그래서 |
|---|---|---|
| Microsoft | 문서가 "다른 용어 모음에 통합 · 기본 IT 용어집으로 사용" 을 허락한다. ZIP 안에 라이선스 파일은 없다 | 각자 받는다(링크가 공개) |
| Apple | **개발자 계정 뒤의 자료** —— 재배포하지 않는 것이 안전하다 | 각자 자기 계정으로 받는다 |
| AOSP | Apache-2.0 —— 재배포 가능 | 각자 받아도 몇 초다 |

## 받기 —— 사람이 내려받기를 허락한 뒤

```bash
python SKILL_DIR/scripts/glossary.py fetch --lang ko de ja zh_TW fr es pt_BR   # Microsoft · AOSP
```

**Apple 은 자동으로 받지 않는다**(로그인 필요 —— 모델은 비밀번호를 넣지 않는다). 사람이 받는다:

1. <https://developer.apple.com/download/all/?q=Glossaries%20-%20iOS> → **View Details**
   (무료 Apple Developer 계정. 브라우저의 "다운로드 전에 저장 위치 묻기" 가 켜져 있으면 파일마다 저장 창이 뜬다)
2. 필요한 언어의 DMG(`platform-languages.json` 의 `apple` 이름 + `.dmg`. 예: `Korean.dmg` · `Traditional Chinese.dmg`).
   한 번에 다 받아 두려면 51개 전부(약 420 MB) —— 받기 링크는 `https://download.developer.apple.com/Developer_Tools/glossaries__ios_21842/<Name>.dmg`
   꼴이다(로그인한 브라우저에서 열어야 받아진다)
3. `python SKILL_DIR/scripts/glossary.py import-apple ~/Downloads` —— 캐시로 옮기고, 같은 이름의 중복 사본은 지운다(맥의 `hdiutil` 로 읽는다)

iOS 용어집(2025)이 macOS 용어집(2020)보다 새롭다 —— iOS 를 쓴다. 맥 앱 낱말도 대부분 같다.

그다음 색인:

```bash
python SKILL_DIR/scripts/glossary.py index --lang ko de ja zh_TW fr es pt_BR
python SKILL_DIR/scripts/glossary.py status
```

## 언어 더하기

모든 언어를 미리 받아 둘 필요는 없다 —— **필요한 언어만** 받는다.

1. `glossary.py langs` 에 그 코드가 있는지 본다(119개가 이미 있다). 없으면 `platform-languages.json` 에 한 줄을 더한다:
   Microsoft 이름은 ZIP 목록(`unzip -Z1 MicrosoftTermCollection.zip`), AOSP 폴더는 GitHub
   `aosp-mirror/platform_frameworks_base/core/res/res` 의 `values-*`(히브리어 `iw`, 인도네시아어 `in` 같은 옛 코드에 주의),
   Apple 이름은 위 다운로드 페이지의 DMG 이름.
2. `fetch --lang <코드>` → (Apple DMG 받기 → `import-apple`) → `index --lang <코드>`.

## 다른 컴퓨터 · 다른 사람

- **스킬(스크립트 · 표 · 문서)** 은 그대로 공유한다 —— 용어집 파일은 들어 있지 않다.
- **자기 다른 컴퓨터:** 위 받기를 다시 한다(Microsoft · AOSP 는 명령 하나, Apple 은 같은 계정으로 DMG 받기 →
  `import-apple`). 또는 이 캐시 폴더를 **개인 저장소**(비공개 클라우드 드라이브 등)로 옮겨 쓴다 —— 공개 저장소에는 올리지 않는다.
- **다른 사람:** 각자 자기 계정 · 자기 컴퓨터에서 받는다. 받은 용어집 · 색인을 넘겨주지 않는다.

---

## 1. Microsoft — 윈도우

**받기**: `fetch` 가 받는다 —— <https://learn.microsoft.com/en-us/globalization/reference/microsoft-terminology> 의
다운로드 링크(`MicrosoftTermCollection.zip`, 약 170 MB, 2024-11 판). 약 100개 언어가 언어별 `.tbx` 로 들어 있다.

문서가 밝히는 용도에 *"다른 terminology collection 에 통합"* 과 *"기본 IT 용어집으로
사용"* 이 **명시**돼 있다. 즉 우리 용어집에 병합해 쓰는 것은 의도된 사용이다.

**형식** — TBX 는 XML 이다. 한 개념에 **여러 term 이 달릴 수 있다** —— 색인은 빈도 순으로 셋까지 남긴다.

---

## 2. Apple — macOS · iOS · iPadOS

**받기**: 사람이 받는다(위). 언어마다 앱 · 프레임워크별 `.lg`(XML) 수십 개가 들어 있다.

```xml
<TranslationSet><base loc="en">Forget This Device</base><tran loc="ko">이 기기 지우기</tran></TranslationSet>
```

🔴 **AppleGlot 도구 자체는 쓰지 마라.** 설치 인증서가 만료됐고 최신 macOS 와 호환이
깨졌다. **필요한 것은 도구가 아니라 `.lg` 파일**이므로 직접 파싱한다.

**보조**: [Apple Style Guide](https://support.apple.com/guide/applestyleguide/welcome/web)
는 계정 없이 공개돼 있다. 다만 **미국 영어 기준**이라 용어집을 대신하지 못하고,
문장 스타일(대문자 표기·어조)에만 참고한다.

---

## 3. AOSP — 안드로이드

**구글은 대역 용어집을 배포하지 않는다.** 대신 AOSP 의 실제 시스템 문자열을 짝짓는다 ——
`fetch` 가 `frameworks/base`(시스템 대화상자 · 단추)와 `packages/apps/Settings`(설정 앱)의
`values/strings.xml`(영어)과 `values-<lang>/strings.xml` 을 받아 `name` 으로 짝짓는다.

🔑 **용어집보다 오히려 정확하다.** 정리된 용어가 아니라 **안드로이드가 실제로 화면에
쓰는 문자열**이기 때문이다. 그리고 **Apache-2.0 이라 세 소스 중 유일하게 재배포가
가능**하다.

---

## 4. 보조 — Mozilla

[Transvision](https://transvision.mozfr.org/) 은 Firefox 계열의 번역을 모아 언어별
TMX 를 내준다. 오픈소스다.

**쓰임**: 플랫폼 용어집에 없는 **일반 소프트웨어 용어**(`sync` · `cache` · `shortcut`)의
실제 번역 사례를 보는 용도. **4순위 참고이지 권위 있는 소스가 아니다** — 플랫폼
용어집과 충돌하면 플랫폼 쪽을 따른다.

---

## 5. 프로젝트 용어집 — 가장 중요하고, 아무도 대신 만들어주지 않는다

```json
{
  "do_not_translate": ["Acme", "Acme Studio", "Quick Preview"],
  "terms": {
    "workspace": { "de": "Arbeitsbereich", "ja": "ワークスペース", "note": "사용자가 만드는 작업 단위" },
    "board":     { "de": "Board",          "ja": "ボード",        "note": "workspace 안의 화면 하나" },
    "sync":      { "de": "Sync",           "ja": "同期",          "note": "기기 간 자동 반영" },
    "host":      { "de": "Host",           "ja": "ホスト",        "note": "연결을 받는 쪽" }
  }
}
```

**`note` 를 반드시 채워라.** 번역자(=모델)가 개념을 모르면 단어만 맞고 뜻이 틀린다.

### 초안 만드는 법 — 사용자에게 맨손으로 시키지 마라

소스 문자열에서 후보를 뽑아 **O/X 만 받는다.**

| 후보 | 어떻게 찾나 |
|---|---|
| **번역 금지** | 대문자로 시작하면서 반복되는 명사 · 사전에 없는 조어 · `About`·제목 문자열에 나오는 이름 |
| **고정 개념** | 여러 화면에 반복되는 도메인 명사. 일반 영어 단어라도 **제품 안에서 특정 의미**를 가지면 후보다 |

⚠️ **일반 단어일수록 위험하다.** `host` · `session` · `direct` 는 사전적으로 여러 뜻이
있어서 화면마다 다르게 번역되기 쉽다. **고정 목록에 넣어야 할 1순위**가 바로 이런
단어들이다.
