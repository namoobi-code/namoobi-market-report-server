#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""send_report_mail.py — 서버에서 Gmail SMTP 로 시황 보고서 docx 발송 (v3.69).

인증: Gmail '앱 비밀번호' (2단계 인증 계정에서 발급) — keys/gmail_app_password.txt
  · 이 파일은 git 미포함(keys/ 는 .gitignore). PC SECURITY 폴더에서 scp 로 배포.
  · 파일 형식: 앱 비밀번호 16자 (공백 포함/미포함 무관 — 공백 제거 후 사용)
발신 계정: namoobi@gmail.com (SMTP 로그인 계정 = 발신자, 보낸편지함에도 남음)

입력: **stdin 으로 JSON** (BCC 주소가 argv/ps 에 노출되지 않도록):
  {"to": "namoobi@gmail.com", "bcc": ["..."], "subject": "...",
   "body": "...", "attach": "/home/ubuntu/namoobi/data/reports/xxx.docx"}
사용: echo "$JSON" | python3 send_report_mail.py            # 발송
      python3 send_report_mail.py --check                    # 인증파일 존재만 검사(exit 0/3)
종료코드: 0=발송 성공 · 2=입력/첨부 오류 · 3=인증파일 없음 · 4=SMTP 실패
출력: 성공 시 "SENT <메시지ID> to=1 bcc=N attach=<파일명> <크기>B" (주소 미노출)
"""
import json, os, re, smtplib, ssl, sys
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ACCOUNT = "namoobi@gmail.com"

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
            filename=os.path.basename(attach))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(),
                              timeout=60) as s:
            s.login(ACCOUNT, pw)
            s.send_message(msg)
    except smtplib.SMTPAuthenticationError as e:
        print("ERR SMTP 인증 실패(앱 비밀번호 확인):", str(e)[:120]); sys.exit(4)
    except Exception as e:
        print("ERR SMTP:", str(e)[:160]); sys.exit(4)
    print(f"SENT {msg['Message-ID']} to=1 bcc={len(bcc)} attach={os.path.basename(attach)} {size}B")

if __name__ == "__main__":
    main()
