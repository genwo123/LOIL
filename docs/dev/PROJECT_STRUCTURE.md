# 📁 프로젝트 구조

## 전체 디렉토리 트리
```
LostArk-Guild-AI-Assistant/
├── 📁 bot/                          # 디스코드 봇 핵심 코드
│   ├── main.py                      # 봇 메인 실행 파일
│   ├── config.py                    # 설정 관리
│   │
│   ├── 📁 commands/                 # 디스코드 명령어 모듈
│   │   ├── __init__.py
│   │   ├── schedule.py              # 일정 조회 명령어
│   │   ├── character.py             # 캐릭터 관리 명령어
│   │   ├── ai.py                    # AI 추천 명령어
│   │   ├── notification.py          # 알림 설정 명령어
│   │   └── admin.py                 # 관리자 명령어
│   │
│   ├── 📁 cogs/                     # Discord.py Cogs
│   │   ├── __init__.py
│   │   ├── schedule_cog.py
│   │   ├── character_cog.py
│   │   └── notification_cog.py
│   │
│   ├── 📁 ai/                       # AI 연동 모듈
│   │   ├── __init__.py
│   │   ├── gemini.py                # Gemini API
│   │   ├── groq.py                  # Groq API (백업)
│   │   ├── prompts.py               # AI 프롬프트 템플릿
│   │   └── optimizer.py             # 파티 편성 알고리즘
│   │
│   ├── 📁 database/                 # 데이터베이스
│   │   ├── __init__.py
│   │   ├── models.py                # SQLAlchemy 모델
│   │   ├── migrations/              # Alembic 마이그레이션
│   │   └── queries.py               # 공통 쿼리
│   │
│   ├── 📁 integrations/             # 외부 API 연동
│   │   ├── __init__.py
│   │   ├── lostark_api.py           # 로아 API
│   │   ├── google_sheets.py         # 구글 시트
│   │   ├── kakao_bot.py             # 카카오톡 봇
│   │   └── api_key_manager.py       # API 키 관리 (Round-Robin)
│   │
│   └── 📁 utils/                    # 유틸리티 함수
│       ├── __init__.py
│       ├── parser.py                # 데이터 파싱
│       ├── validator.py             # 입력 검증
│       ├── scheduler.py             # 스케줄링
│       └── logger.py                # 로깅
│
├── 📁 web/                          # 웹사이트 (향후)
│   ├── 📁 frontend/                 # React 프론트엔드
│   │   ├── src/
│   │   ├── public/
│   │   └── package.json
│   │
│   ├── 📁 backend/                  # FastAPI 백엔드
│   │   ├── main.py
│   │   ├── routers/
│   │   └── models/
│   │
│   └── 📁 docs/                     # Docusaurus 문서 사이트
│       ├── docs/
│       ├── blog/
│       └── docusaurus.config.js
│
├── 📁 templates/                    # 구글 시트 템플릿
│   ├── guild_schedule_template.xlsx
│   └── template_guide.pdf
│
├── 📁 scripts/                      # 설치/배포 스크립트
│   ├── install.sh                   # Linux/Mac 설치
│   ├── install.bat                  # Windows 설치
│   └── deploy.sh                    # 배포 자동화
│
├── 📁 docs/                         # 문서
│   ├── 📁 dev/                      # 개발자 문서
│   │   ├── README.md
│   │   ├── DEVELOPMENT.md
│   │   ├── PROJECT_STRUCTURE.md
│   │   ├── CHANGELOG.md
│   │   ├── API_REFERENCE.md
│   │   ├── DATABASE_SCHEMA.md
│   │   └── MONETIZATION.md
│   │
│   └── 📁 user/                     # 유저 문서
│       ├── USER_GUIDE.md
│       ├── SETUP_GUIDE.md
│       ├── COMMANDS.md
│       └── PREMIUM_GUIDE.md
│
├── 📁 tests/                        # 테스트 코드
│   ├── test_commands.py
│   ├── test_ai.py
│   ├── test_database.py
│   └── test_integrations.py
│
├── 📁 docker/                       # Docker 설정
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── docker-compose.dev.yml
│
├── .env.example                     # 환경변수 예시
├── .gitignore                       # Git 제외 파일
├── requirements.txt                 # Python 패키지
├── pyproject.toml                   # Python 프로젝트 설정
├── LICENSE                          # MIT 라이선스
└── README.md                        # 프로젝트 소개
```

---

## 주요 파일 설명

### 봇 핵심 (bot/)

#### main.py
```python
"""
봇 메인 실행 파일
- 봇 초기화
- Cogs 로드
- 이벤트 핸들러
- 채널 자동 생성
"""
```

#### config.py
```python
"""
설정 관리
- 환경변수 로드
- API 키 관리
- 화이트리스트 관리
"""
```

---

### 명령어 모듈 (bot/commands/)

#### schedule.py
```python
"""
일정 관련 명령어
- /오늘레이드
- /이번주레이드
- /빛쟁 [닉네임] 레이드
"""
```

#### character.py
```python
"""
캐릭터 관리 명령어
- /원정대등록
- /내캐릭터
- /레이드설정
"""
```

#### ai.py
```python
"""
AI 추천 명령어
- /추천생성
- /추천 [요일]
- /통계 AI분석
"""
```

---

### AI 모듈 (bot/ai/)

#### gemini.py
```python
"""
Gemini API 연동
- 파티 편성 추천
- 통계 요약
- 프롬프트 실행
"""
```

#### optimizer.py
```python
"""
자체 파티 편성 알고리즘
- 서폿 우선 배치
- 시간대별 최적화
- 공방 인원 계산
"""
```

---

### 데이터베이스 (bot/database/)

#### models.py
```python
"""
SQLAlchemy 모델 정의
- Player
- Character
- Raid
- Schedule
- Notification
- ApiKey (API 키 관리)
"""
```

---

### 외부 연동 (bot/integrations/)

#### lostark_api.py
```python
"""
로스트아크 API
- 캐릭터 정보 조회
- 원정대 조회
"""
```

#### google_sheets.py
```python
"""
구글 시트 연동
- 시트 읽기
- 데이터 파싱
- 양방향 동기화
"""
```

#### kakao_bot.py
```python
"""
카카오톡 봇 (프리미엄)
- 코드 발급
- 알림 전송
- 일정 요약
"""
```

#### api_key_manager.py (신규 추가!)
```python
"""
API 키 관리 시스템
- Round-Robin 방식
- Rate Limit 추적
- 자동 폴백
- 무료: 2-3개, 프리미엄: 5개
"""
```

---

## 데이터 흐름도
```
┌─────────────────┐
│  구글 스프레드시트  │ (사용자가 일정 입력)
└────────┬────────┘
         │
         ↓ (읽기)
┌─────────────────┐
│  google_sheets  │ (파싱 → JSON)
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   MySQL/PgSQL   │ (데이터 저장)
└────────┬────────┘
         │
         ↓ (조회)
┌─────────────────┐
│  Discord 명령어  │ (사용자 요청)
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  API Key Manager│ (Round-Robin 선택)
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   AI 모듈       │ (분석 & 추천)
│  (Gemini/Groq)  │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Discord 알림   │ (결과 출력)
└────────┬────────┘
         │
         ↓ (프리미엄)
┌─────────────────┐
│  카카오톡 봇    │ (카톡 알림)
└─────────────────┘
```

---

## API 키 관리 흐름 (신규!)
```
사용자 요청
    ↓
API Key Manager
    ↓
┌───────────────────────────┐
│ 무료: Key 1, 2, 3 선택    │
│ 프리미엄: Key 1~5 선택    │
│ Round-Robin 방식          │
└───────────────────────────┘
    ↓
Rate Limit 체크
    ↓
┌──────────────┐
│ 여유 있음?   │
└──────────────┘
    │         │
   Yes       No
    │         │
    │         ↓
    │    다음 Key 선택
    │         │
    ↓         ↓
  요청 실행
    ↓
  응답 반환
```

---

## Docker 환경 구조
```
┌─────────────────────────────┐
│  로컬 개발 (docker-compose) │
├─────────────────────────────┤
│                             │
│  ┌──────────────┐           │
│  │  봇 컨테이너  │           │
│  │  (Python)    │           │
│  └──────┬───────┘           │
│         │                   │
│  ┌──────▼───────┐           │
│  │  MySQL/PgSQL │ (테스트용)│
│  │  컨테이너     │           │
│  └──────────────┘           │
│                             │
└─────────────────────────────┘
        │
        ↓ (배포 시)
┌─────────────────────────────┐
│  클라우드 (Railway/Render)   │
├─────────────────────────────┤
│                             │
│  ┌──────────────┐           │
│  │  봇 서버     │           │
│  └──────┬───────┘           │
│         │                   │
│  ┌──────▼───────┐           │
│  │ 클라우드 DB  │ (실제)    │
│  │ (Supabase)   │           │
│  └──────────────┘           │
│                             │
└─────────────────────────────┘
```

---

## 확장 포인트

### 새로운 게임 추가 시
```
bot/
├── games/
│   ├── lostark/        # 현재
│   ├── wow/            # 향후 추가
│   └── ff14/           # 향후 추가
```

### 새로운 명령어 추가 시
```python
# bot/commands/new_feature.py
from discord.ext import commands

class NewFeatureCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name='새명령어')
    async def new_command(self, ctx):
        # 구현
        pass

def setup(bot):
    bot.add_cog(NewFeatureCommands(bot))
```

---

## 코딩 컨벤션

### 파일명
- 소문자 + 언더스코어: `google_sheets.py`
- 클래스는 PascalCase: `GoogleSheetsAPI`

### 디렉토리명
- 소문자 단수형: `command/`, `model/`
- 복수형은 명확한 경우만: `commands/`, `utils/`

### Import 순서
```python
# 1. 표준 라이브러리
import os
from datetime import datetime

# 2. 서드파티
import discord
from discord.ext import commands

# 3. 프로젝트 내부
from bot.config import Config
from bot.database import models
```

---

## 다음 문서

- [DEVELOPMENT.md](DEVELOPMENT.md) - 개발 환경 설정
- [API_REFERENCE.md](API_REFERENCE.md) - API 사용법
- [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) - DB 구조
