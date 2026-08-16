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
| **운영(기본)** | **161.33.190.254** (Oracle A1 · 4 OCPU/24GB) | **모든 배포는 여기로.** 아직 미공개 — 화면·커밋에 이 IP 를 노출하지 않는다 |
| 구서버 | 141.147.160.13 (E2.1.Micro · 1GB) | 이관 중, 종료 예정. 별도 요청 없으면 배포하지 않는다 |

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

⚠ 장시간 스크립트는 `setsid nohup … > /tmp/x.log 2>&1 < /dev/null &` 로 띄우고 로그로 확인한다
(ssh 세션에 물리면 툴 타임아웃에 같이 죽는다). `pkill -f` 는 자기 ssh 셸까지 죽이므로
`pgrep -f … | xargs -r kill` 을 쓴다.

## 검증

- `node --check` 만으로는 부족하다 — 함수가 통째로 지워져도 통과한다.
  실제 API 응답으로 렌더 테스트를 돌려 화면에 값이 나오는지 확인한 뒤 "됐다"고 말한다.
- 파서를 고쳤으면 대표 종목으로 회귀 검증한다(`scripts/guidance_check.py SYM…`).
