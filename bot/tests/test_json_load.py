"""
JSON 데이터 로드 테스트
- jobs.json
- engravings.json
- synergies.json
- raids.json

settings.py를 통해 중앙 관리되는 JSON 데이터 테스트
"""

from config.settings import (
    JOBS_DATA, 
    ENGRAVINGS_DATA, 
    SYNERGIES_DATA, 
    RAIDS_DATA,
    JOBS_JSON,
    ENGRAVINGS_JSON,
    SYNERGIES_JSON,
    RAIDS_JSON
)

def test_load_json(filename, data):
    """JSON 파일 로드 테스트"""
    
    try:
        print(f"📂 {filename} 확인 중...")
        
        if not data:
            print(f"❌ 데이터가 로드되지 않았습니다: {filename}\n")
            return None
        
        print(f"✅ 로드 성공!")
        print(f"   버전: {data.get('version', 'N/A')}")
        print(f"   업데이트: {data.get('last_updated', 'N/A')}")
        print()
        
        return data
        
    except Exception as e:
        print(f"❌ 에러 발생: {e}\n")
        return None


def test_jobs_data(jobs_data):
    """jobs.json 데이터 검증"""
    print("=" * 50)
    print("🎮 jobs.json 데이터 검증")
    print("=" * 50)
    
    if not jobs_data:
        return False
    
    try:
        classes = jobs_data.get('classes', {})
        print(f"📊 클래스 수: {len(classes)}개\n")
        
        total_jobs = 0
        hybrid_jobs = []
        
        for class_key, class_data in classes.items():
            class_name = class_data.get('name', 'Unknown')
            jobs = class_data.get('jobs', {})
            job_count = len(jobs)
            total_jobs += job_count
            
            print(f"  {class_name}: {job_count}개 직업")
            
            # 하이브리드 직업 찾기
            for job_key, job_data in jobs.items():
                if job_data.get('role') == '하이브리드':
                    hybrid_jobs.append(job_data.get('name'))
        
        print(f"\n총 직업 수: {total_jobs}개")
        print(f"하이브리드 직업: {len(hybrid_jobs)}개")
        print(f"  - {', '.join(hybrid_jobs)}")
        
        print("\n✅ jobs.json 검증 완료!\n")
        return True
        
    except Exception as e:
        print(f"❌ 에러 발생: {e}\n")
        return False


def test_engravings_data(engravings_data):
    """engravings.json 데이터 검증"""
    print("=" * 50)
    print("📜 engravings.json 데이터 검증")
    print("=" * 50)
    
    if not engravings_data:
        return False
    
    try:
        total_engravings = 0
        
        for class_key, class_data in engravings_data.items():
            if class_key in ['version', 'last_updated', 'description', 'notes']:
                continue
            
            class_name = class_data.get('class_name', 'Unknown')
            jobs = class_data.get('jobs', {})
            
            for job_key, job_data in jobs.items():
                job_name = job_data.get('job_name', 'Unknown')
                engravings = job_data.get('engravings', {})
                engraving_count = len(engravings)
                total_engravings += engraving_count
                
                print(f"  {job_name}: {engraving_count}개 각인")
                
                for eng_key, eng_data in engravings.items():
                    eng_name = eng_data.get('name', 'Unknown')
                    notation = eng_data.get('notation', '')
                    print(f"    - {eng_name} ({notation if notation else '표기없음'})")
        
        print(f"\n총 각인 수: {total_engravings}개")
        print("\n✅ engravings.json 검증 완료!\n")
        return True
        
    except Exception as e:
        print(f"❌ 에러 발생: {e}\n")
        return False


def test_synergies_data(synergies_data):
    """synergies.json 데이터 검증"""
    print("=" * 50)
    print("⚡ synergies.json 데이터 검증")
    print("=" * 50)
    
    if not synergies_data:
        return False
    
    try:
        synergy_types = synergies_data.get('synergy_types', {})
        print(f"📊 시너지 타입 수: {len(synergy_types)}개\n")
        
        for synergy_key, synergy_data in synergy_types.items():
            name = synergy_data.get('name', 'Unknown')
            value = synergy_data.get('value', 'N/A')
            providers = synergy_data.get('providers', [])
            
            print(f"  {name} ({value})")
            print(f"    제공 직업: {len(providers)}개")
        
        print("\n✅ synergies.json 검증 완료!\n")
        return True
        
    except Exception as e:
        print(f"❌ 에러 발생: {e}\n")
        return False


def test_raids_data(raids_data):
    """raids.json 데이터 검증"""
    print("=" * 50)
    print("🏆 raids.json 데이터 검증")
    print("=" * 50)
    
    if not raids_data:
        return False
    
    try:
        raid_categories = raids_data.get('raid_categories', {})
        print(f"📊 레이드 카테고리 수: {len(raid_categories)}개\n")
        
        total_raids = 0
        
        for category_key, category_data in raid_categories.items():
            category_name = category_data.get('name', 'Unknown')
            party_size = category_data.get('party_size', 'N/A')
            raids = category_data.get('raids', {})
            raid_count = len(raids)
            total_raids += raid_count
            
            print(f"  {category_name} ({party_size}인)")
            print(f"    레이드: {raid_count}개")
            
            for raid_key, raid_data in raids.items():
                raid_name = raid_data.get('name', 'Unknown')
                difficulties = raid_data.get('difficulties', {})
                print(f"      - {raid_name}: {len(difficulties)}개 난이도")
        
        print(f"\n총 레이드 수: {total_raids}개")
        print("\n✅ raids.json 검증 완료!\n")
        return True
        
    except Exception as e:
        print(f"❌ 에러 발생: {e}\n")
        return False


def test_data_integration():
    """데이터 통합 테스트 - 직업과 각인 매칭"""
    print("=" * 50)
    print("🔗 데이터 통합 테스트")
    print("=" * 50)
    
    try:
        # settings.py에서 이미 로드된 데이터 사용
        print("✅ 데이터 사용 준비 완료 (settings.py에서)\n")
        
        # 워로드 데이터 확인
        print("예시: 워로드 데이터 매칭")
        print("-" * 50)
        
        warlord_job = JOBS_DATA['classes']['warrior']['jobs']['warlord']
        warlord_eng = ENGRAVINGS_DATA['warrior']['jobs']['warlord']
        
        print(f"직업명: {warlord_job['name']}")
        print(f"역할: {warlord_job['role']}")
        print(f"\n각인:")
        
        for eng_key, eng_data in warlord_eng['engravings'].items():
            print(f"  - {eng_data['name']} ({eng_data['abbreviation']})")
            synergies = eng_data.get('synergies', {})
            if synergies:
                print(f"    시너지: {', '.join(synergies.keys())}")
        
        print("-" * 50)
        print("\n✅ 데이터 통합 테스트 성공!\n")
        return True
        
    except Exception as e:
        print(f"❌ 에러 발생: {e}\n")
        return False


if __name__ == "__main__":
    print("\n🧪 JSON 데이터 테스트 시작\n")
    print("💡 settings.py를 통해 중앙 관리되는 데이터 사용\n")
    
    # 개별 파일 확인 (settings.py에서 이미 로드됨)
    jobs_data = test_load_json('jobs.json', JOBS_DATA)
    engravings_data = test_load_json('engravings.json', ENGRAVINGS_DATA)
    synergies_data = test_load_json('synergies.json', SYNERGIES_DATA)
    raids_data = test_load_json('raids.json', RAIDS_DATA)
    
    print()
    
    # 데이터 검증
    test1 = test_jobs_data(jobs_data)
    test2 = test_engravings_data(engravings_data)
    test3 = test_synergies_data(synergies_data)
    test4 = test_raids_data(raids_data)
    
    # 통합 테스트
    test5 = test_data_integration()
    
    # 결과 요약
    print("=" * 50)
    print("📊 테스트 결과 요약")
    print("=" * 50)
    print(f"jobs.json: {'✅' if test1 else '❌'}")
    print(f"engravings.json: {'✅' if test2 else '❌'}")
    print(f"synergies.json: {'✅' if test3 else '❌'}")
    print(f"raids.json: {'✅' if test4 else '❌'}")
    print(f"데이터 통합: {'✅' if test5 else '❌'}")
    
    if all([test1, test2, test3, test4, test5]):
        print("\n🎉 모든 테스트 통과!")
    else:
        print("\n⚠️ 일부 테스트 실패")
    
    print()