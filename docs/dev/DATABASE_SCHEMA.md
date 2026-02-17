# 🗄️ Database Schema

## ERD (Entity Relationship Diagram)
```
┌─────────────┐       ┌──────────────┐       ┌─────────────┐
│   Guild     │       │   Player     │       │  Character  │
├─────────────┤       ├──────────────┤       ├─────────────┤
│ id (PK)     │───┐   │ id (PK)      │───┐   │ id (PK)     │
│ name        │   └──<│ guild_id(FK) │   └──<│ player_id   │
│ server      │       │ nickname     │       │ name        │
│ discord_id  │       │ discord_id   │       │ job         │
│ premium     │       │ main_char    │       │ level       │
│ created_at  │       │ premium      │       │ role        │
└─────────────┘       │ created_at   │       │ status      │
                      └──────────────┘       │ synergies   │
                             │               └─────────────┘
                             │
                             ↓
                      ┌──────────────┐
                      │   ApiKey     │ ← 신규!
                      ├──────────────┤
                      │ id (PK)      │
                      │ player_id(FK)│
                      │ guild_id(FK) │
                      │ api_key_hash │
                      │ nickname     │
                      │ last_used    │
                      │ is_active    │
                      │ created_at   │
                      └──────────────┘
                             │
                             ↓
                      ┌──────────────┐
                      │   Schedule   │
                      ├──────────────┤
                      │ id (PK)      │
                      │ player_id(FK)│
                      │ character_id │
                      │ day_of_week  │
                      │ time         │
                      │ raid_id (FK) │
                      │ updated_at   │
                      └──────────────┘
                             │
                             ↓
┌─────────────┐       ┌──────────────┐       ┌──────────────┐
│    Raid     │       │    Party     │       │Notification  │
├─────────────┤       ├──────────────┤       ├──────────────┤
│ id (PK)     │───┐   │ id (PK)      │       │ id (PK)      │
│ name        │   └──<│ raid_id (FK) │       │ player_id(FK)│
│ type (4/8)  │       │ difficulty   │       │ method       │
│ difficulties│       │ datetime     │       │ times        │
│ min_level   │       │ party_num    │       │ enabled      │
│ duration    │       │ members      │       └──────────────┘
└─────────────┘       │ status       │
                      │ created_by   │
                      └──────────────┘
```

---

## 테이블 정의

### guilds - 길드 정보
```sql
CREATE TABLE guilds (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    server VARCHAR(50),
    discord_guild_id BIGINT UNIQUE NOT NULL,
    spreadsheet_url TEXT,
    premium_tier VARCHAR(20) DEFAULT 'free',  -- free, light, pro, guild
    premium_expires_at TIMESTAMP,
    kakao_bot_code VARCHAR(20) UNIQUE,
    max_api_keys INTEGER DEFAULT 3,  -- 신규! 무료: 3, 프리미엄: 5
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_guilds_discord_id ON guilds(discord_guild_id);
CREATE INDEX idx_guilds_premium_tier ON guilds(premium_tier);
```

**컬럼 설명:**
- `premium_tier`: 프리미엄 등급 (free, light, pro, guild)
- `kakao_bot_code`: 카카오톡 봇 연동 코드
- `max_api_keys`: 등록 가능한 최대 API 키 개수
- `settings`: 길드별 설정 (JSON)

**settings 예시:**
```json
{
  "auto_sync": true,
  "sync_interval": 3600,
  "notification_channel_id": "123456789",
  "alarm_channel_id": "987654321",
  "stats_channel_id": "456789123"
}
```

---

### players - 플레이어 정보
```sql
CREATE TABLE players (
    id SERIAL PRIMARY KEY,
    guild_id INTEGER REFERENCES guilds(id) ON DELETE CASCADE,
    discord_id BIGINT UNIQUE NOT NULL,
    nickname VARCHAR(50) NOT NULL,
    main_character VARCHAR(50),
    lostark_api_linked BOOLEAN DEFAULT FALSE,
    premium_tier VARCHAR(20) DEFAULT 'free',
    premium_expires_at TIMESTAMP,
    last_sync TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(guild_id, nickname)
);

CREATE INDEX idx_players_discord_id ON players(discord_id);
CREATE INDEX idx_players_guild_id ON players(guild_id);
CREATE INDEX idx_players_premium_tier ON players(premium_tier);
```

---

### characters - 캐릭터 정보
```sql
CREATE TABLE characters (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id) ON DELETE CASCADE,
    name VARCHAR(50) UNIQUE NOT NULL,
    job VARCHAR(50) NOT NULL,
    level DECIMAL(6,2) NOT NULL,
    role VARCHAR(20) NOT NULL,  -- dealer, support
    synergies TEXT[],
    status VARCHAR(20) DEFAULT 'active',  -- active, excluded, rest
    weekly_raids JSONB DEFAULT '[]',  -- [{"raid": "종막", "difficulty": "하드", "gold": true}]
    memo TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_characters_player_id ON characters(player_id);
CREATE INDEX idx_characters_name ON characters(name);
CREATE INDEX idx_characters_role ON characters(role);
```

**weekly_raids 예시:**
```json
[
    {"raid": "4막", "difficulty": "노말", "gold": true},
    {"raid": "종막", "difficulty": "하드", "gold": true},
    {"raid": "세르카", "difficulty": "나메", "gold": true}
]
```

---

### api_keys - API 키 관리 (신규!)
```sql
CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id) ON DELETE CASCADE,
    guild_id INTEGER REFERENCES guilds(id) ON DELETE CASCADE,
    api_key_hash VARCHAR(255) NOT NULL,  -- 암호화된 API 키
    nickname VARCHAR(50),  -- "길마 키", "부길마 키" 등
    service VARCHAR(50) DEFAULT 'lostark',  -- lostark, wow, ff14
    last_used TIMESTAMP,
    usage_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(guild_id, api_key_hash)
);

CREATE INDEX idx_api_keys_player_id ON api_keys(player_id);
CREATE INDEX idx_api_keys_guild_id ON api_keys(guild_id);
CREATE INDEX idx_api_keys_is_active ON api_keys(is_active);
```

**컬럼 설명:**
- `api_key_hash`: SHA-256으로 암호화된 API 키
- `nickname`: 사용자가 지정한 키 이름
- `usage_count`: 사용 횟수 추적
- `is_active`: 비활성화된 키

---

### raids - 레이드 마스터 데이터
```sql
CREATE TABLE raids (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    game VARCHAR(50) DEFAULT 'lostark',  -- 향후 wow, ff14 등
    type VARCHAR(10) NOT NULL,  -- 4인, 8인
    difficulties TEXT[] NOT NULL,  -- ['노말', '하드', '나메']
    min_levels JSONB NOT NULL,  -- {"노말": 1680, "하드": 1700, "나메": 1730}
    duration_minutes JSONB NOT NULL,  -- {"노말": 50, "하드": 60}
    required_composition JSONB,  -- {"딜러": 6, "서폿": 2}
    lock_rule VARCHAR(50) DEFAULT 'any_locks_all',
    created_at TIMESTAMP DEFAULT NOW()
);

-- 초기 데이터
INSERT INTO raids (name, type, difficulties, min_levels, duration_minutes, required_composition) VALUES
('종막', '8인', ARRAY['노말', '하드'], '{"노말": 1680, "하드": 1700}', '{"노말": 50, "하드": 60}', '{"딜러": 6, "서폿": 2}'),
('세르카', '4인', ARRAY['노말', '하드', '나메'], '{"노말": 1700, "하드": 1720, "나메": 1730}', '{"노말": 40, "하드": 50, "나메": 70}', '{"딜러": 3, "서폿": 1}'),
('4막', '8인', ARRAY['노말', '하드'], '{"노말": 1660, "하드": 1680}', '{"노말": 50, "하드": 60}', '{"딜러": 6, "서폿": 2}'),
('카멘', '4인', ARRAY['노말', '하드'], '{"노말": 1630, "하드": 1650}', '{"노말": 40, "하드": 50}', '{"딜러": 3, "서폿": 1}');

CREATE INDEX idx_raids_name ON raids(name);
CREATE INDEX idx_raids_game ON raids(game);
```

---

### schedules - 개인 일정
```sql
CREATE TABLE schedules (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id) ON DELETE CASCADE,
    character_id INTEGER REFERENCES characters(id) ON DELETE SET NULL,
    day_of_week INTEGER NOT NULL,  -- 0=월, 1=화, ..., 6=일
    time TIME NOT NULL,
    raid_id INTEGER REFERENCES raids(id),
    difficulty VARCHAR(20),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(player_id, day_of_week, time)
);

CREATE INDEX idx_schedules_player_id ON schedules(player_id);
CREATE INDEX idx_schedules_day_time ON schedules(day_of_week, time);
CREATE INDEX idx_schedules_raid_id ON schedules(raid_id);
```

---

### parties - 파티 편성
```sql
CREATE TABLE parties (
    id SERIAL PRIMARY KEY,
    guild_id INTEGER REFERENCES guilds(id) ON DELETE CASCADE,
    raid_id INTEGER REFERENCES raids(id),
    difficulty VARCHAR(20) NOT NULL,
    party_num INTEGER NOT NULL,  -- 1파티, 2파티
    datetime TIMESTAMP NOT NULL,
    members JSONB NOT NULL,  -- [{"player_id": 1, "character_id": 1, "role": "support"}]
    status VARCHAR(20) DEFAULT 'scheduled',  -- scheduled, completed, cancelled
    completion_time INTEGER,  -- 클리어 타임 (분)
    created_by INTEGER REFERENCES players(id),
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(guild_id, raid_id, difficulty, party_num, datetime)
);

CREATE INDEX idx_parties_guild_id ON parties(guild_id);
CREATE INDEX idx_parties_datetime ON parties(datetime);
CREATE INDEX idx_parties_status ON parties(status);
```

**members 예시:**
```json
[
    {"player_id": 1, "character_id": 1, "character_name": "빛쟁인거니", "job": "홀나", "role": "support"},
    {"player_id": 2, "character_id": 3, "character_name": "하즈소서", "job": "소서리스", "role": "dealer"}
]
```

---

### notifications - 알림 설정
```sql
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id) ON DELETE CASCADE,
    method VARCHAR(20) NOT NULL,  -- dm, mention, both, off
    before_minutes INTEGER[] DEFAULT ARRAY[30],
    discord_enabled BOOLEAN DEFAULT TRUE,
    kakao_enabled BOOLEAN DEFAULT FALSE,
    kakao_chat_id VARCHAR(100),
    channel_settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(player_id)
);

CREATE INDEX idx_notifications_player_id ON notifications(player_id);
```

**channel_settings 예시:**
```json
{
    "use_embed": true,
    "use_thread": false,
    "delete_after_hours": 24
}
```

---

### ai_requests - AI 사용 기록
```sql
CREATE TABLE ai_requests (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id),
    guild_id INTEGER REFERENCES guilds(id),
    request_type VARCHAR(50) NOT NULL,  -- party_recommendation, stats_summary
    prompt TEXT,
    response TEXT,
    tokens_used INTEGER,
    cost DECIMAL(10,4) DEFAULT 0,
    api_provider VARCHAR(20) DEFAULT 'gemini',  -- gemini, groq
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_ai_requests_player_id ON ai_requests(player_id);
CREATE INDEX idx_ai_requests_guild_id ON ai_requests(guild_id);
CREATE INDEX idx_ai_requests_created_at ON ai_requests(created_at);
CREATE INDEX idx_ai_requests_type ON ai_requests(request_type);
```

---

### premium_subscriptions - 프리미엄 구독
```sql
CREATE TABLE premium_subscriptions (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id),
    guild_id INTEGER REFERENCES guilds(id),
    tier VARCHAR(20) NOT NULL,  -- light, pro, guild
    price INTEGER NOT NULL,
    starts_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    auto_renew BOOLEAN DEFAULT TRUE,
    payment_method VARCHAR(50),
    payment_id VARCHAR(100),
    status VARCHAR(20) DEFAULT 'active',  -- active, cancelled, expired
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_subscriptions_player_id ON premium_subscriptions(player_id);
CREATE INDEX idx_subscriptions_guild_id ON premium_subscriptions(guild_id);
CREATE INDEX idx_subscriptions_expires_at ON premium_subscriptions(expires_at);
CREATE INDEX idx_subscriptions_status ON premium_subscriptions(status);
```

---

### api_rate_limits - API Rate Limit 추적 (신규!)
```sql
CREATE TABLE api_rate_limits (
    id SERIAL PRIMARY KEY,
    api_key_id INTEGER REFERENCES api_keys(id) ON DELETE CASCADE,
    remaining_requests INTEGER DEFAULT 60,
    reset_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(api_key_id)
);

CREATE INDEX idx_rate_limits_api_key_id ON api_rate_limits(api_key_id);
CREATE INDEX idx_rate_limits_reset_at ON api_rate_limits(reset_at);
```

---

## 샘플 데이터

### 길드 생성
```sql
INSERT INTO guilds (name, server, discord_guild_id, premium_tier, max_api_keys) VALUES
('빛쟁이들', '아만', 123456789, 'free', 3);
```

### 플레이어 생성
```sql
INSERT INTO players (guild_id, discord_id, nickname, main_character) VALUES
(1, 987654321, '거니', '빛쟁인거니');
```

### 캐릭터 생성
```sql
INSERT INTO characters (player_id, name, job, level, role, synergies) VALUES
(1, '빛쟁인거니', '홀리나이트', 1750.00, 'support', ARRAY['방어력 증가', '실드 제공']),
(1, '뚜띠될거니', '워로드', 1720.00, 'dealer', ARRAY['치명타 저항 감소', '방어력 감소']);
```

### API 키 생성 (신규!)
```sql
-- SHA-256으로 암호화해서 저장
INSERT INTO api_keys (player_id, guild_id, api_key_hash, nickname, service) VALUES
(1, 1, 'hash_of_api_key_1', '길마 키', 'lostark'),
(1, 1, 'hash_of_api_key_2', '부길마 키', 'lostark'),
(1, 1, 'hash_of_api_key_3', '예비 키', 'lostark');
```

### 일정 생성
```sql
INSERT INTO schedules (player_id, character_id, day_of_week, time, raid_id, difficulty) VALUES
(1, 1, 0, '20:00', 1, '하드'),  -- 월요일 20시 종막 하드
(1, 1, 1, '21:00', 2, '나메');  -- 화요일 21시 세르카 나메
```

---

## 쿼리 예시

### 오늘 레이드 조회
```sql
SELECT 
    p.datetime,
    r.name AS raid_name,
    p.difficulty,
    p.party_num,
    p.members
FROM parties p
JOIN raids r ON p.raid_id = r.id
WHERE p.guild_id = $1
  AND DATE(p.datetime) = CURRENT_DATE
ORDER BY p.datetime;
```

### 특정 플레이어 이번 주 일정
```sql
SELECT 
    s.day_of_week,
    s.time,
    r.name AS raid_name,
    s.difficulty,
    c.name AS character_name,
    c.job
FROM schedules s
JOIN raids r ON s.raid_id = r.id
JOIN characters c ON s.character_id = c.id
WHERE s.player_id = $1
ORDER BY s.day_of_week, s.time;
```

### 시간대별 가능 인원
```sql
SELECT 
    s.day_of_week,
    s.time,
    COUNT(*) AS available_count,
    ARRAY_AGG(p.nickname) AS members
FROM schedules s
JOIN players p ON s.player_id = p.id
WHERE p.guild_id = $1
GROUP BY s.day_of_week, s.time
ORDER BY s.day_of_week, s.time;
```

### API 키 Round-Robin 조회 (신규!)
```sql
-- 사용 가능한 API 키 조회
SELECT 
    ak.id,
    ak.api_key_hash,
    ak.nickname,
    rl.remaining_requests,
    rl.reset_at
FROM api_keys ak
LEFT JOIN api_rate_limits rl ON ak.id = rl.api_key_id
WHERE ak.guild_id = $1
  AND ak.is_active = TRUE
  AND (rl.remaining_requests > 0 OR rl.reset_at < NOW())
ORDER BY ak.last_used ASC
LIMIT 1;

-- API 키 사용 후 업데이트
UPDATE api_keys 
SET last_used = NOW(), usage_count = usage_count + 1
WHERE id = $1;

UPDATE api_rate_limits 
SET remaining_requests = remaining_requests - 1,
    updated_at = NOW()
WHERE api_key_id = $1;
```

### 길드 API 키 현황 (신규!)
```sql
SELECT 
    ak.nickname,
    ak.is_active,
    ak.last_used,
    ak.usage_count,
    rl.remaining_requests,
    rl.reset_at
FROM api_keys ak
LEFT JOIN api_rate_limits rl ON ak.id = rl.api_key_id
WHERE ak.guild_id = $1
ORDER BY ak.created_at;
```

---

## 마이그레이션

### Alembic 설정
```bash
# 초기화
alembic init migrations

# 마이그레이션 생성
alembic revision --autogenerate -m "Initial schema"

# 적용
alembic upgrade head

# 롤백
alembic downgrade -1
```

### 마이그레이션 예시 (API 키 추가)
```python
# migrations/versions/xxx_add_api_keys.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('player_id', sa.Integer(), nullable=True),
        sa.Column('guild_id', sa.Integer(), nullable=True),
        sa.Column('api_key_hash', sa.String(255), nullable=False),
        sa.Column('nickname', sa.String(50), nullable=True),
        sa.Column('service', sa.String(50), server_default='lostark'),
        sa.Column('last_used', sa.TIMESTAMP(), nullable=True),
        sa.Column('usage_count', sa.Integer(), server_default='0'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['player_id'], ['players.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['guild_id'], ['guilds.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('guild_id', 'api_key_hash')
    )

def downgrade():
    op.drop_table('api_keys')
```

---

## 백업 & 복구

### 백업
```bash
# MySQL
mysqldump -u username -p loil_db > backup_$(date +%Y%m%d).sql

# PostgreSQL
pg_dump -U username -d loil_db > backup_$(date +%Y%m%d).sql
```

### 복구
```bash
# MySQL
mysql -u username -p loil_db < backup.sql

# PostgreSQL
psql -U username -d loil_db < backup.sql
```

---

## 성능 최적화

### 인덱스 확인
```sql
-- MySQL
SHOW INDEX FROM schedules;

-- PostgreSQL
SELECT * FROM pg_indexes WHERE tablename = 'schedules';
```

### 쿼리 성능 분석
```sql
-- MySQL
EXPLAIN SELECT * FROM schedules WHERE player_id = 1;

-- PostgreSQL
EXPLAIN ANALYZE SELECT * FROM schedules WHERE player_id = 1;
```

### 슬로우 쿼리 로그
```sql
-- MySQL
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1;
```

---

## 참고

- [MySQL 문서](https://dev.mysql.com/doc/)
- [PostgreSQL 문서](https://www.postgresql.org/docs/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)
- [Alembic](https://alembic.sqlalchemy.org/)
