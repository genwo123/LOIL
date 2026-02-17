"""
Gemini AI 유틸리티
- 파티 편성 추천
- 시너지 분석
- 레이드 정보 안내
"""

import google.generativeai as genai
from typing import List, Dict, Optional
from bot.config.settings import (
    GEMINI_API_KEY,
    JOBS_DATA,
    SYNERGIES_DATA,
    RAIDS_DATA
)

# ==================== 초기화 ====================

def _get_model():
    """Gemini 모델 생성"""
    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel('gemini-flash-latest')


# ==================== 파티 편성 추천 ====================

def recommend_party(members: List[Dict], raid_name: str) -> str:
    """
    AI 파티 편성 추천
    
    Args:
        members: 참여 멤버 리스트
            [
                {
                    'name': str,       # 길드원 닉네임
                    'character': str,  # 캐릭터명
                    'job': str,        # 직업
                    'level': float,    # 아이템 레벨
                    'is_support': bool # 서폿 여부
                },
                ...
            ]
        raid_name: 레이드 이름 (예: "에기르 하드")
    
    Returns:
        AI 추천 결과 문자열
    
    Example:
        >>> members = [
        ...     {'name': '거니', 'job': '홀리나이트', 'level': 1750, 'is_support': True},
        ...     {'name': '하즈', 'job': '소서리스', 'level': 1730, 'is_support': False},
        ... ]
        >>> result = recommend_party(members, "에기르 하드")
        >>> print(result)
    """
    if not GEMINI_API_KEY:
        return "❌ Gemini API 키가 설정되지 않았습니다."
    
    try:
        model = _get_model()
        
        # 멤버 정보 문자열 생성
        member_list = ""
        for i, m in enumerate(members, 1):
            support_tag = "(폿)" if m.get('is_support') else ""
            member_list += f"{i}. {m['name']} - {m['job']}{support_tag} {m.get('level', 'N/A')}\n"
        
        # 레이드 정보 가져오기
        raid_info = ""
        if RAIDS_DATA:
            for category in RAIDS_DATA.get('raids', {}).values():
                for raid in category if isinstance(category, list) else []:
                    if raid_name.replace(" ", "") in raid.get('name', '').replace(" ", ""):
                        raid_info = f"""
레이드 요구사항:
- 최소 레벨: {raid.get('min_level', 'N/A')}
- 인원: {raid.get('max_players', 8)}인
- 서폿 권장: {raid.get('support_required', 1)}명 이상
"""
                        break
        
        prompt = f"""당신은 로스트아크 길드 레이드 매니저입니다.
아래 길드원들의 파티 편성을 추천해주세요.

[레이드]
{raid_name}
{raid_info}

[참여 길드원]
{member_list}

[요구사항]
- 서폿 1명 이상 필수
- 시너지 최적화
- 아이템 레벨 확인
- 최적 조합 추천

파티 편성과 이유를 간략하게 알려주세요.
"""
        
        response = model.generate_content(prompt)
        return response.text
    
    except Exception as e:
        return f"❌ AI 추천 실패: {e}"


# ==================== 시너지 분석 ====================

def analyze_synergy(jobs: List[str]) -> str:
    """
    파티 구성의 시너지 분석
    
    Args:
        jobs: 직업 리스트 (예: ["홀리나이트", "소서리스", "리퍼"])
    
    Returns:
        시너지 분석 결과 문자열
    
    Example:
        >>> result = analyze_synergy(["홀리나이트", "소서리스", "리퍼", "블레이드"])
        >>> print(result)
    """
    if not GEMINI_API_KEY:
        return "❌ Gemini API 키가 설정되지 않았습니다."
    
    try:
        model = _get_model()
        
        # 시너지 데이터 준비
        synergy_info = ""
        if SYNERGIES_DATA:
            synergy_info = f"참고 시너지 타입: {list(SYNERGIES_DATA.get('synergy_types', {}).keys())}"
        
        job_list = "\n".join([f"- {job}" for job in jobs])
        
        prompt = f"""로스트아크 파티 시너지를 분석해주세요.

[파티 구성]
{job_list}

{synergy_info}

다음을 간략히 알려주세요:
1. 시너지 점수 (상/중/하)
2. 강점
3. 보완 필요한 점
"""
        
        response = model.generate_content(prompt)
        return response.text
    
    except Exception as e:
        return f"❌ 시너지 분석 실패: {e}"


# ==================== 레이드 정보 안내 ====================

def get_raid_guide(raid_name: str) -> str:
    """
    레이드 공략 정보 안내
    
    Args:
        raid_name: 레이드 이름
    
    Returns:
        레이드 안내 문자열
    
    Example:
        >>> result = get_raid_guide("에기르")
        >>> print(result)
    """
    if not GEMINI_API_KEY:
        return "❌ Gemini API 키가 설정되지 않았습니다."
    
    try:
        model = _get_model()
        
        prompt = f"""로스트아크 {raid_name} 레이드에 대해 간략히 알려주세요.

다음 내용을 3~5줄로 요약해주세요:
1. 레이드 특징
2. 주의사항
3. 추천 파티 구성
"""
        
        response = model.generate_content(prompt)
        return response.text
    
    except Exception as e:
        return f"❌ 레이드 정보 조회 실패: {e}"


# ==================== 간단 질문 ====================

def ask_ai(question: str) -> str:
    """
    로스트아크 관련 질문에 답변
    
    Args:
        question: 질문 내용
    
    Returns:
        AI 답변 문자열
    
    Example:
        >>> result = ask_ai("홀리나이트 서폿 각인 추천해줘")
        >>> print(result)
    """
    if not GEMINI_API_KEY:
        return "❌ Gemini API 키가 설정되지 않았습니다."
    
    try:
        model = _get_model()
        
        prompt = f"""당신은 로스트아크 전문가입니다.
아래 질문에 간략하게 답변해주세요.

질문: {question}
"""
        
        response = model.generate_content(prompt)
        return response.text
    
    except Exception as e:
        return f"❌ AI 응답 실패: {e}"


# ==================== 테스트 코드 ====================

if __name__ == "__main__":
    print("=" * 50)
    print("🧪 Gemini AI 유틸리티 테스트")
    print("=" * 50)
    
    # 1. 파티 편성 추천 테스트
    print("\n🎯 파티 편성 추천 테스트")
    print("-" * 50)
    
    test_members = [
        {'name': '거니',   'job': '홀리나이트', 'level': 1763, 'is_support': True},
        {'name': '자두',   'job': '바드',       'level': 1745, 'is_support': True},
        {'name': '하즈',   'job': '소서리스',   'level': 1730, 'is_support': False},
        {'name': '유라',   'job': '리퍼',       'level': 1720, 'is_support': False},
        {'name': '메지션', 'job': '아르카나',   'level': 1715, 'is_support': False},
        {'name': '실순',   'job': '블레이드',   'level': 1725, 'is_support': False},
        {'name': '뒤버',   'job': '디스트로이어','level': 1710, 'is_support': False},
        {'name': '츄츄캉', 'job': '배틀마스터', 'level': 1700, 'is_support': False},
    ]
    
    result = recommend_party(test_members, "에기르 하드")
    print(result)
    
    # 2. 시너지 분석 테스트
    print("\n⚡ 시너지 분석 테스트")
    print("-" * 50)
    
    test_jobs = ["홀리나이트", "소서리스", "리퍼", "블레이드", "아르카나", "디스트로이어", "배틀마스터", "바드"]
    result = analyze_synergy(test_jobs)
    print(result)
    
    print("\n✅ 테스트 완료!\n")