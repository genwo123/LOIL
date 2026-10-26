"""
로일(LoIl) - 공통 로그 설정

bot/main.py, web/main.py 맨 위에서 각각 setup_logging()을 한 번 호출해서 씀.
콘솔에는 지금까지처럼 그대로 찍히면서, 동시에 logs/ 밑에 프로세스별 날짜 로그 파일로도 남는다.
기존 print() 기반 에러 출력을 하나하나 고치지 않아도 전부 파일에 같이 남도록
stdout/stderr 자체를 파일에도 동시에 쓰는 방식(Tee)을 쓴다.
14일 지난 로그 파일은 시작할 때마다 자동으로 정리된다.
"""

import glob
import logging
import os
import sys
import time
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
KEEP_DAYS = 14


class _Tee:
    def __init__(self, original, log_file):
        self._original = original
        self._log_file = log_file

    def write(self, data):
        self._original.write(data)
        self._log_file.write(data)
        self._log_file.flush()

    def flush(self):
        self._original.flush()
        self._log_file.flush()

    def isatty(self):
        return self._original.isatty()


def setup_logging(process_name: str) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    today = time.strftime("%Y-%m-%d")
    log_path = LOG_DIR / f"{process_name}_{today}.log"
    log_file = open(log_path, "a", encoding="utf-8", buffering=1)

    sys.stdout = _Tee(sys.stdout, log_file)
    sys.stderr = _Tee(sys.stderr, log_file)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)

    # uvicorn은 자체 핸들러를 원본 stderr에 직접 붙여두기 때문에(propagate=False),
    # 위 root 핸들러만으로는 uvicorn 자체 에러/요청 로그가 파일에 안 남는다 — 직접 붙여준다.
    for name in ("uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).addHandler(handler)

    _cleanup_old_logs(process_name)


def _cleanup_old_logs(process_name: str) -> None:
    cutoff = time.time() - KEEP_DAYS * 86400
    for path in glob.glob(str(LOG_DIR / f"{process_name}_*.log")):
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
        except OSError:
            pass
