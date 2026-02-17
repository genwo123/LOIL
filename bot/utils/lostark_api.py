"""
로스트아크 API 유틸리티
- Round-robin API 키 관리
- 캐릭터 정보 조회
- 원정대 정보 조회
- 캐싱 시스템
"""

import requests
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from bot.config.settings import LOSTARK_API_KEYS, LOSTARK_API_BASE_URL

# ==================== Round-robin API 키 관리 ====================

class APIKeyManager:
    """API 키 Round-robin 관리"""
    
    def __init__(self):
        self.keys = LOSTARK_API_KEYS
        self.current_index = 0
    
    def get_next_key(self) -> str:
        """다음 API 키 반환 (Round-robin)"""
        if not self.keys:
            raise ValueError("로스트아크 API 키가 설정되지 않았습니다!")
        
        key = self.keys[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.keys)
        return key
    
    def get_total_keys(self) -> int:
        """전체 키 개수"""
        return len(self.keys)


# 전역 키 매니저
key_manager = APIKeyManager()


# ==================== 캐싱 시스템 ====================

class SimpleCache:
    """간단한 메모리 캐시 (5분)"""
    
    def __init__(self, ttl_minutes: int = 5):
        self.cache: Dict[str, tuple] = {}  # {key: (data, expire_time)}
        self.ttl = timedelta(minutes=ttl_minutes)
    
    def get(self, key: str) -> Optional[dict]:
        """캐시에서 데이터 가져오기"""
        if key in self.cache:
            data, expire_time = self.cache[key]
            if datetime.now() < expire_time:
                return data
            else:
                del self.cache[key]  # 만료된 캐시 삭제
        return None
    
    def set(self, key: str, data: dict):
        """캐시에 데이터 저장"""
        expire_time = datetime.now() + self.ttl
        self.cache[key] = (data, expire_time)
    
    def clear(self):
        """캐시 전체 삭제"""
        self.cache.clear()


# 전역 캐시
cache = SimpleCache(ttl_minutes=5)


# ==================== API 호출 ====================

def _make_request(endpoint: str, use_cache: bool = True) -> Optional[dict]:
    """
    API 요청 (내부 함수)
    
    Args:
        endpoint: API 엔드포인트 (예: /armories/characters/빛쟁인거니/profiles)
        use_cache: 캐시 사용 여부
    
    Returns:
        API 응답 데이터 또는 None
    """
    # 캐시 확인
    if use_cache:
        cached_data = cache.get(endpoint)
        if cached_data:
            return cached_data
    
    # API 호출
    url = f"{LOSTARK_API_BASE_URL}{endpoint}"
    api_key = key_manager.get_next_key()
    
    headers = {
        'accept': 'application/json',
        'authorization': f'bearer {api_key}'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # 캐시 저장
            if use_cache:
                cache.set(endpoint, data)
            return data
        
        elif response.status_code == 503:
            print(f"⚠️ 로스트아크 API 점검 중")
            return None
        
        elif response.status_code == 429:
            print(f"⚠️ Rate Limit 도달 - API 키: {api_key[:20]}...")
            return None
        
        else:
            print(f"⚠️ API 에러 {response.status_code}: {endpoint}")
            return None
    
    except requests.exceptions.Timeout:
        print(f"⚠️ API 타임아웃: {endpoint}")
        return None
    
    except Exception as e:
        print(f"❌ API 호출 에러: {e}")
        return None


# ==================== 캐릭터 정보 ====================

def get_character_info(character_name: str, use_cache: bool = True) -> Optional[dict]:
    """
    캐릭터 정보 조회
    
    Args:
        character_name: 캐릭터명
        use_cache: 캐시 사용 여부
    
    Returns:
        캐릭터 정보 딕셔너리 또는 None
        {
            'CharacterName': str,
            'ServerName': str,
            'CharacterClassName': str,
            'ItemAvgLevel': str,  # 평균 아이템 레벨
            'ExpeditionLevel': int,
            'TownName': str,
            ...
        }
    
    Example:
        >>> info = get_character_info("빛쟁인거니")
        >>> print(info['CharacterClassName'])
        홀리나이트
    """
    endpoint = f"/armories/characters/{character_name}/profiles"
    return _make_request(endpoint, use_cache)


def get_siblings(character_name: str, use_cache: bool = True) -> Optional[List[dict]]:
    """
    원정대 캐릭터 목록 조회
    
    Args:
        character_name: 캐릭터명
        use_cache: 캐시 사용 여부
    
    Returns:
        원정대 캐릭터 리스트 또는 None
        [
            {
                'CharacterName': str,
                'CharacterClassName': str,
                'ItemMaxLevel': str,
                'ServerName': str,
                ...
            },
            ...
        ]
    
    Example:
        >>> siblings = get_siblings("빛쟁인거니")
        >>> for char in siblings:
        ...     print(f"{char['CharacterName']} - {char['CharacterClassName']}")
    """
    endpoint = f"/characters/{character_name}/siblings"
    return _make_request(endpoint, use_cache)


def get_character_equipment(character_name: str, use_cache: bool = True) -> Optional[dict]:
    """
    캐릭터 장비 정보 조회
    
    Args:
        character_name: 캐릭터명
        use_cache: 캐시 사용 여부
    
    Returns:
        장비 정보 딕셔너리 또는 None
    """
    endpoint = f"/armories/characters/{character_name}/equipment"
    return _make_request(endpoint, use_cache)


def get_character_engravings(character_name: str, use_cache: bool = True) -> Optional[dict]:
    """
    캐릭터 각인 정보 조회
    
    Args:
        character_name: 캐릭터명
        use_cache: 캐시 사용 여부
    
    Returns:
        각인 정보 딕셔너리 또는 None
    """
    endpoint = f"/armories/characters/{character_name}/engravings"
    return _make_request(endpoint, use_cache)


# ==================== 유틸리티 함수 ====================

def get_character_item_level(character_name: str) -> Optional[float]:
    """
    캐릭터 아이템 레벨만 빠르게 조회
    
    Args:
        character_name: 캐릭터명
    
    Returns:
        아이템 레벨 (float) 또는 None
    
    Example:
        >>> level = get_character_item_level("빛쟁인거니")
        >>> print(level)
        1763.33
    """
    info = get_character_info(character_name)
    if info and 'ItemAvgLevel' in info:
        try:
            # "1,763.33" → 1763.33
            level_str = info['ItemAvgLevel'].replace(',', '')
            return float(level_str)
        except (ValueError, AttributeError):
            return None
    return None


def get_account_characters(character_name: str, min_level: float = 0) -> List[dict]:
    """
    원정대에서 특정 레벨 이상 캐릭터만 필터링
    
    Args:
        character_name: 캐릭터명
        min_level: 최소 아이템 레벨
    
    Returns:
        필터링된 캐릭터 리스트
    
    Example:
        >>> chars = get_account_characters("빛쟁인거니", min_level=1680)
        >>> for char in chars:
        ...     print(f"{char['CharacterName']}: {char['ItemAvgLevel']}")
    """
    siblings = get_siblings(character_name)
    if not siblings:
        return []
    
    filtered = []
    for char in siblings:
        try:
            level_str = char.get('ItemAvgLevel', '0').replace(',', '')
            level = float(level_str) if level_str else 0
            
            if level >= min_level:
                filtered.append(char)
        except (ValueError, AttributeError):
            continue
    
    return filtered


def clear_cache():
    """캐시 전체 삭제"""
    cache.clear()


def get_api_stats() -> dict:
    """
    API 사용 통계
    
    Returns:
        {
            'total_keys': int,
            'current_key_index': int,
            'cache_size': int
        }
    """
    return {
        'total_keys': key_manager.get_total_keys(),
        'current_key_index': key_manager.current_index,
        'cache_size': len(cache.cache)
    }


# ==================== 테스트 코드 ====================

if __name__ == "__main__":
    # 간단한 테스트
    print("=" * 50)
    print("🧪 로스트아크 API 유틸리티 테스트")
    print("=" * 50)
    
    # API 통계
    stats = get_api_stats()
    print(f"\n📊 API 통계:")
    print(f"  - 전체 키: {stats['total_keys']}개")
    print(f"  - 현재 인덱스: {stats['current_key_index']}")
    print(f"  - 캐시 크기: {stats['cache_size']}\n")
    
    # 캐릭터 조회 테스트
    test_name = input("테스트할 캐릭터명 (Enter로 건너뛰기): ").strip()
    
    if test_name:
        print(f"\n🔍 '{test_name}' 조회 중...\n")
        
        # 캐릭터 정보
        info = get_character_info(test_name)
        if info:
            print(f"✅ 캐릭터 정보:")
            print(f"  - 이름: {info.get('CharacterName')}")
            print(f"  - 직업: {info.get('CharacterClassName')}")
            print(f"  - 레벨: {info.get('ItemAvgLevel')}")
            print(f"  - 서버: {info.get('ServerName')}\n")
        
        # 원정대 정보
        siblings = get_siblings(test_name)
        if siblings:
            print(f"✅ 원정대 캐릭터: {len(siblings)}개\n")
            for char in siblings[:5]:  # 처음 5개만
                print(f"  - {char['CharacterName']} ({char['CharacterClassName']}) - {char.get('ItemAvgLevel', 'N/A')}")
    
    print("\n✅ 테스트 완료!\n")