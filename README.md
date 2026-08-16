# namoobi 시황 대시보드 — 서버 코드

`namoobi-market-report` 플러그인이 생성하는 데이터를 **공개 대시보드**로 서빙하는 서버 코드.
서버가 사라져도 **이 저장소만 있으면 30분 안에 완전 복구**된다.

**운영 주소**: https://namoobi.duckdns.org (2026-08-16 신규 서버로 이관 완료 — DuckDNS 도 신규 IP 를 가리키고,
HTTP 는 HTTPS 로 301, 인증서 정상). 도메인 차단 망에서는 IP 직접 접속.
**호스팅**: Oracle Cloud Always Free (Ampere A1 · 2 OCPU/12GB · ARM aarch64 · 월 0원)

---

## 어디에 무엇이 있나 (3곳)

| | 위치 | 내용 |
|---|---|---|
| **PC — 서버 코드 작업본** | `D:\claudeCowork\namoobi-market-report-server` | 이 저장소. 여기서 고치고 → 서버 배포 → GitHub push |
| **PC — DB 정본** | `D:\claudeCowork\namoobi-market-report-server\db\` | **DB 52종 원본 — 이 저장소가 git 으로 버전관리·백업한다** |
| **PC — 수집 중간산출물** | `D:\claudeCowork\namoobi-market-report-server\data\` | `nmr_*.json` · `report_data_*.json` · `poll.db` · `deriv_signals.db` · `krx_brief/` (DB 아님) |
| **GitHub (백업)** | `namoobi-code/namoobi-market-report-server` (private) | 서버 코드 백업 |
| **서버 (배포본)** | `ubuntu@161.33.190.254:~/namoobi/` | `app.py`·`static/`·`scripts/` + `data/db/` (PC에서 밀어넣은 사본) |

**코드 수정 → 배포 흐름**

```bash
# 1) D:\claudeCowork\namoobi-market-report-server 에서 수정
# 2) 서버 배포
KEY=D:/claudeCowork/SECURITY/nmr_deploy_key
scp -i $KEY static/app.js static/index.html ubuntu@161.33.190.254:namoobi/static/
scp -i $KEY app.py scripts/*.py            ubuntu@161.33.190.254:namoobi/
ssh -i $KEY ubuntu@161.33.190.254 'sudo systemctl restart namoobi'
# 3) GitHub 백업
git add -A && git commit -m "..." && git push origin main
```

키 = `D:\claudeCowork\SECURITY\nmr_deploy_key` · 토큰 = `D:\claudeCowork\SECURITY\githubtoken.txt`

### DB 위치 (2026-07-12 이전)

`db/` = **DB 정본 52종**. 종전엔 `_market_report_data\db\` 에 있어 **어느 저장소에도 속하지 않았고
PC 로컬에만 존재**했다. 서버 코드 저장소로 옮겨 **git 버전관리 + GitHub 백업**이 함께 걸리게 했다.
경로 해석은 `nmr_db.py` 의 `DBROOT_NAME` 한 곳이 정본이다(구 경로는 읽기 폴백만 유지).

- 리포트 실행(`merge.py`)이 매일 `db/*.json` 을 갱신 → **여기서 `git commit` 하면 그날 DB가 백업**된다.
- 서버(`~/namoobi/data/db/`)는 `sync_server.py` 가 밀어 넣는 **사본**이다. 서버 DB를 직접 고치지 말 것 —
  다음 동기화 때 PC 값으로 덮인다.
- 예외: 서버가 cron 으로 자체 누적하는 `poll.db` · `series_mem_*` 는 sync_server 가 PC 로 되가져와 병합한다.

---

## 구조

```
app.py              FastAPI 백엔드 (JSON 직접 서빙 — DB 서버 없음)
poll.py             김치프리미엄·공포탐욕·환율 수집 (cron 1일 2회 → SQLite)
static/index.html   대시보드 (보고서 목차 순서)
static/app.js       차트·표 렌더링 (Chart.js)
deploy/setup.sh     ⭐ 새 서버 완전 복구 스크립트
deploy/*.service    systemd (재부팅 자동 기동)
deploy/nginx.conf   리버스 프록시 + 무캐시 + gzip
```

## 데이터 흐름

```
[내 PC] /namoobi-market-report 실행
   ↓ Phase 5.5 — scripts/sync_server.py (메일 발송 후 1회)
   ↓ db/*.json(37종) + report_data.json + 신규 docx
[서버] FastAPI → 공개 대시보드
[서버] poll.py cron → 김프·공포탐욕 시계열 누적 (SQLite)
   ↓ sync_server.py 가 되가져옴 (백업)
[내 PC] namoobi-market-report-server/data/poll.db
```

**서버는 데이터의 원본이 아니다.** 원본은 전부 PC(`D:\claudeCowork\namoobi-market-report-server\data`)에 있고,
서버가 자체 생성하는 `poll.db` 만 매 동기화 때 PC로 되가져와 백업한다.
→ **서버가 통째로 날아가도 잃는 데이터가 없다.**

## 서버 복구 (Oracle 무료 서버가 회수되거나 재생성이 필요할 때)

1. 새 인스턴스 생성 (Ubuntu 24.04 · Always Free shape)
   - Oracle 콘솔 → VCN Security List 에 **80·443 Ingress** 추가
2. SSH 접속 후:
   ```bash
   git clone https://github.com/namoobi-code/namoobi-market-report-server.git
   bash namoobi-market-report-server/deploy/setup.sh
   ```
3. DuckDNS 의 IP 를 새 서버 IP 로 갱신 (또는 `~/duckdns/duck.sh` 재설정)
4. PC 에서 `python3 scripts/sync_server.py` 실행 → 데이터 복구

## 알려진 함정

- **iptables 순서**: Oracle Ubuntu 이미지는 `REJECT` 가 INPUT 5번에 있다.
  `-I INPUT 6` 으로 넣으면 REJECT 뒤라 **무시된다** → 반드시 `-I INPUT 1`.
- **방화벽 2겹**: 서버 iptables + Oracle 콘솔 Security List 를 **둘 다** 열어야 한다.
- **유휴 회수**: Always Free 인스턴스는 7일간 CPU<20%·네트워크<10% 면 회수 대상.
  nginx + cron 이 상시 돌아 실질적으로 안전.
