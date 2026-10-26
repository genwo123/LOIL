"""
로일(LoIl) - guild_settings.json 공통 저장소 계층

여러 cogs/utils 파일에 각자 복붙돼 있던 load_settings()/save_settings()를 여기 한 곳으로 모았다.
봇 프로세스와 웹 프로세스가 이 파일을 동시에 읽고 쓰기 때문에, 저장할 때 세 가지를 처리한다:

1. 원자적 쓰기 — 임시 파일에 먼저 쓰고 os.replace()로 교체. 쓰는 도중 프로세스가 죽어도
   기존 파일이 반쪽짜리로 깨지지 않는다(os.replace는 POSIX/Windows 둘 다 원자적).
2. 파일 잠금 — 두 프로세스가 동시에 저장을 시도하면 한쪽이 잠깐 기다렸다가 씀. 다만 이건
   "쓰는 순간"만 겹치지 않게 할 뿐, load→수정→save 사이 구간까지 완전히 직렬화하진 않는다
   (완전한 트랜잭션이 되려면 호출부마다 lock 안에서 load/save를 다 하도록 바꿔야 하는데,
   지금 규모(길드 몇 개, 동시 저장 드묾)에선 과한 작업이라 다음 단계로 미룸).
3. 자동 백업 — 저장할 때마다 타임스탬프 백업을 bot/data/backups/에 남기고 오래된 것부터 정리.
"""

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

SETTINGS_FILE = "bot/data/guild_settings.json"
BACKUP_DIR = "bot/data/backups"
MAX_BACKUPS = 30
LOCK_FILE = SETTINGS_FILE + ".lock"
LOCK_TIMEOUT = 5.0  # 초 — 이전 프로세스가 비정상 종료로 락을 못 풀었을 때 무한 대기 방지


def load_settings() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(data: dict):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    _acquire_lock()
    try:
        _backup_current()
        tmp_path = SETTINGS_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, SETTINGS_FILE)
    finally:
        _release_lock()


def _acquire_lock():
    deadline = time.time() + LOCK_TIMEOUT
    while True:
        try:
            fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return
        except FileExistsError:
            if time.time() > deadline:
                return  # 락 파일이 오래됐으면(비정상 종료로 안 풀린 경우) 강제로 진행
            time.sleep(0.05)


def _release_lock():
    try:
        os.remove(LOCK_FILE)
    except FileNotFoundError:
        pass


def _backup_current():
    if not os.path.exists(SETTINGS_FILE):
        return
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_path = os.path.join(BACKUP_DIR, f"guild_settings_{stamp}.json")
    try:
        shutil.copy2(SETTINGS_FILE, backup_path)
    except Exception:
        return
    _cleanup_old_backups()


def _cleanup_old_backups():
    try:
        backups = sorted(Path(BACKUP_DIR).glob("guild_settings_*.json"))
        for old in backups[:-MAX_BACKUPS]:
            old.unlink(missing_ok=True)
    except Exception:
        pass
