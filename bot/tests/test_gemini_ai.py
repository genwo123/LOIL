"""
Gemini AI 테스트
- 기본 응답 테스트
- 파티 편성 추천 테스트
"""

import google.generativeai as genai
from config.settings import GEMINI_API_KEY

def test_gemini_basic():
    """기본 Gemini AI 응답 테스트"""
    print("=" * 50)
    print("📝 Gemini AI 기본 응답 테스트")
    print("=" * 50)
    
    try:
        # API 키 설정
        if not GEMINI_API_KEY:
            print("❌ GEMINI_API_KEY가 설정되지 않았습니다!")
            return False
        
        genai.configure(api_key=GEMINI_API_KEY)
        
        # 모델 생성 (올바른 모델명!)
        model = genai.GenerativeModel('gemini-flash-latest')
        
        # 간단한 질문
        prompt = "안녕하세요! 간단히 인사해주세요."
        print(f"\n질문: {prompt}")
        
        response = model.generate_content(prompt)
        print(f"응답: {response.text}\n")
        
        print("✅ Gemini AI 기본 테스트 성공!\n")
        return True
        
    except Exception as e:
        print(f"❌ 에러 발생: {e}\n")
        return False


def test_gemini_party_recommendation():
    """로스트아크 파티 편성 추천 테스트"""
    print("=" * 50)
    print("🎯 Gemini AI 파티 편성 추천 테스트")
    print("=" * 50)
    
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-flash-latest')
        
        # 파티 편성 프롬프트
        prompt = """
당신은 로스트아크 길드 레이드 매니저입니다.

[길드원 정보]
1. 거니 - 홀나(폿) 1750
2. 하즈 - 소서 1730
3. 자두 - 바드(폿) 1745
4. 유라 - 리퍼 1720
5. 메지션 - 알카 1715
6. 실순 - 블레이드 1725
7. 뒤버 - 디트 1710
8. 츄츄캉 - 배마 1700

[레이드]
에기르 하드 (1680)

[요구사항]
- 8인 파티 편성
- 서폿 1명 이상 필수
- 시너지 고려
- 아이템 레벨 확인

파티 편성을 추천해주세요.
"""
        
        print("프롬프트 전송 중...\n")
        
        response = model.generate_content(prompt)
        
        print("🤖 AI 추천 파티:")
        print("-" * 50)
        print(response.text)
        print("-" * 50)
        
        print("\n✅ 파티 편성 추천 테스트 성공!\n")
        return True
        
    except Exception as e:
        print(f"❌ 에러 발생: {e}\n")
        return False


def test_gemini_with_json_data():
    """JSON 데이터 활용 테스트"""
    print("=" * 50)
    print("📊 JSON 데이터 활용 테스트")
    print("=" * 50)
    
    try:
        from config.settings import SYNERGIES_DATA
        
        print("✅ JSON 데이터 로드 완료 (settings.py에서)\n")
        
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-flash-latest')
        
        # 시너지 설명 요청
        prompt = f"""
로스트아크 시너지 시스템을 간단히 설명해주세요.

사용 가능한 시너지 타입:
{list(SYNERGIES_DATA.get('synergy_types', {}).keys())}

3줄 이내로 설명해주세요.
"""
        
        response = model.generate_content(prompt)
        
        print("🤖 AI 설명:")
        print("-" * 50)
        print(response.text)
        print("-" * 50)
        
        print("\n✅ JSON 데이터 활용 테스트 성공!\n")
        return True
        
    except Exception as e:
        print(f"❌ 에러 발생: {e}\n")
        return False


if __name__ == "__main__":
    print("\n🧪 Gemini AI 테스트 시작\n")
    
    # 테스트 실행
    test1 = test_gemini_basic()
    test2 = test_gemini_party_recommendation()
    test3 = test_gemini_with_json_data()
    
    # 결과 요약
    print("=" * 50)
    print("📊 테스트 결과 요약")
    print("=" * 50)
    print(f"기본 응답 테스트: {'✅' if test1 else '❌'}")
    print(f"파티 편성 테스트: {'✅' if test2 else '❌'}")
    print(f"JSON 데이터 활용: {'✅' if test3 else '❌'}")
    
    if test1 and test2 and test3:
        print("\n🎉 모든 테스트 통과!")
    else:
        print("\n⚠️ 일부 테스트 실패")
    
    print()