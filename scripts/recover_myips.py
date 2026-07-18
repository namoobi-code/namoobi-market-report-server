#!/usr/bin/env python3
"""내 회선 목록(my_ips.json) 복구 — nginx 접근로그에서 되살린다.

/api/visitors 는 로그인해야만 200 이 나온다. 따라서 그 응답을 받은 IP 는
본인 회선이 확실하다. 이 사실을 이용해 목록을 재구성한다.
기존 항목은 덮어쓰지 않고 없는 것만 채운다.
"""
import gzip, json, re, sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
import ipinfo

OUT  = BASE / "data" / "my_ips.json"
LOGS = Path("/var/log/nginx")
PAT  = re.compile(r'^(\S+) .*"(?:GET|POST) (/api/(?:visitors|auth/login|auth/setup)\S*)[^"]*" (\d{3})')

def main():
    found = {}
    files = [LOGS / "access.log", LOGS / "access.log.1"] + sorted(LOGS.glob("access.log.*.gz"))
    for f in files:
        if not f.exists():
            continue
        try:
            op = gzip.open if f.suffix == ".gz" else open
            with op(f, "rt", errors="replace") as fh:
                for ln in fh:
                    m = PAT.match(ln)
                    if not m:
                        continue
                    ip, path, st = m.groups()
                    if ip.startswith("127.") or st not in ("200", "304"):
                        continue
                    found.setdefault(ip, path)
        except PermissionError:
            print(f"{f} 를 읽을 권한이 없다 (sudo 로 실행하거나 adm 그룹 확인)")

    try:
        cur = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        cur = {}

    added = []
    for ip in found:
        if ip in cur:
            continue
        g = ipinfo.lookup(ip)
        if g.get("kind") == "모바일":
            lb = "휴대폰 (%s)" % g.get("isp", "")
        elif g.get("org"):
            lb = "회사 (%s)" % g["org"]
        elif g.get("kind") == "유선":
            lb = "유선 (%s)" % g.get("isp", "")
        else:
            lb = g.get("isp", "")
        cur[ip] = {"label": lb, "since": datetime.now().strftime("%Y-%m-%d"), "auto": True}
        added.append((ip, lb))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(cur, ensure_ascii=False), encoding="utf-8")
    print("복구 %d건 (전체 %d건)" % (len(added), len(cur)))
    for ip, lb in added:
        print("  %-17s%s" % (ip, lb))

if __name__ == "__main__":
    main()
