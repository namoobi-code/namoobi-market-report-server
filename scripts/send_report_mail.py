#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""send_report_mail.py — 서버에서 Gmail SMTP 로 시황 보고서 docx 발송 (v3.70).

인증: Gmail '앱 비밀번호' (2단계 인증 계정에서 발급) — keys/gmail_app_password.txt
  · 이 파일은 git 미포함(keys/ 는 .gitignore). PC SECURITY 폴더에서 scp 로 배포.
  · 파일 형식: 앱 비밀번호 16자 (공백 포함/미포함 무관 — 공백 제거 후 사용)
발신 계정: namoobi@gmail.com (SMTP 로그인 계정 = 발신자, 보낸편지함에도 남음)

입력: **stdin 으로 JSON** (BCC 주소가 argv/ps 에 노출되지 않도록):
  {"to": "namoobi@gmail.com", "bcc": ["..."], "subject": "...",
   "body": "...", "attach": "/home/ubuntu/namoobi/data/reports/xxx.docx"}
사용: echo "$JSON" | python3 send_report_mail.py            # 발송
      python3 send_report_mail.py --check                    # 인증파일 존재만 검사(exit 0/3)
      echo "$JSON" | python3 send_report_mail.py --force     # 멱등 가드 무시하고 강제 발송
종료코드: 0=발송 성공(중복 차단 포함) · 2=입력/첨부 오류 · 3=인증파일 없음 · 4=SMTP 실패
출력: 성공 시 "SENT <메시지ID> to=1 bcc=N attach=<파일명> <크기>B" (주소 미노출)
      중복 시 "SENT <기존 메시지ID> (dedup — 기발송 재확인, 재발송 차단) ..."

[v3.70 멱등 가드 — 2026-07-18 중복 발송 재발방지]
  발송 성공 시 data/mail_sent.log 에 "ISO시각<TAB>첨부파일명<TAB>메시지ID" 를 기록하고,
  발송 전 같은 첨부파일명이 최근 DEDUP_HOURS(20h) 내 기록돼 있으면 SMTP 를 건너뛰고
  기존 메시지ID 로 SENT(dedup) 를 반환한다. 클라이언트(send_mail_server.py)가 45초
  샌드박스 벽 등으로 "SENT" 확인을 유실하고 재시도해도 같은 회차가 두 번 발송되지 않는다.
  (파일명에 _HHMM 이 포함되므로 새로 빌드한 다른 회차는 정상 발송된다. 강제 재발송은 --force.)
"""
import json, os, re, smtplib, ssl, sys, time
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ACCOUNT = "namoobi@gmail.com"
SENT_LOG = BASE / "data" / "mail_sent.log"
DEDUP_HOURS = 20

def app_password():
    for p in (BASE / "keys" / "gmail_app_password.txt",
              *Path("/sessions").glob("*/mnt/claudeCowork/SECURITY/gmail_app_password.txt"),
              Path("D:/claudeCowork/SECURITY/gmail_app_password.txt")):
        try:
            v = Path(p).read_text(encoding="utf-8").strip().replace(" ", "")
            if v:
                return v
        except Exception:
            pass
    return None

def recent_sent(attach_name):
    """최근 DEDUP_HOURS 내 같은 첨부파일명 발송 기록 → (시각, 메시지ID) 또는 None."""
    try:
        lines = SENT_LOG.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None
    cutoff = datetime.now() - timedelta(hours=DEDUP_HOURS)
    for ln in reversed(lines):
        parts = ln.split("\t")
        if len(parts) < 3 or parts[1] != attach_name:
            continue
        try:
            ts = datetime.fromisoformat(parts[0])
        except Exception:
            continue
        if ts >= cutoff:
            return parts[0], parts[2]
    return None

def log_sent(attach_name, msgid):
    try:
        SENT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(SENT_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')}\t{attach_name}\t{msgid}\n")
    except Exception as e:
        print("WARN sent-log 기록 실패:", str(e)[:80])

def main():
    if "--check" in sys.argv:
        ok = bool(app_password())
        print("auth: OK" if ok else "auth: gmail_app_password 없음")
        sys.exit(0 if ok else 3)
    pw = app_password()
    if not pw:
        print("ERR 인증파일 없음 (keys/gmail_app_password.txt)"); sys.exit(3)
    try:
        cfg = json.load(sys.stdin)
    except Exception as e:
        print("ERR stdin JSON:", e); sys.exit(2)
    to = cfg.get("to") or ACCOUNT
    bcc = [b for b in (cfg.get("bcc") or []) if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", b)]
    subject = cfg.get("subject") or "[namoobi] 글로벌 시황 보고서"
    body = cfg.get("body") or "첨부 문서를 참고해 주세요."
    attach = cfg.get("attach")
    if not attach or not os.path.isfile(attach):
        print("ERR 첨부 없음:", attach); sys.exit(2)
    size = os.path.getsize(attach)
    if size > 24 * 1024 * 1024:
        print("ERR 첨부 24MB 초과:", size); sys.exit(2)

    attach_name = os.path.basename(attach)
    if "--force" not in sys.argv:
        dup = recent_sent(attach_name)
        if dup:
            ts, msgid = dup
            print(f"SENT {msgid} (dedup — {ts} 기발송 재확인, 재발송 차단) "
                  f"to=1 bcc={len(bcc)} attach={attach_name} {size}B")
            sys.exit(0)

    msg = EmailMessage()
    msg["From"] = ACCOUNT
    msg["To"] = to
    if bcc:
        msg["Bcc"] = ", ".join(bcc)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="gmail.com")
    msg.set_content(body)
    with open(attach, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=attach_name)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(),
                              timeout=60) as s:
            s.login(ACCOUNT, pw)
            s.send_message(msg)
    except smtplib.SMTPAuthenticationError as e:
        print("ERR SMTP 인증 실패(앱 비밀번호 확인):", str(e)[:120]); sys.exit(4)
    except Exception as e:
        print("ERR SMTP:", str(e)[:160]); sys.exit(4)
    # 성공 직후 즉시 기록 — 이 로그가 멱등 가드의 근거다.
    log_sent(attach_name, msg["Message-ID"])
    print(f"SENT {msg['Message-ID']} to=1 bcc={len(bcc)} attach={attach_name} {size}B")

if __name__ == "__main__":
    main()
