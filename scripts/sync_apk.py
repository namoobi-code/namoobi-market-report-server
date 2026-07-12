#!/usr/bin/env python3
"""GitHub 릴리스(APK) 동기화 — 최신 3개 릴리스의 APK를 data/apk/에 캐시.
   crontab 주기 실행. 토큰: ~/namoobi/.github_token"""
import json, urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
APKD = BASE / "data" / "apk"
TOKEN_FILE = BASE / ".github_token"
REPO = "namoobi-code/namoobi-market-report-android"
KEEP = 3

def gh(url, accept="application/vnd.github+json"):
    req = urllib.request.Request(url, headers={
        "Authorization": "token " + TOKEN_FILE.read_text().strip(),
        "Accept": accept, "User-Agent": "namoobi-apk-sync"})
    return urllib.request.urlopen(req, timeout=120)

def main():
    APKD.mkdir(parents=True, exist_ok=True)
    with gh(f"https://api.github.com/repos/{REPO}/releases?per_page={KEEP}") as r:
        rels = json.load(r)
    out, keep = [], set()
    for rel in rels[:KEEP]:
        assets = [a for a in rel.get("assets", []) if a["name"].endswith(".apk")]
        if not assets:
            continue
        a = assets[0]
        keep.add(a["name"])
        p = APKD / a["name"]
        if not p.exists() or p.stat().st_size != a["size"]:
            tmp = p.with_suffix(".part")
            with gh(a["url"], accept="application/octet-stream") as resp, open(tmp, "wb") as f:
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            tmp.rename(p)
        body = (rel.get("body") or "").strip()
        out.append({
            "tag": rel["tag_name"],
            "name": rel.get("name") or rel["tag_name"],
            "published": (rel.get("published_at") or "")[:10],
            "notes": body.splitlines()[0][:120] if body else "",
            "file": a["name"],
            "size_mb": round(a["size"] / 1048576, 1)})
    for p in APKD.glob("*.apk"):
        if p.name not in keep:
            p.unlink()
    (APKD / "releases.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"synced {len(out)} releases")

if __name__ == "__main__":
    main()
