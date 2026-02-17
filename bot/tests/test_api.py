# 봇 없이 API만 테스트!
from utils.lostark_api import get_character_info

# 1. API 호출
result = get_character_info("빛쟁인거니")

# 2. 결과 확인
print(f"캐릭터명: {result['CharacterName']}")
print(f"레벨: {result['ItemMaxLevel']}")
print(f"직업: {result['CharacterClassName']}")

# 3. 성공 여부
if result:
    print("✅ API 테스트 성공!")
else:
    print("❌ API 테스트 실패!")