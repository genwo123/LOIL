## 파일 5: docs/dev/CHANGELOG.md

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- 시너지 최적화 시스템
- 웹 대시보드
- 길드 매칭 시스템 고도화
- 모바일 앱 (React Native)
- 다국어 지원 (영어, 일본어)
- WoW, FF14 게임 지원

---

## [0.1.0] - 2026-02-06

### Added
- 프로젝트 초기 설정 완료
- 문서 구조 완성
  - README.md
  - PROJECT_STRUCTURE.md
  - DEVELOPMENT.md
  - CHANGELOG.md
  - API_REFERENCE.md
  - DATABASE_SCHEMA.md
  - MONETIZATION.md
  - .env.example
  - .gitignore
  - requirements.txt
- 유저 문서 완성
  - USER_GUIDE.md
  - SETUP_GUIDE.md
  - COMMANDS.md
  - PREMIUM_GUIDE.md
- 개발 로드맵 수립
- 수익화 전략 수립
- 기술 스택 결정
  - Gemini 2.0 Flash (무료 AI)
  - Groq Llama (백업 AI)
  - MySQL 8.0 (데이터베이스)
  - discord.py 2.3.2
  - Docker (개발 환경)
  - Railway (배포)

### Changed
- 프로젝트명 확정: **로일 (LoIl)**
- 데이터베이스: PostgreSQL → **MySQL** (개발자 경험 기반)
- 배포 전략: Railway 무료→유료 전환
- API 키 관리 전략 확정
  - 무료: 2-3개 API 키
  - 프리미엄: 5개 API 키
  - Round-Robin 방식
- 프리미엄 전략 확정
  - 무료: 모든 핵심 기능
  - 라이트 ₩2,500/월: 카톡 알림 + AI 무제한
  - 프로 ₩5,000/월: 관리 통계 + 뉴비 매칭

### Fixed
- N/A (첫 버전)

### Security
- N/A

### Notes
- MVP 개발 시작 예정
- Phase 1 목표: 2026년 3월 말

---

## [0.0.1] - 2026-02-04

### Added
- 프로젝트 구상 시작
- 초기 기획
  - 로스트아크 길드 레이드 일정 관리
  - AI 자동 파티 편성
  - 구글 시트 연동
  - 카카오톡 알림
- 팀 구성 (1인 개발)

---

## Version History Summary

| 버전 | 날짜 | 주요 변경사항 |
|------|------|--------------|
| 0.1.0 | 2026-02-06 | 프로젝트 기획 완료, 문서화 |
| 0.0.1 | 2026-02-04 | 프로젝트 시작 |

---

## 향후 버전 계획

### v0.2.0 (예정: 2026-02-15)
- [ ] 디스코드 봇 기본 틀
- [ ] 구글 시트 파싱
- [ ] 기본 명령어
  - /오늘레이드
  - /이번주레이드
  - /내캐릭터

### v0.3.0 (예정: 2026-02-28)
- [ ] AI 파티 편성 (Gemini)
- [ ] 알림 시스템 (Discord DM/멘션)
- [ ] 데이터베이스 연동 (MySQL)
- [ ] Docker 개발 환경

### v0.4.0 (예정: 2026-03-15)
- [ ] 로스트아크 API 연동
- [ ] 캐릭터 자동 등록 (/원정대등록)
- [ ] 통계 기능
- [ ] API 키 관리 시스템
  - Round-Robin
  - Rate Limit 추적

### v0.5.0 (예정: 2026-03-22)
- [ ] 채널 자동 생성
- [ ] 프리미엄 기능 기반
- [ ] 결제 시스템 준비

### v0.9.0 (예정: 2026-03-31) - Beta
- [ ] 베타 테스트 시작
- [ ] 버그 수정
- [ ] 성능 최적화
- [ ] 카카오톡 봇 연동 (프리미엄)
- [ ] 웹사이트 베타

### v1.0.0 (예정: 2026-04-15) - 정식 출시
- [ ] 공식 출시
- [ ] 프리미엄 결제 시스템
- [ ] 카카오톡 봇 정식 오픈
- [ ] 홈페이지 오픈
- [ ] 광고 시스템 (Google AdSense)

### v1.1.0 (예정: 2026-05-01)
- [ ] 웹 대시보드
- [ ] 길드 매칭 시스템
- [ ] 템플릿 기능
- [ ] AI 뉴비 매칭

### v2.0.0 (예정: 2026-07-01) - 다중 게임 지원
- [ ] WoW (월드 오브 워크래프트) 지원
- [ ] 게임 선택 기능
- [ ] 다국어 지원 (영어)

---

## Changelog 작성 가이드

### Categories
- **Added**: 새로운 기능
- **Changed**: 기존 기능 변경
- **Deprecated**: 곧 제거될 기능
- **Removed**: 제거된 기능
- **Fixed**: 버그 수정
- **Security**: 보안 관련

### Example Entry
```markdown
## [1.0.0] - 2026-04-15

### Added
- 프리미엄 결제 시스템 (Stripe)
- 카카오톡 봇 연동
- 길드 매칭 시스템

### Changed
- 알림 시스템 UI 개선
- AI 프롬프트 최적화
- 데이터베이스 인덱스 추가

### Fixed
- 시간대 계산 버그 수정 (#123)
- 메모리 누수 문제 해결 (#145)
- API 키 로테이션 오류 수정 (#167)

### Security
- API 키 암호화 강화
- SQL Injection 방어 추가
- Rate Limiting 개선
```

---

## Contact

버그 리포트 및 기능 제안: [GitHub Issues](https://github.com/your-username/loil/issues)

---

## 다음 검토일

**2026년 5월** (3개월 후)
- 실제 사용 데이터 분석
- 수익화 현황 점검
- 로드맵 재조정
```

---
