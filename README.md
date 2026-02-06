# 🎮 로일 (LoIl)

> 로스트아크 길드 레이드 일정을 AI가 자동으로 관리해드립니다

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.3.2-blue.svg)](https://github.com/Rapptz/discord.py)

---

## ✨ 주요 기능

### 🤖 AI 자동 파티 편성
- **Gemini 2.0 Flash** 무료 AI 활용
- 서폿 자동 균등 배치
- 시간대별 최적화
- 시너지 고려 파티 구성

### 📊 구글 시트 연동
- 익숙한 스프레드시트로 일정 관리
- 실시간 양방향 동기화
- 길드원 모두 함께 편집 가능

### 🔔 스마트 알림
- 디스코드 DM/멘션 알림
- 다중 시간 설정 (30분, 15분, 5분 전 등)
- **프리미엄**: 카카오톡 알림

### 📈 상세 통계
- 레이드 참여 기록
- 클리어 타임 분석
- 골드 수익 계산
- AI 인사이트 (프리미엄)

### 🔑 API 키 관리 시스템
- **무료**: 2-3개 API 키 등록
- **프리미엄**: 5개 API 키 등록
- Round-Robin 방식으로 부하 분산
- Rate Limit 자동 관리

---

## 🚀 빠른 시작

### 사용자 (길드 마스터/멤버)

1. **봇 초대**
```
   [초대 링크 예정]
```

2. **초기 설정**
```
   /설정
```

3. **구글 시트 연동**
```
   /시트연동 [시트 URL]
```

4. **캐릭터 등록**
```
   /원정대등록 [캐릭터명]
```

5. **AI 추천 받기**
```
   /추천생성
```

**자세한 가이드**: [사용자 가이드](docs/user/USER_GUIDE.md)

---

### 개발자

#### 요구사항
- Python 3.11+
- PostgreSQL 15+ (또는 MySQL 8.0+)
- Docker (선택사항)
- Git

#### 설치
```bash
# 저장소 클론
git clone https://github.com/your-username/loil.git
cd loil

# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일 편집 (API 키 등)

# 데이터베이스 마이그레이션
alembic upgrade head

# 봇 실행
python bot/main.py
```

**자세한 가이드**: [개발 가이드](docs/dev/DEVELOPMENT.md)

---

## 🏗️ 기술 스택

### Backend
- **Python 3.11+**
- **discord.py 2.3.2** - 디스코드 봇
- **MySQL 8.0** / PostgreSQL 15 - 데이터베이스
- **SQLAlchemy 2.0** - ORM
- **Alembic** - DB 마이그레이션

### AI
- **Gemini 2.0 Flash** - 메인 AI (무료!)
- **Groq Llama** - 백업 AI (무료)

### 외부 API
- **로스트아크 API** - 캐릭터 정보
- **Google Sheets API** - 시트 연동
- **카카오톡 API** - 카톡 알림 (프리미엄)

### 인프라
- **Docker** - 로컬 개발 환경
- **Railway** / Render - 배포 (무료→유료 전환)
- **Supabase** / PlanetScale - 클라우드 DB

### Frontend (향후)
- React
- FastAPI
- Docusaurus

---

## 📁 프로젝트 구조
```
loil/
├── bot/                    # 봇 핵심 코드
│   ├── commands/          # 명령어
│   ├── ai/                # AI 모듈
│   ├── database/          # DB 모델
│   └── integrations/      # 외부 API
├── web/                   # 웹사이트 (향후)
├── docs/                  # 문서
├── tests/                 # 테스트
└── scripts/               # 유틸리티
```

**자세한 구조**: [PROJECT_STRUCTURE.md](docs/dev/PROJECT_STRUCTURE.md)

---

## 💎 무료 vs 프리미엄

### 무료 (평생)
✅ 모든 핵심 기능  
✅ 구글 시트 연동  
✅ 디스코드 알림  
✅ AI 추천 (주 3회)  
✅ 전체 통계  
✅ API 키 2-3개  

### 프리미엄 (₩2,500/월)
✅ 무료 기능 전체  
✅ AI 추천 무제한  
✅ AI 통계 요약  
✅ **카카오톡 알림** ⭐ (1명 구독 = 길드 전체 혜택)  
✅ 편의 명령어  
✅ API 키 5개  

**자세한 내용**: [프리미엄 가이드](docs/user/PREMIUM_GUIDE.md)

---

## 📚 문서

### 사용자
- [사용자 가이드](docs/user/USER_GUIDE.md)
- [설치 가이드](docs/user/SETUP_GUIDE.md)
- [명령어 모음](docs/user/COMMANDS.md)
- [프리미엄 가이드](docs/user/PREMIUM_GUIDE.md)

### 개발자
- [개발 가이드](docs/dev/DEVELOPMENT.md)
- [프로젝트 구조](docs/dev/PROJECT_STRUCTURE.md)
- [API 레퍼런스](docs/dev/API_REFERENCE.md)
- [데이터베이스 스키마](docs/dev/DATABASE_SCHEMA.md)
- [변경 기록](docs/dev/CHANGELOG.md)

---

## 🗺️ 로드맵

### Phase 1: MVP (2026년 3월)
- [x] 기획 완료
- [ ] 디스코드 봇 기본 틀
- [ ] 구글 시트 파싱
- [ ] AI 파티 편성
- [ ] 알림 시스템

### Phase 2: Beta (2026년 4월)
- [ ] 로스트아크 API 연동
- [ ] 카카오톡 봇 (프리미엄)
- [ ] 통계 기능
- [ ] 베타 테스트

### Phase 3: 정식 출시 (2026년 4월 중순)
- [ ] 결제 시스템
- [ ] 웹사이트
- [ ] 공식 출시

### Phase 4: 확장 (2026년 하반기)
- [ ] WoW 지원
- [ ] 길드 매칭
- [ ] 모바일 앱

**전체 로드맵**: [GitHub Projects](https://github.com/your-username/loil/projects)

---

## 🤝 기여하기

기여는 언제나 환영입니다! 🎉

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

**기여 가이드**: [CONTRIBUTING.md](CONTRIBUTING.md)

---

## 🐛 버그 리포트 & 기능 제안

- **버그 리포트**: [GitHub Issues](https://github.com/your-username/loil/issues)
- **기능 제안**: [GitHub Discussions](https://github.com/your-username/loil/discussions)
- **Discord**: [지원 서버](https://discord.gg/loil)

---

## 📄 라이선스

MIT License - 자유롭게 사용하세요!

**상세**: [LICENSE](LICENSE)

---

## 🙏 감사의 말

- [discord.py](https://github.com/Rapptz/discord.py) - 디스코드 봇 라이브러리
- [Google Gemini](https://ai.google.dev/) - 무료 AI API
- [Groq](https://groq.com/) - 백업 AI
- [Smilegate RPG](https://lostark.game.onstove.com/) - 로스트아크 API

---

## 📞 연락처

- **웹사이트**: https://loil.kr (예정)
- **Discord**: [지원 서버](https://discord.gg/loil)
- **이메일**: support@loil.kr
- **GitHub**: [@your-username](https://github.com/your-username)

---

<div align="center">

**로일과 함께 더 쉽고 편한 길드 생활!** 🎮

[봇 초대하기](#) • [문서 보기](docs/) • [지원 서버](https://discord.gg/loil)

Made with ❤️ by [Your Name]

</div>
