# 로일(LoIl) 변경 기록

Discord 봇 + 웹사이트 전체 변경 이력을 월별 · 주차별로 관리합니다.

---

## 월별 기록

| 월 | 링크 | 주요 작업 |
|----|------|-----------|
| 2026-03 | [2026-03.md](./CHANGELOG/2026-03.md) | raid_data 개편, 채널 구조 개선, 버그 수정 3종, 웹사이트 7페이지 |
| 2026-07 | [2026-07.md](./CHANGELOG/2026-07.md) | 기록 시작 (진행 중) |
| 2026-08 | [2026-08.md](./CHANGELOG/2026-08.md) | 웹 대시보드 구축(일정·시너지·AI 편성·멤버·가입 승인), 엑셀 일괄 등록, 온보딩, 디자인 시스템 |
| 2026-09 | [2026-09.md](./CHANGELOG/2026-09.md) | 홍보/가이드 사이트 통합·공용 CSS, 로그 파일, Gemini 신 SDK 이전, API 키 유출 발견 |
| 2026-10 | [2026-10.md](./CHANGELOG/2026-10.md) | CLAUDE.md 갱신, 서버 이전 준비(Hetzner), 문의 박스, 모바일 대응·PC 버전 전환 (진행 중) |

---

## 마일스톤

| 단계 | 상태 | 내용 |
|------|------|------|
| M1 | ✅ | 봇 기본 구조, 채널 자동 생성, 패널 UI |
| M2 | ✅ | AI 파티 편성, 이미지 렌더링, 시트 연동 |
| M3 | 🔄 진행 중 | 실서버 이전 후 실사용 온보딩 테스트, 버그 수정 |
| M4 | 🔄 진행 중 | 실서버 배포(Hetzner VPS + DuckDNS + Caddy) — MySQL 이전은 보류(JSON 저장소 유지) |
| M5 | ✅ | 웹 대시보드 설계 및 구현 |
| M6 | ⬜ | 수익화 (AdSense, 카카오톡 알림 프리미엄) |

---

## 누적 수정 파일

> 아래 목록은 2026-07 기준입니다. 이후 변경은 위 월별 기록을 참고하세요.

- `bot/main.py`
- `bot/cogs/party.py`
- `bot/cogs/schedule_view.py`
- `bot/cogs/raid_config.py` ← 신규
- `bot/cogs/raid_manage.py`
- `bot/cogs/help.py`
- `bot/utils/sheets.py`
- `bot/utils/image_renderer.py`
- `bot/config/channels.py`
- `bot/data/guild_settings.json`
- `bot/data/raid_data.json`
- `docs/` ← 웹사이트 7페이지