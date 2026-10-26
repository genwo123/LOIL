"""
로일(LoIl) - 초기 등록용 엑셀 업로드 파서
길드 최초 세팅 시 레이드 목록 + 멤버 명단을 엑셀 하나로 한번에 읽어서
"레이드 하나씩 웹에서 추가", "멤버 하나씩 /닉네임등록" 하는 수고를 없앤다.

기대 형식: .xlsx, 시트 탭 이름 "레이드"와 "멤버" (첫 행은 헤더).
  레이드 탭: 레이드명(필수) | 난이도(필수) | 요일(선택) | 시간(선택, "18:00") | 소요시간(선택, 분)
  멤버 탭:   닉네임(선택, 비우면 캐릭터명 사용) | 캐릭터명(필수) | 권한(선택, "길드장"/"부길드장"/공란=일반 길드원 — 길드장은 1명이어야 함)
"""

import io
import re
from openpyxl import load_workbook

DAY_CHARS = {"월", "화", "수", "목", "금", "토", "일"}


def _norm_header(v) -> str:
    return str(v).strip() if v is not None else ""


def _find_sheet(wb, keyword: str):
    for name in wb.sheetnames:
        if keyword in name:
            return wb[name]
    return None


def _row_dicts(sheet):
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [_norm_header(h) for h in rows[0]]
    result = []
    for raw in rows[1:]:
        if raw is None or all(v is None or str(v).strip() == "" for v in raw):
            continue
        row = {}
        for i, h in enumerate(headers):
            if not h:
                continue
            row[h] = raw[i] if i < len(raw) else None
        result.append(row)
    return result


def _parse_day(v) -> str:
    s = str(v).strip() if v is not None else ""
    if not s:
        return "미정"
    s = s.replace("요일", "").strip()
    return s if s in DAY_CHARS else "미정"


def _parse_time(v) -> tuple[int, int]:
    s = str(v).strip() if v is not None else ""
    if not s:
        return 0, 0
    m = re.match(r"(\d{1,2})\s*[:시]\s*(\d{0,2})", s)
    if not m:
        return 0, 0
    hour = int(m.group(1))
    minute = int(m.group(2)) if m.group(2) else 0
    return hour, minute


def parse_roster_workbook(file_bytes: bytes) -> dict:
    """반환: {"raids": [...], "members": [...], "errors": [...]}
    errors가 있으면 그 시트는 건너뛴 것 — 미리보기 화면에서 그대로 사용자에게 보여줄 것."""
    errors = []
    raids = []
    members = []

    try:
        wb = load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
    except Exception as e:
        return {"raids": [], "members": [], "errors": [f"엑셀 파일을 읽을 수 없습니다: {e}"]}

    raid_sheet = _find_sheet(wb, "레이드")
    if raid_sheet is None:
        errors.append("'레이드' 탭을 찾지 못했습니다 (레이드 목록은 건너뜀).")
    else:
        for i, row in enumerate(_row_dicts(raid_sheet), start=2):
            name = _norm_header(row.get("레이드명"))
            diff = _norm_header(row.get("난이도"))
            if not name or not diff:
                errors.append(f"[레이드 탭 {i}행] 레이드명/난이도가 비어 건너뜀.")
                continue
            hour, minute = _parse_time(row.get("시간"))
            duration_raw = row.get("소요시간")
            try:
                duration = int(duration_raw) if duration_raw else 60
            except (TypeError, ValueError):
                duration = 60
            raids.append({
                "name": name,
                "diff": diff,
                "day": _parse_day(row.get("요일")),
                "hour": hour,
                "minute": minute,
                "duration": duration,
            })

    member_sheet = _find_sheet(wb, "멤버")
    if member_sheet is None:
        errors.append("'멤버' 탭을 찾지 못했습니다 (멤버 명단은 건너뜀).")
    else:
        seen = set()
        leaders = []
        for i, row in enumerate(_row_dicts(member_sheet), start=2):
            character = _norm_header(row.get("캐릭터명"))
            if not character:
                errors.append(f"[멤버 탭 {i}행] 캐릭터명이 비어 건너뜀.")
                continue
            nickname = _norm_header(row.get("닉네임")) or character
            if nickname in seen:
                errors.append(f"[멤버 탭 {i}행] '{nickname}' 중복 — 첫 번째 것만 사용.")
                continue
            seen.add(nickname)

            role_raw = _norm_header(row.get("권한"))
            if role_raw in ("길드장", "부길드장"):
                role = role_raw
            elif role_raw:
                errors.append(f"[멤버 탭 {i}행] 권한 '{role_raw}'을(를) 알 수 없어 '일반 길드원'으로 처리.")
                role = ""
            else:
                role = ""
            if role == "길드장":
                leaders.append(nickname)

            members.append({"nickname": nickname, "character": character, "role": role})

        if len(leaders) > 1:
            errors.append(f"⚠️ 길드장이 {len(leaders)}명입니다 (길드장은 1명이어야 함): {', '.join(leaders)}")

    wb.close()
    return {"raids": raids, "members": members, "errors": errors}
