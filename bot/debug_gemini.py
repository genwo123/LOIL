"""
최소한의 Gemini 테스트
"""

import google.generativeai as genai

# 직접 하드코딩
API_KEY = "AIzaSyA2GVn5z_lezneOM3nDWVcCFL8j5CJ6H48"

print("=" * 50)
print("🔍 Gemini 최소 테스트")
print("=" * 50)

print(f"\nAPI 키: {API_KEY[:30]}...\n")

try:
    # 1. 설정
    genai.configure(api_key=API_KEY)
    print("✅ Step 1: API 키 설정 완료\n")
    
    # 2. 사용 가능한 모델 확인
    print("사용 가능한 모델 확인 중...\n")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"  ✅ {m.name}")
    
    print()
    
    # 3. 모델 생성 시도
    print("모델 생성 시도...\n")
    model = genai.GenerativeModel('gemini-pro')
    print("✅ Step 2: 모델 생성 완료\n")
    
    # 4. 콘텐츠 생성
    print("콘텐츠 생성 시도...\n")
    response = model.generate_content("안녕")
    print(f"✅ Step 3: 응답 받음!\n")
    print(f"응답: {response.text}\n")
    
    print("🎉 모든 단계 성공!")
    
except Exception as e:
    print(f"❌ 에러: {e}")
    print(f"\n에러 타입: {type(e).__name__}")
    
    # 자세한 에러 정보
    import traceback
    print("\n상세 에러:")
    traceback.print_exc()