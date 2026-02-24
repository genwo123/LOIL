"""
로일(LoIl) - 이미지 렌더러
Pillow로 Discord용 이미지 생성
- 개인 일정 (스타일 D: 다크카드)
- 이번주 레이드 (요일 카드형)
- 파티 편성 결과
"""

from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import os

# ==================== 폰트 경로 ====================

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FONT_DIR   = os.path.join(BASE_DIR, "bot", "assets", "fonts")
FONT_REG   = os.path.join(FONT_DIR, "NanumGothic.ttf")
FONT_BOLD  = os.path.join(FONT_DIR, "NanumGothicBold.ttf")

def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    try:
        path = FONT_BOLD if bold else FONT_REG
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


# ==================== 색상 팔레트 ====================

C = {
    "bg":         "#1E1F22",   # 메인 배경
    "card":       "#2B2D31",   # 카드 배경
    "card_hover": "#313338",   # 카드 밝은 버전
    "accent":     "#9B59B6",   # 보라 (로일 테마)
    "support":    "#57F287",   # 초록 (서폿)
    "dps":        "#ED4245",   # 빨강 (딜러)
    "gold":       "#FFD700",   # 골드
    "text_white": "#FFFFFF",
    "text_gray":  "#B5BAC1",
    "text_muted": "#6D6F78",
    "divider":    "#3F4147",
    "time_bg":    "#383A40",
}

def _hex(color: str) -> tuple:
    """#RRGGBB → (R, G, B)"""
    c = color.lstrip("#")
    return tuple(int(c[i:i+2], 16) for i in (0, 2, 4))


# ==================== 공통 유틸 ====================

def _text_w(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont) -> int:
    return draw.textlength(text, font=font)

def _rounded_rect(draw: ImageDraw.Draw, xy: tuple, radius: int, fill: str):
    """둥근 모서리 사각형"""
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill)

def _pill(draw: ImageDraw.Draw, x: int, y: int, text: str,
          bg: str, fg: str, font: ImageFont.FreeTypeFont, pad_x: int = 12, pad_y: int = 4):
    """알약형 태그"""
    w = int(_text_w(draw, text, font))
    _rounded_rect(draw, (x, y, x + w + pad_x * 2, y + font.size + pad_y * 2), radius=20, fill=bg)
    draw.text((x + pad_x, y + pad_y), text, font=font, fill=fg)
    return w + pad_x * 2  # 너비 반환


# ==================== 개인 일정 이미지 (스타일 D 다크카드) ====================

def render_my_schedule(nickname: str, schedule: list) -> BytesIO:
    """
    개인 일정 → 다크카드 스타일 이미지
    schedule: get_user_schedule() 반환값
    """
    W = 640
    PAD = 24
    CARD_H = 88       # 레이드 카드 높이
    CARD_GAP = 8      # 카드 간격
    DAY_H = 40        # 요일 헤더 높이
    HEADER_H = 90     # 상단 헤더

    # 요일 그룹화
    DAY_ORDER = {'월':0,'화':1,'수':2,'목':3,'금':4,'토':5,'일':6,'미정':7}
    day_groups: dict[str, list] = {}
    for s in schedule:
        day = s.get('day', '미정')
        day_groups.setdefault(day, []).append(s)
    day_groups = dict(sorted(day_groups.items(), key=lambda x: DAY_ORDER.get(x[0], 7)))

    # 높이 계산
    total_raids = sum(len(v) for v in day_groups.values())
    H = (HEADER_H + PAD
         + len(day_groups) * (DAY_H + CARD_GAP)
         + total_raids * (CARD_H + CARD_GAP)
         + PAD * 2)

    img  = Image.new("RGBA", (W, H), _hex(C["bg"]))
    draw = ImageDraw.Draw(img)

    # ── 폰트 ──
    f_name   = _font(26, bold=True)
    f_sub    = _font(14)
    f_day    = _font(15, bold=True)
    f_time   = _font(22, bold=True)
    f_raid   = _font(17, bold=True)
    f_char   = _font(14)
    f_tag    = _font(12, bold=True)

    # ── 상단 헤더 ──
    # 보라 악센트 바
    draw.rectangle([0, 0, 6, HEADER_H], fill=_hex(C["accent"]))

    draw.text((PAD, 18), nickname, font=f_name, fill=_hex(C["text_white"]))
    draw.text((PAD, 52), f"이번 주 레이드  {total_raids}개", font=f_sub, fill=_hex(C["text_gray"]))

    # 서폿/딜러 카운트
    sup = sum(1 for s in schedule if s.get('is_support'))
    dps = total_raids - sup
    x_stat = W - PAD
    sup_txt = f"💚 서폿 {sup}"
    dps_txt = f"⚔️ 딜러 {dps}"
    draw.text((x_stat - int(_text_w(draw, sup_txt, f_sub)), 20), sup_txt, font=f_sub, fill=_hex(C["support"]))
    draw.text((x_stat - int(_text_w(draw, dps_txt, f_sub)), 42), dps_txt, font=f_sub, fill=_hex(C["dps"]))

    # 구분선
    draw.rectangle([PAD, HEADER_H - 2, W - PAD, HEADER_H], fill=_hex(C["divider"]))

    # ── 요일 그룹 ──
    y = HEADER_H + PAD

    for day, raids in day_groups.items():
        # 요일 헤더
        draw.text((PAD, y + 10), f"📅  {day}요일", font=f_day, fill=_hex(C["text_gray"]))
        y += DAY_H + CARD_GAP

        for s in sorted(raids, key=lambda x: (x.get('hour', 0), x.get('minute', 0))):
            is_sup    = s.get('is_support', False)
            role_col  = C["support"] if is_sup else C["dps"]
            role_txt  = "💚 서폿" if is_sup else "⚔️ 딜러"
            time_str  = s.get('time_str', '?:??')
            raid_name = s.get('raid_name', '')
            char      = s.get('character', '')
            dur       = s.get('duration', 30)
            dur_str   = f"~{dur // 60}시간" if dur >= 60 else f"~{dur}분"

            # 카드 배경
            _rounded_rect(draw, (PAD, y, W - PAD, y + CARD_H), radius=10, fill=C["card"])

            # 왼쪽 역할 컬러 바
            draw.rounded_rectangle([PAD, y, PAD + 5, y + CARD_H], radius=4, fill=role_col)

            # 시간 박스
            TIME_W = 72
            _rounded_rect(draw, (PAD + 16, y + 18, PAD + 16 + TIME_W, y + 50), radius=6, fill=C["time_bg"])
            tw = int(_text_w(draw, time_str, f_time))
            draw.text((PAD + 16 + (TIME_W - tw) // 2, y + 20), time_str, font=f_time, fill=_hex(C["text_white"]))

            # 레이드명 + 캐릭터
            tx = PAD + 16 + TIME_W + 16
            draw.text((tx, y + 16), raid_name, font=f_raid, fill=_hex(C["text_white"]))
            draw.text((tx, y + 44), f"{char}  ·  {dur_str}", font=f_char, fill=_hex(C["text_gray"]))

            # 역할 태그 (우측)
            tag_x = W - PAD - 90
            _pill(draw, tag_x, y + 28, role_txt, bg=role_col + "44", fg=role_col, font=f_tag)

            y += CARD_H + CARD_GAP

        y += CARD_GAP  # 요일 간 추가 여백

    # 하단 여백 + 워터마크
    draw.text((PAD, H - 22), "로일(LoIl) · 24시간 후 자동 삭제", font=_font(11), fill=_hex(C["text_muted"]))

    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf


# ==================== 이번주 레이드 이미지 (요일 카드형) ====================

def render_weekly_raids(summary: list) -> BytesIO:
    """
    이번주-레이드 → 요일 카드형 이미지
    summary: get_weekly_summary() 반환값
    """
    W = 680
    PAD = 24
    HEADER_H = 70
    DAY_H = 36
    ROW_H = 44
    ROW_GAP = 4

    # 요일 그룹화
    DAY_ORDER = {'월':0,'화':1,'수':2,'목':3,'금':4,'토':5,'일':6,'미정':7}
    day_groups: dict[str, list] = {}
    for r in summary:
        day = r.get('day', '미정')
        day_groups.setdefault(day, []).append(r)
    day_groups = dict(sorted(day_groups.items(), key=lambda x: DAY_ORDER.get(x[0], 7)))

    total = sum(len(v) for v in day_groups.values())
    H = (HEADER_H + PAD
         + len(day_groups) * (DAY_H + PAD)
         + total * (ROW_H + ROW_GAP)
         + PAD * 2)

    img  = Image.new("RGBA", (W, H), _hex(C["bg"]))
    draw = ImageDraw.Draw(img)

    f_title = _font(22, bold=True)
    f_day   = _font(14, bold=True)
    f_time  = _font(15, bold=True)
    f_raid  = _font(15)
    f_meta  = _font(13)

    # 헤더
    draw.rectangle([0, 0, 6, HEADER_H], fill=_hex(C["accent"]))
    draw.text((PAD, 16), "📅  이번 주 레이드 일정", font=f_title, fill=_hex(C["text_white"]))
    draw.text((PAD, 46), f"총 {total}개 레이드", font=f_meta, fill=_hex(C["text_gray"]))
    draw.rectangle([PAD, HEADER_H - 2, W - PAD, HEADER_H], fill=_hex(C["divider"]))

    y = HEADER_H + PAD

    for day, raids in day_groups.items():
        # 요일 헤더
        draw.text((PAD, y + 8), f"🗓  {day}요일", font=f_day, fill=_hex(C["text_gray"]))
        y += DAY_H

        for r in sorted(raids, key=lambda x: (x.get('hour', 0), x.get('minute', 0))):
            _rounded_rect(draw, (PAD, y, W - PAD, y + ROW_H), radius=8, fill=C["card"])

            time_str  = r.get('time_str', '?:??')
            name      = r.get('name', '')
            count     = r.get('member_count', 0)
            dur       = r.get('duration', 30)
            dur_str   = f"~{dur // 60}h" if dur >= 60 else f"~{dur}m"

            # 시간
            draw.text((PAD + 14, y + 13), time_str, font=f_time, fill=_hex(C["gold"]))
            # 레이드명
            tx = PAD + 85
            draw.text((tx, y + 13), name, font=f_raid, fill=_hex(C["text_white"]))
            # 인원 + 시간 (우측)
            meta = f"{count}명  ·  {dur_str}"
            mw   = int(_text_w(draw, meta, f_meta))
            draw.text((W - PAD - mw - 10, y + 14), meta, font=f_meta, fill=_hex(C["text_gray"]))

            y += ROW_H + ROW_GAP

        y += PAD  # 요일 간 간격

    draw.text((PAD, H - 22), "로일(LoIl) · 매주 수요일 자동 갱신", font=_font(11), fill=_hex(C["text_muted"]))

    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf


# ==================== 파티 편성 결과 이미지 ====================

def render_party_result(raid_name: str, parties: list[list]) -> BytesIO:
    """
    파티 편성 결과 → 이미지
    parties: [[member_dict, ...], ...]
    """
    W = 640
    PAD = 24
    HEADER_H = 80
    PARTY_TITLE_H = 36
    MEMBER_H = 40
    MEMBER_GAP = 4
    PARTY_GAP = 16

    total_members = sum(len(p) for p in parties)
    sup_total     = sum(1 for p in parties for m in p if m.get('is_support'))
    dps_total     = total_members - sup_total

    H = (HEADER_H + PAD
         + len(parties) * (PARTY_TITLE_H + PARTY_GAP)
         + total_members * (MEMBER_H + MEMBER_GAP)
         + PAD * 2)

    img  = Image.new("RGBA", (W, H), _hex(C["bg"]))
    draw = ImageDraw.Draw(img)

    f_title  = _font(22, bold=True)
    f_sub    = _font(13)
    f_party  = _font(15, bold=True)
    f_num    = _font(18, bold=True)
    f_name   = _font(15, bold=True)
    f_char   = _font(13)
    f_tag    = _font(11, bold=True)

    # 헤더
    draw.rectangle([0, 0, 6, HEADER_H], fill=_hex(C["accent"]))
    draw.text((PAD, 14), f"⚔️  {raid_name}", font=f_title, fill=_hex(C["text_white"]))
    draw.text((PAD, 48), f"총 {total_members}명  ·  💚 서폿 {sup_total}명  ·  ⚔️ 딜러 {dps_total}명", font=f_sub, fill=_hex(C["text_gray"]))
    draw.rectangle([PAD, HEADER_H - 2, W - PAD, HEADER_H], fill=_hex(C["divider"]))

    y = HEADER_H + PAD

    for pi, party in enumerate(parties, 1):
        # 파티 타이틀
        _rounded_rect(draw, (PAD, y, PAD + 120, y + 28), radius=6, fill=C["accent"])
        draw.text((PAD + 12, y + 6), f"PARTY  {pi}", font=f_party, fill=_hex(C["text_white"]))
        y += PARTY_TITLE_H

        for mi, m in enumerate(party, 1):
            is_sup   = m.get('is_support', False)
            role_col = C["support"] if is_sup else C["dps"]
            role_txt = "서폿" if is_sup else "딜러"
            name     = m.get('name', '')
            char     = m.get('character', '')

            # 멤버 카드
            _rounded_rect(draw, (PAD, y, W - PAD, y + MEMBER_H), radius=8, fill=C["card"])

            # 역할 컬러 바
            draw.rounded_rectangle([PAD, y, PAD + 4, y + MEMBER_H], radius=3, fill=role_col)

            # 슬롯 번호
            draw.text((PAD + 14, y + 12), str(mi), font=f_num, fill=_hex(C["text_muted"]))

            # 이름 + 캐릭터
            draw.text((PAD + 42, y + 8), name, font=f_name, fill=_hex(C["text_white"]))
            draw.text((PAD + 42, y + 26), char, font=f_char, fill=_hex(C["text_gray"]))

            # 역할 태그 (우측)
            tag_w = int(_text_w(draw, role_txt, f_tag)) + 20
            tag_x = W - PAD - tag_w - 8
            _rounded_rect(draw, (tag_x, y + 10, tag_x + tag_w, y + 30), radius=10, fill=role_col)
            draw.text((tag_x + 10, y + 12), role_txt, font=f_tag, fill="#FFFFFF")

            y += MEMBER_H + MEMBER_GAP

        y += PARTY_GAP

    draw.text((PAD, H - 22), "로일(LoIl) · 확정 후 시트 자동 저장", font=_font(11), fill=_hex(C["text_muted"]))

    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf