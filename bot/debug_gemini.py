"""
최소한의 Gemini 테스트
"""

from google import genai
from bot.config.settings import GEMINI_API_KEY, GEMINI_MODEL

print("=" * 50)
print("🔍 Gemini 최소 테스트")
print("=" * 50)

if not GEMINI_API_KEY:
    print("❌ .env에 GEMINI_API_KEY가 설정되지 않았습니다.")
else:
    print(f"\nAPI 키: {GEMINI_API_KEY[:10]}...\n")

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        print("✅ Step 1: 클라이언트 생성 완료\n")

        print(f"모델({GEMINI_MODEL})로 콘텐츠 생성 시도...\n")
        response = client.models.generate_content(model=GEMINI_MODEL, contents="안녕")
        print(f"✅ Step 2: 응답 받음!\n")
        print(f"응답: {response.text}\n")

        print("🎉 모든 단계 성공!")

    except Exception as e:
        print(f"❌ 에러: {e}")
        print(f"\n에러 타입: {type(e).__name__}")

        import traceback
        print("\n상세 에러:")
        traceback.print_exc()