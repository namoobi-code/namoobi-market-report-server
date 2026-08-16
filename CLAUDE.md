# 작업 규칙 (namoobi)

## 깃 반영 — 수정할 때마다 즉시

파일을 고칠 때마다 **그 자리에서 커밋·푸시**한다. 나중에 몰아서 하지 않는다
(몰아서 하면 "어제 한 것 중 뭐가 안 올라갔는지" 를 매번 찾아야 한다).

```
sh /sessions/*/mnt/claudeCowork/gitsync.sh "커밋 메시지"
```

이 스크립트가 두 저장소를 함께 처리한다.

| 저장소 | 경로 | 내용 |
|---|---|---|
| namoobi-market-report-server | `claudeCowork/namoobi-market-report-server` | FastAPI 서버·프론트(app.js)·수집 스크립트 |
| namoobi-market-report | `claudeCowork/../namoobi-market-report` | 플러그인·스킬·문서 |

- 토큰: `claudeCowork/SECURITY/githubtoken.txt`
- 커밋 메시지는 **무엇을 왜 고쳤는지** 한국어로. 실측 근거(종목·수치)가 있으면 함께 적는다.
- 서버 배포와 커밋은 한 세트다. scp 로 올렸으면 커밋도 같이 한다.

## 배포 — 대상 서버 (2026-08-16 이관)

| 구분 | 주소 | 상태 |
|---|---|---|
| **운영(유일)** | **161.33.190.254** = `namoobi.duckdns.org` (Oracle A1 · 2 OCPU/12GB · ARM aarch64) | **모든 배포·수정은 여기로.** DuckDNS 가 이 IP 를 가리키고 HTTPS 정상이므로, 화면·문서에는 **도메인**을 쓴다(IP 직접 노출은 도메인 차단 망에서만) |
| 구서버 | 인스턴스 `instance-20260711-1936` (E2.1.Micro · 1GB) | **2026-08-16 정지(STOPPED)** — 실수로 구서버를 고치는 사고를 막으려 인스턴스째 내렸다. 되살리려면 OCI 콘솔 → Compute → Instances → 해당 인스턴스 → **Start** |

⚠ **구서버에는 배포하지 않는다.** 정지 상태라 SSH 도 안 되지만, 되살린 경우에도
구서버 파일은 2026-08-16 시점에서 멈춰 있으므로 이관 이후 수정은 전부 신규 서버 기준이다.

절차:

1. 로컬 수정 → `scp -i ~/nmr_deploy_key … ubuntu@161.33.190.254:/home/ubuntu/namoobi/…`
   (원본 키: `claudeCowork/SECURITY/nmr_deploy_key` → 홈으로 복사 후 chmod 600.
   `/tmp` 는 쓰기 권한이 없다)
2. `app.py` 를 고쳤으면 `sudo systemctl restart namoobi`
3. `static/` 을 고쳤으면 `index.html` 의 `app.js?v=`·`sub.js?v=` 값을 올린다(캐시 무효화)
4. **새 수집 스크립트를 추가했으면 cron 등록도 함께**(`crontab -l | grep -q … || (crontab -l; echo …) | crontab -`)
   — 신규 서버는 크론이 자동으로 따라오지 않는다
5. 새 데이터 파일(`data/db/*.json`, sqlite)은 서버에서 생성되므로, 구서버에만 있으면 scp 로 이관한다
6. `sh gitsync.sh "…"` 로 커밋·푸시

### HTTPS (2026-08-16 적용)

- `https://namoobi.duckdns.org` — Let's Encrypt(certbot 2.9.0 · nginx 플러그인), 만료 2026-11-14,
  `certbot.timer` 가 자동 갱신하고 갱신 후 nginx 를 알아서 리로드한다(installer=nginx). 손댈 것 없음.
- 도메인 접속은 80 → 443 **301 리다이렉트**. IP 직접 접속(`http://161.33.190.254`)은 리다이렉트 없이
  그대로 열린다 — 인증서가 도메인용이라 IP 로는 HTTPS 경고가 뜨는 게 정상이다.
- nginx 설정 사본: `deploy/nginx_default` (서버에서 회수한 실물). 재구축 시 이 파일을
  `/etc/nginx/sites-enabled/default` 로 복사한 뒤 `certbot --nginx -d namoobi.duckdns.org` 재발급.
- 로그인 비밀번호 평문 전송 문제는 이걸로 해소됐다 — 로그인은 **도메인으로** 접속해서 쓴다.

⚠ 장시간 스크립트는 `setsid nohup … > /tmp/x.log 2>&1 < /dev/null &` 로 띄우고 로그로 확인한다
(ssh 세션에 물리면 툴 타임아웃에 같이 죽는다). `pkill -f` 는 자기 ssh 셸까지 죽이므로
`pgrep -f … | xargs -r kill` 을 쓴다.

## 검증

- `node --check` 만으로는 부족하다 — 함수가 통째로 지워져도 통과한다.
  실제 API 응답으로 렌더 테스트를 돌려 화면에 값이 나오는지 확인한 뒤 "됐다"고 말한다.
- 파서를 고쳤으면 대표 종목으로 회귀 검증한다(`scripts/guidance_check.py SYM…`).
