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

**처음 쓸 때 받아서 로컬에 캐시하고, 스킬 안에 넣어 배포하지 않는다.**

```
~/.cache/localize/glossaries/
├── microsoft/MicrosoftTermCollection.tbx
├── apple/<os>_<lang>.lg
└── aosp/values-<lang>/strings.xml
```

이유: MS 는 재배포 조건이 문서 페이지에 없고 ZIP 안 라이선스를 봐야 한다. Apple 은
**개발자 계정 뒤에 있는 자료**라 재배포하지 않는 것이 안전하다. AOSP 만 Apache-2.0 이라
재배포가 가능하지만, **규칙을 하나로 두는 편이 단순**하다.

---

## 1. Microsoft — 윈도우

**받기**: <https://learn.microsoft.com/en-us/globalization/reference/microsoft-terminology>
에서 `.tbx`(ZIP). 약 100개 언어가 한 파일에 들어 있다.

문서가 밝히는 용도에 *"다른 terminology collection 에 통합"* 과 *"기본 IT 용어집으로
사용"* 이 **명시**돼 있다. 즉 우리 용어집에 병합해 쓰는 것은 의도된 사용이다.

**형식** — TBX 는 XML 이다. 필요한 것은 개념별 언어쌍이다.

```xml
<termEntry>
  <langSet xml:lang="en-US"><tig><term>Settings</term></tig></langSet>
  <langSet xml:lang="de-DE"><tig><term>Einstellungen</term></tig></langSet>
</termEntry>
```

⚠️ 한 개념에 **여러 term 이 달릴 수 있다.** 첫 번째(또는 `usage="preferred"`)를 쓴다.

⚠️ ZIP 안 라이선스 파일은 **확인하지 않았다.** 스킬을 공개 배포할 계획이 생기면
그때 확인할 것.

---

## 2. Apple — macOS · iOS · iPadOS

**받기**: <https://developer.apple.com/localization/resources>
**조건**: **무료 Apple Developer 계정**이면 된다. 유료 프로그램($99/년)은 필요 없다.

OS 별 이중언어 용어집을 `.lg`(XML)로 준다 — iOS · iPadOS · macOS · tvOS · watchOS.

🔴 **AppleGlot 도구 자체는 쓰지 마라.** 설치 인증서가 만료됐고 최신 macOS 와 호환이
깨졌다. **필요한 것은 도구가 아니라 `.lg` 파일**이므로 직접 파싱하면 된다.

**보조**: [Apple Style Guide](https://support.apple.com/guide/applestyleguide/welcome/web)
는 계정 없이 공개돼 있다. 다만 **미국 영어 기준**이라 용어집을 대신하지 못하고,
문장 스타일(대문자 표기·어조)에만 참고한다.

---

## 3. AOSP — 안드로이드

**구글은 대역 용어집을 배포하지 않는다.** `developer.android.com` 의 glossary 와
Material Design glossary 는 **영어 단일 개발 용어**라 UI 번역에 쓸 수 없다.

**대신 AOSP 에서 실제 시스템 문자열을 가져온다.**

```
https://github.com/aosp-mirror/platform_frameworks_base
  core/res/res/values-de/strings.xml
  core/res/res/values-ja/strings.xml
  core/res/res/values-zh-rTW/strings.xml
```

`values/strings.xml`(영어)과 `values-<lang>/strings.xml` 을 **`name` 으로 짝지으면
영어→대상 언어 쌍**이 만들어진다.

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
