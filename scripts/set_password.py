#!/usr/bin/env python3
"""개발자 계정 설정.

  방법 A — 브라우저에서 설정 (권장)
      python3 scripts/set_password.py --token
    일회용 토큰을 발급한다. 대시보드 🔒 버튼에서 토큰과 함께 아이디·비밀번호를
    입력하면 등록된다. 비밀번호가 SSH·터미널·대화기록 어디에도 남지 않는다.

  방법 B — 서버에서 직접 입력
      python3 scripts/set_password.py
    비밀번호를 직접 입력한다 (화면에 표시되지 않음).

어느 쪽이든 평문은 저장되지 않는다. PBKDF2-SHA256 20만 회 해시만 남는다.
"""
import json, sys, time, getpass, secrets, hashlib
from pathlib import Path

BASE    = Path(__file__).resolve().parent.parent
AUTH_F  = BASE / "data" / "auth.json"
SETUP_F = BASE / "data" / "setup_token.json"
IT      = 200_000
TOKEN_TTL = 30 * 60

def issue_token():
    if AUTH_F.exists():
        print("이미 계정이 등록돼 있습니다.")
        if input("기존 계정을 지우고 새로 설정할까요? (yes 입력): ").strip() != "yes":
            sys.exit("취소했습니다.")
        AUTH_F.unlink()
        (BASE / "data" / "sessions.json").unlink(missing_ok=True)

    tok = secrets.token_hex(4).upper()
    SETUP_F.parent.mkdir(parents=True, exist_ok=True)
    SETUP_F.write_text(json.dumps({"token": tok, "exp": time.time() + TOKEN_TTL}))
    SETUP_F.chmod(0o600)
    print("\n── 일회용 설정 토큰 ──")
    print(f"\n      {tok}\n")
    print(f"유효시간: 30분 · 1회 사용 후 자동 폐기")
    print("대시보드 우측 상단 🔒 버튼 → 최초 설정 화면에 입력하세요.")

def main():
    print("── namoobi 개발자 계정 설정 ──")
    user = input("아이디: ").strip()
    if not user:
        sys.exit("아이디가 비었습니다.")

    pw = getpass.getpass("비밀번호 (화면에 안 보입니다): ")
    if len(pw) < 8:
        sys.exit("비밀번호는 8자 이상이어야 합니다.")
    if pw != getpass.getpass("비밀번호 확인: "):
        sys.exit("두 번 입력한 비밀번호가 다릅니다.")

    weak = {"12345678", "password", "qwerty123", "namoobi1", "11111111"}
    if pw.lower() in weak:
        sys.exit("너무 흔한 비밀번호입니다. 다른 것을 쓰세요.")

    salt = secrets.token_hex(16)
    AUTH_F.parent.mkdir(parents=True, exist_ok=True)
    AUTH_F.write_text(json.dumps({
        "user": user,
        "salt": salt,
        "hash": hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), IT).hex(),
        "iter": IT,
    }))
    AUTH_F.chmod(0o600)

    # 기존 로그인 세션 전부 무효화 (비밀번호를 바꿨으니 당연히)
    s = BASE / "data" / "sessions.json"
    if s.exists():
        s.unlink()

    print(f"\n완료 — {AUTH_F} (권한 600)")
    print("서버 반영:  sudo systemctl restart namoobi")

if __name__ == "__main__":
    if "--token" in sys.argv:
        issue_token()
    else:
        main()
