# Oracle A1(Ampere) 무료 이전 계획 — 1GB → 24GB

작성 2026-08-14. 현 서버 실측 기준.

## 왜 하나

| | 현재 | A1 이전 후 | 비용 |
|---|---|---|---|
| Shape | VM.Standard.E2.1.Micro | VM.Standard.A1.Flex | 둘 다 **Always Free** |
| CPU | 1 OCPU (x86 EPYC) | 최대 4 OCPU (ARM Ampere) | 0원 |
| RAM | **954MB** (가용 340~430MB) | 최대 **24GB** | 0원 |
| 디스크 | 45GB | 최대 200GB | 0원 |

가용 메모리가 340MB 수준이라 대형 JSON(스크리너 12MB·global_hist 12.5MB)을 동시에 다루면 여유가 없다.
유료 인스턴스(월 20~30달러)로 가기 전에 **무료 한도 안에서 CPU 4배·RAM 24배**를 먼저 쓴다.

## 현 서버 실측 (이전 대상)

- 리전/AD: **ap-tokyo-1 / AD-1** · Ubuntu 24.04.4 · Python 3.12.3
- 총 용량: **1.6GB** (data 826MB 포함)
- 서비스: `namoobi.service`(uvicorn 127.0.0.1:8000) · `namoobi-nightws.service` · `nginx`(sites-enabled/default)
- 크론: **97줄**
- HTTPS: **미설정(http only)** — 이전 시 Let's Encrypt 함께 적용 권장(로그인 비밀번호 평문 전송 문제 해소)
- 키/자격증명: `keys/`(gmail 앱 비밀번호 등) — **rsync 대상이지만 git 에는 절대 올리지 않는다**

## ARM 호환성 — 사전 점검 결과

venv 47개 패키지 전수 확인. **aarch64 wheel 미제공으로 막히는 것 없음.**

- numpy · pandas · matplotlib · pillow · lxml · pydantic-core · cffi → 공식 ARM wheel 있음
- curl_cffi · maxminddb · peewee · yfinance · fastapi/uvicorn → 순수 파이썬 또는 ARM wheel 있음
- 시스템 pip3 의 certbot·boto3 계열도 ARM 정상

주의 1개: `matplotlib`·`weasyprint`(부록F 생성기) 는 ARM 에서 빌드 의존성이 필요할 수 있어
`sudo apt install -y libpango-1.0-0 libpangoft2-1.0-0 libjpeg-dev libopenjp2-7-dev fonts-noto-cjk` 를 먼저 깔면 안전하다.

## 절차 (예상 1~2시간, 무중단 아님 · 전환 순간만 수 분)

### 1단계 — 인스턴스 생성 (사용자 콘솔 작업, 내가 대신 못 함)
1. OCI 콘솔 → Compute → Instances → Create
2. Shape: **VM.Standard.A1.Flex**, OCPU **4**, Memory **24GB**
3. Image: **Ubuntu 24.04 (aarch64)**
4. VCN: 기존과 동일, 공인 IP 할당, SSH 키는 기존 `nmr_deploy_key.pub` 등록
5. Boot volume 100~200GB

> ⚠️ 도쿄 리전은 A1 용량 부족("Out of host capacity")이 잦다. 실패하면 ① 다른 AD 시도
> ② 2 OCPU/12GB 로 낮춰 시도 ③ 며칠 간격 재시도. 용량은 수시로 열린다.

### 2단계 — 기반 설치 (신규 서버)
```bash
sudo apt update && sudo apt install -y python3-venv python3-pip nginx sqlite3 \
  libpango-1.0-0 libpangoft2-1.0-0 libjpeg-dev libopenjp2-7-dev fonts-noto-cjk poppler-utils
sudo timedatectl set-timezone Asia/Seoul     # 크론이 KST 기준
```

### 3단계 — 코드·데이터 이전 (구 서버에서 실행)
```bash
rsync -az --info=progress2 -e "ssh -i ~/.ssh/nmr_deploy_key" \
  --exclude 'venv' --exclude '__pycache__' --exclude '*.log' \
  /home/ubuntu/namoobi/ ubuntu@<신규IP>:/home/ubuntu/namoobi/
```
`venv` 는 x86 바이너리라 **반드시 제외**하고 신규 서버에서 재생성한다:
```bash
cd /home/ubuntu/namoobi && python3 -m venv venv && ./venv/bin/pip install -U pip
./venv/bin/pip install fastapi uvicorn requests beautifulsoup4 lxml pandas numpy matplotlib \
  pillow yfinance peewee curl_cffi maxminddb websockets python-dateutil pytz
```

### 4단계 — 서비스·웹서버
```bash
sudo cp /home/ubuntu/namoobi/deploy/namoobi.service /etc/systemd/system/   # 구 서버에서 복사해 온 것
sudo systemctl daemon-reload && sudo systemctl enable --now namoobi
sudo cp /home/ubuntu/namoobi/deploy/nginx_default /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
crontab /home/ubuntu/namoobi/deploy/crontab.txt        # 97줄 그대로 이관
```

### 5단계 — 전환·검증
1. 신규 서버에서 `python3 scripts/healthcheck.py` → **경보 0** 확인
2. DuckDNS 도메인을 신규 IP 로 변경(`~/duckdns/duck.sh` 의 IP 갱신 또는 웹에서 수동)
3. 5~10분 관찰 후 구 서버 크론 중지(`crontab -r`) — **데이터 이중 수집 방지**
4. 이상 없으면 구 인스턴스는 1주일 보관 후 종료(롤백 여지)

### 6단계 — HTTPS (권장, 이전과 함께)
```bash
sudo certbot --nginx -d namoobi.duckdns.org
```
로그인 창의 "암호화되지 않은 연결" 경고가 사라지고 비밀번호가 암호화 전송된다.

## 롤백
DuckDNS 를 구 IP 로 되돌리고 구 서버 크론을 복구하면 끝(구 서버는 그대로 살려둔다).

## 내가 할 수 있는 것 / 사용자가 해야 하는 것

- **사용자**: 1단계 인스턴스 생성(OCI 콘솔 로그인 필요), DuckDNS IP 변경
- **나**: 2~6단계 전부 SSH 로 수행 가능 — 신규 IP 와 SSH 접근만 주면 된다
