# 로일(LoIl) 프로젝트 작업 규칙

## 프로젝트 개요

- **무엇을 만드는가**: 로스트아크 길드 레이드 일정 조율 및 파티 편성 자동화 Discord 봇 + 웹 대시보드
- **사용 언어/프레임워크**: Python 3.13+ (개발 PC는 3.14) / discord.py 2.3.2 / FastAPI + Jinja2 / openpyxl(엑셀 일괄 등록) / Pillow / Gemini(`google-genai` 신 SDK, 모델 `gemini-flash-latest`)
- **데이터 저장**: `bot/data/guild_settings.json` 하나에 길드별 설정·멤버·일정·신청 전부 통합. 반드시 `bot/utils/storage.py` 경유(원자적 쓰기 + 파일 락 + 최근 30개 자동 백업). MySQL은 안 씀(아직 계획 단계)
- **목적**: 포트폴리오 + 실사용 배포 (데모 수준, 여러 길드 대상)
- **향후 방향**: 웹 대시보드 중심 구조(이미 대부분 전환됨, Discord는 알림·조회·신원 확인이 필요한 액션 담당), 다른 RPG 게임으로 확장 가능한 구조 유지

---

## 절대 규칙

1. **파일 삭제는 절대 자동으로 하지 않는다.** 삭제 후보만 보고하고, 명시적 승인 후에만 삭제.
2. **파일 단위로 제공한다.** 수정이 1~2줄이어도 전체 파일로 준다. diff만 주면 적용 실수가 생기므로 금지.
3. **수정 전 반드시 현재 파일을 확인한다.** 이전 세션 기억이나 요약에 의존하지 않고 실제 파일 기준으로 작업.
4. **API 키, 토큰은 절대 코드에 하드코딩하지 않는다.** `.env` 또는 `guild_settings.json`으로만 관리. 디버그/테스트 스크립트도 예외 없음. (2026-09 실제 사고: `bot/debug_gemini.py`에 박힌 키가 유출돼 구글이 키를 차단함)
5. **임의 판단으로 기능을 추가하거나 제거하지 않는다.** 애매한 부분은 반드시 질문 후 진행.
6. **봇/웹 재시작이 필요한 변경인지 항상 명시한다.** (`bot/utils/*` 공용 모듈이 바뀌면 봇+웹 둘 다, `web/`만 바뀌면 웹만, `docs/`·`web/static/`은 정적이라 불필요)
7. **데이터 원본은 `guild_settings.json`이다.** 읽기/쓰기는 `storage.py`를 거친다. Google Sheets 연동은 폐기됨(레거시 코드 일부 잔존 — 아래 "주의사항" 참고).
8. **실데이터를 건드리는 테스트는 백업 후 진행하고 끝나면 원복한다.** (`bot/data/guild_settings.json` 직접 백업/복원)

---

## 작업 체크포인트 구조

### 1단계 — 조사/분석 (자동, 확인 불필요)
- 관련 파일/코드를 읽고 현재 상태를 파악한다. 이 단계에서는 수정하지 않는다.

### 2단계 — 계획 제시 → 🔴 1차 컨펌 필요
- 무엇을 어떻게 수정할지 표/목록으로 제시한다.
- 실제 파일은 건드리지 않는다.
- 승인 없이는 3단계로 넘어가지 않는다.

### 3단계 — 실제 수정 (승인 후 자동 진행)
- 2단계에서 승인받은 계획대로만 수정한다.
- 전체 파일로 제공한다.
- 봇/웹 재시작 필요 여부를 명시한다.

### 4단계 — 결과 요약 → 🔴 2차 컨펌 필요
- 무엇을 했는지 요약 보고.
- 임의 판단한 부분이 있다면 반드시 명시.
- CHANGELOG 항목 초안을 같이 제시한다.

### 5단계 — 정리/삭제 → 🔴 3차 컨펌 필요 (절대 자동 진행 금지)
- 파일 삭제, 의존성 제거 등은 이 단계에서만, 명시적 승인 후에만 진행.

### 작업 방식 메모 (사용자 선호, 세션에서 반복 확인됨)
- 화면/UI 변경은 브라우저로 실제 before/after를 확인한 뒤 완료 보고한다.
- 백엔드/공용 모듈을 바꾸면 프로세스를 재시작하고 httpx 또는 브라우저로 실제 응답을 확인한다.
- 완료 보고 때는 확인할 수 있는 실제 링크(`http://localhost:8000/...`)를 같이 준다.
- 사용자가 마음에 들어 하는 기존 디자인이 있으면 새로 만들지 않고 그걸 이식/응용한다.
- 사용자는 비개발자(게임 기획자)이며 시간·체력이 제한적이다 — 보고는 짧게, 해야 할 일은 우선순위 체크리스트로.

---

## 변경 기록 관리 규칙

### 폴더 구조
```
CHANGELOG/
├── 2026-07.md / 2026-08.md / 2026-09.md ...   ← 월별 기록 (그날그날 "## YYYY-MM-DD" 헤더로 누적)
├── 로그_문제해결_매뉴얼.md                      ← logs/ 로그 패턴별 해결법 (사용자가 직접 계속 추가)
└── 할일_정리_YYYY-MM-DD.md                      ← 그 시점의 할 일 스냅샷
README.md (루트)                                 ← 변경 기록 인덱스(월별 링크) — 현재 2026-08까지만 반영돼 있어 갱신 필요
```

### 월별 항목 형식 (최근 사용 중인 형식)
```markdown
### 제목

**배경**: 왜 필요했는지 / 사용자 피드백
**변경**: 무엇을 어떻게 (파일별)
**검증**: 어떻게 확인했는지
**봇 재시작 필요**: 예/아니오
**웹 서버 재시작 필요**: 예/아니오
```

### 기록 규칙
- 작업 완료 후 4단계에서 CHANGELOG 항목 초안을 제시한다.
- 삭제된 코드는 반드시 코드블록으로 보존한다. (롤백·검토용)
- 버그 수정은 **이유**와 **에러 메시지**도 함께 기록한다.

---

## 작업 보고서(reports) 관리 규칙

2단계(계획 제시) 등에서 만든 계획/제안은 대화창에만 남기지 않고 `docs/reports/`에 파일로도 저장한다. **매번 물어보지 않고 자동으로** 진행한다. (기존 계획 보고서와 2026-10-08 서버 이전 체크리스트가 들어 있음)

### 파일 위치 & 이름
```
docs/reports/YYYY-MM-DD_제목.md
```
예: `docs/reports/2026-07-31_웹대시보드-1차계획.md`

### 규칙
- 날짜별로 파일을 나눈다. 한 파일에 여러 날짜를 누적하지 않는다.
- 같은 날 여러 건이면 제목만 다르게 해서 파일을 각각 만든다.
- 그날그날의 핵심 결정/계획만 간결하게 남긴다. (CHANGELOG처럼 상세 코드 diff까지 남기는 건 아님)
- Artifact(웹페이지)로 따로 보여주는 것과 별개로, 이 파일은 항상 남긴다.

---

## 프로젝트 구조

```
프로젝트 루트/
├── bot/                          ← Discord 봇 (discord.py)
│   ├── main.py                   ← 맨 위에서 setup_logging("bot") 호출
│   ├── cogs/
│   │   ├── setup.py / schedule.py / schedule_view.py / party.py
│   │   ├── raid_manage.py / raid_config.py
│   │   ├── notice.py / suggest.py / admin.py / help.py / alias.py
│   │   ├── links.py / character_info.py
│   │   └── guild_connect.py     ← 웹에서 만든 임시 길드를 실제 서버에 연결
│   ├── utils/
│   │   ├── storage.py           ← guild_settings.json 단일 저장소 (원자적 쓰기/락/백업)
│   │   ├── app_logging.py       ← 콘솔 출력을 logs/{bot|web}_날짜.log에도 남김(14일 보관)
│   │   ├── gemini_ai.py         ← Gemini 호출(google-genai). 길드별 키 우선, 없으면 .env 키
│   │   ├── lostark_api.py       ← 로스트아크 API (5분 캐시)
│   │   ├── roster_import.py     ← 엑셀(.xlsx) 레이드/멤버 일괄 등록 파서
│   │   ├── member_link.py       ← 멤버 연결, 불참 관리, 개인 웹 토큰, 가능시간
│   │   ├── raid_signup.py / raid_schedule.py / raid_icon.py
│   │   ├── guild_link.py        ← 길드 생성/가입코드/연결코드
│   │   ├── guild_url.py / guild_banner.py / web_results.py
│   │   ├── permissions.py       ← require_admin 단일 소스
│   │   ├── synergy_ui.py        ← 시너지/파티 나누기 추천, 직업 옵션
│   │   ├── image_renderer.py / channel_cleanup.py / dm_queue.py / favorite_links.py / resolver.py
│   │   └── sheets.py            ← (레거시) 시트 연동은 폐기, 레이드 카탈로그 매칭 헬퍼만 계속 사용
│   ├── config/
│   │   ├── settings.py          ← .env 로드, GEMINI_MODEL 등
│   │   ├── channels.py          ← 채널명 상수 단일 소스
│   │   └── constants.py
│   └── data/
│       ├── guild_settings.json  ← 길드별 설정 전체 (.gitignore 대상 — 실데이터, 커밋 금지)
│       ├── backups/             ← storage.py가 저장 때마다 남기는 백업(최근 30개)
│       ├── raid_data.json / jobs.json / synergy_benefits.json / dps_types.json 등 정적 데이터
│       └── web_results/         ← 공개 조회용 편성 결과 스냅샷
├── web/                          ← 웹 대시보드 (FastAPI, bot과 별도 프로세스)
│   ├── main.py                   ← /, /g/{slug}, /guide(StaticFiles로 docs/ 서빙)
│   ├── admin.py                  ← /admin/* (로그인, 길드홈, 일정관리, 시너지, AI편성, 멤버, 엑셀등록, 가입승인, 건의함, 시간정책)
│   ├── availability.py           ← 개인 가능시간·관심 레이드 페이지
│   ├── onboarding.py             ← /guild/new, /guild/join
│   ├── auth.py                   ← Discord OAuth2
│   ├── static/css/site.css       ← 홍보 사이트(홈+가이드 9페이지) 공용 디자인 시스템 — 공통 CSS는 여기 한 곳만 고침
│   ├── static/                   ← guild_banners/, raid_icons/, loil/ (기본 브랜딩)
│   └── templates/                ← 템플릿 22개 (index.html = 실제 홈 포함)
├── docs/                          ← 가이드 정적 페이지(웹서버가 /guide/*로 서빙) + 문서
│   ├── guide.html / guide-*.html / contact.html  ← 홍보·가이드 사이트 (상단 nav 구성 전부 동일 유지)
│   ├── index.html                 ← 옛 홈 사본. /guide, /guide/index.html은 서버가 / 로 리다이렉트하므로 더 이상 동기화 불필요
│   ├── dev/                       ← 개발 문서 (START_GUIDE, API_REFERENCE 등 .md)
│   ├── user/                      ← 사용자 문서 (COMMANDS, SETUP_GUIDE 등)
│   ├── reports/                   ← 작업 보고서 (YYYY-MM-DD_제목.md)
│   ├── sample/                    ← 디자인 시안·목업 등 외형만 보여주는 자료
│   └── 웹_UI_텍스트_카탈로그.md, 할일_2026-08-31.md
├── deploy/                        ← 실서버 이전용 systemd 서비스 템플릿 + README(체크리스트)
├── logs/                          ← 실행 로그 (.gitignore 대상)
├── CHANGELOG/
├── CLAUDE.md
└── bot/.env                      ← 실제로 쓰이는 환경변수 파일 (루트 .env는 안 씀)
```

---

## 채널 구조

```
로일(LoIl) 카테고리
├── 📡│공지          — 길드 공지, 주간 갱신 알림 (전체 읽기)
├── 🗒│일정조회      — 일정 조회 패널만 고정 (전체 접근)
├── 📋│일정확인      — 일정 스레드 전용, 24시간 자동 삭제 (전체 접근)
├── 🛡│레이드편성    — AI 편성 + 일정 관리 (전체 읽기, 버튼은 관리자)
├── 💌│건의함        — 길드 문의 (전체 접근)
├── ⚙│봇설정        — API 키 등록, 길드 연결 (관리자 전용)
└── ⚔️│레이드설정   — 레이드 활성화, 소요시간 설정 (관리자 전용)
    ※ 슬롯 수(파티 수)는 참가 신청 인원 기반으로 관리자가 웹/디스코드에서 "공대 추가"로 늘리는 방식
```

---

## 역할 구분

| 역할 | 대상 | 할 수 있는 것 |
|------|------|---------------|
| 관리자 | 길드장, 부길드장 | 일정 추가/수정/삭제, AI 편성 확정, 레이드 설정, 엑셀 일괄 등록, 가입 승인, 배너, API 키 등록, 채널 청소 |
| 사용자 | 일반 길드원 | 일정 조회, 내 가능시간/관심 레이드 제출, 건의함(작성·조회), 가입 코드 열람 |

- `require_admin`은 반드시 `bot/utils/permissions.py`에서만 import한다.
- 웹에서 관리자가 `?as=member`를 붙이면 길드원 시점 미리보기(`_require_view_access`). 변경 라우트의 실제 권한 검사(`_require_guild_access`)와는 별개라 보안에 영향 없음.
- 길드 홈의 관리자 전용 카드(AI 자동편성, 가입 신청 관리)는 길드원에게 숨기지 않고 비활성(.disabled)으로 같은 자리에 보여준다.

---

## 현재 상태 (스냅샷 — 2026-10-08 갱신)

**완료**
- **웹 대시보드 본격 가동**: 길드 홈 허브, 일정관리, 시너지(파티 나누기 추천), AI 자동편성, 길드원 명단, 시간정책, 그룹 가능시간, 가입 신청 관리, 건의함, 배너 업로드, 개인 가능시간·관심 레이드, 공개 조회(`/g/{slug}`)
- **엑셀 일괄 등록**(`/admin/{id}/import`): 레이드+멤버를 .xlsx 하나로 업로드 → 미리보기 → 확정
- **온보딩**: 웹에서 봇 초대 전에 길드 생성(`web_...` 임시 ID) → `/길드연결`로 실제 서버에 병합, 가입 코드로 신청 → 관리자 승인. **Discord 역할 자동 부여는 의도적으로 안 함**
- **관리자/길드원 화면 구분 + 미리보기**(`?as=member`)
- **홈페이지(`/`)와 가이드(`/guide/*`)**: 손수 만든 디자인 톤으로 통일, 공용 CSS(`site.css`) 하나로 통합, 홈 히어로는 3버튼(Discord에 추가 / 길드 가입 / 내 길드 보기)
- **운영 안전장치**: `storage.py`(원자적 저장+락+백업), `app_logging.py`(로그 파일), 문제해결 매뉴얼
- **Gemini SDK 이전**: 단종된 `google-generativeai` → `google-genai`, 모델 `gemini-flash-latest` (코드 쪽은 완료)
- **웹 시뮬레이션 검증**: pending 길드 포함 온보딩 웹 흐름 34개 체크 통과(`int(guild_id)` 계열 버그 전수 수정 — `web/admin.py`에서 `int(guild_id)` 금지)

**미완료 / 확인 필요**
- 🔴 **Gemini API 키 유출·차단**: `.env`와 `guild_settings.json`(길드 `1473254272433913961`)의 키가 구글에 의해 차단됨 → AI 자동편성/파티추천 현재 동작 안 함. 새 키 발급 후 두 군데 교체 필요 (사용자가 "나중에"로 보류 중)
- 🔴 **작업물 미커밋**: 마지막 커밋 2026-07-27, 이후 변경 약 70개 파일(새 파일 다수)이 워킹트리에만 있음
- **GitHub 저장소(`genwo123/LOIL`) 공개 여부 확인** — 옛 커밋(`248c859`)에 키가 평문으로 남아 있음. 히스토리 재작성은 파괴적이라 사용자 승인 필요
- **실서버 이전 안 됨**: 지금은 개발 PC 수동 실행. `WEB_BASE_URL`/`DISCORD_REDIRECT_URI`가 localhost라 외부 사용자는 로그인 불가. 체크리스트는 `deploy/README.md`
- **Discord 봇 라이브 테스트 미확인**: 새 명령어 슬래시 동기화, 실제 서버 온보딩(초대→연결→가입)은 사람이 직접 해봐야 함(자동화 불가)
- **문의 창구 없음**: `docs/contact.html`의 "Discord 서버 입장하기"가 링크 없는 스텁 (사용자가 고민 중)
- **모바일 UI**: 전체 틀이 잡힌 뒤 진행하기로 보류
- 광고 위치/방식 결정, 테스트 길드 `web_1bcb30f58f8e` 정리 여부 (`docs/할일_2026-08-31.md`)
- `DEV_SKIP_LOGIN`은 현재 `false`. 개발용으로 켜면 **배포 전 반드시 끌 것**

---

## 다음 목표 (우선순위 — 2026-10-08 기준)

1. **작업물 로컬 커밋** (secrets 포함 여부 확인 후) — 소실 방지
2. **GitHub 공개 여부 확인 → 필요 시 비공개 전환**
3. **실서버 이전** — 비용 없이 시작하려면 개발 PC + 무료 터널(고정 도메인)로 먼저 테스트하는 방법 있음. 상시 가동은 `deploy/README.md` 체크리스트
4. **Discord 봇 실제 재시작 + 온보딩 라이브 테스트** (사람이 직접)
5. **Gemini 키 교체 + AI 자동편성 실호출 검증**
6. **모바일 UI**, 레이아웃 고도화(주간 7일 그리드, 월간 캘린더, 퀵 대시보드)
7. **아이템레벨 기반 자격 필터링**, 길드별 커스텀 테마
8. **DB 마이그레이션(`guild_settings.json` → DB)** — 더 장기

---

## 장기 방향

- **웹 대시보드 중심 구조**: Discord는 알림 수신 + 결과 조회 + 신원이 확실해야 하는 개인 액션(가능시간 링크 발급, 길드연결)만.
- **게임 확장성**: 레이드 카탈로그를 게임별 설정 파일로 분리 (`raid_data_lostark.json`, `raid_data_maplestory.json` 등)
- **길드별 커스텀 테마**: 색상 플레이그라운드(`docs/sample/color_playground.html`) 컨셉을 실제 관리자 설정 화면으로 승격
- **AdSense 수익화**: `ca-pub-4097734794611688` (홈/가이드 페이지에 슬롯 이미 삽입됨, 승인·노출 여부는 미확인)
- **카카오톡 알림 프리미엄**: 1인 구독 = 길드 전체 혜택 모델

---

## 미해결 질문 / 주의사항

- `guild_settings.json` → DB 마이그레이션 시 설정 읽기 함수 전면 수정 필요 (지금은 `storage.py` 한 곳으로 모여 있어 이전 쉬움). 단 `load→수정→save` 구간까지 완전 직렬화된 건 아님(저장 순간만 락) — 동시 저장이 잦아지면 보강 필요
- 🔴 **`SESSION_SECRET_KEY`가 `.env`에 없어서 코드 기본값(`dev-insecure-session-key`)이 쓰이고 있음** — 공개 서버에서는 누구나 가짜 세션 쿠키로 모든 길드 관리자 화면에 들어갈 수 있음(2026-10-08 점검 때 실제로 확인). 인터넷에 열기 전에 반드시 무작위 값으로 설정할 것
- `validate_config()`는 레거시로 `credentials.json`(구글 서비스 계정) 존재를 검사하지만 `main.py`가 결과를 무시해서 없어도 봇은 시작됨. 다만 `sheets.py`가 `gspread`/`oauth2client`를 import하므로 패키지 자체는 필요
- 서버 설치는 `requirements-server.txt`(개발 PC에서 실제 동작하는 버전 고정)를 사용 — 기존 `requirements.txt`는 개발 도구 포함 + discord.py 2.3.2 구버전 핀이라 실제 환경(2.6.4)과 다름
- 로아 API 키 최대 3개 풀링 (라운드로빈), 요청 한도 주의
- `on_guild_remove` 시점에는 서버 접근 불가 → `_cleanup_guild_settings()`만 호출
- Discord 봇 초대 URL(스코프 `bot` + `applications.commands`, 권한 `311385517136`)은 홈/가이드에 이미 박혀 있음
- 버튼은 `defer()` 대신 `edit_message(view=self)`로 즉시 비활성화 (3초 타임아웃 방지)
- **`.env`는 `bot/.env`만 실제로 읽힘** — 루트 `D:\LOIL\.env`는 안 쓰임. 새 환경변수는 반드시 `bot/.env`에 추가
- **`raid_signups`(참가신청)는 컬럼(col) 번호로 데이터를 물고 있음** — 레이드 삭제 시 `clear_signups()`를 꼭 같이 호출해야 함
- `guild_settings.json` 안의 `sheet_url` 필드는 레거시(시트 연동 폐기). 신규 코드에서 쓰지 말 것
- 가이드 페이지(`docs/*.html`) 상단 nav는 전부 같은 구성(홈·가이드·문의)을 유지하고, "홈"은 항상 `/`(실제 사이트)로 연결한다
- `requirements.txt`에 구 SDK `google-generativeai`가 남아 있는 건 `bot/tests/test_gemini_ai.py` 때문 — 앱 실행 경로는 `google-genai`만 씀
- GitHub Pages 소스는 `/docs`로 확정(저장소에 `.github/workflows` 없음, "브랜치에서 배포" 방식) — 단 실제 서비스 경로는 웹서버의 `/guide/*`

---

## 도구 & 리소스

- **언어/런타임**: Python 3.13+ / discord.py 2.3.2 / FastAPI + uvicorn
- **AI**: Gemini (`google-genai`, `gemini-flash-latest`) — 파티 편성/시너지 해설. 키는 길드별(`guild_settings.json`) 우선, 없으면 `bot/.env`
- **데이터**: `guild_settings.json`(storage.py 경유), 엑셀 업로드는 `openpyxl`
- **이미지**: Pillow (레이드 일정 이미지 렌더링)
- **배포**: 현재 로컬 실행. 실서버 이전은 `deploy/` (systemd + nginx + HTTPS 체크리스트). Railway는 무료 티어가 없어져 후보에서 사실상 제외
- **웹**: FastAPI(`uvicorn web.main:app --port 8000`), 홍보/가이드는 `/guide/*`, AdSense `ca-pub-4097734794611688`
- **로그**: `logs/bot_날짜.log`, `logs/web_날짜.log`, 해석은 `CHANGELOG/로그_문제해결_매뉴얼.md`
- **핵심 파일**: `party.py`, `schedule_view.py`, `main.py`, `image_renderer.py`, `channels.py`, `storage.py`, `guild_settings.json`, `raid_data.json`, `web/admin.py`, `web/static/css/site.css`
