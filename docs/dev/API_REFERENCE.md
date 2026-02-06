## 파일 6: docs/dev/API_REFERENCE.md

```markdown
# 📚 API Reference

## 디스코드 명령어

### 조회 명령어

#### /오늘레이드
오늘 예정된 레이드 일정을 조회합니다.

**사용법:**
```
/오늘레이드
```

**출력 예시:**
```
📅 오늘(화요일) 레이드 일정

20:00 | 종막 하드1 (8인) - ✅ 완성
21:00 | 세르카 나메1 (4인) - ⚠️ 공방 1딜 필요
22:00 | 4막 하드2 (8인) - ✅ 완성
```

**권한:** 모든 사용자  
**제한:** 없음

---

#### /이번주레이드
이번 주 전체 레이드 일정을 조회합니다.

**사용법:**
```
/이번주레이드
```

**출력 예시:**
```
📅 이번 주 레이드 일정

월요일:
  20:00 종막 하드1 (8명)
  21:00 세르카 나메1 (4명)

화요일:
  20:00 4막 하드1 (8명)
...
```

**권한:** 모든 사용자  
**제한:** 없음

---

#### /빛쟁 [닉네임] 레이드
특정 멤버의 개인 일정을 조회합니다.

**사용법:**
```
/빛쟁 거니 레이드
```

**파라미터:**
- `닉네임` (필수): 조회할 길드원의 닉네임

**출력 예시:**
```
━━━━━━━━━━━━━━
🔍 거니님 이번 주 일정
━━━━━━━━━━━━━━

월 20:00 | 종막 하드1 (홀나)
화 21:00 | 세르카 나메1 (홀나)
수 20:00 | 카멘 하드2 (홀나)
목 휴식
금 20:00 | 종막 노말1 (홀나)

💚 이번 주 총 4회 레이드
━━━━━━━━━━━━━━
```

**권한:** 모든 사용자  
**제한:** 없음

---

#### /내레이드
본인의 이번 주 일정을 조회합니다.

**사용법:**
```
/내레이드
```

**권한:** 모든 사용자  
**제한:** 없음

---

#### /통계
길드 전체 통계를 조회합니다.

**사용법:**
```
/통계
/통계 이번달
```

**파라미터:**
- `기간` (선택): 이번달, 지난달 등

**출력 예시:**
```
━━━━━━━━━━━━━━
📊 12월 길드 통계
━━━━━━━━━━━━━━

📅 총 레이드: 48회
👥 평균 참여: 7.2명
💰 총 골드: 약 6,500만

⏰ 인기 시간대
1위: 월 20:00 (평균 8명)
2위: 화 21:00 (평균 7명)

🏆 인기 레이드
1위: 종막 하드 (15회)
2위: 세르카 나메 (12회)
━━━━━━━━━━━━━━
```

**권한:** 모든 사용자  
**제한:** 없음

---

#### /내통계
개인 통계를 조회합니다.

**사용법:**
```
/내통계
```

**권한:** 모든 사용자  
**제한:** 없음

---

### 캐릭터 관리

#### /원정대등록 [캐릭터명]
로스트아크 API를 통해 계정의 모든 캐릭터를 자동으로 등록합니다.

**사용법:**
```
/원정대등록 빛쟁인거니
```

**파라미터:**
- `캐릭터명` (필수): 계정 내 아무 캐릭터 이름

**출력 예시:**
```
✅ 캐릭터 정보 조회 완료!

📋 계정의 모든 캐릭터 (8개)
━━━━━━━━━━━━━━

빛쟁인거니 | 홀나 | Lv.1750 💚 서폿
뚜띠될거니 | 워로드 | Lv.1720 ⚔️ 딜러
뒷차기인거니 | 스트라이커 | Lv.1710 ⚔️ 딜러
...

━━━━━━━━━━━━━━
📌 이 캐릭터들을 등록하시겠어요? (예/아니오)
```

**권한:** 모든 사용자  
**제한:** 없음  
**API 호출:** 로스트아크 API

---

#### /내캐릭터
등록된 캐릭터 목록을 조회합니다.

**사용법:**
```
/내캐릭터
```

**출력 예시:**
```
━━━━━━━━━━━━━━
🎮 거니님의 캐릭터
━━━━━━━━━━━━━━

✅ 빛쟁인거니
   💚 홀나 | Lv.1750
   📅 이번 주: 종막하드, 세르카나메, 4막하드

✅ 뚜띠될거니
   ⚔️ 워로드 | Lv.1720
   📅 이번 주: 종막노말, 세르카노말, 카멘노말

💤 뒷차기인거니
   ⚔️ 스트라이커 | Lv.1710
   📅 이번 주: 숙제 제외 (트라이 준비)

━━━━━━━━━━━━━━
```

**권한:** 모든 사용자  
**제한:** 없음

---

#### /레이드설정 [캐릭터명] [레이드1] [레이드2] [레이드3]
캐릭터별 주간 레이드를 설정합니다 (최대 3개).

**사용법:**
```
/레이드설정 뚜띠될거니 4막노말 종막노말 세르카노말
```

**파라미터:**
- `캐릭터명` (필수)
- `레이드1` (필수)
- `레이드2` (선택)
- `레이드3` (선택)

**출력 예시:**
```
✅ 뚜띠될거니의 레이드 설정 완료!

━━━━━━━━━━━━━━
1. 4막 노말
2. 종막 노말
3. 세르카 노말
━━━━━━━━━━━━━━
```

**규칙:**
- 최대 3개 레이드 (골드 획득 제한)
- 같은 레이드는 하나만 (노말 또는 하드)

**권한:** 모든 사용자  
**제한:** 없음

---

#### /캐릭터상태 [캐릭터명] [상태]
캐릭터 상태를 변경합니다.

**사용법:**
```
/캐릭터상태 뒷차기인거니 숙제제외
/캐릭터상태 뒷차기인거니 활성
/캐릭터상태 뒷차기인거니 휴식
```

**파라미터:**
- `캐릭터명` (필수)
- `상태` (필수): 활성, 숙제제외, 휴식

**상태 종류:**
- `활성`: 일반적으로 레이드 참여
- `숙제제외`: 이번 주만 제외 (트라이 등)
- `휴식`: 장기간 쉬는 중

**권한:** 모든 사용자  
**제한:** 없음

---

### AI 명령어

#### /추천생성 ⭐
AI가 주간 전체 일정을 자동으로 생성합니다.

**사용법:**
```
/추천생성
```

**출력 예시:**
```
🤖 AI 추천 일정 생성 중...

✅ 생성 완료!

━━━━━━━━━━━━━━
📅 월요일 20:00 | 종막 하드1 (8인)
━━━━━━━━━━━━━━

【 1파티 】
  ⚔️ 하즈(소서), 김실순(블레), 유라이니(리퍼)
  💚 자두(바드)

【 2파티 】
  ⚔️ 츄츄캉(디트), 뒤버(디트), 퓨체링(아르카나)
  💚 거니(홀나)

✅ 파티 완성 (8/8)
━━━━━━━━━━━━━━

💡 시너지 최적화됨
💡 서폿 균등 배치
```

**권한:** 모든 사용자  
**제한:**
- 무료: 주 3회
- 프리미엄: 무제한

**API 호출:** Gemini API

---

#### /추천 [요일]
특정 요일만 AI 추천을 받습니다.

**사용법:**
```
/추천 월요일
/추천 화
```

**파라미터:**
- `요일` (필수): 월요일, 화, 수, 목, 금, 토, 일

**권한:** 모든 사용자  
**제한:**
- 무료: 주 3회
- 프리미엄: 무제한

---

#### /일정추천 [닉네임]
개인 맞춤 일정을 AI가 추천합니다.

**사용법:**
```
/일정추천 거니
```

**파라미터:**
- `닉네임` (필수)

**권한:** 모든 사용자  
**제한:** 무료도 사용 가능

---

#### /통계 AI분석 💎
AI가 통계를 분석하고 인사이트를 제공합니다.

**사용법:**
```
/통계 AI분석
```

**출력 예시:**
```
🤖 AI 분석 결과

"12월 활동이 11월보다 15% 증가했어요!
월요일 20시가 가장 인기 있고,
종막 하드 클리어 타임이 6분 단축됐네요.

💡 개선 제안:
- 화요일 인원이 부족하니 시간 조정 추천드려요
- 세르카 나메 파티에 시너지 중복이 있어요
- 서폿 배치를 더 균등하게 하면 좋을 것 같아요"
```

**권한:** 프리미엄 사용자 전용  
**제한:** 프리미엄 구독 필요

---

### 알림 설정

#### /알림설정 [방식] [시간들]
알림 방식과 시간을 설정합니다.

**사용법:**
```
/알림설정 DM 30 15 5
/알림설정 태그 30
/알림설정 둘다 30 15
/알림설정 끄기
```

**파라미터:**
- `방식` (필수): DM, 디엠, 태그, 멘션, 둘다, 끄기
- `시간들` (선택): 분 단위 (예: 30 = 30분 전)

**방식:**
- `DM` 또는 `디엠`: 개인 DM 알림
- `태그` 또는 `멘션`: 채널에서 @태그
- `둘다`: 채널 + DM
- `끄기`: 알림 끄기

**출력 예시:**
```
✅ 알림 설정 완료!

방식: 개인 DM
시간: 30분, 15분, 5분 전
```

**권한:** 모든 사용자  
**제한:** 없음

---

#### /내알림
현재 알림 설정을 확인합니다.

**사용법:**
```
/내알림
```

**권한:** 모든 사용자  
**제한:** 없음

---

### 시스템 관리

#### /설정
초기 설정을 시작합니다.

**사용법:**
```
/설정
```

**권한:** 관리자 전용  
**제한:** 서버 관리자

---

#### /시트연동 [URL]
구글 시트를 연동합니다.

**사용법:**
```
/시트연동 https://docs.google.com/spreadsheets/d/...
```

**파라미터:**
- `URL` (필수): 구글 스프레드시트 공유 링크

**권한:** 관리자 전용  
**제한:** 서버 관리자  
**API 호출:** Google Sheets API

---

#### /동기화
구글 시트와 수동으로 동기화합니다.

**사용법:**
```
/동기화
```

**출력 예시:**
```
🔄 데이터를 동기화하는 중...

✅ 동기화 완료!
(마지막 동기화: 2026-02-06 15:30)
```

**권한:** 모든 사용자  
**제한:** 1분에 1회  
**API 호출:** Google Sheets API

---

### 프리미엄 전용 명령어

#### /카톡봇코드 💎
카카오톡 봇 연동 코드를 발급받습니다.

**사용법:**
```
/카톡봇코드
```

**출력 예시:**
```
✅ 카톡봇 연동 코드 발급!

━━━━━━━━━━━━━━
코드: ABC-123-XYZ
━━━━━━━━━━━━━━

📱 사용 방법:
1. 카카오톡에서 '로일봇' 검색
2. 친구 추가
3. 코드 입력
4. 길드 카톡방에 초대

💡 이 코드로 길드 전체가 카톡 알림을 받을 수 있어요!
```

**권한:** 프리미엄 사용자 전용  
**제한:** 프리미엄 구독 필요

---

#### /빠른일정 💎
일정을 빠르게 설정합니다.

**사용법:**
```
/빠른일정
```

**권한:** 프리미엄 사용자 전용  
**제한:** 프리미엄 구독 필요

---

#### /일정복사 💎
지난주 일정을 복사합니다.

**사용법:**
```
/일정복사
```

**권한:** 프리미엄 사용자 전용  
**제한:** 프리미엄 구독 필요

---

#### /템플릿저장 [이름] 💎
현재 일정을 템플릿으로 저장합니다.

**사용법:**
```
/템플릿저장 평소주간
```

**파라미터:**
- `이름` (필수): 템플릿 이름

**권한:** 프리미엄 사용자 전용  
**제한:** 프리미엄 구독 필요

---

#### /템플릿불러오기 [이름] 💎
저장된 템플릿을 불러옵니다.

**사용법:**
```
/템플릿불러오기 평소주간
```

**파라미터:**
- `이름` (필수): 템플릿 이름

**권한:** 프리미엄 사용자 전용  
**제한:** 프리미엄 구독 필요

---

### 도움말

#### /도움말
전체 명령어 목록을 봅니다.

**사용법:**
```
/도움말
/도움말 [명령어]
```

**파라미터:**
- `명령어` (선택): 특정 명령어 상세 설명

---

#### /문의 [내용]
지원팀에 문의합니다.

**사용법:**
```
/문의 봇이 응답하지 않아요
```

**파라미터:**
- `내용` (필수): 문의 내용

---

## 외부 API

### 로스트아크 API

#### 캐릭터 정보 조회
```python
import requests

API_KEY = "your_lostark_api_key"
headers = {
    "accept": "application/json",
    "authorization": f"bearer {API_KEY}"
}

url = "https://developer-lostark.game.onstove.com/armories/characters/{character_name}/profiles"
response = requests.get(url, headers=headers)

data = response.json()
print(data["CharacterName"])  # 캐릭터명
print(data["ItemMaxLevel"])   # 아이템 레벨
print(data["CharacterClassName"])  # 직업
```

#### 원정대 조회
```python
url = "https://developer-lostark.game.onstove.com/characters/{character_name}/siblings"
response = requests.get(url, headers=headers)

characters = response.json()
for char in characters:
    print(char["CharacterName"], char["ItemMaxLevel"])
```

---

### Google Sheets API

#### 시트 읽기
```python
import gspread
from oauth2client.service_account import ServiceAccountCredentials

scope = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]

creds = ServiceAccountCredentials.from_json_keyfile_name(
    'service-account-key.json', scope
)

client = gspread.authorize(creds)
spreadsheet = client.open_by_url('YOUR_SHEET_URL')

# 특정 시트 선택
sheet = spreadsheet.worksheet('거니')

# 데이터 읽기
data = sheet.get_all_records()
print(data)
```

---

### Gemini API (AI)

#### 파티 편성 추천
```python
import google.generativeai as genai

genai.configure(api_key="YOUR_GEMINI_KEY")
model = genai.GenerativeModel('gemini-2.0-flash-exp')

prompt = """
당신은 로스트아크 길드 레이드 매니저입니다.

[길드원 정보]
- 거니: 홀나 1750 (서폿)
- 자두: 바드 1745 (서폿)
- 하즈: 소서 1730 (딜러)
...

[가능 시간대]
월요일 20:00 - 8명 가능
화요일 21:00 - 6명 가능
...

8인 레이드 파티 편성을 추천해주세요.
규칙: 6딜 2폿
"""

response = model.generate_content(prompt)
print(response.text)
```

---

### API 키 관리 시스템 (Round-Robin)

#### API 키 매니저
```python
# bot/integrations/api_key_manager.py
from typing import List
import time

class ApiKeyManager:
    def __init__(self, keys: List[str]):
        self.keys = keys
        self.current_index = 0
        self.limits = {}  # {key: {"remaining": 60, "reset_at": timestamp}}
    
    def get_next_key(self) -> str:
        """Round-Robin 방식으로 다음 키 반환"""
        attempts = 0
        while attempts < len(self.keys):
            key = self.keys[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.keys)
            
            if self._can_use_key(key):
                self._use_key(key)
                return key
            
            attempts += 1
        
        raise Exception("모든 API 키가 Rate Limit에 도달했습니다")
    
    def _can_use_key(self, key: str) -> bool:
        """키 사용 가능 여부 확인"""
        if key not in self.limits:
            return True
        
        limit = self.limits[key]
        if limit["remaining"] <= 0:
            if time.time() >= limit["reset_at"]:
                # 리셋
                limit["remaining"] = 60
                limit["reset_at"] = time.time() + 60
                return True
            return False
        
        return True
    
    def _use_key(self, key: str):
        """키 사용 기록"""
        if key not in self.limits:
            self.limits[key] = {"remaining": 60, "reset_at": time.time() + 60}
        
        self.limits[key]["remaining"] -= 1

# 사용 예시
manager = ApiKeyManager([
    "key1_from_db",
    "key2_from_db",
    "key3_from_db"
])

# 요청 시
api_key = manager.get_next_key()
response = requests.get(url, headers={"authorization": f"bearer {api_key}"})
```

---

## 에러 코드

| 코드 | 의미 | 해결 방법 |
|------|------|----------|
| 1001 | API 키 없음 | .env 파일 확인 |
| 1002 | 시트 권한 없음 | 시트 공유 설정 확인 |
| 1003 | 캐릭터 없음 | 캐릭터명 확인 |
| 1004 | 프리미엄 필요 | 구독 필요 |
| 2001 | AI 쿼터 초과 | 백업 AI 사용 또는 프리미엄 구독 |
| 2002 | 모든 API 키 Rate Limit | 잠시 후 재시도 |
| 3001 | DB 연결 실패 | DB 상태 확인 |

---

## Rate Limit

| API | 무료 제한 | 해결 방법 |
|-----|----------|----------|
| 로스트아크 API | 100 req/min (키당) | API 키 3-5개 사용 |
| Gemini API | 15 req/min (무료) | 무료: 주 3회 제한, 프리미엄: Groq 백업 |
| Google Sheets API | 100 req/100초 | 캐싱 사용 |

---

## 참고 자료

- [discord.py 문서](https://discordpy.readthedocs.io/)
- [로스트아크 API](https://developer-lostark.game.onstove.com/)
- [Gemini API](https://ai.google.dev/docs)
- [Google Sheets API](https://developers.google.com/sheets/api)
- [Groq API](https://console.groq.com/docs)
```

---

# ✅ 3차 완료!

**저장 위치:**
- `[docs/dev] CHANGELOG.md`
- `[docs/dev] API_REFERENCE.md`

**다음 (4차):**
- DATABASE_SCHEMA.md
- MONETIZATION.md

**"4차 시작"** 입력하시면 계속 드릴게요! 🚀
