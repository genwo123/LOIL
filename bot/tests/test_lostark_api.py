"""
로스트아크 API 테스트
- API 연결 테스트
- 캐릭터 정보 조회
- 원정대 정보 조회
- Round-robin 키 관리
"""

import requests
from config.settings import LOSTARK_API_KEYS, LOSTARK_API_BASE_URL

# Round-robin을 위한 현재 키 인덱스
current_key_index = 0

def get_next_api_key():
    """Round-robin으로 다음 API 키 가져오기"""
    global current_key_index
    
    if not LOSTARK_API_KEYS:
        print("❌ 로스트아크 API 키가 설정되지 않았습니다!")
        return None
    
    key = LOSTARK_API_KEYS[current_key_index]
    current_key_index = (current_key_index + 1) % len(LOSTARK_API_KEYS)
    
    return key


def test_api_connection():
    """API 연결 테스트"""
    print("=" * 50)
    print("🔗 로스트아크 API 연결 테스트")
    print("=" * 50)
    
    try:
        api_key = get_next_api_key()
        
        if not api_key:
            return False
        
        print(f"📊 등록된 API 키: {len(LOSTARK_API_KEYS)}개")
        print(f"🔑 사용할 키: {api_key[:20]}...\n")
        
        # 간단한 API 호출 테스트
        url = f"{LOSTARK_API_BASE_URL}/news/events"
        headers = {
            'accept': 'application/json',
            'authorization': f'bearer {api_key}'
        }
        
        print("📡 API 호출 중...\n")
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            print(f"✅ API 연결 성공! (상태 코드: {response.status_code})")
            return True
        elif response.status_code == 401:
            print(f"❌ 인증 실패! API 키를 확인하세요. (상태 코드: {response.status_code})")
            return False
        elif response.status_code == 503:
            print(f"⚠️ 서버 점검 중입니다. (상태 코드: {response.status_code})")
            return False
        else:
            print(f"⚠️ 예상치 못한 응답: {response.status_code}")
            return False
        
    except Exception as e:
        print(f"❌ 에러 발생: {e}\n")
        return False


def test_get_character_info(character_name):
    """캐릭터 정보 조회 테스트"""
    print("\n" + "=" * 50)
    print(f"👤 캐릭터 정보 조회: {character_name}")
    print("=" * 50)
    
    try:
        api_key = get_next_api_key()
        
        if not api_key:
            return None
        
        # 캐릭터 프로필 조회
        url = f"{LOSTARK_API_BASE_URL}/armories/characters/{character_name}/profiles"
        headers = {
            'accept': 'application/json',
            'authorization': f'bearer {api_key}'
        }
        
        print(f"📡 API 호출 중...\n")
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            
            print("✅ 캐릭터 정보 조회 성공!\n")
            print("-" * 50)
            print(f"캐릭터명: {data.get('CharacterName', 'N/A')}")
            print(f"서버: {data.get('ServerName', 'N/A')}")
            print(f"직업: {data.get('CharacterClassName', 'N/A')}")
            print(f"아이템 레벨: {data.get('ItemMaxLevel', 'N/A')}")
            print(f"원정대 레벨: {data.get('ExpeditionLevel', 'N/A')}")
            print(f"영지명: {data.get('TownName', 'N/A')}")
            print("-" * 50)
            
            return data
            
        elif response.status_code == 503:
            print("⚠️ 서버 점검 중입니다.")
            return None
        else:
            print(f"❌ 캐릭터를 찾을 수 없습니다. (상태 코드: {response.status_code})")
            return None
        
    except Exception as e:
        print(f"❌ 에러 발생: {e}\n")
        return None


def test_get_siblings(character_name):
    """원정대 정보 조회 테스트"""
    print("\n" + "=" * 50)
    print(f"🎮 원정대 정보 조회: {character_name}")
    print("=" * 50)
    
    try:
        api_key = get_next_api_key()
        
        if not api_key:
            return None
        
        # 원정대 캐릭터 목록 조회
        url = f"{LOSTARK_API_BASE_URL}/characters/{character_name}/siblings"
        headers = {
            'accept': 'application/json',
            'authorization': f'bearer {api_key}'
        }
        
        print(f"📡 API 호출 중...\n")
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            characters = response.json()
            
            if not characters:
                print("⚠️ 원정대 캐릭터 정보가 없습니다.")
                return None
            
            print(f"✅ 원정대 캐릭터 조회 성공! (총 {len(characters)}개)\n")
            print("-" * 50)
            
            for i, char in enumerate(characters, 1):
                char_name = char.get('CharacterName', 'N/A')
                char_class = char.get('CharacterClassName', 'N/A')
                item_level = char.get('ItemMaxLevel', 'N/A')
                server = char.get('ServerName', 'N/A')
                
                print(f"{i}. {char_name} | {char_class} | Lv.{item_level} | {server}")
            
            print("-" * 50)
            
            return characters
            
        elif response.status_code == 503:
            print("⚠️ 서버 점검 중입니다.")
            return None
        else:
            print(f"❌ 원정대 정보를 찾을 수 없습니다. (상태 코드: {response.status_code})")
            return None
        
    except Exception as e:
        print(f"❌ 에러 발생: {e}\n")
        return None


def test_round_robin():
    """Round-robin 키 순환 테스트"""
    print("\n" + "=" * 50)
    print("🔄 Round-robin 키 순환 테스트")
    print("=" * 50)
    
    if not LOSTARK_API_KEYS:
        print("❌ API 키가 설정되지 않았습니다.")
        return False
    
    print(f"📊 등록된 API 키: {len(LOSTARK_API_KEYS)}개\n")
    
    # 키 개수의 2배만큼 호출해서 순환 확인
    test_count = len(LOSTARK_API_KEYS) * 2
    
    print(f"🔄 {test_count}번 호출하여 순환 테스트...\n")
    
    for i in range(test_count):
        key = get_next_api_key()
        key_preview = f"{key[:10]}...{key[-10:]}" if len(key) > 20 else key
        key_index = LOSTARK_API_KEYS.index(key) + 1
        print(f"  호출 {i+1}: 키 #{key_index} - {key_preview}")
    
    print("\n✅ Round-robin 순환 테스트 완료!")
    print(f"💡 {len(LOSTARK_API_KEYS)}개 키를 순환하여 Rate Limit 분산\n")
    
    return True


def test_api_rate_limit():
    """API Rate Limit 확인 (주의: 실제 호출 발생)"""
    print("\n" + "=" * 50)
    print("⚡ API Rate Limit 테스트")
    print("=" * 50)
    
    print("⚠️  이 테스트는 실제 API를 여러 번 호출합니다.")
    print("⚠️  Rate Limit 소진에 주의하세요!\n")
    
    proceed = input("계속 진행하시겠습니까? (y/N): ").strip().lower()
    
    if proceed != 'y':
        print("❌ 테스트 취소됨\n")
        return False
    
    try:
        api_key = get_next_api_key()
        
        if not api_key:
            return False
        
        url = f"{LOSTARK_API_BASE_URL}/news/events"
        headers = {
            'accept': 'application/json',
            'authorization': f'bearer {api_key}'
        }
        
        print(f"\n📡 10번 연속 API 호출 테스트...\n")
        
        success_count = 0
        for i in range(10):
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                success_count += 1
                print(f"  호출 {i+1}: ✅ 성공")
            elif response.status_code == 429:
                print(f"  호출 {i+1}: ⚠️ Rate Limit 도달!")
                break
            else:
                print(f"  호출 {i+1}: ❌ 실패 (코드: {response.status_code})")
        
        print(f"\n📊 결과: {success_count}/10 성공")
        
        if success_count == 10:
            print("✅ Rate Limit 테스트 통과!\n")
        else:
            print("⚠️ Rate Limit에 도달했습니다.\n")
        
        return True
        
    except Exception as e:
        print(f"❌ 에러 발생: {e}\n")
        return False


if __name__ == "__main__":
    print("\n🧪 로스트아크 API 테스트 시작\n")
    
    # 1. API 연결 테스트
    test1 = test_api_connection()
    
    if not test1:
        print("\n⚠️ API 연결 실패 - 점검 중이거나 키가 잘못되었습니다.")
        print("점검 종료 후 다시 시도하거나 API 키를 확인하세요.\n")
    else:
        # 2. Round-robin 테스트
        test2 = test_round_robin()
        
        # 3. 캐릭터 조회 테스트
        print()
        test_character = input("👤 조회할 캐릭터명 입력 (Enter로 건너뛰기): ").strip()
        
        if test_character:
            # 캐릭터 정보 조회
            char_info = test_get_character_info(test_character)
            
            # 원정대 정보 조회
            if char_info:
                siblings = test_get_siblings(test_character)
        
        # 4. Rate Limit 테스트 (선택)
        # test_api_rate_limit()
    
    # 결과 요약
    print("=" * 50)
    print("📊 테스트 완료")
    print("=" * 50)
    
    if test1:
        print("🎉 로스트아크 API 연동 성공!")
        print(f"💡 {len(LOSTARK_API_KEYS)}개 API 키로 Round-robin 사용 가능")
    else:
        print("⚠️ API 테스트 실패 - 설정 확인 필요")
    
    print()