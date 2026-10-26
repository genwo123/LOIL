"""
로일(LoIl) - 시너지 체크박스 UI
synergy_benefits.json 기반으로 클래스별 직업/각인 선택
- engraving_dependent=true  → 각인별 분리 (워로드 고기/전태, 홀나 폿/딜)
- engraving_dependent=false → 직업 하나 (인파이터, 버서커 등)
- 하이브리드 서폿 → (폿)/(딜) 구분
"""

import discord
from bot.config.settings import SYNERGY_BENEFITS_DATA, JOBS_DATA

# ==================== 직업 선택지 생성 ====================

# 클래스별 이모지
CLASS_EMOJI = {
    "warrior":        "⚔️",
    "martial_artist": "🥊",
    "mage":           "🔮",
    "gunner":         "🔫",
    "assassin":       "🗡️",
    "specialist":     "🎨",
    "guardian_knight":"🛡️",
}

# synergies.json job_synergies 기준 각인 표시명
# engraving_dependent=true인 직업만 각인 분리, 나머지는 직업명 하나
ENGRAVING_LABELS = {
    # 전사
    "warlord":      [("워로드(고기)", "lonely_knight"),   ("워로드(전태)", "combat_readiness")],
    "holyknight":   [("홀나(폿)",    "blessing_aura"),    ("홀나(딜)",     "judgment")],
    "valkyrie":     [("발키리(폿)",  "liberator"),        ("발키리(딜)",   "light_knight")],
    # 마법사
    "bard":         [("바드(폿)",    "desperate_salvation"), ("바드(딜)", "true_courage")],
    "arcana":       [("아르카나(황제)", "emperor"),       ("아르카나(황후)", "empress")],
    # 헌터
    "hawkeye":      [("호크아이(동료)", "second_identity"), ("호크아이(습격)", "death_strike")],
    "devilhunter":  [("데빌헌터(전술)", "tactical_reload"), ("데빌헌터(핸드)", "handgunner")],
    # 스페셜리스트
    "artist":       [("도화가(폿)",   "full_bloom"),      ("도화가(딜)",    "recurrence")],
    "aeromancer":   [("기상술사(질풍)", "wind_fury"),     ("기상술사(이슬)", "drizzle")],
}

def get_class_job_options(include_emoji: bool = True) -> dict:
    """
    클래스별 선택지 생성
    반환: { class_key: [ (display_label, value_key), ... ] }
    value_key = "직업키:각인키" or "직업키"
    """
    options = {}
    jobs_data = JOBS_DATA.get("classes", {})

    for class_key, class_data in jobs_data.items():
        class_name = class_data.get("name", class_key)
        emoji      = CLASS_EMOJI.get(class_key, "🎮")
        opts       = []

        for job_key, job_data in class_data.get("jobs", {}).items():
            job_name = job_data.get("name", job_key)

            if job_key in ENGRAVING_LABELS:
                # 각인별 분리
                for label, eng_key in ENGRAVING_LABELS[job_key]:
                    opts.append((label, f"{job_key}:{eng_key}"))
            else:
                # 직업 하나
                opts.append((job_name, job_key))

        options[class_key] = {
            "name":  f"{emoji} {class_name}" if include_emoji else class_name,
            "jobs":  opts,
        }

    return options


CLASS_JOB_OPTIONS = get_class_job_options()
CLASS_JOB_OPTIONS_PLAIN = get_class_job_options(include_emoji=False)


# ==================== 실제 편성(레이드 신청 인원)에서 시너지 체크박스 값 추론 ====================

def _build_job_name_to_key() -> dict:
    """"홀리나이트" 같은 표시명 → "holyknight" 같은 직업키 역매핑."""
    mapping = {}
    for class_data in JOBS_DATA.get("classes", {}).values():
        for job_key, job_data in class_data.get("jobs", {}).items():
            mapping[job_data.get("name", job_key)] = job_key
    return mapping


JOB_NAME_TO_KEY = _build_job_name_to_key()

# 폿/딜 구분이 실제로 존재하는 하이브리드 직업만 — 서폿 각인키 지정.
# 워로드/아르카나/호크아이/데빌헌터는 두 각인 다 딜러 빌드라 여기 없음(항상 첫 번째 각인으로 추론).
SUPPORT_ENGRAVING = {
    "holyknight": "blessing_aura",
    "valkyrie": "liberator",
    "bard": "desperate_salvation",
    "artist": "full_bloom",
    "aeromancer": "drizzle",
}


def guess_job_value(std_job: str, is_support: bool) -> str | None:
    """실제 편성 인원의 (표시 직업명, 서폿 여부)로 시너지 체크박스 value를 추론.
    각인이 하이브리드(폿/딜 나뉨)인 직업은 is_support로 그 중 하나를 고름 — 워로드처럼
    둘 다 딜러 빌드인 하이브리드는 첫 번째 각인으로 기본 추론(정확한 각인은 체크박스에서 직접 조정)."""
    job_key = JOB_NAME_TO_KEY.get(std_job)
    if not job_key:
        return None
    if job_key not in ENGRAVING_LABELS:
        return job_key
    if is_support and job_key in SUPPORT_ENGRAVING:
        return f"{job_key}:{SUPPORT_ENGRAVING[job_key]}"
    for label, eng_key in ENGRAVING_LABELS[job_key]:
        if job_key not in SUPPORT_ENGRAVING or eng_key != SUPPORT_ENGRAVING[job_key]:
            return f"{job_key}:{eng_key}"
    return f"{job_key}:{ENGRAVING_LABELS[job_key][0][1]}"


def is_support_value(val: str) -> bool:
    """체크박스 value가 실제 서폿 각인인지(하이브리드 직업의 폿 빌드인지)."""
    if ":" not in val:
        return False
    job_key, eng_key = val.split(":", 1)
    return SUPPORT_ENGRAVING.get(job_key) == eng_key


# ==================== 시너지 분석 로직 ====================

def get_synergies_for_selection(selected_values: list[str]) -> dict:
    """
    선택된 직업/각인 목록 → 시너지 타입별 제공 직업 분류
    반환: { synergy_type: { name, jobs: [label, ...], description } }
    """
    benefits  = SYNERGY_BENEFITS_DATA.get("synergy_types", {})
    result    = {}

    # 선택값 → 표시명 역매핑
    label_map = {}
    for class_data in CLASS_JOB_OPTIONS.values():
        for label, val in class_data["jobs"]:
            label_map[val] = label

    for val in selected_values:
        label = label_map.get(val, val)
        job_key = val.split(":")[0]

        # job_name 원본
        job_name_raw = label.split("(")[0].strip()

        # synergy_benefits providers 체크
        for syn_key, syn_data in benefits.items():
            providers = syn_data.get("providers", {})
            matched   = False

            # providers가 dict인 경우 (직업명: [각인들])
            if isinstance(providers, dict):
                for prov_job, prov_engs in providers.items():
                    if prov_job in label or prov_job == job_name_raw:
                        matched = True
                        break
            # providers가 list인 경우
            elif isinstance(providers, list):
                if job_name_raw in providers:
                    matched = True

            if matched:
                if syn_key not in result:
                    result[syn_key] = {
                        "name":        syn_data.get("name", syn_key),
                        "description": syn_data.get("description", ""),
                        "jobs":        [],
                    }
                result[syn_key]["jobs"].append(label)

    return result


# 중요도 순 정렬 — Discord 임베드와 웹 페이지가 같이 씀
SYNERGY_PRIORITY = [
    "damage_amplification", "defense_reduction", "crit_rate",
    "crit_damage", "attack_power", "head_back_damage",
    "attack_speed", "movement_speed", "stagger_damage",
]


def split_covered_overlaps(synergy_map: dict) -> tuple[list[str], list[str]]:
    """synergy_map(보유 시너지)을 보고 (중요도순 보유 목록, 그중 2명 이상이 같은 시너지를
    제공해서 겹칠 수 있는 시너지 목록) 반환. "필수인데 빠졌다" 개념은 없음 — 이미 뽑은 인원
    안에서 최적 조합인지(같은 시너지가 겹쳐서 한쪽이 낭비되는 자리가 없는지)만 확인한다."""
    covered = [k for k in SYNERGY_PRIORITY if k in synergy_map]
    overlaps = [k for k in covered if len(synergy_map[k]["jobs"]) >= 2]
    return covered, overlaps


def get_optimization_suggestions(synergy_map: dict, selected_values: list[str]) -> list[dict]:
    """"필수인데 없다"가 아니라 "최적화 참고용" — 지금 아무도 안 채운 시너지마다
    "이 직업을 추가하면 채워짐" 후보를 보여준다. 이미 선택된 직업은 후보에서 제외."""
    benefits = SYNERGY_BENEFITS_DATA.get("synergy_types", {})
    label_map = {}
    for class_data in CLASS_JOB_OPTIONS.values():
        for label, val in class_data["jobs"]:
            label_map[val] = label
    already_selected_names = {label_map.get(v, v).split("(")[0].strip() for v in selected_values}

    result = []
    for syn_key in SYNERGY_PRIORITY:
        if syn_key in synergy_map:
            continue
        syn_data = benefits.get(syn_key, {})
        providers = syn_data.get("providers", {})
        job_names = list(providers.keys()) if isinstance(providers, dict) else list(providers)
        candidates = [j for j in job_names if j not in already_selected_names]
        if candidates:
            result.append({
                "name": syn_data.get("name", syn_key),
                "jobs": candidates[:6],
                "more": max(0, len(candidates) - 6),
            })
    return result


def suggest_party_split(selected_values: list[str], party_size: int = 4) -> list[dict] | None:
    """선택 인원이 파티 하나(4명) 넘으면, 시너지가 파티 안에서 최대한 안 겹치게 여러 파티로
    나누는 걸 추천한다. 로스트아크 시너지 버프는 자기 파티(4명) 안에서만 적용되니, 전체
    합산이 아니라 "이 파티 안에서" 겹치는지가 실제로 중요함.
    규칙: 서폿은 파티마다 최대 1명씩 우선 배치. 딜러는 "이 사람을 넣으면 이 파티에 새로
    추가되는 시너지가 가장 많은 파티"부터 그리디하게 채워서 파티 내 중복을 최소화한다."""
    total = len(selected_values)
    if total <= party_size:
        return None

    num_parties = max(1, -(-total // party_size))
    label_map = {}
    for class_data in CLASS_JOB_OPTIONS.values():
        for label, val in class_data["jobs"]:
            label_map[val] = label
    benefits = SYNERGY_BENEFITS_DATA.get("synergy_types", {})

    supports = [v for v in selected_values if is_support_value(v)]
    dps = [v for v in selected_values if not is_support_value(v)]

    parties = [{"members": [], "synergies": set()} for _ in range(num_parties)]
    for i, v in enumerate(supports):
        parties[i % num_parties]["members"].append(v)

    member_synergies = {v: set(get_synergies_for_selection([v]).keys()) for v in selected_values}
    for v in dps:
        open_parties = [p for p in parties if len(p["members"]) < party_size] or parties
        best = max(open_parties, key=lambda p: len(member_synergies[v] - p["synergies"]))
        best["members"].append(v)
        best["synergies"] |= member_synergies[v]

    result = []
    for p in parties:
        result.append({
            "members": [label_map.get(v, v) for v in p["members"]],
            "synergies": [benefits.get(k, {}).get("name", k) for k in p["synergies"]],
        })
    return result


def build_synergy_result_embed(selected_labels: list[str], synergy_map: dict) -> discord.Embed:
    """시너지 분석 결과 임베드"""

    embed = discord.Embed(
        title="⚡ 시너지 분석 결과",
        color=0x9B59B6
    )

    # 선택 직업 요약
    embed.description = "**선택 직업:** " + "  ·  ".join(selected_labels)

    if not synergy_map:
        embed.add_field(
            name="⚠️ 시너지 없음",
            value="선택한 직업들이 제공하는 시너지가 없습니다.",
            inline=False
        )
        return embed

    covered, overlaps = split_covered_overlaps(synergy_map)

    # 커버된 시너지 필드 — 2명 이상이 같은 시너지를 제공하면 겹침 경고를 같이 붙임
    for syn_key in covered:
        data     = synergy_map[syn_key]
        jobs_str = "  ·  ".join(data["jobs"])
        is_overlap = syn_key in overlaps
        name  = f"✅ {data['name']}" + (" ⚠️ 겹침" if is_overlap else "")
        value = f"{jobs_str}\n*{data['description']}*"
        if is_overlap:
            value += "\n⚠️ 같은 시너지를 여러 명이 제공하고 있어요 — 한쪽은 낭비될 수 있으니 다른 조합을 고려해보세요."
        embed.add_field(name=name, value=value, inline=False)

    embed.set_footer(text="✅ 보유  ⚠️ 겹침 = 2명 이상이 같은 시너지 제공(낭비 가능성)")
    return embed


# ==================== 1단계: 클래스 선택 View ====================

class SynergyClassSelectView(discord.ui.View):
    """클래스 선택 드롭다운"""

    def __init__(self):
        super().__init__(timeout=180)

        options = [
            discord.SelectOption(
                label=data["name"],
                value=class_key,
                description=f"{len(data['jobs'])}개 직업/각인"
            )
            for class_key, data in CLASS_JOB_OPTIONS.items()
        ]

        select = discord.ui.Select(
            placeholder="🎮 클래스 선택 (여러 개 가능)",
            options=options,
            min_values=1,
            max_values=len(options),
            custom_id="synergy_class_select",
            row=0
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction):
        select    = discord.utils.get(self.children, custom_id="synergy_class_select")
        selected  = select.values  # 선택된 class_key 목록

        # 2단계 직업 선택 View로 이동
        view  = SynergyJobSelectView(class_keys=selected)
        embed = discord.Embed(
            title="⚡ 시너지 분석 — 직업/각인 선택",
            description="파티에 포함된 직업/각인을 모두 선택해주세요",
            color=0x9B59B6
        )
        await interaction.response.edit_message(embed=embed, view=view)


# ==================== 2단계: 직업/각인 선택 View ====================

class SynergyJobSelectView(discord.ui.View):
    """선택된 클래스의 직업/각인 체크박스"""

    def __init__(self, class_keys: list[str]):
        super().__init__(timeout=180)
        self.class_keys     = class_keys
        self.selected_jobs: set[str] = set()

        # 클래스별로 Select Menu 생성 (최대 5개 row)
        for i, class_key in enumerate(class_keys[:4]):
            data    = CLASS_JOB_OPTIONS.get(class_key, {})
            jobs    = data.get("jobs", [])
            if not jobs:
                continue

            options = [
                discord.SelectOption(label=label[:100], value=val)
                for label, val in jobs
            ]

            select = discord.ui.Select(
                placeholder=f"{data.get('name','직업')} 선택",
                options=options[:25],
                min_values=0,
                max_values=len(options[:25]),
                custom_id=f"synergy_job_{class_key}",
                row=i
            )
            select.callback = self._on_job_select
            self.add_item(select)

        # 분석 버튼
        btn = discord.ui.Button(
            label="⚡ 시너지 분석",
            style=discord.ButtonStyle.primary,
            custom_id="synergy_analyze",
            row=4
        )
        btn.callback = self._analyze
        self.add_item(btn)

    async def _on_job_select(self, interaction: discord.Interaction):
        # 모든 select에서 선택값 수집
        for item in self.children:
            if isinstance(item, discord.ui.Select):
                for val in item.values:
                    self.selected_jobs.add(val)
        await interaction.response.defer()

    async def _analyze(self, interaction: discord.Interaction):
        if not self.selected_jobs:
            await interaction.response.send_message(
                "❌ 직업을 하나 이상 선택해주세요!", ephemeral=True
            )
            return

        # 선택된 직업 → 표시명 변환
        label_map = {}
        for class_data in CLASS_JOB_OPTIONS.values():
            for label, val in class_data["jobs"]:
                label_map[val] = label

        selected_labels = [label_map.get(v, v) for v in self.selected_jobs]
        synergy_map     = get_synergies_for_selection(list(self.selected_jobs))
        embed           = build_synergy_result_embed(selected_labels, synergy_map)

        await interaction.response.edit_message(embed=embed, view=SynergyRetryView())


# ==================== 결과 후 재시도 View ====================

class SynergyRetryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="🔄 다시 분석", style=discord.ButtonStyle.secondary, custom_id="synergy_retry")
    async def retry(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="⚡ 시너지 분석 — 클래스 선택",
            description="분석할 직업의 클래스를 선택하세요",
            color=0x9B59B6
        )
        await interaction.response.edit_message(embed=embed, view=SynergyClassSelectView())