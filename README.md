# 로일(LoIl) 변경 기록

Discord 봇 + 웹사이트 전체 변경 이력을 월별 · 주차별로 관리합니다.

---

## 월별 기록

| 월 | 링크 | 주요 작업 |
|----|------|-----------|
| 2026-03 | [2026-03.md](./CHANGELOG/2026-03.md) | raid_data 개편, 채널 구조 개선, 버그 수정 3종, 웹사이트 7페이지 |
| 2026-07 | [2026-07.md](./CHANGELOG/2026-07.md) | 기록 시작 (진행 중) |
| 2026-08 | [2026-08.md](./CHANGELOG/2026-08.md) | 웹 대시보드 로그인 스킵 개발 스위치, 디자인 미리보기 (진행 중) |

---

## 마일스톤

| 단계 | 상태 | 내용 |
|------|------|------|
| M1 | ✅ | 봇 기본 구조, 채널 자동 생성, 패널 UI |
| M2 | ✅ | AI 파티 편성, 이미지 렌더링, 시트 연동 |
| M3 | 🔄 진행 중 | 동생 서버 배포 테스트, 버그 수정 |
| M4 | ⬜ | Railway 배포 + MySQL 마이그레이션 |
| M5 | ⬜ | 웹 대시보드 설계 및 구현 |
| M6 | ⬜ | 수익화 (AdSense, 카카오톡 알림 프리미엄) |

---

## 누적 수정 파일

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