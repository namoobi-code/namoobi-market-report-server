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
- 서버(141.147.160.13) 배포와 커밋은 한 세트다. scp 로 올렸으면 커밋도 같이 한다.

## 배포

1. 로컬 수정 → `scp -i /tmp/nmr_deploy_key`(원본 키: `claudeCowork/SECURITY/nmr_deploy_key`, chmod 600)
2. `app.py` 를 고쳤으면 `sudo systemctl restart namoobi`
3. `static/` 을 고쳤으면 `index.html` 의 `app.js?v=` 값을 올린다(캐시 무효화)
4. `sh gitsync.sh "…"` 로 커밋·푸시

## 검증

- `node --check` 만으로는 부족하다 — 함수가 통째로 지워져도 통과한다.
  실제 API 응답으로 렌더 테스트를 돌려 화면에 값이 나오는지 확인한 뒤 "됐다"고 말한다.
- 파서를 고쳤으면 대표 종목으로 회귀 검증한다(`scripts/guidance_check.py SYM…`).
