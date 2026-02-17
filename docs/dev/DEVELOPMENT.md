# 🛠 개발 가이드

## 개발 환경 요구사항

### 필수
- **Python 3.11+**
- **MySQL 8.0+** (또는 PostgreSQL 15+)
- **Docker** (로컬 개발용)
- **Git**
- **VSCode** (추천 IDE)

### 선택
- **Node.js 18+** (웹 개발 시)
- **Redis** (캐싱용)

---

## 초기 설정

### 1. 저장소 클론
```bash
git clone https://github.com/your-username/loil.git
cd loil
```

### 2. 가상환경 생성
```bash
# venv 사용
python -m venv venv

# 활성화 (Linux/Mac)
source venv/bin/activate

# 활성화 (Windows)
venv\Scripts\activate
```

### 3. 패키지 설치
```bash
pip install -r requirements.txt
```

### 4. 환경변수 설정
```bash
cp .env.example .env
```

`.env` 파일 편집:
```env
# Discord
DISCORD_BOT_TOKEN=your_token_here
DISCORD_GUILD_ID=your_guild_id

# Database
DATABASE_URL=mysql://user:password@localhost:3306/loil

# AI
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key

# APIs
LOSTARK_API_KEY=your_lostark_key
GOOGLE_CREDENTIALS_FILE=service-account-key.json
```

### 5. Docker로 MySQL 실행 (로컬 개발)
```bash
# MySQL 컨테이너 실행
docker run -d \
  --name loil-mysql \
  -e MYSQL_ROOT_PASSWORD=yourpassword \
  -e MYSQL_DATABASE=loil \
  -p 3306:3306 \
  mysql:8.0

# 확인
docker ps
```

### 6. 데이터베이스 마이그레이션
```bash
# Alembic 초기화 (최초 1회)
alembic init migrations

# 마이그레이션 실행
alembic upgrade head
```

### 7. 봇 실행
```bash
python bot/main.py
```

---

## VSCode 설정

### 추천 확장
`.vscode/extensions.json`:
```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.vscode-pylance",
    "ms-python.black-formatter",
    "charliermarsh.ruff",
    "eamodio.gitlens",
    "github.copilot",
    "ms-azuretools.vscode-docker"
  ]
}
```

### 프로젝트 설정
`.vscode/settings.json`:
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  },
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter",
    "editor.rulers": [88]
  }
}
```

---

## 개발 워크플로우

### Git 브랜치 전략 (Git Flow)
```
main (프로덕션)
├── develop (개발)
│   ├── feature/character-system
│   ├── feature/ai-recommendation
│   └── feature/notification-system
├── hotfix/critical-bug
└── release/v1.0.0
```

### 커밋 컨벤션
```
feat: 새로운 기능 추가
fix: 버그 수정
docs: 문서 수정
style: 코드 포맷팅
refactor: 코드 리팩토링
test: 테스트 추가
chore: 빌드, 패키지 수정

예시:
feat: 캐릭터 등록 API 연동 추가
fix: 알림 시간 계산 버그 수정
docs: README에 설치 가이드 추가
```

### PR (Pull Request) 템플릿
```markdown
## 변경 사항
- 

## 테스트
- [ ] 로컬 테스트 완료
- [ ] 단위 테스트 추가

## 스크린샷 (선택)

## 관련 이슈
Closes #
```

---

## 테스트

### 단위 테스트
```bash
# 전체 테스트
pytest

# 특정 파일
pytest tests/test_commands.py

# 커버리지
pytest --cov=bot --cov-report=html
```

### 테스트 작성 예시
```python
# tests/test_commands.py
import pytest
from bot.commands import schedule

@pytest.mark.asyncio
async def test_today_raid_command():
    # Given
    ctx = MockContext()
    
    # When
    await schedule.today_raid(ctx)
    
    # Then
    assert ctx.send.called
    assert "오늘" in ctx.send.call_args[0][0]
```

---

## 디버깅

### 로그 설정
```python
# bot/utils/logger.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
```

### VSCode 디버그 설정
`.vscode/launch.json`:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Bot",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/bot/main.py",
      "console": "integratedTerminal",
      "env": {
        "PYTHONPATH": "${workspaceFolder}"
      }
    }
  ]
}
```

---

## Docker 개발 환경

### docker-compose.yml (개발용)
```yaml
version: '3.8'

services:
  mysql:
    image: mysql:8.0
    container_name: loil-mysql
    environment:
      MYSQL_ROOT_PASSWORD: rootpassword
      MYSQL_DATABASE: loil
      MYSQL_USER: loil_user
      MYSQL_PASSWORD: loil_password
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
    networks:
      - loil-network

  bot:
    build: .
    container_name: loil-bot
    depends_on:
      - mysql
    environment:
      - DATABASE_URL=mysql://loil_user:loil_password@mysql:3306/loil
    volumes:
      - ./bot:/app/bot
      - ./.env:/app/.env
    networks:
      - loil-network

volumes:
  mysql_data:

networks:
  loil-network:
    driver: bridge
```

### 실행
```bash
# 컨테이너 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f bot

# 중지
docker-compose down

# 볼륨까지 삭제 (DB 초기화)
docker-compose down -v
```

---

## 배포

### 개발 환경 (Local)
```bash
python bot/main.py
```

### 스테이징 환경 (Railway)
```bash
# Railway CLI 설치
npm install -g @railway/cli

# 로그인
railway login

# 프로젝트 연결
railway link

# 배포
railway up
```

### 프로덕션 환경 (GitHub Actions)
```yaml
# .github/workflows/deploy.yml
name: Deploy to Railway

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Railway
        run: railway up
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
```

---

## 코드 스타일

### Black (포맷터)
```bash
# 전체 포맷팅
black bot/

# 특정 파일
black bot/main.py

# 체크만 (변경 안 함)
black --check bot/
```

### Ruff (린터)
```bash
# 린팅
ruff check bot/

# 자동 수정
ruff check --fix bot/
```

### Type Hints
```python
# 타입 힌트 사용 권장
from typing import Optional, List

def get_character(character_id: int) -> Optional[Character]:
    return db.query(Character).filter_by(id=character_id).first()

def get_characters(player_id: int) -> List[Character]:
    return db.query(Character).filter_by(player_id=player_id).all()
```

---

## 성능 최적화

### 데이터베이스 쿼리 최적화
```python
# ❌ N+1 문제
for character in characters:
    player = character.player  # 매번 쿼리

# ✅ Eager Loading
from sqlalchemy.orm import joinedload

characters = db.query(Character).options(
    joinedload(Character.player)
).all()
```

### 캐싱
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_raid_info(raid_name: str) -> RaidInfo:
    # 무거운 연산
    return fetch_raid_info(raid_name)
```

### API 키 Round-Robin
```python
# bot/integrations/api_key_manager.py
class ApiKeyManager:
    def __init__(self, keys: List[str]):
        self.keys = keys
        self.current_index = 0
    
    def get_next_key(self) -> str:
        key = self.keys[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.keys)
        return key
```

---

## 트러블슈팅

### 봇이 응답하지 않을 때
1. 토큰 확인: `.env` 파일의 `DISCORD_BOT_TOKEN`
2. 권한 확인: 봇이 메시지 읽기/쓰기 권한 있는지
3. 로그 확인: `bot.log` 파일

### 데이터베이스 연결 실패
1. MySQL 실행 확인: `docker ps`
2. `DATABASE_URL` 확인
3. 포트 충돌 확인 (3306)

### AI API 오류
1. API 키 유효성 확인
2. 쿼터 초과 확인 (무료 티어 제한)
3. 백업 API로 전환 (Groq)

### Docker 컨테이너 문제
```bash
# 컨테이너 로그 확인
docker logs loil-mysql
docker logs loil-bot

# 컨테이너 재시작
docker restart loil-mysql

# 네트워크 확인
docker network inspect loil-network
```

---

## 유용한 명령어

### 데이터베이스
```bash
# 마이그레이션 생성
alembic revision --autogenerate -m "Add new table"

# 롤백
alembic downgrade -1

# 현재 버전 확인
alembic current

# MySQL 접속 (Docker)
docker exec -it loil-mysql mysql -u loil_user -p
```

### 패키지 관리
```bash
# 패키지 추가
pip install package_name
pip freeze > requirements.txt

# 패키지 업데이트
pip install --upgrade package_name

# 가상환경 초기화
deactivate
rm -rf venv
python -m venv venv
```

### Docker
```bash
# 이미지 빌드
docker build -t loil-bot .

# 컨테이너 실행
docker run -d --name loil-bot loil-bot

# 컨테이너 접속
docker exec -it loil-bot bash

# 볼륨 확인
docker volume ls

# 네트워크 확인
docker network ls
```

---

## API 키 관리 베스트 프랙티스

### 무료 유저 (2-3개 키)
```python
# config.py
class Config:
    MAX_API_KEYS_FREE = 3
    MAX_API_KEYS_PREMIUM = 5
    
    @staticmethod
    def get_max_keys(is_premium: bool) -> int:
        return Config.MAX_API_KEYS_PREMIUM if is_premium else Config.MAX_API_KEYS_FREE
```

### Rate Limit 추적
```python
# bot/integrations/api_key_manager.py
class ApiKeyTracker:
    def __init__(self):
        self.limits = {}  # {key: {"remaining": 60, "reset_at": timestamp}}
    
    def can_use_key(self, key: str) -> bool:
        if key not in self.limits:
            return True
        
        limit = self.limits[key]
        if limit["remaining"] <= 0:
            if time.time() >= limit["reset_at"]:
                # 리셋
                limit["remaining"] = 60
                limit["reset_at"] = time.time() + 60
            else:
                return False
        
        return True
    
    def use_key(self, key: str):
        if key not in self.limits:
            self.limits[key] = {"remaining": 60, "reset_at": time.time() + 60}
        
        self.limits[key]["remaining"] -= 1
```

---

## 다음 단계

- [API_REFERENCE.md](API_REFERENCE.md) - API 사용법
- [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) - DB 구조
- [CHANGELOG.md](CHANGELOG.md) - 버전 히스토리

---

## 참고 자료

- [discord.py 문서](https://discordpy.readthedocs.io/)
- [Gemini API 문서](https://ai.google.dev/docs)
- [FastAPI 문서](https://fastapi.tiangolo.com/)
- [MySQL 문서](https://dev.mysql.com/doc/)
- [Docker 문서](https://docs.docker.com/)
- [Railway 문서](https://docs.railway.app/)
