"""
로일(LoIl) - 이미지 렌더러
"""

from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from bot.utils.sheets import get_raid_size
import re
import os

def _find_font(filename: str) -> str:
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        for sub in ["bot/assets/fonts", "assets/fonts"]:
            p = os.path.join(current, sub.replace("/", os.sep), filename)
            if os.path.exists(p):
                return p
        current = os.path.dirname(current)
    return ""

FONT_REG  = _find_font("NanumGothic.ttf")
FONT_BOLD = _find_font("NanumGothicBold.ttf")

def _font(size: int, bold: bool = False):
    path = FONT_BOLD if bold else FONT_REG
    try:
        if path:
            return ImageFont.truetype(path, size)
    except Exception:
        pass
    return ImageFont.load_default()

C = {
    "bg":         "#1E1F22",
    "card":       "#2B2D31",
    "card_dark":  "#232428",
    "col_header": "#26272B",
    "accent":     "#9B59B6",
    "support":    "#57F287",
    "dps":        "#ED4245",
    "undecided":  "#6D6F78",
    "gold":       "#FFD700",
    "text_white": "#FFFFFF",
    "text_gray":  "#B5BAC1",
    "text_muted": "#6D6F78",
    "divider":    "#3F4147",
    "time_bg":    "#383A40",
    "dur_bg":     "#2E3035",
    "overlap_bg": "#2e2038",
    "overlap_bar": "#7c5cbf",
}

DAY_ORDER_LOA = {'수':0,'목':1,'금':2,'토':3,'일':4,'월':5,'화':6,'미정':7}
ALL_DAYS = ['수','목','금','토','일','월','화','미정']

def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i+2],16) for i in (0,2,4))

def _blend(fg_hex, bg_hex, alpha):
    """fg를 bg 위에 alpha 비율로 얹은 불투명 RGB. 최종 PNG가 RGB로 저장돼
    실제 알파 채널은 무시되므로, 반투명 느낌은 색 자체를 섞어서 흉내낸다."""
    fg, bg = _hex(fg_hex), _hex(bg_hex)
    return tuple(round(f*alpha + b*(1-alpha)) for f, b in zip(fg, bg))

def _tw(draw, text, font):
    return int(draw.textlength(text, font=font))

def _rect(draw, xy, r, fill):
    draw.rounded_rectangle(list(xy), radius=r, fill=fill)

def _pill(draw, x, y, text, bg, fg, font, px=10, py=4):
    tw = _tw(draw, text, font)
    w  = tw + px*2
    h  = font.size + py*2
    _rect(draw, (x, y, x+w, y+h), r=h//2, fill=bg)
    draw.text((x+px, y+py), text, font=font, fill=fg)
    return w

def _dur_label(dur):
    if dur >= 60:
        h, m = dur//60, dur%60
        return f"{h}시간" if m==0 else f"{h}시간 {m}분"
    return f"{dur}분"

def _week_title(guild_name: str) -> str:
    KST = timezone(timedelta(hours=9))
    now = datetime.now(KST)
    days_back = (now.weekday() - 2) % 7
    if now.weekday() == 2 and now.hour < 9:
        days_back = 7
    ref = now - timedelta(days=days_back)
    month = ref.month
    first_day = ref.replace(day=1)
    first_wed_offset = (2 - first_day.weekday()) % 7
    first_wed = first_day + timedelta(days=first_wed_offset)
    week_num = (ref - first_wed).days // 7 + 1
    prefix = f"{guild_name} " if guild_name else ""
    return f"{prefix}{month}월 {week_num}주차 일정"


def _split_parties(members: list, party_size: int = None) -> list[list]:
    """
    party_size: 레이드 정원 (4/8/16). None이면 인원수로 자동 판단.
    party_size 이하이면 무조건 1파티 — 4인 레이드 강제 분리 방지.
    """
    if not members:
        return []

    # party_size 미지정이면 멤버 수 기반 추정
    if party_size is None:
        party_size = 8 if len(members) > 4 else 4

    # 정원 이하면 1파티
    if len(members) <= party_size:
        ordered = sorted(members, key=lambda m: (1 if m.get('is_support') else 0, m.get('name', '')))
        return [ordered]

    # 초과 시 2파티 분리
    supports = [m for m in members if m.get('is_support')]
    dps_list = [m for m in members if not m.get('is_support')]
    p1_sup = supports[:1]
    p2_sup = supports[1:2]
    remaining_sup = supports[2:]
    all_dps = dps_list + remaining_sup
    half = len(all_dps) // 2
    p1_dps = all_dps[:half + len(all_dps) % 2]
    p2_dps = all_dps[half + len(all_dps) % 2:]
    p1 = p1_dps + p1_sup
    p2 = p2_dps + p2_sup
    return [p1, p2] if p2 else [p1]


def _get_base_name(name: str) -> str:
    m = re.match(r'^([^(]+)', name)
    return m.group(1).strip() if m else name


def _make_overlap_label(names: list) -> str:
    bases = []
    seen  = set()
    for n in names:
        b = _get_base_name(n)
        if b not in seen:
            seen.add(b)
            bases.append(b)
    if len(bases) == 1:
        return f"{bases[0]}  {len(names)}팀"
    else:
        return " / ".join(bases)


# ══════════════════════════════════════════════
#  개인 일정 이미지
# ══════════════════════════════════════════════

def render_my_schedule(nickname: str, schedule: list, guild_name: str = "로일길드") -> BytesIO:
    W=680; PAD=24; CARD_H=84; CARD_GAP=8; DAY_H=40; HEADER_H=100
    TIME_BX_W=76; PILL_JOB="#7c5cbf"

    day_groups: dict[str, list] = {}
    for s in schedule:
        day_groups.setdefault(s.get('day','미정'), []).append(s)
    day_groups = dict(sorted(day_groups.items(), key=lambda x: DAY_ORDER_LOA.get(x[0],7)))

    total   = sum(len(v) for v in day_groups.values())
    sup_cnt = sum(1 for s in schedule if s.get('is_support'))
    dps_cnt = total - sup_cnt

    H = HEADER_H + PAD + len(day_groups)*(DAY_H+CARD_GAP) + total*(CARD_H+CARD_GAP) + PAD*2

    img  = Image.new("RGBA", (W, H), _hex(C["bg"]))
    draw = ImageDraw.Draw(img)

    f_title  = _font(13)
    f_name   = _font(28, bold=True)
    f_legend = _font(13, bold=True)
    f_day    = _font(15, bold=True)
    f_time   = _font(18, bold=True)
    f_raid   = _font(16, bold=True)
    f_job    = _font(13, bold=True)
    f_dur    = _font(12)
    f_tag    = _font(11)
    f_wm     = _font(11)

    draw.rectangle([0,0,6,HEADER_H], fill=_hex(C["accent"]))
    draw.text((PAD,12), _week_title(guild_name), font=f_title, fill=_hex(C["text_muted"]))
    draw.text((PAD,30), nickname, font=f_name, fill=_hex(C["text_white"]))
    rx = W - PAD
    draw.text((rx-_tw(draw,f"⚔  딜러  {dps_cnt}",f_legend),14), f"⚔  딜러  {dps_cnt}", font=f_legend, fill=_hex(C["dps"]))
    draw.text((rx-_tw(draw,f"●  서폿  {sup_cnt}",f_legend),38), f"●  서폿  {sup_cnt}", font=f_legend, fill=_hex(C["support"]))
    draw.rectangle([PAD,HEADER_H-2,W-PAD,HEADER_H], fill=_hex(C["divider"]))

    y = HEADER_H + PAD
    for day, raids in day_groups.items():
        is_und  = day == '미정'
        day_col = C["undecided"] if is_und else C["text_gray"]
        draw.text((PAD, y+10), "미정 (조율 필요)" if is_und else f"{day}요일", font=f_day, fill=_hex(day_col))
        y += DAY_H

        for s in sorted(raids, key=lambda x:(x.get('hour',0), x.get('minute',0))):
            is_sup   = s.get('is_support', False)
            cleared  = s.get('cleared', False)
            role_col = C["undecided"] if is_und else (C["support"] if is_sup else C["dps"])
            bar_col  = C["gold"] if cleared else role_col
            time_str = s.get('time_str','?:??')
            raid_name= s.get('raid_name','')
            std_job  = s.get('std_job','')
            is_alt   = s.get('is_alt', False)
            dur_lbl  = _dur_label(s.get('duration',30))

            _rect(draw,(PAD,y,W-PAD,y+CARD_H),r=10,fill=C["card"])
            draw.rounded_rectangle([PAD,y,PAD+5,y+CARD_H],radius=4,fill=bar_col)

            tx = PAD + 14
            _rect(draw,(tx,y+12,tx+TIME_BX_W,y+50),r=6,fill=C["time_bg"])
            tw2 = _tw(draw,time_str,f_time)
            draw.text((tx+(TIME_BX_W-tw2)//2,y+16), time_str, font=f_time, fill=_hex(C["text_white"]))
            dtw = _tw(draw,dur_lbl,f_dur)
            draw.text((tx+(TIME_BX_W-dtw)//2,y+56), dur_lbl, font=f_dur, fill=_hex(C["text_muted"]))

            cx = tx + TIME_BX_W + 16
            draw.text((cx,y+12), raid_name, font=f_raid, fill=_hex(C["text_white"]))

            if is_alt:
                draw.text((cx,y+48), "부캐", font=f_tag, fill=_hex(C["text_muted"]))

            pill_x = W - PAD - 110
            pill_y = y + 12
            role_txt = "서폿" if is_sup else "딜러"
            role_bg  = _blend(role_col, C["card"], 0.33)
            _pill(draw, pill_x, pill_y, role_txt, bg=role_bg, fg=role_col, font=f_job, px=16, py=7)
            if std_job:
                _pill(draw, pill_x, pill_y+36, std_job, bg=PILL_JOB, fg="#ffffff", font=f_job, px=12, py=7)
            if cleared:
                cw = _tw(draw,"✓ 완료",f_dur)
                draw.text((W-PAD-cw-10,y+54), "✓ 완료", font=f_dur, fill=_hex(C["gold"]))

            y += CARD_H + CARD_GAP
        y += CARD_GAP

    draw.text((PAD,H-18),"로일(LoIl) · 24시간 후 자동 삭제",font=f_wm,fill=_hex(C["text_muted"]))
    buf=BytesIO(); img.convert("RGB").save(buf,format="PNG"); buf.seek(0)
    return buf


# ══════════════════════════════════════════════
#  주간 전체 레이드 이미지
# ══════════════════════════════════════════════

def render_weekly_raids(summary: list, guild_name: str = "로일길드") -> BytesIO:
    COLS=ALL_DAYS; N_COLS=len(COLS); COL_W=210; PAD=20; COL_GAP=8
    HEADER_H=72; COL_HDR_H=36; RAID_GAP=8
    PARTY_LBL_H=20; MEMBER_H=26; MEMBER_GAP=3; DUR_ROW_H=30; CARD_VPAD=10

    def card_height(members, raid_name=""):
        size    = get_raid_size(raid_name)          # 레이드 정원 (4/8/16)
        parties = _split_parties(members, party_size=size)  # party_size 전달
        n_parties = len(parties)
        is_8man   = size == 8 and n_parties == 2
        if is_8man:
            max_p = max(len(p) for p in parties)
            return 44 + PARTY_LBL_H + max_p*(MEMBER_H+MEMBER_GAP) + DUR_ROW_H + CARD_VPAD*2
        else:
            n_lbl = n_parties if n_parties > 1 else 0
            n_mem = sum(len(p) for p in parties)
            return 44 + n_lbl*PARTY_LBL_H + n_mem*(MEMBER_H+MEMBER_GAP) + DUR_ROW_H + CARD_VPAD*2

    day_map={d:[] for d in COLS}
    for r in summary:
        day=r.get('day','미정')
        day_map[day if day in day_map else '미정'].append(r)

    max_col_h=max(
        sum(card_height(r.get('members',[]), r.get('name','')) for r in day_map[d])+RAID_GAP*len(day_map[d]) if day_map[d] else 60
        for d in COLS
    )

    W=PAD*2+N_COLS*COL_W+(N_COLS-1)*COL_GAP
    H=HEADER_H+COL_HDR_H+max_col_h+PAD*2

    img=Image.new("RGBA",(W,H),_hex(C["bg"]))
    draw=ImageDraw.Draw(img)

    f_title=_font(20,bold=True); f_sub=_font(12); f_col_hdr=_font(14,bold=True)
    f_time=_font(14,bold=True); f_raid=_font(13,bold=True); f_party=_font(10,bold=True)
    f_member=_font(12,bold=True); f_dur=_font(13,bold=True); f_wm=_font(10)

    draw.rectangle([0,0,W,HEADER_H],fill=_hex(C["card_dark"]))
    draw.rectangle([0,0,8,HEADER_H],fill=_hex(C["accent"]))
    draw.text((PAD+10,16),_week_title(guild_name),font=f_title,fill=_hex(C["text_white"]))
    total_raids=sum(len(v) for v in day_map.values())
    draw.text((PAD+10,46),f"총 {total_raids}개 레이드",font=f_sub,fill=_hex(C["text_gray"]))

    rx=W-PAD
    for txt,col in reversed([("딜러",C["dps"]),("서폿",C["support"]),("미정",C["undecided"])]):
        tw=_tw(draw,txt,f_sub); rx-=tw+28
        draw.ellipse([rx,24,rx+10,34],fill=_hex(col))
        draw.text((rx+14,22),txt,font=f_sub,fill=_hex(col))

    for ci,day in enumerate(COLS):
        cx=PAD+ci*(COL_W+COL_GAP)
        is_und=day=='미정'; col=C["undecided"] if is_und else C["accent"]
        draw.rectangle([cx,HEADER_H,cx+COL_W,HEADER_H+COL_HDR_H],fill=_hex(C["col_header"]))
        label="미정" if is_und else f"{day}요일"
        tw=_tw(draw,label,f_col_hdr)
        draw.text((cx+(COL_W-tw)//2,HEADER_H+10),label,font=f_col_hdr,fill=_hex(col))
        draw.rectangle([cx,HEADER_H+COL_HDR_H-3,cx+COL_W,HEADER_H+COL_HDR_H],fill=_hex(col))

    for ci,day in enumerate(COLS):
        cx=PAD+ci*(COL_W+COL_GAP); cy=HEADER_H+COL_HDR_H+PAD//2
        raids=sorted(day_map[day],key=lambda r:(r.get('hour',0),r.get('minute',0)))
        is_und_day=day=='미정'

        if not raids:
            _rect(draw,(cx,cy,cx+COL_W,cy+50),r=8,fill=C["card_dark"])
            draw.text((cx+10,cy+16),"없음",font=f_sub,fill=_hex(C["text_muted"]))
            continue

        for r in raids:
            is_und_raid=is_und_day or r.get('day','')=='미정'
            name=r.get('name',''); time_str=r.get('time_str','?:??')
            dur=r.get('duration',30); dur_lbl=_dur_label(dur)
            cleared=r.get('cleared',False); members=r.get('members',[])

            size = get_raid_size(name)
            ch=card_height(members, name)
            _rect(draw,(cx,cy,cx+COL_W,cy+ch),r=8,fill=C["card_dark"] if is_und_raid else C["card"])
            bar_col=C["undecided"] if is_und_raid else (C["gold"] if cleared else C["accent"])
            draw.rectangle([cx,cy,cx+COL_W,cy+3],fill=_hex(bar_col))

            draw.text((cx+8,cy+6),time_str,font=f_time,fill=_hex(C["gold"]))
            rname_x=cx+8+_tw(draw,time_str,f_time)+8
            avail_w=COL_W-(rname_x-cx)-6
            rname=name
            while rname and _tw(draw,rname+"…",f_raid)>avail_w:
                rname=rname[:-1]
            if rname!=name: rname+="…"
            draw.text((rname_x,cy+7),rname,font=f_raid,fill=_hex(C["text_white"]))
            draw.rectangle([cx+6,cy+26,cx+COL_W-6,cy+27],fill=_hex(C["divider"]))

            # party_size 전달 — 4인 레이드 강제 분리 방지
            parties=_split_parties(members, party_size=size)
            my=cy+30
            is_8man_card = size == 8 and len(parties) == 2
            if is_8man_card:
                half_w = (COL_W - 6) // 2
                draw.text((cx+8, my), "1파티", font=f_party, fill=_hex(C["text_muted"]))
                draw.text((cx+8+half_w, my), "2파티", font=f_party, fill=_hex(C["text_muted"]))
                my += PARTY_LBL_H
                max_len = max(len(parties[0]), len(parties[1]))
                for i in range(max_len):
                    for pi, party in enumerate(parties):
                        if i >= len(party):
                            continue
                        m = party[i]
                        ox = cx + pi * half_w
                        is_sup = m.get('is_support', False)
                        role_col = C["undecided"] if is_und_raid else (C["support"] if is_sup else C["dps"])
                        mname = m.get('name', '')
                        draw.ellipse([ox+8, my+7, ox+17, my+16], fill=_hex(role_col))
                        draw.text((ox+21, my+4), mname, font=f_member, fill=_hex(C["text_white"]))
                    my += MEMBER_H + MEMBER_GAP
            else:
                for pi,party in enumerate(parties,1):
                    if len(parties)>1:
                        draw.text((cx+8,my),f"{pi}파티",font=f_party,fill=_hex(C["text_muted"]))
                        my+=PARTY_LBL_H
                    for m in party:
                        is_sup=m.get('is_support',False)
                        role_col=C["undecided"] if is_und_raid else (C["support"] if is_sup else C["dps"])
                        mname=m.get('name','')
                        draw.ellipse([cx+8,my+7,cx+17,my+16],fill=_hex(role_col))
                        draw.text((cx+21,my+4),mname,font=f_member,fill=_hex(C["text_white"]))
                        my+=MEMBER_H+MEMBER_GAP

            dur_y=cy+ch-DUR_ROW_H
            draw.rectangle([cx,dur_y,cx+COL_W,dur_y+1],fill=_hex(C["divider"]))
            draw.text((cx+8,dur_y+8),dur_lbl,font=f_dur,fill=_hex(C["text_gray"]))
            if cleared:
                sw=_tw(draw,"✓ 완료",f_dur)
                draw.text((cx+COL_W-sw-8,dur_y+8),"✓ 완료",font=f_dur,fill=_hex(C["gold"]))

            cy+=ch+RAID_GAP

    draw.text((PAD,H-16),"로일(LoIl) · 매주 수요일 자동 갱신",font=f_wm,fill=_hex(C["text_muted"]))
    buf=BytesIO(); img.convert("RGB").save(buf,format="PNG"); buf.seek(0)
    return buf


# ══════════════════════════════════════════════
#  주간 타임라인 이미지 (시간축 고정)
# ══════════════════════════════════════════════

def render_weekly_timeline(summary: list, guild_name: str = "로일길드") -> BytesIO:
    DAYS     = ['수', '목', '금', '토', '일', '월', '화']
    BASE_H   = 12
    MAX_H    = 25
    SLOT_H   = 28
    BLOCK_H  = SLOT_H - 2
    TIME_W   = 48
    COL_W    = 110
    COL_GAP  = 4
    PAD      = 16
    HEADER_H = 64
    HDR_H    = 30
    UND_W    = 120
    SEC_GAP  = 20

    n_slots = (MAX_H - BASE_H) * 2
    body_h  = n_slots * SLOT_H
    main_w  = TIME_W + len(DAYS)*(COL_W+COL_GAP) - COL_GAP

    W = PAD*2 + main_w + SEC_GAP + UND_W
    H = HEADER_H + HDR_H + body_h + PAD*2

    img  = Image.new("RGBA", (W, H), _hex(C["bg"]))
    draw = ImageDraw.Draw(img)

    f_title   = _font(17, bold=True)
    f_sub     = _font(11)
    f_hdr     = _font(12, bold=True)
    f_time    = _font(10)
    f_raid    = _font(11, bold=True)
    f_overlap = _font(10, bold=True)
    f_wm      = _font(9)

    draw.rectangle([0,0,W,HEADER_H], fill=_hex(C["card_dark"]))
    draw.rectangle([0,0,6,HEADER_H], fill=_hex(C["accent"]))
    draw.text((PAD+10,14), _week_title(guild_name), font=f_title, fill=_hex(C["text_white"]))
    total = sum(1 for r in summary if r.get('day','미정') != '미정')
    draw.text((PAD+10,42), f"총 {total}개 레이드", font=f_sub, fill=_hex(C["text_gray"]))

    body_y = HEADER_H + HDR_H

    for ci, day in enumerate(DAYS):
        cx = PAD + TIME_W + ci*(COL_W+COL_GAP)
        draw.rectangle([cx,HEADER_H,cx+COL_W,HEADER_H+HDR_H], fill=_hex(C["col_header"]))
        tw = _tw(draw, f"{day}요일", f_hdr)
        draw.text((cx+(COL_W-tw)//2, HEADER_H+8), f"{day}요일", font=f_hdr, fill=_hex(C["accent"]))
        draw.rectangle([cx,HEADER_H+HDR_H-2,cx+COL_W,HEADER_H+HDR_H], fill=_hex(C["accent"]))

    for s in range(n_slots+1):
        h = BASE_H + s//2; m = (s%2)*30
        y = body_y + s*SLOT_H
        if y > H - PAD: break
        if m == 0:
            t  = f"{h:02d}:00"
            tw = _tw(draw, t, f_time)
            draw.text((PAD+TIME_W-tw-4, y-7), t, font=f_time, fill=_hex(C["text_muted"]))
            draw.line([(PAD+TIME_W,y),(PAD+TIME_W+main_w-TIME_W,y)], fill=_hex("#2d2d40"), width=1)
        else:
            draw.line([(PAD+TIME_W,y),(PAD+TIME_W+main_w-TIME_W,y)], fill=_hex("#1e1e2e"), width=1)

    day_raids = {d: [] for d in DAYS}
    for r in summary:
        d = r.get('day', '미정')
        if d in day_raids:
            day_raids[d].append(r)

    for ci, day in enumerate(DAYS):
        cx = PAD + TIME_W + ci*(COL_W+COL_GAP)
        slot_map: dict[tuple, list] = defaultdict(list)
        for r in day_raids[day]:
            slot = (r.get('hour', 0), r.get('minute', 0))
            slot_map[slot].append(r)

        for (h, m), raids_at_slot in slot_map.items():
            ry = body_y + int(((h - BASE_H)*60 + m) / 30 * SLOT_H)
            if len(raids_at_slot) == 1:
                r   = raids_at_slot[0]
                clr = r.get('cleared', False)
                bar = C["gold"] if clr else C["accent"]
                bg  = "#1a1c2e" if clr else "#23253a"
                draw.rectangle([cx+2, ry+1, cx+COL_W-2, ry+BLOCK_H], fill=_hex(bg))
                draw.rectangle([cx+2, ry+1, cx+5,        ry+BLOCK_H], fill=_hex(bar))
                name  = r.get('name', '')
                avail = COL_W - 12
                while name and _tw(draw, name+"…", f_raid) > avail:
                    name = name[:-1]
                if name != r.get('name', ''): name += "…"
                draw.text((cx+8, ry+7), name, font=f_raid, fill=_hex(C["text_white"]))
                if clr:
                    sw = _tw(draw, "✓", f_raid)
                    draw.text((cx+COL_W-sw-5, ry+7), "✓", font=f_raid, fill=_hex(C["gold"]))
            else:
                names_list = [r.get('name', '') for r in raids_at_slot]
                label      = _make_overlap_label(names_list)
                draw.rectangle([cx+2, ry+1, cx+COL_W-2, ry+BLOCK_H], fill=_hex(C["overlap_bg"]))
                draw.rectangle([cx+2, ry+1, cx+5,        ry+BLOCK_H], fill=_hex(C["overlap_bar"]))
                avail = COL_W - 12
                while label and _tw(draw, label+"…", f_overlap) > avail:
                    label = label[:-1]
                if label != _make_overlap_label(names_list): label += "…"
                draw.text((cx+8, ry+6), label, font=f_overlap, fill=_hex(C["text_white"]))

    ux = PAD + main_w + SEC_GAP
    draw.rectangle([ux,HEADER_H,ux+UND_W,HEADER_H+HDR_H], fill=_hex(C["col_header"]))
    draw.text((ux+8,HEADER_H+8), "미정", font=f_hdr, fill=_hex(C["undecided"]))
    draw.rectangle([ux,HEADER_H+HDR_H-2,ux+UND_W,HEADER_H+HDR_H], fill=_hex(C["undecided"]))

    uy = HEADER_H + HDR_H + 8
    for r in [r for r in summary if r.get('day','미정') == '미정']:
        draw.rectangle([ux+2,uy,ux+UND_W-2,uy+BLOCK_H], fill=_hex(C["card_dark"]))
        draw.rectangle([ux+2,uy,ux+5,       uy+BLOCK_H], fill=_hex(C["undecided"]))
        name = r.get('name','')
        while name and _tw(draw,name+"…",f_raid) > UND_W-14:
            name = name[:-1]
        if name != r.get('name',''): name += "…"
        draw.text((ux+8,uy+7), name, font=f_raid, fill=_hex(C["text_white"]))
        uy += BLOCK_H + 4

    draw.text((PAD,H-13),"로일(LoIl) · 매주 수요일 자동 갱신",font=f_wm,fill=_hex(C["text_muted"]))
    buf=BytesIO(); img.convert("RGB").save(buf,format="PNG"); buf.seek(0)
    return buf


# ══════════════════════════════════════════════
#  파티 편성 결과 이미지 (시간 포함)
# ══════════════════════════════════════════════

def render_party_result(raid_name: str, parties: list,
                         time_str: str = "", day: str = "") -> BytesIO:
    if not parties:
        parties = [[]]

    PAD=24; HEADER_H=96; PTH=36; MH=40; MG=4; PG=16
    fp=_font(15,bold=True); fn=_font(18,bold=True)
    fm=_font(15,bold=True); fc=_font(13)
    ftg=_font(11,bold=True); ft=_font(22,bold=True)
    fs=_font(13); ft2=_font(16,bold=True); fwm=_font(11)

    two_col = len(parties) == 2

    if two_col:
        W = 760
        col_w = (W - PAD*3) // 2
        max_members = max(len(p) for p in parties)
        body_h = PTH + max_members*(MH+MG) + PG
        H = HEADER_H + PAD + body_h + PAD*2
    else:
        W = 640
        col_w = W - PAD*2
        total_m = sum(len(p) for p in parties)
        H = HEADER_H + PAD + len(parties)*(PTH+PG) + total_m*(MH+MG) + PAD*2

    total = sum(len(p) for p in parties)
    sup   = sum(1 for p in parties for m in p if m.get('is_support'))

    img  = Image.new("RGBA", (W, H), _hex(C["bg"]))
    draw = ImageDraw.Draw(img)

    draw.rectangle([0,0,6,HEADER_H], fill=_hex(C["accent"]))
    draw.text((PAD,14), raid_name, font=ft, fill=_hex(C["text_white"]))
    draw.text((PAD,48), f"총 {total}명  ·  서폿 {sup}명  ·  딜러 {total-sup}명", font=fs, fill=_hex(C["text_gray"]))

    if time_str or day:
        time_label = f"{day}요일  {time_str}" if day else time_str
        TIME_BOX_W = _tw(draw, time_label, ft2) + 24
        tx = W - PAD - TIME_BOX_W
        _rect(draw, (tx, 14, tx+TIME_BOX_W, 46), r=8, fill=C["time_bg"])
        draw.text((tx+12, 19), time_label, font=ft2, fill=_hex(C["gold"]))

    draw.rectangle([PAD, HEADER_H-2, W-PAD, HEADER_H], fill=_hex(C["divider"]))

    y0 = HEADER_H + PAD

    if two_col:
        for pi, party in enumerate(parties):
            cx = PAD + pi * (col_w + PAD)
            y  = y0
            _rect(draw, (cx, y, cx+120, y+28), r=6, fill=C["accent"])
            draw.text((cx+12, y+6), f"PARTY  {pi+1}", font=fp, fill=_hex(C["text_white"]))
            y += PTH
            for mi, m in enumerate(party, 1):
                is_sup = m.get('is_support', False)
                rc = C["support"] if is_sup else C["dps"]
                _rect(draw, (cx, y, cx+col_w, y+MH), r=8, fill=C["card"])
                draw.rounded_rectangle([cx, y, cx+4, y+MH], radius=3, fill=rc)
                draw.text((cx+14, y+12), str(mi), font=fn, fill=_hex(C["text_muted"]))
                draw.text((cx+42, y+8),  m.get('name',''), font=fm, fill=_hex(C["text_white"]))
                draw.text((cx+42, y+26), m.get('character',''), font=fc, fill=_hex(C["text_gray"]))
                rt = "서폿" if is_sup else "딜러"
                rw = _tw(draw, rt, ftg) + 16
                rx2 = cx + col_w - rw - 4
                _rect(draw, (rx2, y+10, rx2+rw, y+30), r=10, fill=rc)
                draw.text((rx2+8, y+12), rt, font=ftg, fill=_hex(C["text_white"]))
                y += MH + MG
    else:
        y = y0
        for pi, party in enumerate(parties, 1):
            _rect(draw, (PAD, y, PAD+120, y+28), r=6, fill=C["accent"])
            draw.text((PAD+12, y+6), f"PARTY  {pi}", font=fp, fill=_hex(C["text_white"]))
            y += PTH
            for mi, m in enumerate(party, 1):
                is_sup = m.get('is_support', False)
                rc = C["support"] if is_sup else C["dps"]
                _rect(draw, (PAD, y, W-PAD, y+MH), r=8, fill=C["card"])
                draw.rounded_rectangle([PAD, y, PAD+4, y+MH], radius=3, fill=rc)
                draw.text((PAD+14, y+12), str(mi), font=fn, fill=_hex(C["text_muted"]))
                draw.text((PAD+42, y+8),  m.get('name',''), font=fm, fill=_hex(C["text_white"]))
                draw.text((PAD+42, y+26), m.get('character',''), font=fc, fill=_hex(C["text_gray"]))
                rt = "서폿" if is_sup else "딜러"
                rw = _tw(draw, rt, ftg) + 20
                rx2 = W - PAD - rw - 8
                _rect(draw, (rx2, y+10, rx2+rw, y+30), r=10, fill=rc)
                draw.text((rx2+10, y+12), rt, font=ftg, fill=_hex(C["text_white"]))
                y += MH + MG
            y += PG

    draw.text((PAD, H-22), "로일(LoIl) · 확정 후 시트 자동 저장", font=fwm, fill=_hex(C["text_muted"]))
    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf