"""
로일(LoIl) - Gemini AI 유틸
dps_types, synergy_benefits 데이터를 프롬프트에 주입해
정확한 파티 편성 추천 제공
"""

import json
from pathlib import Path
from typing import List
from google import genai

from bot.config.settings import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    DPS_TYPES_DATA,
    SYNERGY_BENEFITS_DATA,
    SYNERGIES_DATA,
)

# ==================== 초기화 ====================

SETTINGS_FILE = Path("bot/data/guild_settings.json")

def _get_guild_api_key(guild_id: int) -> str:
    """길드가 /설정에서 등록한 Gemini API 키. 없으면 빈 문자열."""
    if not guild_id:
        return ""
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(str(guild_id), {}).get("gemini_api_key", "")
    except Exception:
        return ""

def _resolve_api_key(guild_id: int = 0) -> str:
    """길드 전용 키 우선, 없으면 .env의 전역 키."""
    return _get_guild_api_key(guild_id) or GEMINI_API_KEY

def _get_client(guild_id: int = 0) -> genai.Client:
    return genai.Client(api_key=_resolve_api_key(guild_id))


# ==================== 컨텍스트 빌더 ====================

def _build_dps_context() -> str:
    """dps_types.json 핵심 요약 (프롬프트 길이 최적화)"""
    if not DPS_TYPES_DATA:
        return ""

    lines = ["[딜러 유형 분류]"]
    jobs = DPS_TYPES_DATA.get("jobs", {})

    for job_name, job_data in jobs.items():
        engravings = job_data.get("engravings", {})
        for eng_name, eng_data in engravings.items():
            dps_type  = eng_data.get("dps_type", "")
            stat_base = eng_data.get("stat_base", "")
            abbrev    = eng_data.get("abbrev", "")
            if dps_type:
                lines.append(f"  {job_name}({abbrev}): {dps_type} / 특성:{stat_base}")

    return "\n".join(lines)


def _build_synergy_context() -> str:
    """synergy_benefits.json 핵심 요약"""
    if not SYNERGY_BENEFITS_DATA:
        return ""

    lines = ["[시너지 제공 직업]"]
    synergy_types = SYNERGY_BENEFITS_DATA.get("synergy_types", {})

    for syn_key, syn_data in synergy_types.items():
        name      = syn_data.get("name", syn_key)
        providers = syn_data.get("providers", {})
        provider_list = []
        for job, engs in providers.items():
            eng_str = "/".join(engs) if isinstance(engs, list) else str(engs)
            provider_list.append(f"{job}({eng_str})")
        if provider_list:
            lines.append(f"  {name}: {', '.join(provider_list)}")

    lines.append("")
    lines.append("[시너지 수혜 우선순위]")
    priority = SYNERGY_BENEFITS_DATA.get("benefit_priority", {})
    for syn_key, p_data in priority.items():
        note = p_data.get("note", "")
        if note:
            lines.append(f"  {syn_key}: {note}")

    lines.append("")
    smite = SYNERGY_BENEFITS_DATA.get("smite_synergy_pairing", {})
    if smite:
        lines.append("[사멸 딜러 시너지 페어링]")
        lines.append(f"  헤드사멸: {smite.get('head_smite_pairs', {}).get('preferred_synergy_providers', [])}")
        lines.append(f"  백사멸: {smite.get('back_smite_pairs', {}).get('preferred_synergy_providers', [])}")
        lines.append(f"  {smite.get('note', '')}")

    return "\n".join(lines)


def _build_party_rules() -> str:
    """파티 구성 기본 규칙"""
    rules = SYNERGY_BENEFITS_DATA.get("party_synergy_checklist", {}) if SYNERGY_BENEFITS_DATA else {}
    lines = ["[파티 구성 규칙]"]

    eight = rules.get("ideal_8man", {})
    if eight:
        lines.append("  8인 파티:")
        for s in eight.get("must_have", []):
            lines.append(f"    필수: {s}")

    four = rules.get("ideal_4man", {})
    if four:
        lines.append("  4인 파티:")
        for s in four.get("must_have", []):
            lines.append(f"    필수: {s}")

    return "\n".join(lines)


# ==================== 파티 추천 ====================

def recommend_party(members: list, raid_name: str, guild_id: int = 0) -> str:
    """
    AI 파티 편성 추천 — 이미 확정된 편성 결과에 대한 시너지 해설/코멘트.
    (파티 배정 자체를 바꾸지는 않음. 결과 화면에 참고용으로 덧붙이는 용도)

    Args:
        members:  [{ name, character, std_job, is_support, is_alt, level }, ...]
        raid_name: 레이드 이름
        guild_id: 길드 ID (등록된 길드 전용 Gemini 키 우선 사용)

    Returns:
        추천 결과 문자열
    """
    if not _resolve_api_key(guild_id):
        return "❌ Gemini API 키가 설정되지 않았습니다."

    try:
        client = _get_client(guild_id)

        # 참여 인원 정리
        member_lines = []
        for m in members:
            role    = "서폿" if m.get("is_support") else "딜러"
            std_job = m.get("std_job") or m.get("job") or m.get("character", "")
            char    = m.get("character", "")
            alt_str = " (부캐)" if m.get("is_alt") else ""
            member_lines.append(f"  - {m['name']}: {char} ({std_job}) [{role}]{alt_str}")

        member_str  = "\n".join(member_lines)
        total       = len(members)
        sup_cnt     = sum(1 for m in members if m.get("is_support"))
        dps_cnt     = total - sup_cnt
        party_size  = "8인" if total >= 6 else "4인"

        dps_context     = _build_dps_context()
        synergy_context = _build_synergy_context()
        party_rules     = _build_party_rules()

        prompt = f"""당신은 로스트아크 전문 파티 편성 어시스턴트입니다.
아래 데이터를 참고해 최적의 파티를 편성해주세요.

{dps_context}

{synergy_context}

{party_rules}

━━━━━━━━━━━━━━━━━━━━━━━━━
[레이드] {raid_name}
[인원] 총 {total}명 (서폿 {sup_cnt}명 / 딜러 {dps_cnt}명) → {party_size} 파티

[참여 길드원]
{member_str}
━━━━━━━━━━━━━━━━━━━━━━━━━

다음 형식으로 답변해주세요:

**📋 파티 구성 추천**
(서폿 배치 + 딜러 배치를 그룹으로 나눠 표시)

**⚡ 시너지 분석**
(어떤 시너지가 적용되는지, 사멸 딜러에게 헤드/백 시너지가 잘 배치됐는지)

**💡 편성 이유**
(3줄 이내 핵심 이유)

**⚠️ 주의사항**
(있으면 간략히)

답변은 간결하게, 500자 이내로 해주세요."""

        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return response.text

    except Exception as e:
        return f"❌ AI 추천 실패: {e}"


# ==================== 시너지 분석 ====================

def analyze_synergy(jobs: List[str]) -> str:
    """
    파티 시너지 분석

    Args:
        jobs: 직업 리스트 (예: ["홀리나이트", "소서리스", "리퍼", "블레이드"])

    Returns:
        시너지 분석 결과
    """
    if not GEMINI_API_KEY:
        return "❌ Gemini API 키가 설정되지 않았습니다."

    try:
        client = _get_client()

        synergy_context = _build_synergy_context()
        dps_context     = _build_dps_context()
        job_list_str    = "\n".join([f"  - {j}" for j in jobs])

        prompt = f"""당신은 로스트아크 시너지 분석 전문가입니다.

{dps_context}

{synergy_context}

━━━━━━━━━━━━━━━━━━━━━━━━━
[분석할 파티 구성]
{job_list_str}
━━━━━━━━━━━━━━━━━━━━━━━━━

다음 형식으로 분석해주세요:

**⚡ 시너지 점수**: 상/중/하

**✅ 제공되는 시너지**
(어떤 직업이 어떤 시너지를 제공하는지)

**⚔️ 사멸 딜러 배치**
(헤드/백 시너지가 사멸 딜러에게 잘 매칭됐는지)

**❌ 부족한 시너지**
(빠진 시너지)

**💡 개선 제안**
(2줄 이내)

400자 이내로 간결하게."""

        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return response.text

    except Exception as e:
        return f"❌ 시너지 분석 실패: {e}"


# ==================== 레이드 정보 ====================

def get_raid_guide(raid_name: str) -> str:
    """레이드 공략 정보"""
    if not GEMINI_API_KEY:
        return "❌ Gemini API 키가 설정되지 않았습니다."

    try:
        client = _get_client()
        prompt = f"""로스트아크 {raid_name} 레이드를 3~5줄로 요약해주세요.
1. 레이드 특징
2. 주의사항
3. 추천 파티 구성"""

        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return response.text

    except Exception as e:
        return f"❌ 레이드 정보 조회 실패: {e}"


# ==================== 간단 질문 ====================

def ask_ai(question: str) -> str:
    """로스트아크 관련 질문 답변"""
    if not GEMINI_API_KEY:
        return "❌ Gemini API 키가 설정되지 않았습니다."

    try:
        client = _get_client()
        prompt = f"로스트아크 전문가로서 간략하게 답변해주세요.\n\n질문: {question}"
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return response.text

    except Exception as e:
        return f"❌ AI 응답 실패: {e}"