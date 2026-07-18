#!/usr/bin/env python3
"""내 회선 목록(my_ips.json) 복구 — nginx 접근로그에서 되살린다.

근거는 단 하나: **로그인·계정등록에 성공(POST 200)한 기록**.
비밀번호를 아는 사람만 받을 수 있는 응답이므로 본인이 확실하다.

/api/auth/me 나 /api/visitors 의 200 을 근거로 쓰면 안 된다 —
전자는 로그인 여부와 무관하게 누구에게나 200 을 주고, 후자는 정적파일
경로와 섞여 오탐이 난다. 실제로 그렇게 만들었다가 남의 휴대폰을
'나'로 등록한 적이 있다.
"""
import gzip, json, re, sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
import ipinfo

import auth_visitors as A

OUT  = BASE / "data" / "my_ips.json"
LOGS = Path("/var/log/nginx")
# nginx combined 형식을 필드 그대로 읽는다 (느슨한 .* 는 엉뚱한 줄을 문다).
#   IP - - [시각] "POST 경로 프로토콜" 상태 바이트 "리퍼러" "UA"
# IP + UA 를 함께 잡는다 — 공유기 뒤에서는 IP 하나에 여러 기기가 있으므로
# 등록 단위가 IP 가 아니라 'IP + 기기' 여야 한다.
PAT = re.compile(
    r'^(\S+) \S+ \S+ \[[^\]]+\] "POST (/api/auth/(?:login|setup))[^"]*" 200 '
    r'\S+ "[^"]*" "([^"]*)"')

def label_for(ip: str, ua: str) -> str:
    g = ipinfo.lookup(ip)
    if g.get("kind") == "모바일":
        lb = "휴대폰 (%s)" % g.get("isp", "")
    elif g.get("org"):
        lb = "회사 (%s)" % g["org"]
    elif g.get("kind") == "유선":
        lb = "유선 (%s)" % g.get("isp", "")
    else:
        lb = g.get("isp", "") or "?"
    u = A._ua_parse(ua)
    dev = " · ".join(x for x in (u["dev"], u["br"]) if x)
    return "%s · %s" % (lb, dev) if dev else lb

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
                    ip, _path, ua = m.groups()
                    if ip.startswith("127."):          # 서버에서 돌린 점검용 호출
                        continue
                    u = A._ua_parse(ua)
                    found.setdefault(A._sig(ip, u["dev"], u["br"]), (ip, ua))
        except PermissionError:
            print("%s 를 읽을 권한이 없다 (adm 그룹 확인)" % f)

    try:
        cur = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        cur = {}

    added = []
    for key, (ip, ua) in found.items():
        if key in cur:
            continue
        cur[key] = {"label": label_for(ip, ua),
                    "since": datetime.now().strftime("%Y-%m-%d"), "auto": True}
        added.append((key, cur[key]["label"]))

    # 자동 등록(auto=True)인데 로그인 근거가 없는 항목은 오탐이므로 제거한다.
    # 이동통신 IP 는 다른 가입자에게 재할당되므로 IP 단위 등록은 특히 위험하다.
    # 직접 지정한 항목(auto=False)은 사용자의 판단이므로 건드리지 않는다.
    proven_ips = {ip for _, (ip, _ua) in found.items()}
    dropped = []
    for key in list(cur):
        if not cur[key].get("auto") or key in found:
            continue
        if key.split("|")[0] not in proven_ips:
            dropped.append(key)
            cur.pop(key)
        elif "|" not in key:                  # 같은 IP 의 기기 단위 등록으로 대체됨
            dropped.append(key)
            cur.pop(key)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(cur, ensure_ascii=False), encoding="utf-8")
    print("기기 단위 복구 %d건 · 오탐·중복 제거 %d건 · 전체 %d건" % (len(added), len(dropped), len(cur)))
    for k, lb in added:
        print("  + %-40s%s" % (k, lb))
    for k in dropped:
        print("  - %-40s(근거 없음 · 해제)" % k)
    left = [k for k in cur if "|" not in k]
    if left:
        print("\n아직 IP 통째로 남은 항목 (화면에서 '회선전체' 배지로 보인다):")
        for k in left:
            print("  %-20s%s" % (k, cur[k].get("label", "")))

if __name__ == "__main__":
    main()
