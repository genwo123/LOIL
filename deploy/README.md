# 로일(LoIl) 실제 호스팅 이전 체크리스트

지금은 개발 PC에서 `python -m bot.main` / `uvicorn web.main:app`을 터미널 창으로 수동 실행 중 —
PC가 꺼지거나 재부팅되면 서비스가 전부 멈춘다. 9~10월 시범가동 전에 상시 가동되는 실제 서버로
옮겨야 한다. 이 문서는 그 이전 작업 체크리스트 — 호스팅 업체/예산 선택은 사용자 결정 사항이라
여기 포함 안 함.

## 1. 서버 준비 (업체 정해지면)

- Linux VPS 하나면 충분(봇+웹 둘 다 가벼움). Python 3.13+ 설치.
- `git clone`으로 레포 받고, `python -m venv venv && venv/bin/pip install -r requirements.txt`.
- `bot/config/credentials.json`(구글 서비스 계정 키), `bot/.env`를 서버로 안전하게 옮기기(git에는 안 올라가 있음 — 직접 scp 등으로 전송).

## 2. 환경변수(.env) 프로덕션 전환

`bot/.env`에서 아래 값들을 반드시 바꿀 것:

| 변수 | 지금(개발) | 배포 시 |
|---|---|---|
| `WEB_BASE_URL` | `http://localhost:8000` | 실제 도메인(예: `https://loil.example.com`) |
| `DEV_SKIP_LOGIN` | `true` | **반드시 `false`로** (안 그러면 로그인 없이 아무나 관리자 화면 접근 가능) |
| `DISCORD_CLIENT_ID` / `DISCORD_CLIENT_SECRET` | (미설정 또는 테스트용) | Discord 개발자 포털에서 실제 발급 |
| `DISCORD_REDIRECT_URI` | `http://localhost:8000/callback` | `https://실제도메인/callback` — Discord 앱 설정의 OAuth2 Redirect URI에도 **동일하게** 등록해야 함 |

## 3. 도메인 + HTTPS

- Discord OAuth2는 `redirect_uri`로 `http://localhost`를 프로덕션에서 받아주지 않음(HTTPS 필수) — 도메인 하나 + Let's Encrypt(certbot) 무료 인증서로 충분.
- nginx(또는 caddy) 리버스 프록시로 443(HTTPS) → uvicorn(127.0.0.1:8000) 연결.
- `deploy/loil-web.service`는 이미 `--host 127.0.0.1`로 로컬만 열어두게 해놨음(외부에서 8000 포트로 직접 못 들어오게, 리버스 프록시 통해서만 접근).

## 4. 상시 실행 전환 (systemd)

`deploy/loil-bot.service`, `deploy/loil-web.service` 템플릿 참고 — `User`/`WorkingDirectory`/venv 경로만 실제 서버에 맞게 고치면 됨.

```bash
sudo cp deploy/loil-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now loil-bot loil-web
sudo systemctl status loil-bot loil-web   # 정상 기동 확인
journalctl -u loil-bot -f                 # 로그 실시간 확인
```

터미널 창을 계속 띄워둘 필요 없이, 서버 재부팅돼도 자동으로 다시 켜짐(`Restart=on-failure` + `enable`).

## 5. 순서 요약

1. 서버 계약 + 접속 확인
2. 코드 배포 + `.env` 프로덕션 값으로 교체 (위 2번 표)
3. Discord 개발자 포털에 OAuth2 Redirect URI 실제 도메인으로 등록
4. nginx + HTTPS 인증서 설정
5. systemd 서비스 등록 + 기동 확인
6. `DEV_SKIP_LOGIN=false` 상태로 실제 로그인 흐름 한 번 끝까지 테스트
7. 기존 개발 PC의 로컬 프로세스는 종료

## 참고: requirements.txt 정리함

이번에 확인해보니 `requirements.txt`에 두 가지 문제가 있었음(호스팅 이전 전에 미리 고쳐둠):

- `pillow` — 실제로 `bot/utils/image_renderer.py`(주간 레이드 이미지 렌더링)가 쓰는데 주석 처리돼 있었음. 새 서버에 배포했으면 설치가 안 돼서 바로 깨졌을 것 — 주석 해제함.
- `pymysql`/`mysqlclient`/`SQLAlchemy`/`alembic` — 코드 어디서도 안 씀(Google Sheets가 source of truth라 SQL DB 자체를 안 씀, 기획 초기 흔적). 특히 `mysqlclient`는 빌드 도구 없으면 설치 자체가 실패하는 흔한 배포 실패 원인이라 주석 처리함.
