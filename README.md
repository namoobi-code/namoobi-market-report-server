# namoobi 시황 대시보드 — 서버 코드

`namoobi-market-report` 플러그인이 생성하는 데이터를 **공개 대시보드**로 서빙하는 서버 코드.
서버가 사라져도 **이 저장소만 있으면 30분 안에 완전 복구**된다.

**운영 주소**: http://namoobi.duckdns.org
**호스팅**: Oracle Cloud Always Free (도쿄 · VM.Standard.E2.1.Micro · 월 0원)

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
[내 PC] _market_report_data/poll.db
```

**서버는 데이터의 원본이 아니다.** 원본은 전부 PC(`D:\claudeCowork\_market_report_data`)에 있고,
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
